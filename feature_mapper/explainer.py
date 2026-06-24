"""
feature_mapper/explainer.py
───────────────────────────
Relevance explanations: why is each retrieved paper relevant to a feature?

One LLM call per feature — never one call per paper. The call receives the
feature (name, description, verbatim source_text) and its top-K papers (title,
abstract snippet, techniques, and the signals that fired the match), and returns
structured JSON for all papers at once.

Grounding rules enforced by the prompt:
  - Every explanation must reference something specific from the feature text
    AND something specific from the paper (a technique, contribution, or domain).
  - Generic explanations ("relevant because similar") are rejected.
  - The matched techniques/categories are passed as hints so the model anchors
    on the real signal rather than inventing a connection.

Uses the same direct-client max_tokens=2048 path as the extractor (the provider
default of 1024 truncates structured JSON for 5 papers).

Public API:
    explain_feature(feature, papers) → papers (mutated in place with explanations)
"""

from __future__ import annotations

import json
import logging
import os
import re

from feature_mapper.models import Feature, PaperMatch

log = logging.getLogger(__name__)

_EXPLAIN_MAX_TOKENS = 2048
_ABSTRACT_CHARS = 500

_SYSTEM_PROMPT = (
    "You are a research analyst explaining why specific papers are relevant to "
    "a feature of a software/ML project. You return only valid JSON — no prose, "
    "no markdown fences. Every explanation must be specific and grounded: it must "
    "reference something concrete from the feature AND something concrete from the "
    "paper (a named technique, contribution, dataset, or domain). Never write a "
    "generic explanation like 'this paper is relevant because it is similar'."
)


def _format_paper(idx: int, p: PaperMatch) -> str:
    hints = p.matched_techniques or p.top_techniques
    hint_line = f"Matched/known techniques: {', '.join(hints[:6])}" if hints else ""
    venue = f"{p.venue or '?'} {p.year or ''}".strip()
    abstract = (p.abstract or "").strip()[:_ABSTRACT_CHARS]
    return (
        f"[Paper {idx}] {p.title} ({venue})\n"
        f"{hint_line}\n"
        f"Abstract: {abstract}"
    ).strip()


def _build_prompt(feature: Feature, papers: list[PaperMatch]) -> str:
    paper_blocks = "\n\n".join(_format_paper(i, p) for i, p in enumerate(papers))
    schema = (
        '[{"paper":0,'
        '"relevance_explanation":"2-4 sentence paragraph referencing both the '
        'feature and this specific paper",'
        '"similarity_points":["short bullet","short bullet"],'
        '"difference_points":["short bullet","short bullet"]}]'
    )
    return (
        "FEATURE\n"
        f"Name: {feature.name}\n"
        f"Description: {feature.description}\n"
        f"Source text from the project document: {feature.source_text or feature.description}\n\n"
        f"PAPERS ({len(papers)} retrieved for this feature)\n"
        f"{paper_blocks}\n\n"
        "For EACH paper, explain why it is relevant to the feature above.\n"
        "- relevance_explanation: one concise paragraph (2-4 sentences). It MUST "
        "reference something specific from the feature AND something specific from "
        "the paper (e.g. a shared technique by name, or how the paper's contribution "
        "relates to what the feature does).\n"
        "- similarity_points: 2-4 short bullets naming concrete shared techniques, "
        "approaches, or goals.\n"
        "- difference_points: 1-3 short bullets naming concrete differences (domain, "
        "dataset, scope, method variant). If genuinely none, return an empty array.\n\n"
        f"Return a JSON array ONLY, one object per paper, matching exactly:\n{schema}"
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
        max_tokens=_EXPLAIN_MAX_TOKENS,
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
        raise ValueError(f"No JSON array in explanation output: {raw[:300]!r}")
    parsed = json.loads(m.group())
    if not isinstance(parsed, list):
        raise ValueError("Explanation output is not a JSON array.")
    return parsed


def _as_str_list(value) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(v).strip() for v in value if isinstance(v, (str, int, float)) and str(v).strip()]


def explain_feature(feature: Feature, papers: list[PaperMatch]) -> list[PaperMatch]:
    """
    Populate relevance_explanation / similarity_points / difference_points on
    each PaperMatch for a feature, using one LLM call. Papers are mutated in
    place and also returned.

    On any failure the papers are returned unchanged (explanation fields stay
    None/empty) — explanations are additive and must never break retrieval.
    """
    if not papers:
        return papers

    try:
        raw = _call_llm(_build_prompt(feature, papers))
        items = _parse_json_array(raw)
    except Exception as exc:  # noqa: BLE001
        log.warning("Explanation generation failed for feature %r: %s", feature.name, exc)
        return papers

    # Index returned objects by their "paper" field, falling back to position.
    by_index: dict[int, dict] = {}
    for pos, item in enumerate(items):
        if not isinstance(item, dict):
            continue
        idx = item.get("paper")
        if not isinstance(idx, int):
            idx = pos
        by_index[idx] = item

    for i, paper in enumerate(papers):
        item = by_index.get(i)
        if not item:
            continue
        explanation = (item.get("relevance_explanation") or "").strip()
        paper.relevance_explanation = explanation or None
        paper.similarity_points = _as_str_list(item.get("similarity_points"))
        paper.difference_points = _as_str_list(item.get("difference_points"))

    return papers
