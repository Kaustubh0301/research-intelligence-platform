"""
Lightweight schema migration helper for SQLite development.

create_all() creates missing *tables* but never adds columns to existing ones.
This module runs safe ADD COLUMN statements that are no-ops if the column exists.
Called automatically by the pipeline before it queries.
"""

from __future__ import annotations

import logging
from sqlalchemy import inspect, text
from db.session import engine
from db.models  import Base

log = logging.getLogger(__name__)


_FTS_DDL = [
    "CREATE VIRTUAL TABLE IF NOT EXISTS papers_fts USING fts5(paper_id, title, abstract, tokenize = 'porter unicode61')",
    "CREATE VIRTUAL TABLE IF NOT EXISTS entities_fts USING fts5(paper_id, entity_type, name, tokenize = 'unicode61')",
]


def _create_fts_tables_if_missing() -> None:
    """Create FTS5 virtual tables if absent.  No-op if already present."""
    from search.fts import tables_exist
    from sqlalchemy.orm import Session
    with Session(bind=engine) as session:
        if tables_exist(session):
            return

    with engine.begin() as conn:
        for stmt in _FTS_DDL:
            conn.execute(text(stmt))
    log.info("Created FTS5 virtual tables (migration 010).  Run rebuild_fts.py to populate.")


def _column_exists(table: str, column: str) -> bool:
    insp = inspect(engine)
    return any(c["name"] == column for c in insp.get_columns(table))


def _add_column_if_missing(table: str, column: str, col_type: str) -> None:
    if not _column_exists(table, column):
        with engine.begin() as conn:
            conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}"))
        log.info("Added column %s.%s", table, column)


def run_migrations() -> None:
    """Create all tables, then add any new columns that don't exist yet."""
    Base.metadata.create_all(engine)

    # New columns added to papers in migration 003
    _add_column_if_missing("papers", "pdf_local_path",   "TEXT")
    _add_column_if_missing("papers", "pdf_word_count",   "INTEGER")
    _add_column_if_missing("papers", "pdf_extracted_at", "TIMESTAMP")

    # Analysis V2 columns added 2026-06-08
    _add_column_if_missing("paper_analyses", "methodology",                "TEXT")
    _add_column_if_missing("paper_analyses", "experimental_findings",      "TEXT")
    _add_column_if_missing("paper_analyses", "strengths",                  "TEXT")
    _add_column_if_missing("paper_analyses", "practical_applications",     "TEXT")
    _add_column_if_missing("paper_analyses", "future_research_directions", "TEXT")

    # Migration 010: FTS5 virtual tables (2026-06-11)
    # Only creates the tables — backfill is NOT automatic.
    # Run:  python rebuild_fts.py   after applying this migration.
    _create_fts_tables_if_missing()
