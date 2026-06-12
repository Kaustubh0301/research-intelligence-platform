"""
One-time migration: populate canonical_name on paper_technique rows where it is
NULL but LOWER(name) matches an existing canonical_name in the same table.

Safe to re-run (no-ops if already applied).

Usage:
    python migrate_canonicalize_techniques.py
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("migrate")

if not os.environ.get("DATABASE_URL"):
    os.environ["DATABASE_URL"] = "sqlite:///research_platform.db"

sys.path.insert(0, str(Path(__file__).resolve().parent))

from dotenv import load_dotenv
load_dotenv()

from sqlalchemy import text
from db.session import engine


def main() -> None:
    with engine.begin() as conn:
        # Build lower → canonical mapping from all rows that already have a canonical_name.
        canon_rows = conn.execute(text(
            "SELECT DISTINCT canonical_name FROM paper_techniques WHERE canonical_name IS NOT NULL"
        )).fetchall()

        canonical_map: dict[str, str] = {r[0].lower(): r[0] for r in canon_rows}
        log.info("Known canonicals: %d", len(canonical_map))

        # Fetch all NULL-canonical rows
        null_rows = conn.execute(text(
            "SELECT rowid, name FROM paper_techniques WHERE canonical_name IS NULL AND name IS NOT NULL"
        )).fetchall()
        log.info("Rows with NULL canonical_name: %d", len(null_rows))

        updated = 0
        for rowid, name in null_rows:
            canon = canonical_map.get(name.lower())
            if canon is not None:
                conn.execute(text(
                    "UPDATE paper_techniques SET canonical_name = :canon WHERE rowid = :rid"
                ), {"canon": canon, "rid": rowid})
                updated += 1

        log.info("Rows updated: %d", updated)

    log.info("Migration complete.")


if __name__ == "__main__":
    main()
