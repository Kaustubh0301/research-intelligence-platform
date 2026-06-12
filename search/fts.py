"""
search/fts.py
─────────────
Raw FTS5 query functions and table health utilities.

All functions in this module accept an open SQLAlchemy Session and return
plain Python values (lists, sets, tuples, booleans).  No ORM models, no
business logic, no scoring.

FTS table schema (migration 010):
    papers_fts   (paper_id, title, abstract)          tokenize='porter unicode61'
    entities_fts (paper_id, entity_type, name)        tokenize='unicode61'

Phase 1 scope: techniques + categories indexed in entities_fts.
               datasets excluded (added in Phase 2).
"""

from __future__ import annotations

import uuid as _uuid_mod

from sqlalchemy import text
from sqlalchemy.orm import Session


def _norm_id(raw: str) -> str:
    """
    Normalize a paper_id returned by FTS5 to the hyphenated UUID format used
    by the SQLAlchemy ORM layer.

    SQLite stores Paper.id as a raw hex string without hyphens (e.g.
    '4eeffea528b342f4bba999e2f625cc9a'), but SQLAlchemy's UUID type returns
    it as '4eeffea5-28b3-42f4-bba9-99e2f625cc9a'.  FTS5 stores whatever the
    INSERT...SELECT brought in from SQLite, so IDs come back without hyphens.
    Normalizing here keeps the rest of the stack consistent.
    """
    try:
        return str(_uuid_mod.UUID(raw))
    except ValueError:
        return raw  # non-UUID IDs passed through unchanged

FTS_PAPERS_TABLE   = "papers_fts"
FTS_ENTITIES_TABLE = "entities_fts"

# BM25 column weights for papers_fts(paper_id, title, abstract).
# paper_id is UNINDEXED-equivalent (not a text column) → weight 0.
# title weight / abstract weight ratio mirrors the legacy +20 / +15 scoring.
_BM25_TITLE_WEIGHT    = 10.0
_BM25_ABSTRACT_WEIGHT =  5.0

# Maximum candidates returned from the papers FTS query before metadata join.
_FTS_PAPER_CANDIDATES  = 200
# Maximum entity rows returned per query.
_FTS_ENTITY_CANDIDATES = 500


def tables_exist(session: Session) -> bool:
    """Return True if both FTS virtual tables are present in the schema."""
    rows = session.execute(
        text(
            "SELECT name FROM sqlite_master "
            "WHERE type = 'table' AND name IN ('papers_fts', 'entities_fts')"
        )
    ).fetchall()
    found = {r[0] for r in rows}
    return "papers_fts" in found and "entities_fts" in found


def tables_healthy(session: Session) -> tuple[bool, str]:
    """
    Multi-signal health check for both FTS tables.

    Checks:
      1. Both tables exist.
      2. DISTINCT paper_id count in papers_fts >= DISTINCT paper_id count in papers.
      3. DISTINCT paper_id count in entities_fts >= 90% of papers that have
         at least one technique or category row (lenient: not every paper has
         entities, so strict equality is wrong).
      4. Sample row integrity: spot-check 3 random paper_id values from
         papers_fts exist as real IDs in the papers table.

    Returns (ok: bool, message: str).
    """
    if not tables_exist(session):
        return False, "FTS tables do not exist — run rebuild_fts.py"

    # Check 1: paper count
    n_source = session.execute(
        text("SELECT COUNT(DISTINCT id) FROM papers")
    ).scalar() or 0

    n_fts_papers = session.execute(
        text("SELECT COUNT(DISTINCT paper_id) FROM papers_fts")
    ).scalar() or 0

    if n_source == 0:
        return True, "papers table is empty — nothing to index"

    if n_fts_papers < n_source:
        return (
            False,
            f"papers_fts has {n_fts_papers} distinct paper_ids, "
            f"source has {n_source} — run rebuild_fts.py",
        )

    # Check 2: entity coverage
    n_papers_with_entities = session.execute(
        text("""
            SELECT COUNT(DISTINCT paper_id) FROM (
                SELECT paper_id FROM paper_techniques
                UNION
                SELECT paper_id FROM paper_categories
            )
        """)
    ).scalar() or 0

    if n_papers_with_entities > 0:
        n_fts_entities = session.execute(
            text("SELECT COUNT(DISTINCT paper_id) FROM entities_fts")
        ).scalar() or 0
        coverage = n_fts_entities / n_papers_with_entities
        if coverage < 0.9:
            return (
                False,
                f"entities_fts covers {n_fts_entities}/{n_papers_with_entities} "
                f"papers with entities ({coverage:.0%}) — run rebuild_fts.py",
            )

    # Check 3: sample row integrity — verify 3 random FTS paper_ids are real
    sample_rows = session.execute(
        text("""
            SELECT f.paper_id
            FROM papers_fts f
            LEFT JOIN papers p ON p.id = f.paper_id
            WHERE p.id IS NULL
            LIMIT 3
        """)
    ).fetchall()
    if sample_rows:
        bad_ids = [r[0] for r in sample_rows]
        return (
            False,
            f"papers_fts contains paper_ids not in papers table: {bad_ids} "
            f"— run rebuild_fts.py",
        )

    return (
        True,
        f"FTS healthy: {n_fts_papers} papers indexed, "
        f"{n_papers_with_entities} entity-covered papers",
    )


def query_papers_fts(
    session: Session,
    term: str,
    limit: int = _FTS_PAPER_CANDIDATES,
) -> list[tuple[str, float]]:
    """
    Search papers_fts with BM25 ranking.

    Returns [(paper_id, bm25_score), ...] ordered best-first.
    bm25_score is positive (negated from SQLite's negative BM25 output).
    Returns [] if FTS tables do not exist or term is blank.
    """
    term = term.strip()
    if not term:
        return []
    try:
        rows = session.execute(
            text(
                f"SELECT paper_id, -bm25({FTS_PAPERS_TABLE}, 0.0, "
                f"{_BM25_TITLE_WEIGHT}, {_BM25_ABSTRACT_WEIGHT}) AS score "
                f"FROM {FTS_PAPERS_TABLE} "
                f"WHERE {FTS_PAPERS_TABLE} MATCH :q "
                f"ORDER BY bm25({FTS_PAPERS_TABLE}) "
                f"LIMIT :lim"
            ),
            {"q": term, "lim": limit},
        ).fetchall()
        return [(_norm_id(r[0]), float(r[1])) for r in rows]
    except Exception:
        return []


def query_papers_title_only(
    session: Session,
    term: str,
    limit: int = _FTS_PAPER_CANDIDATES,
) -> set[str]:
    """
    Return paper_ids where the FTS match is in the title column.

    Used to generate the "title" vs "abstract" matched_in label.
    Uses FTS5 column filter syntax: title:{term}
    Falls back to empty set if the column filter syntax fails (e.g. phrase
    with spaces not yet quoted).
    """
    term = term.strip()
    if not term:
        return set()
    try:
        rows = session.execute(
            text(
                f"SELECT paper_id FROM {FTS_PAPERS_TABLE} "
                f"WHERE {FTS_PAPERS_TABLE} MATCH :q LIMIT :lim"
            ),
            {"q": f"title:{term}", "lim": limit},
        ).fetchall()
        return {_norm_id(r[0]) for r in rows}
    except Exception:
        return set()


def query_papers_abstract_only(
    session: Session,
    term: str,
    limit: int = _FTS_PAPER_CANDIDATES,
) -> set[str]:
    """
    Return paper_ids where the FTS match is in the abstract column.

    Used to generate the "abstract" matched_in label.
    """
    term = term.strip()
    if not term:
        return set()
    try:
        rows = session.execute(
            text(
                f"SELECT paper_id FROM {FTS_PAPERS_TABLE} "
                f"WHERE {FTS_PAPERS_TABLE} MATCH :q LIMIT :lim"
            ),
            {"q": f"abstract:{term}", "lim": limit},
        ).fetchall()
        return {_norm_id(r[0]) for r in rows}
    except Exception:
        return set()


def query_entities_fts(
    session: Session,
    term: str,
    limit: int = _FTS_ENTITY_CANDIDATES,
) -> list[tuple[str, str, str]]:
    """
    Search entities_fts for techniques and categories.

    Returns [(paper_id, entity_type, name), ...].
    entity_type is 'technique' or 'category'.
    Returns [] if FTS tables do not exist or term is blank.
    """
    term = term.strip()
    if not term:
        return []
    try:
        rows = session.execute(
            text(
                f"SELECT paper_id, entity_type, name "
                f"FROM {FTS_ENTITIES_TABLE} "
                f"WHERE {FTS_ENTITIES_TABLE} MATCH :q "
                f"LIMIT :lim"
            ),
            {"q": term, "lim": limit},
        ).fetchall()
        return [(_norm_id(r[0]), r[1], r[2]) for r in rows]
    except Exception:
        return []
