"""
feature_mapper/report.py
────────────────────────
Project-level Research Report Generator (Phase 3).

Synthesizes a single structured report from the *persisted* Feature Mapper
output for a project — features, retrieved papers, relevance explanations, and
recommendations. Operates entirely on DB data; does not re-run retrieval or the
LLM extraction.

Strategy (same grounded pattern as the rest of the pipeline):
  1. Load + deterministically aggregate the project's persisted data into
     structured section inputs (research areas, cross-feature top papers,
     recommended techniques, missing components, evaluation suggestions).
  2. ONE LLM call writes the prose sections (Executive Summary, Feature
     Analysis narrative, Research Gaps, Next Steps) grounded in those structured
     inputs — so it cannot invent papers or techniques.
  3. Assemble the 9-section Markdown report from prose + structured lists.
  Fail-soft: if the LLM call fails, prose sections fall back to templates.

Nine sections:
  1. Executive Summary       5. Recommended Techniques
  2. Key Research Areas      6. Missing Components
  3. Feature Analysis        7. Evaluation Suggestions
  4. Most Relevant Papers    8. Research Gaps
                             9. Next Steps

Public API:
    generate_report(project_id, session) → (markdown, sections_dict, model, ms)
    load_project_report_data(project_id, session) → ProjectReportData | None
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models import FmFeature, FmPaperMatch, FmProject, FmRecommendation
from search.metadata import fetch_paper_metadata_batch

log = logging.getLogger(__name__)

_REPORT_MAX_TOKENS = 2048
_TOP_PAPERS = 10
_TOP_AREAS = 8

_SYSTEM_PROMPT = (
    "You are a senior research analyst writing a research-backed design review. "
    "You are given structured findings from mapping a project's features to a "
    "research-paper corpus. You return only valid JSON. Every statement must be "
    "grounded in the provided findings — never invent papers, techniques, or "
    "metrics not present in the input."
)


# ── Structured data loaded from the DB ────────────────────────────────────────

@dataclass
class FeatureView:
    name: str
    description: str
    feature_type: str
    coverage_score: float | None
    coverage_tier: str | None
    matched_techniques: list[str]
    matched_categories: list[str]
    unrecognized_terms: list[str]
    papers: list[dict] = field(default_factory=list)          # {paper_id,title,year,venue,rank,rrf,explanation}
    recommendations: list[dict] = field(default_factory=list)  # {rec_type,title,body,evidence_count,paper_ids}


@dataclass
class ProjectReportData:
    project_id: str
    title: str | None
    feature_count: int
    features: list[FeatureView]


def _jl(raw) -> list[str]:
    if not raw:
        return []
    try:
        v = json.loads(raw)
        return v if isinstance(v, list) else []
    except (json.JSONDecodeError, TypeError):
        return []


def load_project_report_data(project_id: str, session: Session) -> ProjectReportData | None:
    """Load a project's full persisted Feature Mapper output into a flat view."""
    project = session.get(FmProject, project_id)
    if not project:
        return None

    features = session.execute(
        select(FmFeature).where(FmFeature.project_id == project_id).order_by(FmFeature.position)
    ).scalars().all()
    if not features:
        return ProjectReportData(project_id, project.title, 0, [])

    feature_ids = [f.id for f in features]

    # Matches + recommendations in two batched queries.
    matches = session.execute(
        select(FmPaperMatch).where(FmPaperMatch.feature_id.in_(feature_ids)).order_by(FmPaperMatch.rank)
    ).scalars().all()
    recs = session.execute(
        select(FmRecommendation).where(FmRecommendation.feature_id.in_(feature_ids)).order_by(FmRecommendation.rank)
    ).scalars().all()

    # Hydrate paper titles/venues for all matched papers in one batch.
    all_paper_ids = list({m.paper_id for m in matches})
    meta = fetch_paper_metadata_batch(session, all_paper_ids) if all_paper_ids else {}

    matches_by_feature: dict[str, list[FmPaperMatch]] = defaultdict(list)
    for m in matches:
        matches_by_feature[m.feature_id].append(m)
    recs_by_feature: dict[str, list[FmRecommendation]] = defaultdict(list)
    for r in recs:
        recs_by_feature[r.feature_id].append(r)

    views: list[FeatureView] = []
    for f in features:
        fv = FeatureView(
            name=f.name,
            description=f.description or "",
            feature_type=f.feature_type or "other",
            coverage_score=f.coverage_score,
            coverage_tier=f.coverage_tier,
            matched_techniques=_jl(f.matched_techniques),
            matched_categories=_jl(f.matched_categories),
            unrecognized_terms=_jl(f.unrecognized_terms),
        )
        for m in matches_by_feature.get(f.id, []):
            md = meta.get(m.paper_id, {})
            fv.papers.append({
                "paper_id": m.paper_id,
                "title": md.get("title") or "(unknown title)",
                "year": md.get("year"),
                "venue": md.get("conference"),
                "categories": md.get("categories", []),
                "rank": m.rank,
                "rrf": m.rrf_score,
                "explanation": m.relevance_explanation,
            })
        for r in recs_by_feature.get(f.id, []):
            fv.recommendations.append({
                "rec_type": r.rec_type,
                "title": r.title,
                "body": r.body,
                "evidence_count": r.evidence_count or 0,
                "paper_ids": _jl(r.supporting_paper_ids),
            })
        views.append(fv)

    return ProjectReportData(project_id, project.title, len(views), views)


# ── Deterministic aggregation ─────────────────────────────────────────────────

def _aggregate_research_areas(data: ProjectReportData) -> list[tuple[str, int]]:
    """
    Research areas = feature-level categories first; supplemented by the most
    common categories of the retrieved papers and the recognized techniques.

    The feature category signal is often sparse (only ~15 coarse corpus
    categories), so we fall back to paper-level categories and techniques to
    keep this section meaningful.
    """
    counter: Counter[str] = Counter()
    # Feature-level categories carry the most weight.
    for fv in data.features:
        for cat in fv.matched_categories:
            counter[cat] += 2
    # Paper-level categories: count distinct features each category spans.
    cat_features: dict[str, set[str]] = defaultdict(set)
    for fv in data.features:
        for p in fv.papers:
            for cat in p.get("categories", []):
                cat_features[cat].add(fv.name)
    for cat, feats in cat_features.items():
        counter[cat] += len(feats)
    # If still sparse, supplement with recurring recognized techniques.
    if len(counter) < 3:
        for fv in data.features:
            for tech in fv.matched_techniques:
                counter[tech] += 1
    return counter.most_common(_TOP_AREAS)


def _aggregate_top_papers(data: ProjectReportData) -> list[dict]:
    """Rank papers across all features: more features + better ranks = more central."""
    score: dict[str, float] = defaultdict(float)
    info: dict[str, dict] = {}
    feature_hits: dict[str, set[str]] = defaultdict(set)
    for fv in data.features:
        for p in fv.papers:
            pid = p["paper_id"]
            score[pid] += 1.0 / p["rank"]          # reward high ranks
            feature_hits[pid].add(fv.name)
            if pid not in info or p["rank"] < info[pid]["rank"]:
                info[pid] = p
    ranked = sorted(score, key=lambda pid: (len(feature_hits[pid]), score[pid]), reverse=True)
    out = []
    for pid in ranked[:_TOP_PAPERS]:
        p = info[pid]
        out.append({
            "title": p["title"],
            "year": p["year"],
            "venue": p["venue"],
            "feature_count": len(feature_hits[pid]),
            "features": sorted(feature_hits[pid]),
            "explanation": p.get("explanation"),
        })
    return out


def _collect_recs(data: ProjectReportData, rec_type: str) -> list[dict]:
    """All recommendations of a type across features, deduped by title, evidence-sorted."""
    seen: dict[str, dict] = {}
    for fv in data.features:
        for r in fv.recommendations:
            if r["rec_type"] != rec_type:
                continue
            key = r["title"].strip().lower()
            entry = seen.get(key)
            if not entry or r["evidence_count"] > entry["evidence_count"]:
                seen[key] = {**r, "feature": fv.name}
    return sorted(seen.values(), key=lambda r: r["evidence_count"], reverse=True)


def _coverage_summary(data: ProjectReportData) -> dict[str, int]:
    c: Counter[str] = Counter()
    for fv in data.features:
        c[fv.coverage_tier or "unknown"] += 1
    return dict(c)


# ── LLM prose synthesis ───────────────────────────────────────────────────────

def _build_prompt(data: ProjectReportData, areas, top_papers, tech_recs, eval_recs) -> str:
    cov = _coverage_summary(data)
    feat_lines = "\n".join(
        f'- "{fv.name}" [{fv.feature_type}] coverage={fv.coverage_tier or "?"} '
        f'({(fv.coverage_score if fv.coverage_score is not None else 0):.2f}); '
        f'techniques: {", ".join(fv.matched_techniques[:4]) or "none"}; '
        f'top paper: {fv.papers[0]["title"] if fv.papers else "none"}'
        for fv in data.features
    )
    tech_lines = "\n".join(f'- {r["title"]} (evidence: {r["evidence_count"]} papers)' for r in tech_recs[:10]) or "(none)"
    eval_lines = "\n".join(f'- {r["title"]} (evidence: {r["evidence_count"]} papers)' for r in eval_recs[:10]) or "(none)"
    area_lines = ", ".join(f"{name} ({n})" for name, n in areas) or "(none)"
    paper_lines = "\n".join(
        f'- {p["title"]} ({p["venue"] or "?"} {p["year"] or ""}) — relevant to {p["feature_count"]} feature(s)'
        for p in top_papers[:8]
    ) or "(none)"

    schema = (
        '{"executive_summary":"3-5 sentence overview",'
        '"feature_analysis":"2-4 paragraph narrative across the features",'
        '"research_gaps":"2-3 paragraph analysis of where the project diverges from or '
        'lacks coverage in the literature",'
        '"next_steps":["actionable step","actionable step","actionable step"]}'
    )
    return (
        f"PROJECT: {data.title or 'Untitled'}\n"
        f"Features: {data.feature_count}. Coverage distribution: {cov}.\n\n"
        f"FEATURES:\n{feat_lines}\n\n"
        f"KEY RESEARCH AREAS (corpus categories, by frequency): {area_lines}\n\n"
        f"MOST RELEVANT PAPERS (cross-feature):\n{paper_lines}\n\n"
        f"RECOMMENDED MISSING TECHNIQUES:\n{tech_lines}\n\n"
        f"EVALUATION SUGGESTIONS:\n{eval_lines}\n\n"
        "Write the prose sections of a research-backed design review for this project. "
        "Ground every claim in the findings above. Be specific and reference feature "
        "names, papers, and techniques from the input.\n\n"
        f"Return a JSON object ONLY matching exactly:\n{schema}"
    )


def _call_llm(prompt: str) -> str:
    from llm.providers import AnthropicProvider

    api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY is not set.")
    base_url = os.getenv("ANTHROPIC_BASE_URL", "").strip() or None
    provider = AnthropicProvider(api_key=api_key, base_url=base_url)
    client = provider._client()
    resp = client.messages.create(
        model=AnthropicProvider.MODEL,
        max_tokens=_REPORT_MAX_TOKENS,
        system=_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )
    return resp.content[0].text


def _parse_json_obj(raw: str) -> dict:
    try:
        v = json.loads(raw)
        if isinstance(v, dict):
            return v
    except json.JSONDecodeError:
        pass
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    if not m:
        raise ValueError(f"No JSON object in report output: {raw[:200]!r}")
    v = json.loads(m.group())
    if not isinstance(v, dict):
        raise ValueError("Report output is not a JSON object.")
    return v


# ── Templated fallback prose ──────────────────────────────────────────────────

def _fallback_prose(data: ProjectReportData, top_papers, tech_recs) -> dict:
    cov = _coverage_summary(data)
    cov_str = ", ".join(f"{n} {tier}" for tier, n in cov.items())
    return {
        "executive_summary": (
            f"This report maps {data.feature_count} feature(s) of "
            f"\"{data.title or 'the project'}\" against the research corpus. "
            f"Coverage across features: {cov_str}. "
            f"{len(tech_recs)} missing-technique and evidence-backed recommendations were identified."
        ),
        "feature_analysis": "\n".join(
            f"**{fv.name}** ({fv.coverage_tier or '?'} coverage) maps to "
            f"{len(fv.papers)} paper(s); recognized techniques: "
            f"{', '.join(fv.matched_techniques[:4]) or 'none'}."
            for fv in data.features
        ),
        "research_gaps": (
            "Features with weak or novel coverage indicate areas under-represented "
            "in the corpus or potentially novel. Review the Missing Components and "
            "Recommended Techniques sections for specifics."
        ),
        "next_steps": [
            f"Review the {len(tech_recs)} recommended missing technique(s) against the project design.",
            "Adopt the evaluation benchmarks listed in the Evaluation Suggestions section.",
            "Investigate features flagged with weak/novel coverage for novelty or terminology mismatches.",
        ],
    }


# ── Markdown assembly ─────────────────────────────────────────────────────────

def _assemble_markdown(data: ProjectReportData, prose: dict, areas, top_papers, tech_recs, eval_recs) -> str:
    L: list[str] = []
    title = data.title or "Untitled Project"
    L.append(f"# Research Report — {title}\n")

    # 1
    L.append("## 1. Executive Summary\n")
    L.append(prose.get("executive_summary", "").strip() + "\n")

    # 2
    L.append("## 2. Key Research Areas\n")
    if areas:
        for name, n in areas:
            L.append(f"- **{name}** — appears across {n} feature(s)")
    else:
        L.append("_No research areas were resolved from the corpus._")
    L.append("")

    # 3
    L.append("## 3. Feature Analysis\n")
    L.append(prose.get("feature_analysis", "").strip() + "\n")
    L.append("| Feature | Type | Coverage | Papers | Recommendations |")
    L.append("|---|---|---|---|---|")
    for fv in data.features:
        score = f"{fv.coverage_score:.2f}" if fv.coverage_score is not None else "—"
        L.append(
            f"| {fv.name} | {fv.feature_type} | {fv.coverage_tier or '?'} ({score}) "
            f"| {len(fv.papers)} | {len(fv.recommendations)} |"
        )
    L.append("")

    # 4
    L.append("## 4. Most Relevant Papers\n")
    if top_papers:
        for i, p in enumerate(top_papers, 1):
            venue = f"{p['venue'] or '?'} {p['year'] or ''}".strip()
            L.append(f"{i}. **{p['title']}** ({venue}) — relevant to {p['feature_count']} feature(s): "
                     f"{', '.join(p['features'])}")
    else:
        L.append("_No papers were retrieved._")
    L.append("")

    # 5
    L.append("## 5. Recommended Techniques\n")
    if tech_recs:
        for r in tech_recs:
            L.append(f"- **{r['title']}** — {r['body']} _(evidence: {r['evidence_count']} paper(s); "
                     f"feature: {r['feature']})_")
    else:
        L.append("_No missing techniques were identified — features align with the literature._")
    L.append("")

    # 6
    L.append("## 6. Missing Components\n")
    if tech_recs:
        L.append("The following techniques appear in the retrieved literature but are absent "
                 "from the corresponding features:\n")
        for r in tech_recs:
            L.append(f"- {r['title'].replace('Add ', '').replace('Consider adopting ', '')} "
                     f"(missing from: {r['feature']})")
    else:
        L.append("_No missing components were detected._")
    L.append("")

    # 7
    L.append("## 7. Evaluation Suggestions\n")
    if eval_recs:
        for r in eval_recs:
            L.append(f"- **{r['title']}** — {r['body']} _(evidence: {r['evidence_count']} paper(s))_")
    else:
        L.append("_No evaluation suggestions were derived._")
    L.append("")

    # 8
    L.append("## 8. Research Gaps\n")
    L.append(prose.get("research_gaps", "").strip() + "\n")

    # 9
    L.append("## 9. Next Steps\n")
    steps = prose.get("next_steps", [])
    if isinstance(steps, list) and steps:
        for i, s in enumerate(steps, 1):
            L.append(f"{i}. {str(s).strip()}")
    else:
        L.append("_No next steps generated._")
    L.append("")

    return "\n".join(L).strip() + "\n"


# ── Public entry point ────────────────────────────────────────────────────────

def generate_report(project_id: str, session: Session) -> tuple[str, dict, str | None, int] | None:
    """
    Generate the project-level research report from persisted data.

    Returns (markdown, sections_dict, llm_model, generation_ms), or None if the
    project does not exist / has no features.
    """
    t0 = time.monotonic()
    data = load_project_report_data(project_id, session)
    if not data or not data.features:
        return None

    areas = _aggregate_research_areas(data)
    top_papers = _aggregate_top_papers(data)
    tech_recs = _collect_recs(data, "missing_technique")
    eval_recs = _collect_recs(data, "evaluation_suggestion")

    model_used: str | None = None
    try:
        from llm.providers import AnthropicProvider
        prose = _parse_json_obj(_call_llm(_build_prompt(data, areas, top_papers, tech_recs, eval_recs)))
        model_used = AnthropicProvider.MODEL
    except Exception as exc:  # noqa: BLE001
        log.warning("Report LLM synthesis failed for %s: %s — using templates", project_id, exc)
        prose = _fallback_prose(data, top_papers, tech_recs)

    markdown = _assemble_markdown(data, prose, areas, top_papers, tech_recs, eval_recs)

    sections = {
        "executive_summary": prose.get("executive_summary", ""),
        "key_research_areas": [{"name": n, "feature_count": c} for n, c in areas],
        "feature_analysis": prose.get("feature_analysis", ""),
        "most_relevant_papers": top_papers,
        "recommended_techniques": tech_recs,
        "missing_components": [r["title"] for r in tech_recs],
        "evaluation_suggestions": eval_recs,
        "research_gaps": prose.get("research_gaps", ""),
        "next_steps": prose.get("next_steps", []),
    }
    ms = int((time.monotonic() - t0) * 1000)
    return markdown, sections, model_used, ms
