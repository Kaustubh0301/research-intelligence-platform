"""
Knowledge graph build job.

Usage:
    python -m build_graph               # full rebuild (builder + analytics)
    python -m build_graph --stage build      # paper + entity edges only
    python -m build_graph --stage analytics  # recompute metrics only (requires edges)
    python -m build_graph --stats            # print current graph stats (no rebuild)

Output:
    Graph statistics, strongest paper pairs, strongest technique co-occurrences,
    cluster summaries.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("build_graph")

from sqlalchemy import select, func

from db.models import (
    EntityRelationship,
    Paper,
    PaperGraphMetric,
    PaperRelationship,
    TechniqueGraphMetric,
)
from db.session import get_session
from graph import builder, analytics


# ── Report helpers ─────────────────────────────────────────────────────────────

def _print_current_stats() -> None:
    with get_session() as s:
        n_papers     = s.execute(select(func.count()).select_from(Paper)).scalar()
        n_edges      = s.execute(select(func.count()).select_from(PaperRelationship)).scalar()
        n_ent_edges  = s.execute(select(func.count()).select_from(EntityRelationship)).scalar()
        n_clusters   = s.execute(
            select(func.count(PaperGraphMetric.cluster_id.distinct()))
        ).scalar()
        n_isolated   = s.execute(
            select(func.count()).select_from(PaperGraphMetric)
            .where(PaperGraphMetric.neighbors_count == 0)
        ).scalar()
        n_techniques = s.execute(select(func.count()).select_from(TechniqueGraphMetric)).scalar()

        avg_w = s.execute(
            select(func.avg(PaperRelationship.weight))
        ).scalar() or 0.0

        max_w = s.execute(
            select(func.max(PaperRelationship.weight))
        ).scalar() or 0.0

        print("\n=== Graph statistics ===")
        print(f"  Papers (nodes)          {n_papers}")
        print(f"  Paper edges             {n_edges}")
        print(f"  Entity co-occ. edges    {n_ent_edges}")
        print(f"  Clusters                {n_clusters}")
        print(f"  Isolated papers         {n_isolated}")
        print(f"  Tracked techniques      {n_techniques}")
        print(f"  Avg edge weight         {avg_w:.2f}")
        print(f"  Max edge weight         {max_w:.0f}")

        if n_edges == 0:
            print("\n  (Graph not yet built — run `python -m build_graph`)")
            return

        # Top-10 strongest paper pairs
        print("\n=== Top 10 strongest paper pairs ===")
        top_pairs = s.execute(
            select(
                PaperRelationship.source_paper_id,
                PaperRelationship.target_paper_id,
                PaperRelationship.weight,
                PaperRelationship.shared_techniques,
                PaperRelationship.shared_categories,
            )
            .order_by(PaperRelationship.weight.desc())
            .limit(10)
        ).all()

        paper_titles: dict[str, str] = {}
        for row in top_pairs:
            for pid in (row.source_paper_id, row.target_paper_id):
                if pid not in paper_titles:
                    p = s.get(Paper, pid)
                    paper_titles[pid] = (p.title[:50] + "…") if p else pid[:8]

        for row in top_pairs:
            techs = json.loads(row.shared_techniques or "[]")
            cats  = json.loads(row.shared_categories or "[]")
            print(f"\n  weight={row.weight:.0f}")
            print(f"    A: {paper_titles[row.source_paper_id]}")
            print(f"    B: {paper_titles[row.target_paper_id]}")
            if techs:
                print(f"    shared techniques: {', '.join(techs[:4])}" +
                      (f" + {len(techs)-4} more" if len(techs) > 4 else ""))
            if cats:
                print(f"    shared categories: {', '.join(cats)}")

        # Top-10 strongest technique co-occurrences
        print("\n=== Top 10 technique co-occurrences ===")
        top_tech = s.execute(
            select(
                EntityRelationship.source_entity,
                EntityRelationship.target_entity,
                EntityRelationship.co_occurrence_count,
            )
            .where(EntityRelationship.entity_type == "technique")
            .order_by(EntityRelationship.co_occurrence_count.desc())
            .limit(10)
        ).all()
        for row in top_tech:
            print(f"  {row.co_occurrence_count:3d}×  {row.source_entity}  ↔  {row.target_entity}")

        # Cluster summaries
        print("\n=== Cluster summaries (top 8 by size) ===")
        cluster_data = s.execute(
            select(
                PaperGraphMetric.cluster_id,
                func.count(PaperGraphMetric.paper_id).label("size"),
            )
            .group_by(PaperGraphMetric.cluster_id)
            .order_by(func.count(PaperGraphMetric.paper_id).desc())
            .limit(8)
        ).all()

        for cd in cluster_data:
            member_ids = s.scalars(
                select(PaperGraphMetric.paper_id)
                .where(PaperGraphMetric.cluster_id == cd.cluster_id)
                .order_by(PaperGraphMetric.betweenness_centrality.desc())
                .limit(5)
            ).all()
            titles = []
            for pid in member_ids:
                p = s.get(Paper, pid)
                if p:
                    titles.append(p.title[:45] + "…")
            print(f"\n  Cluster {cd.cluster_id}  ({cd.size} papers):")
            for t in titles[:3]:
                print(f"    • {t}")
            if cd.size > 3:
                print(f"    … and {cd.size - 3} more")

        # Top-10 techniques by usage
        print("\n=== Top 10 techniques by usage ===")
        top_usage = s.execute(
            select(TechniqueGraphMetric)
            .order_by(TechniqueGraphMetric.usage_count.desc())
            .limit(10)
        ).scalars().all()
        for tm in top_usage:
            cooccur = json.loads(tm.top_cooccurring or "[]")
            conames = [c["name"] for c in cooccur[:3]]
            co_str  = "  co-occ: " + ", ".join(conames) if conames else ""
            print(f"  {tm.usage_count:3d} papers  {tm.canonical_name}{co_str}")

        print()


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Build the research knowledge graph.")
    parser.add_argument(
        "--stage",
        choices=["build", "analytics", "all"],
        default="all",
        help="Which stage to run: build (edges), analytics (metrics), or all (default)",
    )
    parser.add_argument(
        "--stats",
        action="store_true",
        help="Print current graph stats and exit (no rebuild)",
    )
    args = parser.parse_args()

    if args.stats:
        _print_current_stats()
        return

    with get_session() as session:
        if args.stage in ("build", "all"):
            log.info("=== Stage 1: Building edges ===")
            build_stats = builder.build(session)
            print(f"\nEdge building complete:")
            print(f"  {build_stats.papers_loaded} papers loaded")
            print(f"  {build_stats.paper_pairs_evaluated} pairs evaluated")
            print(f"  {build_stats.paper_edges_created} paper edges created")
            print(f"  {build_stats.entity_edges_created} entity co-occ. edges created")
            print(f"     breakdown: {build_stats.entity_breakdown}")
            print(f"  {build_stats.isolated_papers} isolated papers (no edges)")
            print(f"  max edge weight: {build_stats.max_edge_weight:.0f}  avg: {build_stats.avg_edge_weight:.1f}")

        if args.stage in ("analytics", "all"):
            log.info("=== Stage 2: Computing analytics ===")
            a_stats = analytics.run(session)
            print(f"\nAnalytics complete:")
            print(f"  {a_stats.papers_in_graph} papers in graph")
            print(f"  {a_stats.total_edges} edges")
            print(f"  {a_stats.clusters_found} clusters detected")
            print(f"  {a_stats.largest_cluster_size} papers in largest cluster")
            print(f"  {a_stats.isolated_papers} isolated papers")
            print(f"  {a_stats.techniques_computed} technique metrics computed")

    # Always print stats at the end
    _print_current_stats()


if __name__ == "__main__":
    main()
