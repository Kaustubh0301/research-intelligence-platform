#!/usr/bin/env python3
"""
rebuild_fts.py — Populate / rebuild FTS5 search indexes.

Usage:
    python rebuild_fts.py              # full rebuild
    python rebuild_fts.py --check      # health check only, no writes
    python rebuild_fts.py --dry-run    # print row counts, no writes

Prerequisites:
    1. SQLite must be compiled with FTS5 support (verified below).
    2. Migration 010 must have been applied (tables created by db/migrate.py).
    3. Source tables must be populated.

After a full corpus expansion, run this script once.  Incremental sync
during ingestion is handled automatically by sync_papers() / sync_entities().
"""

from __future__ import annotations

import argparse
import sys
import time

from sqlalchemy import text
from sqlalchemy.orm import Session

from db.session import engine
from search.fts import tables_exist, tables_healthy
from search.sync import rebuild_all


# ── FTS5 capability check ──────────────────────────────────────────────────────

def _check_fts5_available() -> None:
    """Fail fast with a clear message if SQLite was built without FTS5."""
    with engine.connect() as conn:
        rows = conn.execute(text("PRAGMA compile_options")).fetchall()
    options = {r[0] for r in rows}
    if "ENABLE_FTS5" not in options:
        print(
            "ERROR: This SQLite installation was not compiled with FTS5 support.\n"
            "       PRAGMA compile_options does not include ENABLE_FTS5.\n\n"
            "       On macOS you can install a FTS5-enabled SQLite via Homebrew:\n"
            "           brew install sqlite\n"
            "       then reinstall pysqlite3-binary or rebuild Python against it.\n"
            "\n"
            "       Available options:\n"
            + "       " + ", ".join(sorted(options)),
            file=sys.stderr,
        )
        sys.exit(1)
    print(f"SQLite FTS5 available  (compile options: {len(options)} flags)")


# ── Row count helpers ─────────────────────────────────────────────────────────

def _count(session: Session, table: str, column: str = "*") -> int:
    try:
        return session.execute(
            text(f"SELECT COUNT({column}) FROM {table}")
        ).scalar() or 0
    except Exception:
        return -1


def _print_counts(session: Session) -> None:
    n_papers          = _count(session, "papers", "id")
    n_fts_papers      = _count(session, "papers_fts", "paper_id")
    n_techniques      = _count(session, "paper_techniques")
    n_categories      = _count(session, "paper_categories")
    n_fts_entities    = _count(session, "entities_fts", "paper_id")

    print(f"  papers source rows     : {n_papers}")
    print(f"  papers_fts rows        : {n_fts_papers}")
    print(f"  technique + category   : {n_techniques + n_categories}")
    print(f"  entities_fts rows      : {n_fts_entities}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Rebuild FTS5 search indexes.")
    parser.add_argument("--check",   action="store_true", help="Health check only, no writes.")
    parser.add_argument("--dry-run", action="store_true", help="Print row counts, no writes.")
    args = parser.parse_args()

    _check_fts5_available()

    with Session(bind=engine) as session:
        if not tables_exist(session):
            print(
                "ERROR: FTS5 tables do not exist yet.\n"
                "       Run db/migrate.py (or start the API once) to create them.",
                file=sys.stderr,
            )
            sys.exit(1)

        if args.check:
            ok, msg = tables_healthy(session)
            status = "OK" if ok else "UNHEALTHY"
            print(f"FTS health: {status} — {msg}")
            sys.exit(0 if ok else 2)

        if args.dry_run:
            print("Dry run — current index counts:")
            _print_counts(session)
            sys.exit(0)

        # Full rebuild
        print("Starting full FTS rebuild …")
        print("Before:")
        _print_counts(session)

        t0 = time.perf_counter()
        n_papers, n_entities = rebuild_all(session)
        session.commit()
        elapsed = time.perf_counter() - t0

        print(f"\nRebuild complete in {elapsed:.2f}s")
        print(f"  papers_fts rows  : {n_papers}")
        print(f"  entities_fts rows: {n_entities}")
        print("\nAfter:")
        _print_counts(session)

        ok, msg = tables_healthy(session)
        print(f"\nHealth check: {'OK' if ok else 'FAIL'} — {msg}")
        if not ok:
            sys.exit(2)


if __name__ == "__main__":
    main()
