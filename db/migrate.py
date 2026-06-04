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
