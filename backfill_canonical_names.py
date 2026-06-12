"""
backfill_canonical_names.py
────────────────────────────
Populate canonical_name on paper_techniques rows where it is NULL,
using only exact or case-insensitive exact matching against canonical
names that already exist in the table.

NO AI matching.  NO fuzzy matching.  Safe to re-run (idempotent).

Usage
-----
  python backfill_canonical_names.py          # dry-run: show what would change
  python backfill_canonical_names.py --apply  # apply the backfill
  python backfill_canonical_names.py --rollback-sql  # print rollback SQL only
"""

from __future__ import annotations

import argparse
import sqlite3
from collections import defaultdict
from pathlib import Path

DB_PATH = Path(__file__).parent / "research_platform.db"
ROLLBACK_SQL_PATH = Path(__file__).parent / "rollback_canon_backfill.sql"


# ── helpers ───────────────────────────────────────────────────────────────────

def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def build_canonical_lookup(conn: sqlite3.Connection) -> dict[str, str]:
    """
    Return {lower(canonical_name): canonical_name} for every distinct
    canonical_name that is NOT NULL in paper_techniques.

    Where two canonical names differ only by case, the one with more
    paper assignments wins (most-used form is the anchor).
    """
    rows = conn.execute("""
        SELECT canonical_name, COUNT(DISTINCT paper_id) AS cnt
        FROM   paper_techniques
        WHERE  canonical_name IS NOT NULL
        GROUP  BY canonical_name
        ORDER  BY cnt DESC
    """).fetchall()

    lookup: dict[str, str] = {}
    for row in rows:
        key = row["canonical_name"].lower()
        if key not in lookup:          # first seen = most-used wins
            lookup[key] = row["canonical_name"]

    return lookup


def find_backfill_rows(
    conn: sqlite3.Connection,
    lookup: dict[str, str],
) -> list[dict]:
    """
    Return all rows where canonical_name IS NULL and whose raw `name`
    maps (exactly or case-insensitively) to a known canonical.

    Each entry: {rowid, paper_id, name, proposed_canonical, match_type}
    """
    null_rows = conn.execute("""
        SELECT rowid, paper_id, name
        FROM   paper_techniques
        WHERE  canonical_name IS NULL
    """).fetchall()

    results = []
    for row in null_rows:
        raw = row["name"]
        if raw is None:
            continue

        # 1. Exact match (raw name IS a canonical name as-is)
        if raw in {v for v in lookup.values()}:
            results.append({
                "rowid":              row["rowid"],
                "paper_id":           row["paper_id"],
                "name":               raw,
                "proposed_canonical": raw,
                "match_type":         "exact",
            })
        # 2. Case-insensitive match
        elif raw.lower() in lookup:
            results.append({
                "rowid":              row["rowid"],
                "paper_id":           row["paper_id"],
                "name":               raw,
                "proposed_canonical": lookup[raw.lower()],
                "match_type":         "case_insensitive",
            })
        # else: no match → leave NULL untouched

    return results


def build_rollback_sql(backfill_rows: list[dict]) -> str:
    lines = [
        "-- Rollback: restore canonical_name to NULL for every row touched by",
        "-- backfill_canonical_names.py --apply",
        "-- Generated automatically; apply with: sqlite3 research_platform.db < rollback_canon_backfill.sql",
        "BEGIN;",
    ]
    for r in backfill_rows:
        lines.append(
            f"UPDATE paper_techniques SET canonical_name = NULL "
            f"WHERE rowid = {r['rowid']};"
        )
    lines.append("COMMIT;")
    return "\n".join(lines)


# ── reporting ─────────────────────────────────────────────────────────────────

def print_before_counts(conn: sqlite3.Connection) -> None:
    total, = conn.execute("SELECT COUNT(*) FROM paper_techniques").fetchone()
    null,  = conn.execute(
        "SELECT COUNT(*) FROM paper_techniques WHERE canonical_name IS NULL"
    ).fetchone()
    print(f"\nBEFORE")
    print(f"  Total paper_techniques rows : {total}")
    print(f"  NULL canonical_name         : {null}")
    print(f"  Non-NULL canonical_name     : {total - null}")


def print_after_counts(conn: sqlite3.Connection) -> None:
    total, = conn.execute("SELECT COUNT(*) FROM paper_techniques").fetchone()
    null,  = conn.execute(
        "SELECT COUNT(*) FROM paper_techniques WHERE canonical_name IS NULL"
    ).fetchone()
    print(f"\nAFTER")
    print(f"  Total paper_techniques rows : {total}")
    print(f"  NULL canonical_name         : {null}")
    print(f"  Non-NULL canonical_name     : {total - null}")


def print_backfill_plan(backfill_rows: list[dict]) -> None:
    exact = [r for r in backfill_rows if r["match_type"] == "exact"]
    case  = [r for r in backfill_rows if r["match_type"] == "case_insensitive"]

    # Group by (name → proposed_canonical) for compact display
    by_mapping: dict[tuple[str, str], list[str]] = defaultdict(list)
    for r in backfill_rows:
        by_mapping[(r["name"], r["proposed_canonical"])].append(r["paper_id"])

    print(f"\nBACKFILL PLAN")
    print(f"  Rows to update : {len(backfill_rows)}")
    print(f"    exact match  : {len(exact)}")
    print(f"    case match   : {len(case)}")
    print(f"  Distinct mappings:")

    for (raw, canon), paper_ids in sorted(by_mapping.items()):
        tag = "exact" if raw == canon else "case "
        papers_str = f"{len(paper_ids)} paper(s)"
        print(f"    [{tag}]  '{raw}'  ->  '{canon}'  ({papers_str})")


# ── main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill canonical_name on paper_techniques.")
    parser.add_argument("--apply",        action="store_true", help="Apply the backfill (default: dry-run)")
    parser.add_argument("--rollback-sql", action="store_true", help="Print rollback SQL and exit")
    args = parser.parse_args()

    conn = connect()

    lookup       = build_canonical_lookup(conn)
    backfill_rows = find_backfill_rows(conn, lookup)

    if args.rollback_sql:
        print(build_rollback_sql(backfill_rows))
        return

    print_before_counts(conn)
    print_backfill_plan(backfill_rows)

    rollback_sql = build_rollback_sql(backfill_rows)
    ROLLBACK_SQL_PATH.write_text(rollback_sql)
    print(f"\nRollback SQL written to: {ROLLBACK_SQL_PATH.name}")

    if not args.apply:
        print("\nDRY RUN — no changes made.  Re-run with --apply to commit.")
        return

    # ── apply ────────────────────────────────────────────────────────────────
    print(f"\nApplying {len(backfill_rows)} updates...")
    try:
        conn.execute("BEGIN")
        for r in backfill_rows:
            conn.execute(
                "UPDATE paper_techniques SET canonical_name = ? WHERE rowid = ?",
                (r["proposed_canonical"], r["rowid"]),
            )
        conn.execute("COMMIT")
        print("Committed.")
    except Exception as exc:
        conn.execute("ROLLBACK")
        print(f"ERROR — rolled back: {exc}")
        raise

    print_after_counts(conn)
    print(
        f"\nDone.  To undo: sqlite3 {DB_PATH.name} < {ROLLBACK_SQL_PATH.name}"
    )

    # Rebuild FTS entities index after canonical_name backfill.
    # Uses a new SQLAlchemy session (this script uses raw sqlite3).
    try:
        import os
        if not os.environ.get("DATABASE_URL"):
            os.environ["DATABASE_URL"] = f"sqlite:///{DB_PATH}"
        from db.session import get_session
        from search.sync import rebuild_all
        with get_session() as session:
            n_p, n_e = rebuild_all(session)
        print(f"FTS rebuild: {n_p} paper rows, {n_e} entity rows indexed.")
    except Exception as exc:
        print(f"FTS rebuild failed (non-fatal): {exc}")


if __name__ == "__main__":
    main()
