"""
feature_mapper/extractor.py
───────────────────────────
Extract discrete technical features from a parsed document via a single LLM call.

The extraction call uses max_tokens=2048 — validation confirmed that the
provider default of 1024 truncates JSON output for documents with ~8+ features
(stop_reason=max_tokens, unparseable JSON). We call the Anthropic client
directly through AnthropicProvider._client() rather than going through
generate_response(), which hardcodes max_tokens=1024.

Public API:
    extract_features(sections, session) → list[Feature]
"""

from __future__ import annotations

import json
import logging
import os
import re
import uuid

from sqlalchemy.orm import Session

from feature_mapper.models import FEATURE_TYPES, ExtractedFeature, Feature, RawSection
from feature_mapper.normalizer import normalize_terms

log = logging.getLogger(__name__)

_MAX_FEATURES = 10
_EXTRACTION_MAX_TOKENS = 4096

_SYSTEM_PROMPT = (
    "You extract discrete technical features from software and ML system "
    "documents. You return only valid JSON — no prose, no markdown fences."
)

_JSON_FORMAT = (
    '[{"name":"short feature name (5-10 words)",'
    '"description":"2-3 sentences of technical detail",'
    '"source_section":"the heading this came from, or null",'
    '"source_text":"the exact sentence(s) from the document describing this",'
    '"feature_type":"algorithm|architecture|training|evaluation|data|infrastructure|other",'
    '"raw_terms":["specific","technical","terms","to","look","up"]}]'
)


def _build_prompt(sections: list[RawSection]) -> str:
    formatted = "\n\n".join(
        f"## {s.heading}\n{s.text}" if s.heading else s.text
        for s in sections
    )
    return (
        f"Analyze the following project document and identify 3-{_MAX_FEATURES} "
        "discrete technical features or components.\n\n"
        "Rules:\n"
        "- Each feature must be a specific technical concern "
        "(e.g. 'bi-encoder dense retrieval', not 'search').\n"
        "- Stay strictly grounded in what the document actually says. "
        "Do not invent features not present in the text.\n"
        "- 'raw_terms' should list the specific algorithms, models, datasets, "
        "and method names mentioned, so they can be matched against a research corpus.\n\n"
        f"Return a JSON array ONLY, matching exactly this schema:\n{_JSON_FORMAT}\n\n"
        f"Document:\n{formatted}"
    )


def _call_extraction_llm(prompt: str) -> str:
    """Call Claude with max_tokens=2048 (validated minimum for ~10 features)."""
    from llm.providers import AnthropicProvider

    api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY is not set.")
    base_url = os.getenv("ANTHROPIC_BASE_URL", "").strip() or None

    provider = AnthropicProvider(api_key=api_key, base_url=base_url)
    client = provider._client()
    resp = client.messages.create(
        model=AnthropicProvider.MODEL,
        max_tokens=_EXTRACTION_MAX_TOKENS,
        system=_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )
    return resp.content[0].text


def _parse_json_array(raw: str) -> list[dict]:
    """Parse a JSON array from the model output, tolerating code fences / prose."""
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            return parsed
    except json.JSONDecodeError:
        pass

    # Fall back to extracting the outermost [...] block.
    m = re.search(r"\[.*\]", raw, re.DOTALL)
    if not m:
        raise ValueError(f"No JSON array found in extraction output: {raw[:300]!r}")
    parsed = json.loads(m.group())
    if not isinstance(parsed, list):
        raise ValueError("Extraction output is not a JSON array.")
    return parsed


def _coerce_feature_type(value: str | None) -> str:
    if value and value.strip().lower() in FEATURE_TYPES:
        return value.strip().lower()
    return "other"


def extract_features(sections: list[RawSection], session: Session) -> list[Feature]:
    """
    Extract and normalize features from parsed document sections.

    One LLM call; raw_terms from each feature are resolved to corpus vocabulary
    via the dual-path normalizer. Returns at most _MAX_FEATURES features.
    """
    if not sections:
        return []

    prompt = _build_prompt(sections)
    raw_output = _call_extraction_llm(prompt)
    items = _parse_json_array(raw_output)

    features: list[Feature] = []
    for item in items[:_MAX_FEATURES]:
        if not isinstance(item, dict):
            continue
        name = (item.get("name") or "").strip()
        if not name:
            continue

        try:
            ef = ExtractedFeature(
                name=name,
                description=(item.get("description") or "").strip(),
                source_section=item.get("source_section") or None,
                source_text=(item.get("source_text") or "").strip(),
                feature_type=_coerce_feature_type(item.get("feature_type")),
                raw_terms=[t for t in (item.get("raw_terms") or []) if isinstance(t, str)],
            )
        except Exception as exc:  # noqa: BLE001 — skip malformed items, keep the rest
            log.warning("Skipping malformed feature item: %s", exc)
            continue

        matched_tech, matched_cat, unrecognized = normalize_terms(ef.raw_terms, session)

        features.append(
            Feature(
                id=str(uuid.uuid4()),
                name=ef.name,
                description=ef.description,
                source_section=ef.source_section,
                source_text=ef.source_text,
                feature_type=ef.feature_type,
                matched_techniques=matched_tech,
                matched_categories=matched_cat,
                unrecognized_terms=unrecognized,
            )
        )

    return features


# ── Manual smoke test ─────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    _root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.path.insert(0, _root)
    from dotenv import load_dotenv

    load_dotenv(dotenv_path=os.path.join(_root, ".env"), override=True)
    from db.session import get_session
    from feature_mapper.parser import parse

    doc = """# Hybrid Search Engine

## Sparse Retrieval
We use BM25 over an inverted index built with Pyserini for lexical matching.

## Dense Retrieval
Bi-encoder dense retrieval with DPR. Passages indexed in FAISS for ANN search.

## Fusion
BM25 and dense scores are combined using Reciprocal Rank Fusion with k=60.

## Re-ranking
Top candidates re-ranked by a cross-encoder fine-tuned on MS MARCO.
"""
    sections = parse(doc)
    with get_session() as s:
        feats = extract_features(sections, s)
        for f in feats:
            print(f"\n● {f.name}  [{f.feature_type}]")
            print(f"  {f.description}")
            print(f"  techniques: {f.matched_techniques}")
            print(f"  categories: {f.matched_categories}")
            print(f"  unrecognized: {f.unrecognized_terms}")
