"""
feature_mapper/explain_and_recommend.py
────────────────────────────────────────
Single LLM call that produces both relevance explanations and recommendations.

Replaces the two sequential calls in _process_feature():
    explain_feature(feature, papers)              → 1 LLM call (~25s)
    generate_recommendations(feature, papers, db) → 1 LLM call (~14s)

With one call that returns both sections in a single JSON object:
    explain_and_recommend(feature, papers, db)    → 1 LLM call (~17-20s)

Deterministic aggregation (_aggregate_techniques, _aggregate_eval_items)
is unchanged — only the final LLM phrasing step is merged.

Fail-soft contract:
    LLM call failure        → papers unchanged, template recommendations
    explanations unparse    → papers unchanged, still try recommendation section
    recommendations unparse → papers with explanations, template recommendations
    individual paper miss   → that paper's explanation fields stay None/empty
"""

from __future__ import annotations

import json
import logging
import os
import re
from collections import defaultdict

from sqlalchemy.orm import Session

from feature_mapper.models import Feature, PaperMatch, Recommendation
from feature_mapper.recommender import (
    _MAX_RECS_PER_TYPE,
    _aggregate_eval_items,
    _aggregate_techniques,
    _template_recs,
)
from feature_mapper.explainer import _as_str_list, _format_paper

log = logging.getLogger(__name__)

# Enough headroom for explanation (~1500 tokens) + recommendations (~800 tokens)
# with margin for variation in feature/paper length.
_COMBINED_MAX_TOKENS = 3072


_SYSTEM_PROMPT = (
    "You are a research analyst. Given a software/ML project feature and retrieved "
    "research papers you will produce two things: "
    "(1) a relevance explanation for each paper, and "
    "(2) evidence-based engineering recommendations for the feature. "
    "Return ONLY a valid JSON object — no prose, no markdown fences. "
    "Every explanation must name a concrete technique or contribution from both the "
    "feature and the paper. Every recommendation must use only the candidate names "
    "provided — never invent new candidates."
)


def _fmt_candidates(cands: list[dict], titles_by_id: dict[str, str]) -> str:
    if not cands:
        return "(none)"
    lines = []
    for c in cands:
        titles = [titles_by_id.get(pid, pid) for pid in c["paper_ids"][:3]]
        lines.append(
            f'- "{c["name"]}" — in {c["paper_count"]} paper(s): {"; ".join(titles)}'
        )
    return "\n".join(lines)


def _build_prompt(
    feature: Feature,
    papers: list[PaperMatch],
    tech_candidates: list[dict],
    eval_candidates: list[dict],
    titles_by_id: dict[str, str],
) -> str:
    paper_blocks = "\n\n".join(_format_paper(i, p) for i, p in enumerate(papers))

    explain_schema = (
        '[{"paper":0,'
        '"relevance_explanation":"2-4 sentence paragraph referencing both the '
        'feature and this specific paper",'
        '"similarity_points":["short bullet","short bullet"],'
        '"difference_points":["short bullet"]}]'
    )
    rec_schema = (
        '[{"rec_type":"missing_technique|evaluation_suggestion",'
        '"item":"<exact candidate name>",'
        '"title":"short imperative title",'
        '"body":"2-3 sentences why it would help THIS feature"}]'
    )

    return (
        "FEATURE\n"
        f"Name: {feature.name}\n"
        f"Description: {feature.description}\n"
        f"Source text: {feature.source_text or feature.description}\n"
        f"Already uses: {', '.join(feature.matched_techniques) or '(none recognized)'}\n\n"
        f"RETRIEVED PAPERS ({len(papers)})\n"
        f"{paper_blocks}\n\n"
        "CANDIDATE MISSING TECHNIQUES (absent from feature, appear in papers above):\n"
        f"{_fmt_candidates(tech_candidates, titles_by_id)}\n\n"
        "CANDIDATE EVALUATION METHODS (absent from feature, appear in papers above):\n"
        f"{_fmt_candidates(eval_candidates, titles_by_id)}\n\n"
        "TASK 1 — For EACH paper write a relevance explanation.\n"
        "  relevance_explanation: 2-4 sentences, must name something specific from "
        "both the feature and the paper.\n"
        "  similarity_points: 2-4 short bullets of concrete shared techniques/goals.\n"
        "  difference_points: 1-3 short bullets of concrete differences. [] if none.\n\n"
        "TASK 2 — Write up to 3 missing_technique and up to 3 evaluation_suggestion "
        "recommendations.\n"
        "  item: copy the exact candidate name from the lists above.\n"
        "  Skip any candidate that would not genuinely help this feature.\n\n"
        'Return a JSON object with exactly two keys "explanations" and "recommendations":\n'
        f'{{"explanations": {explain_schema}, "recommendations": {rec_schema}}}'
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
        max_tokens=_COMBINED_MAX_TOKENS,
        system=_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )
    return resp.content[0].text


def _parse_combined(raw: str) -> tuple[list[dict] | None, list[dict] | None]:
    """
    Parse {explanations: [...], recommendations: [...]}.
    Returns (explanations_or_None, recommendations_or_None).
    None means that section is absent or unparseable.
    """
    obj: dict | None = None

    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            obj = parsed
    except json.JSONDecodeError:
        pass

    if obj is None:
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        if m:
            try:
                parsed = json.loads(m.group())
                if isinstance(parsed, dict):
                    obj = parsed
            except json.JSONDecodeError:
                pass

    if obj is None:
        return None, None

    explanations = obj.get("explanations")
    recommendations = obj.get("recommendations")
    return (
        explanations if isinstance(explanations, list) else None,
        recommendations if isinstance(recommendations, list) else None,
    )


def _apply_explanations(papers: list[PaperMatch], items: list[dict]) -> None:
    """Mutate papers in place with explanation fields. Matches by 'paper' index."""
    by_index: dict[int, dict] = {}
    for pos, item in enumerate(items):
        if not isinstance(item, dict):
            continue
        idx = item.get("paper")
        by_index[idx if isinstance(idx, int) else pos] = item

    for i, paper in enumerate(papers):
        item = by_index.get(i)
        if not item:
            continue
        explanation = (item.get("relevance_explanation") or "").strip()
        paper.relevance_explanation = explanation or None
        paper.similarity_points = _as_str_list(item.get("similarity_points"))
        paper.difference_points = _as_str_list(item.get("difference_points"))


def _build_recs(
    items: list[dict],
    tech_by_name: dict[str, dict],
    eval_by_name: dict[str, dict],
    titles_by_id: dict[str, str],
) -> list[Recommendation]:
    """Map LLM recommendation items back to Recommendation objects via evidence look-up."""
    recs: list[Recommendation] = []
    rank_by_type: dict[str, int] = defaultdict(int)

    for item in items:
        if not isinstance(item, dict):
            continue
        rec_type = (item.get("rec_type") or "").strip()
        name = (item.get("item") or "").strip()
        title = (item.get("title") or "").strip()
        body = (item.get("body") or "").strip()

        if rec_type not in ("missing_technique", "evaluation_suggestion"):
            continue
        if not title or not body:
            continue

        source = tech_by_name if rec_type == "missing_technique" else eval_by_name
        cand = source.get(name.lower())
        if not cand:
            continue  # LLM used a name not in our candidate set — drop it
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

    return recs


def explain_and_recommend(
    feature: Feature,
    papers: list[PaperMatch],
    session: Session,
) -> tuple[list[PaperMatch], list[Recommendation]]:
    """
    One LLM call returning relevance explanations for each paper and
    evidence-based recommendations for the feature.

    Returns (papers, recommendations). Papers are mutated in place with
    explanation fields; caller receives the same list reference.

    Fail-soft: never raises. On any failure, explanations fields stay
    None/empty and recommendations fall back to deterministic templates.
    """
    if not papers:
        return papers, []

    paper_ids = [p.paper_id for p in papers]
    titles_by_id = {p.paper_id: p.title for p in papers}

    # ── Deterministic aggregation (unchanged from recommender.py) ─────────────
    tech_candidates = _aggregate_techniques(paper_ids, feature, session)
    eval_candidates = _aggregate_eval_items(paper_ids, feature, session)
    no_candidates = not tech_candidates and not eval_candidates

    tech_by_name = {c["name"].lower(): c for c in tech_candidates}
    eval_by_name = {c["name"].lower(): c for c in eval_candidates}

    # ── Single LLM call ───────────────────────────────────────────────────────
    try:
        raw = _call_llm(
            _build_prompt(feature, papers, tech_candidates, eval_candidates, titles_by_id)
        )
    except Exception as exc:
        log.warning(
            "explain_and_recommend LLM call failed for %r: %s — "
            "papers unchanged, using template recommendations",
            feature.name, exc,
        )
        if no_candidates:
            return papers, []
        return papers, _template_recs(tech_candidates, eval_candidates, titles_by_id)

    # ── Parse ─────────────────────────────────────────────────────────────────
    explanation_items, rec_items = _parse_combined(raw)

    # Apply explanations (fail-soft per-section)
    if explanation_items is not None:
        try:
            _apply_explanations(papers, explanation_items)
        except Exception as exc:
            log.warning(
                "Explanation application failed for %r: %s — fields stay empty",
                feature.name, exc,
            )
    else:
        log.warning(
            "Explanation section absent/unparseable for %r — fields stay empty",
            feature.name,
        )

    # Build recommendations (fail-soft: template on any failure)
    if no_candidates:
        return papers, []

    if rec_items is not None:
        try:
            recs = _build_recs(rec_items, tech_by_name, eval_by_name, titles_by_id)
            if recs:
                return papers, recs
            # Parsed successfully but nothing usable → fall through to templates
        except Exception as exc:
            log.warning(
                "Recommendation parsing failed for %r: %s — using templates",
                feature.name, exc,
            )
    else:
        log.warning(
            "Recommendation section absent/unparseable for %r — using templates",
            feature.name,
        )

    return papers, _template_recs(tech_candidates, eval_candidates, titles_by_id)
