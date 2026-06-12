"""
search/sync.py
──────────────
Batch synchronization functions for FTS5 virtual tables.

Rules:
  - Never call with a single paper_id.  Always pass a list.
  - Never open a session internally.  Accept Session from caller.
  - The caller is responsible for commit/rollback.
  - FTS sync failure is always logged but should not abort the caller's
    transaction: wrap calls in try/except at the call site.

Phase 1 entity scope: paper_techniques + paper_categories only.
                      Datasets added in Phase 2 (see PHASE2_TODO marker).
"""

from __future__ import annotations

import logging

from sqlalchemy import bindparam, text
from sqlalchemy.orm import Session

log = logging.getLogger(__name__)

# SQLite default SQLITE_MAX_VARIABLE_NUMBER is 999.
# We stay under it with a safe margin to leave room for other bound params.
SQLITE_IN_LIMIT: int = 900


# ── Internal helpers ──────────────────────────────────────────────────────────

def _chunks(lst: list, n: int):
    """Yield successive n-sized chunks from lst."""
    for i in range(0, len(lst), n):
        yield lst[i : i + n]


def _raw_ids(ids: list[str]) -> list[str]:
    """
    Strip hyphens from UUID strings to match the raw SQLite storage format.

    SQLAlchemy's UUID type stores IDs WITHOUT hyphens in SQLite (e.g.
    '4eeffea528b342f4bba999e2f625cc9a'), but the ORM layer returns them WITH
    hyphens ('4eeffea5-28b3-42f4-bba9-99e2f625cc9a').  FTS5 sync queries use
    raw text() SQL, so they must match the raw on-disk format.
    """
    return [uid.replace("-", "") for uid in ids]


def _delete_papers_fts(session: Session, ids: list[str]) -> None:
    raw = _raw_ids(ids)
    session.execute(
        text("DELETE FROM papers_fts WHERE paper_id IN :ids").bindparams(
            bindparam("ids", expanding=True)
        ),
        {"ids": raw},
    )


def _insert_papers_fts(session: Session, ids: list[str]) -> int:
    raw = _raw_ids(ids)
    result = session.execute(
        text(
            "INSERT INTO papers_fts(paper_id, title, abstract) "
            "SELECT id, title, COALESCE(abstract, '') FROM papers "
            "WHERE id IN :ids"
        ).bindparams(bindparam("ids", expanding=True)),
        {"ids": raw},
    )
    return result.rowcount if result.rowcount >= 0 else len(ids)


def _delete_entities_fts(session: Session, ids: list[str]) -> None:
    raw = _raw_ids(ids)
    session.execute(
        text("DELETE FROM entities_fts WHERE paper_id IN :ids").bindparams(
            bindparam("ids", expanding=True)
        ),
        {"ids": raw},
    )


def _insert_entities_fts(session: Session, ids: list[str]) -> int:
    raw = _raw_ids(ids)
    result = session.execute(
        text("""
            INSERT INTO entities_fts(paper_id, entity_type, name)
            SELECT paper_id, 'technique', COALESCE(canonical_name, name)
              FROM paper_techniques
             WHERE paper_id IN :ids
               AND (canonical_name IS NOT NULL OR name IS NOT NULL)
            UNION ALL
            SELECT paper_id, 'category', COALESCE(canonical_name, name)
              FROM paper_categories
             WHERE paper_id IN :ids
               AND (canonical_name IS NOT NULL OR name IS NOT NULL)
            -- PHASE2_TODO: add paper_datasets here
        """).bindparams(bindparam("ids", expanding=True)),
        {"ids": raw},
    )
    return result.rowcount if result.rowcount >= 0 else 0


# ── Public API ────────────────────────────────────────────────────────────────

def sync_papers(session: Session, paper_ids: list[str]) -> int:
    """
    Delete and re-insert papers_fts rows for the given paper IDs.

    Processes in chunks of SQLITE_IN_LIMIT to stay within SQLite's
    variable limit.  Returns total rows inserted.

    Call site: ingestion/run_ingestion.py — once per ingest_one() batch.
    """
    if not paper_ids:
        return 0

    total = 0
    for chunk in _chunks(paper_ids, SQLITE_IN_LIMIT):
        _delete_papers_fts(session, chunk)
        total += _insert_papers_fts(session, chunk)

    log.debug("sync_papers: synced %d / %d paper rows", total, len(paper_ids))
    return total


def sync_entities(session: Session, paper_ids: list[str]) -> int:
    """
    Delete and re-insert entities_fts rows for the given paper IDs.

    Indexes techniques and categories (Phase 1).
    Processes in chunks of SQLITE_IN_LIMIT.
    Returns total rows inserted.

    Call sites:
        notebooklm/normalizer.py  — once after normalize() loop completes.
        pdf_pipeline/pipeline.py  — once after run() loop completes.
        normalize_entities.py     — calls rebuild_all() instead (full rebuild).
        backfill_canonical_names.py — calls rebuild_all() instead (full rebuild).
    """
    if not paper_ids:
        return 0

    total = 0
    for chunk in _chunks(paper_ids, SQLITE_IN_LIMIT):
        _delete_entities_fts(session, chunk)
        total += _insert_entities_fts(session, chunk)

    log.debug("sync_entities: synced %d rows for %d papers", total, len(paper_ids))
    return total


def rebuild_all(session: Session) -> tuple[int, int]:
    """
    Full truncate + rebuild of both FTS indexes from source tables.

    Returns (papers_inserted, entities_inserted).

    Called by: rebuild_fts.py only.
    NOT called by migrate.py (backfill is an explicit operator step).
    """
    log.info("rebuild_all: truncating papers_fts")
    session.execute(text("DELETE FROM papers_fts"))

    log.info("rebuild_all: inserting papers")
    r_papers = session.execute(
        text(
            "INSERT INTO papers_fts(paper_id, title, abstract) "
            "SELECT id, title, COALESCE(abstract, '') FROM papers"
        )
    )
    n_papers = r_papers.rowcount if r_papers.rowcount >= 0 else 0

    log.info("rebuild_all: truncating entities_fts")
    session.execute(text("DELETE FROM entities_fts"))

    log.info("rebuild_all: inserting entities (techniques + categories)")
    r_entities = session.execute(
        text("""
            INSERT INTO entities_fts(paper_id, entity_type, name)
            SELECT paper_id, 'technique', COALESCE(canonical_name, name)
              FROM paper_techniques
             WHERE canonical_name IS NOT NULL OR name IS NOT NULL
            UNION ALL
            SELECT paper_id, 'category', COALESCE(canonical_name, name)
              FROM paper_categories
             WHERE canonical_name IS NOT NULL OR name IS NOT NULL
            -- PHASE2_TODO: add paper_datasets here
        """)
    )
    n_entities = r_entities.rowcount if r_entities.rowcount >= 0 else 0

    log.info(
        "rebuild_all: done — %d paper rows, %d entity rows", n_papers, n_entities
    )
    return n_papers, n_entities
