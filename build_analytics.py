"""
Compute graph analytics: centrality, clustering, technique metrics.

Reads paper_relationships (must be built first by build_edges.py).
Writes paper_graph_metrics and technique_graph_metrics.

Run:
    export DATABASE_URL=sqlite:///research_platform.db
    python build_analytics.py

This is Tier-2 of the graph pipeline (optional; only needed when
FEATURES.GRAPH is enabled in apps/web/src/lib/features.ts).
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
log = logging.getLogger("build_analytics")

if not os.environ.get("DATABASE_URL"):
    os.environ["DATABASE_URL"] = "sqlite:///research_platform.db"

sys.path.insert(0, str(Path(__file__).resolve().parent))

from dotenv import load_dotenv
load_dotenv()

from sqlalchemy import func, select
from db.models import Base, PaperRelationship
from db.session import engine, get_session
from graph import analytics


def main() -> None:
    start = time.perf_counter()
    log.info("=== build_analytics: Tier-2 graph pipeline ===")

    Base.metadata.create_all(engine)

    with get_session() as session:
        edge_count = session.scalar(select(func.count()).select_from(PaperRelationship)) or 0

    if edge_count == 0:
        log.error("paper_relationships is empty. Run build_edges.py first.")
        sys.exit(1)

    log.info("Found %d edges — running analytics.", edge_count)

    with get_session() as session:
        stats = analytics.run(session)

    elapsed = time.perf_counter() - start
    log.info("─" * 60)
    log.info("build_analytics complete in %.1fs", elapsed)
    log.info("  Papers in graph      : %d", stats.papers_in_graph)
    log.info("  Total edges          : %d", stats.total_edges)
    log.info("  Clusters found       : %d", stats.clusters_found)
    log.info("  Largest cluster      : %d", stats.largest_cluster_size)
    log.info("  Isolated papers      : %d", stats.isolated_papers)
    log.info("  Techniques computed  : %d", stats.techniques_computed)


if __name__ == "__main__":
    main()
