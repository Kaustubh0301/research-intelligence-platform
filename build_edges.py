"""
Rebuild paper_relationships and entity_relationships from entity tables.

Run:
    export DATABASE_URL=sqlite:///research_platform.db
    python build_edges.py

This is Tier-1 of the graph pipeline (required after every ingestion batch).
Tier-2 analytics (NetworkX centrality + clustering) are in build_analytics.py
and are only needed when FEATURES.GRAPH is enabled in
apps/web/src/lib/features.ts.
"""

from __future__ import annotations

import logging
import os
import sys
import time
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("build_edges")

if not os.environ.get("DATABASE_URL"):
    os.environ["DATABASE_URL"] = "sqlite:///research_platform.db"

sys.path.insert(0, str(Path(__file__).resolve().parent))

from dotenv import load_dotenv
load_dotenv()

from sqlalchemy import text
from db.models import Base
from db.session import engine, get_session
from graph import builder


def _apply_migration_009() -> None:
    """Add technique_score / dataset_score / category_score to paper_relationships if missing."""
    with engine.connect() as conn:
        cols = {
            row[1]
            for row in conn.execute(text("PRAGMA table_info(paper_relationships)")).fetchall()
        }
        for col, defn in [
            ("technique_score", "REAL"),
            ("dataset_score",   "REAL"),
            ("category_score",  "REAL"),
        ]:
            if col not in cols:
                conn.execute(text(f"ALTER TABLE paper_relationships ADD COLUMN {col} {defn}"))
                log.info("Migration 009: added column %s to paper_relationships", col)
        conn.commit()


def main() -> None:
    start = time.perf_counter()
    log.info("=== build_edges: Tier-1 graph pipeline ===")

    Base.metadata.create_all(engine)
    log.info("Schema ready.")

    _apply_migration_009()

    with get_session() as session:
        stats = builder.build(session)

    elapsed = time.perf_counter() - start
    log.info("─" * 60)
    log.info("build_edges complete in %.1fs", elapsed)
    log.info("  Papers loaded        : %d", stats.papers_loaded)
    log.info("  Pairs evaluated      : %d", stats.paper_pairs_evaluated)
    log.info("  Edges created        : %d", stats.paper_edges_created)
    log.info("  Entity edges created : %d", stats.entity_edges_created)
    log.info("  Isolated papers      : %d", stats.isolated_papers)
    log.info("  Max edge weight      : %.2f", stats.max_edge_weight)
    log.info("  Avg edge weight      : %.2f", stats.avg_edge_weight)


if __name__ == "__main__":
    main()
