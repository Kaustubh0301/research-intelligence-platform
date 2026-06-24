"""
feature_mapper/recommender.py
─────────────────────────────
Evidence-based recommendations for a feature (Phase 2C).

Two recommendation types, both derived ENTIRELY from the feature's already-
retrieved papers:

  missing_technique     — techniques appearing in multiple retrieved papers but
                          absent from the feature.
  evaluation_suggestion — datasets/benchmarks/metrics appearing in multiple
                          retrieved papers but absent from the feature.

Pipeline:
  1. Deterministic aggregation across the top retrieved paper_ids
     (paper_techniques, paper_datasets, paper_analyses.experimental_findings).
     Candidates are corpus-derived, ranked by how many papers support them, and
     filtered against what the feature already mentions.
  2. ONE LLM call per feature turns the pre-filtered candidates into polished,
     evidence-citing recommendations. Because candidates come from the corpus,
     the model cannot invent techniques.
  3. Fail-soft: if the LLM call fails, fall back to deterministic templated
     recommendations built from the same candidates.

Public API:
    generate_recommendations(feature, papers, session) → list[Recommendation]
"""

from __future__ import annotations

import json
import logging
import os
import re
from collections import defaultdict

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from db.models import PaperAnalysisRecord, PaperDataset, PaperTechnique
from feature_mapper.models import Feature, PaperMatch, Recommendation

log = logging.getLogger(__name__)

_REC_MAX_TOKENS = 1536
_MAX_CANDIDATES_PER_TYPE = 8   # candidates handed to the LLM
_MAX_RECS_PER_TYPE = 3         # recommendations kept per type
_MIN_EVIDENCE = 2              # prefer items supported by ≥ 2 papers

_SYSTEM_PROMPT = (
    "You write concise, evidence-based engineering recommendations. You are given "
    "a project feature and candidate techniques / evaluation methods that appear in "
    "research papers retrieved for that feature but are absent from it. You return "
    "only valid JSON. Each recommendation must be specific and grounded in the "
    "candidate evidence — never generic."
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _hex_maps(paper_ids: list[str]) -> tuple[list[str], dict[str, str]]:
    """Return (hex_ids, hex→original) — paper_techniques etc. store hex ids."""
    hex_ids = [p.replace("-", "") for p in paper_ids]
    return hex_ids, {p.replace("-", ""): p for p in paper_ids}


def _feature_text_blob(feature: Feature) -> str:
    return " ".join([
        feature.name or "",
        feature.description or "",
        feature.source_text or "",
        " ".join(feature.matched_techniques),
        " ".join(feature.matched_categories),
    ]).lower()


def _already_present(name: str, blob: str, present_set: set[str]) -> bool:
    n = name.lower().strip()
    if not n:
        return True
    if n in present_set:
        return True
    # Substring either direction: feature mentions it, catches "FAISS" in text.
    return n in blob


# ── Aggregation ───────────────────────────────────────────────────────────────

def _aggregate_techniques(
    paper_ids: list[str],
    feature: Feature,
    session: Session,
) -> list[dict]:
    """Candidate missing techniques, ranked by # supporting papers."""
    if not paper_ids:
        return []
    hex_ids, hex_to_orig = _hex_maps(paper_ids)
    blob = _feature_text_blob(feature)
    present = {t.lower() for t in feature.matched_techniques}

    rows = session.execute(
        select(PaperTechnique.paper_id, PaperTechnique.canonical_name)
        .where(
            PaperTechnique.paper_id.in_(hex_ids),
            PaperTechnique.canonical_name.isnot(None),
        )
    ).all()

    by_name: dict[str, set[str]] = defaultdict(set)
    for hex_pid, cname in rows:
        if not cname:
            continue
        if _already_present(cname, blob, present):
            continue
        by_name[cname].add(hex_to_orig.get(hex_pid, hex_pid))

    candidates = [
        {"name": name, "paper_ids": sorted(pids), "paper_count": len(pids)}
        for name, pids in by_name.items()
    ]
    candidates.sort(key=lambda c: c["paper_count"], reverse=True)
    return candidates[:_MAX_CANDIDATES_PER_TYPE]


_FINDING_SPLIT = re.compile(r"\s*::\s*")


def _aggregate_eval_items(
    paper_ids: list[str],
    feature: Feature,
    session: Session,
) -> list[dict]:
    """Candidate evaluation items (datasets + benchmarks/metrics), ranked by # papers."""
    if not paper_ids:
        return []
    hex_ids, hex_to_orig = _hex_maps(paper_ids)
    blob = _feature_text_blob(feature)

    by_name: dict[str, set[str]] = defaultdict(set)

    # Datasets / benchmarks
    ds_rows = session.execute(
        select(PaperDataset.paper_id, PaperDataset.canonical_name, PaperDataset.name)
        .where(PaperDataset.paper_id.in_(hex_ids))
    ).all()
    for hex_pid, cname, name in ds_rows:
        item = (cname or name or "").strip()
        if item and not _already_present(item, blob, set()):
            by_name[item].add(hex_to_orig.get(hex_pid, hex_pid))

    # Benchmarks + metrics parsed from experimental_findings ("bench :: metric :: score")
    fnd_rows = session.execute(
        select(PaperAnalysisRecord.paper_id, PaperAnalysisRecord.experimental_findings)
        .where(
            PaperAnalysisRecord.paper_id.in_(hex_ids),
            PaperAnalysisRecord.experimental_findings.isnot(None),
        )
    ).all()
    for hex_pid, raw in fnd_rows:
        try:
            findings = json.loads(raw) if raw else []
        except (json.JSONDecodeError, TypeError):
            continue
        if not isinstance(findings, list):
            continue
        orig = hex_to_orig.get(hex_pid, hex_pid)
        for entry in findings:
            if not isinstance(entry, str):
                continue
            parts = _FINDING_SPLIT.split(entry)
            for token in parts[:2]:  # benchmark + metric (skip the score value)
                item = token.strip()
                if item and len(item) <= 60 and not _already_present(item, blob, set()):
                    by_name[item].add(orig)

    candidates = [
        {"name": name, "paper_ids": sorted(pids), "paper_count": len(pids)}
        for name, pids in by_name.items()
    ]
    candidates.sort(key=lambda c: c["paper_count"], reverse=True)
    return candidates[:_MAX_CANDIDATES_PER_TYPE]


def _filter_by_evidence(candidates: list[dict]) -> list[dict]:
    """Prefer candidates supported by ≥ _MIN_EVIDENCE papers; fall back to top-1 each."""
    strong = [c for c in candidates if c["paper_count"] >= _MIN_EVIDENCE]
    chosen = strong if strong else candidates[:_MAX_RECS_PER_TYPE]
    return chosen[:_MAX_RECS_PER_TYPE]


# ── LLM phrasing ──────────────────────────────────────────────────────────────

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
        max_tokens=_REC_MAX_TOKENS,
        system=_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )
    return resp.content[0].text


def _parse_json_array(raw: str) -> list[dict]:
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            return parsed
    except json.JSONDecodeError:
        pass
    m = re.search(r"\[.*\]", raw, re.DOTALL)
    if not m:
        raise ValueError(f"No JSON array in recommendation output: {raw[:200]!r}")
    parsed = json.loads(m.group())
    if not isinstance(parsed, list):
        raise ValueError("Recommendation output is not a JSON array.")
    return parsed


def _build_prompt(
    feature: Feature,
    tech_candidates: list[dict],
    eval_candidates: list[dict],
    titles_by_id: dict[str, str],
) -> str:
    def _fmt(cands: list[dict]) -> str:
        lines = []
        for c in cands:
            titles = [titles_by_id.get(pid, pid) for pid in c["paper_ids"][:3]]
            lines.append(
                f'- "{c["name"]}" — in {c["paper_count"]} paper(s): {"; ".join(titles)}'
            )
        return "\n".join(lines) if lines else "(none)"

    schema = (
        '[{"rec_type":"missing_technique","item":"<exact candidate name>",'
        '"title":"short imperative title","body":"2-3 sentences: what it is and why '
        'it would help THIS feature, referencing the supporting papers"}]'
    )
    return (
        "FEATURE\n"
        f"Name: {feature.name}\n"
        f"Description: {feature.description}\n"
        f"Already uses techniques: {', '.join(feature.matched_techniques) or '(none recognized)'}\n\n"
        "CANDIDATE MISSING TECHNIQUES (appear in retrieved papers, absent from feature):\n"
        f"{_fmt(tech_candidates)}\n\n"
        "CANDIDATE EVALUATION METHODS / BENCHMARKS (appear in retrieved papers, absent from feature):\n"
        f"{_fmt(eval_candidates)}\n\n"
        "Write up to 3 'missing_technique' and up to 3 'evaluation_suggestion' "
        "recommendations. Use ONLY the candidate names above (copy the exact name into "
        "the \"item\" field). Skip a candidate if it would not genuinely help this "
        "feature. Each body must reference why it matters for this specific feature.\n\n"
        f"Return a JSON array ONLY, matching exactly:\n{schema}"
    )


# ── Fallback templating ───────────────────────────────────────────────────────

def _template_recs(
    tech_candidates: list[dict],
    eval_candidates: list[dict],
    titles_by_id: dict[str, str],
) -> list[Recommendation]:
    recs: list[Recommendation] = []
    rank = 1
    for c in _filter_by_evidence(tech_candidates):
        recs.append(Recommendation(
            rec_type="missing_technique",
            rank=rank,
            title=f"Consider adopting {c['name']}",
            body=(
                f"{c['name']} appears in {c['paper_count']} of the retrieved papers "
                f"for this feature but is not part of it. Reviewing how those papers "
                f"apply it may strengthen this component."
            ),
            supporting_paper_ids=c["paper_ids"],
            supporting_paper_titles=[titles_by_id.get(p, p) for p in c["paper_ids"]],
            priority_score=float(c["paper_count"]),
            evidence_count=c["paper_count"],
        ))
        rank += 1
    rank = 1
    for c in _filter_by_evidence(eval_candidates):
        recs.append(Recommendation(
            rec_type="evaluation_suggestion",
            rank=rank,
            title=f"Evaluate against {c['name']}",
            body=(
                f"{c['name']} is used by {c['paper_count']} of the retrieved papers "
                f"to evaluate similar work, but is not mentioned in this feature. "
                f"Adopting it would enable direct comparison with the literature."
            ),
            supporting_paper_ids=c["paper_ids"],
            supporting_paper_titles=[titles_by_id.get(p, p) for p in c["paper_ids"]],
            priority_score=float(c["paper_count"]),
            evidence_count=c["paper_count"],
        ))
        rank += 1
    return recs


# ── Public entry point ────────────────────────────────────────────────────────

def generate_recommendations(
    feature: Feature,
    papers: list[PaperMatch],
    session: Session,
) -> list[Recommendation]:
    """
    Produce evidence-based recommendations for a feature from its retrieved papers.
    One LLM call max; fail-soft to deterministic templates.
    """
    if not papers:
        return []

    paper_ids = [p.paper_id for p in papers]
    titles_by_id = {p.paper_id: p.title for p in papers}

    tech_candidates = _aggregate_techniques(paper_ids, feature, session)
    eval_candidates = _aggregate_eval_items(paper_ids, feature, session)

    if not tech_candidates and not eval_candidates:
        return []

    # Candidate name → aggregation row, for mapping LLM output back to evidence.
    tech_by_name = {c["name"].lower(): c for c in tech_candidates}
    eval_by_name = {c["name"].lower(): c for c in eval_candidates}

    try:
        raw = _call_llm(_build_prompt(feature, tech_candidates, eval_candidates, titles_by_id))
        items = _parse_json_array(raw)
    except Exception as exc:  # noqa: BLE001
        log.warning("Recommendation LLM call failed for %r: %s — using templates", feature.name, exc)
        return _template_recs(tech_candidates, eval_candidates, titles_by_id)

    recs: list[Recommendation] = []
    rank_by_type: dict[str, int] = defaultdict(int)
    for item in items:
        if not isinstance(item, dict):
            continue
        rec_type = (item.get("rec_type") or "").strip()
        name = (item.get("item") or "").strip()
        title = (item.get("title") or "").strip()
        body = (item.get("body") or "").strip()
        if rec_type not in ("missing_technique", "evaluation_suggestion") or not title or not body:
            continue

        source = tech_by_name if rec_type == "missing_technique" else eval_by_name
        cand = source.get(name.lower())
        if not cand:
            # LLM referenced something not in our evidence set — drop to stay grounded.
            continue
        if rank_by_type[rec_type] >= _MAX_RECS_PER_TYPE:
            continue
        rank_by_type[rec_type] += 1

        recs.append(Recommendation(
            rec_type=rec_type,
            rank=rank_by_type[rec_type],
            title=title,
            body=body,
            supporting_paper_ids=cand["paper_ids"],
            supporting_paper_titles=[titles_by_id.get(p, p) for p in cand["paper_ids"]],
            priority_score=float(cand["paper_count"]),
            evidence_count=cand["paper_count"],
        ))

    # If the LLM produced nothing usable, fall back to templates.
    return recs or _template_recs(tech_candidates, eval_candidates, titles_by_id)
