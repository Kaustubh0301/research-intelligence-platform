"""
feature_mapper/normalizer.py
────────────────────────────
Resolve raw technical terms (from the extractor) to corpus vocabulary.

Dual-path lookup per term:
  1. FTS MATCH against entities_fts — fast, handles tokenized partial terms.
  2. Fallback: direct LIKE against paper_techniques / paper_categories
     canonical_name — catches exact canonical names that the FTS unicode61
     tokenizer fragments (e.g. "Grouped-Query Attention", "Chain-of-Thought
     prompting"), which the validation run showed FTS misses.

A term that matches nothing in either path is returned as unrecognized — an
important signal for downstream coverage/novelty.

Public API:
    normalize_terms(raw_terms, session)
        → (matched_techniques, matched_categories, unrecognized)
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from db.models import PaperCategory, PaperTechnique
from search.fts import query_entities_fts

# Max canonical-name candidates pulled in the LIKE fallback per term.
_FALLBACK_TECH_LIMIT = 3
_FALLBACK_CAT_LIMIT = 2
# Max FTS names accepted per term per entity type (avoids flooding from a
# generic term that matches dozens of entity rows).
_FTS_TECH_LIMIT = 2
_FTS_CAT_LIMIT = 2


def _fallback_techniques(term: str, session: Session) -> list[str]:
    like = f"%{term.lower()}%"
    rows = session.execute(
        select(PaperTechnique.canonical_name)
        .where(
            PaperTechnique.canonical_name.isnot(None),
            func.lower(PaperTechnique.canonical_name).like(like),
        )
        .group_by(PaperTechnique.canonical_name)
        .order_by(func.count(PaperTechnique.id).desc())
        .limit(_FALLBACK_TECH_LIMIT)
    ).all()
    return [r[0] for r in rows if r[0]]


def _fallback_categories(term: str, session: Session) -> list[str]:
    like = f"%{term.lower()}%"
    rows = session.execute(
        select(PaperCategory.canonical_name)
        .where(
            PaperCategory.canonical_name.isnot(None),
            func.lower(PaperCategory.canonical_name).like(like),
        )
        .group_by(PaperCategory.canonical_name)
        .order_by(func.count(PaperCategory.id).desc())
        .limit(_FALLBACK_CAT_LIMIT)
    ).all()
    return [r[0] for r in rows if r[0]]


def normalize_terms(
    raw_terms: list[str],
    session: Session,
) -> tuple[list[str], list[str], list[str]]:
    """
    Resolve raw_terms to corpus vocabulary via dual-path lookup.

    Returns (matched_techniques, matched_categories, unrecognized).
    All three lists are deduplicated, order-preserving.
    """
    matched_techniques: list[str] = []
    matched_categories: list[str] = []
    unrecognized: list[str] = []

    def _add(target: list[str], name: str) -> None:
        if name and name not in target:
            target.append(name)

    for raw in raw_terms:
        term = (raw or "").strip()
        if not term:
            continue

        found = False

        # ── Path 1: FTS MATCH ─────────────────────────────────────────────
        # query_entities_fts swallows tokenizer syntax errors and returns [].
        hits = query_entities_fts(session, term, limit=20)
        techs = [h[2] for h in hits if h[1] == "technique"][:_FTS_TECH_LIMIT]
        cats = [h[2] for h in hits if h[1] == "category"][:_FTS_CAT_LIMIT]
        for t in techs:
            _add(matched_techniques, t)
            found = True
        for c in cats:
            _add(matched_categories, c)
            found = True

        # ── Path 2: canonical_name LIKE fallback ─────────────────────────
        # Only when FTS found nothing for this term.
        if not found:
            for t in _fallback_techniques(term, session):
                _add(matched_techniques, t)
                found = True
            for c in _fallback_categories(term, session):
                _add(matched_categories, c)
                found = True

        if not found:
            _add(unrecognized, term)

    return matched_techniques, matched_categories, unrecognized
