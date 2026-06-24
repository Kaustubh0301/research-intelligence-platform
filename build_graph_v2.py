"""
Graph V2 build + diagnostic report.

Steps:
  1. Capture v1 baseline stats from current graph tables.
  2. Apply migration 009 (add score columns) if not already applied.
  3. Rebuild graph using IDF-weighted techniques (graph/builder.py).
  4. Recompute analytics (graph/analytics.py).
  5. Write outputs/graph_v2_report.md comparing v1 vs v2.

Run:
  export DATABASE_URL=sqlite:///research_platform.db
  python build_graph_v2.py
"""

from __future__ import annotations

import json
import logging
import math
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("build_graph_v2")

if not os.environ.get("DATABASE_URL"):
    os.environ["DATABASE_URL"] = "sqlite:///research_platform.db"

from sqlalchemy import func, select, text

from db.models import (
    EntityRelationship,
    Paper,
    PaperGraphMetric,
    PaperRelationship,
    TechniqueGraphMetric,
)
from db.session import engine, get_session
from graph import analytics, builder


# ── Snapshot types ────────────────────────────────────────────────────────────

@dataclass
class GraphSnapshot:
    label:         str
    n_edges:       int   = 0
    avg_weight:    float = 0.0
    max_weight:    float = 0.0
    n_clusters:    int   = 0
    isolated:      int   = 0
    # weight distribution buckets: [0-1), [1-2), [2-4), [4-8), [8+)
    weight_buckets: dict[str, int] = field(default_factory=dict)
    # top 10 pairs: list of {title_a, title_b, weight, shared_techs}
    top_pairs:     list[dict] = field(default_factory=list)
    # top 10 by betweenness: list of {title, bc, cluster_id, neighbors}
    top_central:   list[dict] = field(default_factory=list)
    # cluster sizes: {cluster_id: size}
    clusters:      dict[int, int] = field(default_factory=dict)


# ── Snapshot capture ──────────────────────────────────────────────────────────

def _capture_snapshot(session, label: str) -> GraphSnapshot:
    snap = GraphSnapshot(label=label)

    # Basic stats
    snap.n_edges    = session.scalar(select(func.count()).select_from(PaperRelationship)) or 0
    snap.avg_weight = session.scalar(select(func.avg(PaperRelationship.weight))) or 0.0
    snap.max_weight = session.scalar(select(func.max(PaperRelationship.weight))) or 0.0
    snap.isolated   = session.scalar(
        select(func.count()).select_from(PaperGraphMetric)
        .where(PaperGraphMetric.neighbors_count == 0)
    ) or 0

    # Cluster count
    snap.n_clusters = session.scalar(
        select(func.count(PaperGraphMetric.cluster_id.distinct()))
    ) or 0

    # Weight distribution
    all_weights = [
        row[0] for row in session.execute(select(PaperRelationship.weight)).all()
    ]
    buckets = {"0–1": 0, "1–2": 0, "2–4": 0, "4–8": 0, "8+": 0}
    for w in all_weights:
        if w < 1:
            buckets["0–1"] += 1
        elif w < 2:
            buckets["1–2"] += 1
        elif w < 4:
            buckets["2–4"] += 1
        elif w < 8:
            buckets["4–8"] += 1
        else:
            buckets["8+"] += 1
    snap.weight_buckets = buckets

    # Top 10 pairs by weight
    pair_rows = session.execute(
        select(
            PaperRelationship.source_paper_id,
            PaperRelationship.target_paper_id,
            PaperRelationship.weight,
            PaperRelationship.shared_techniques,
            PaperRelationship.shared_categories,
            PaperRelationship.technique_score,
            PaperRelationship.dataset_score,
            PaperRelationship.category_score,
        )
        .order_by(PaperRelationship.weight.desc())
        .limit(10)
    ).all()

    titles: dict[str, str] = {}
    for row in pair_rows:
        for pid in (row.source_paper_id, row.target_paper_id):
            if pid not in titles:
                p = session.get(Paper, pid)
                titles[pid] = p.title if p else pid[:8]

    for row in pair_rows:
        techs = json.loads(row.shared_techniques or "[]")
        snap.top_pairs.append({
            "title_a":       titles[row.source_paper_id],
            "title_b":       titles[row.target_paper_id],
            "weight":        row.weight,
            "shared_techs":  techs,
            "shared_cats":   json.loads(row.shared_categories or "[]"),
            "technique_score": row.technique_score,
            "dataset_score":   row.dataset_score,
            "category_score":  row.category_score,
        })

    # Top 10 by betweenness centrality
    bc_rows = session.execute(
        select(
            PaperGraphMetric.paper_id,
            PaperGraphMetric.betweenness_centrality,
            PaperGraphMetric.cluster_id,
            PaperGraphMetric.neighbors_count,
            PaperGraphMetric.total_edge_weight,
        )
        .order_by(PaperGraphMetric.betweenness_centrality.desc())
        .limit(10)
    ).all()

    for row in bc_rows:
        p = session.get(Paper, row.paper_id)
        title = p.title if p else row.paper_id[:8]
        snap.top_central.append({
            "title":     title,
            "bc":        row.betweenness_centrality,
            "cluster_id": row.cluster_id,
            "neighbors": row.neighbors_count,
            "total_w":   row.total_edge_weight,
        })

    # Cluster sizes
    for cid, size in session.execute(
        select(PaperGraphMetric.cluster_id, func.count(PaperGraphMetric.paper_id))
        .group_by(PaperGraphMetric.cluster_id)
        .order_by(func.count(PaperGraphMetric.paper_id).desc())
    ).all():
        snap.clusters[cid] = size

    return snap


# ── Migration application ─────────────────────────────────────────────────────

def _apply_migration_009() -> None:
    """Add technique_score / dataset_score / category_score columns if missing."""
    with engine.connect() as conn:
        # Check whether columns already exist (SQLite PRAGMA)
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


# ── Markdown report ───────────────────────────────────────────────────────────

def _write_report(v1: GraphSnapshot, v2: GraphSnapshot, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    lines: list[str] = []

    def h(n: int, t: str) -> None:
        lines.append(f"{'#' * n} {t}\n")

    def row(*cells) -> str:
        return "| " + " | ".join(str(c) for c in cells) + " |"

    def sep(n: int) -> str:
        return "| " + " | ".join(["---"] * n) + " |"

    def delta(v1_val, v2_val, fmt=".2f", higher_is_better=True) -> str:
        if isinstance(v1_val, (int, float)) and isinstance(v2_val, (int, float)):
            d = v2_val - v1_val
            sign = "+" if d >= 0 else ""
            arrow = ""
            if d != 0:
                if (d > 0) == higher_is_better:
                    arrow = " ▲"
                else:
                    arrow = " ▼"
            return f"{sign}{d:{fmt}}{arrow}"
        return "—"

    h(1, "Graph V2 Report")
    lines.append("> IDF-weighted technique edges. Read-only comparison vs Graph V1.\n")

    # ── Summary comparison ──
    h(2, "Summary: V1 vs V2")
    lines.append(row("Metric", "V1", "V2", "Δ"))
    lines.append(sep(4))
    lines.append(row("Paper edges",          v1.n_edges,                v2.n_edges,
                      delta(v1.n_edges, v2.n_edges, "d")))
    lines.append(row("Average edge weight",  f"{v1.avg_weight:.3f}",    f"{v2.avg_weight:.3f}",
                      delta(v1.avg_weight, v2.avg_weight)))
    lines.append(row("Max edge weight",      f"{v1.max_weight:.1f}",    f"{v2.max_weight:.1f}",
                      delta(v1.max_weight, v2.max_weight, ".1f", higher_is_better=False)))
    lines.append(row("Clusters",             v1.n_clusters,             v2.n_clusters,
                      delta(v1.n_clusters, v2.n_clusters, "d")))
    lines.append(row("Isolated papers",      v1.isolated,               v2.isolated,
                      delta(v1.isolated, v2.isolated, "d", higher_is_better=False)))
    lines.append("")

    # ── Weight distribution ──
    h(2, "Edge Weight Distribution")
    all_buckets = ["0–1", "1–2", "2–4", "4–8", "8+"]
    lines.append(row("Weight Range", "V1 edges", "V2 edges", "Δ"))
    lines.append(sep(4))
    for b in all_buckets:
        v1c = v1.weight_buckets.get(b, 0)
        v2c = v2.weight_buckets.get(b, 0)
        d   = f"{v2c - v1c:+d}"
        lines.append(row(b, v1c, v2c, d))
    lines.append("")
    lines.append(
        "> IDF weighting redistributes technique edges downward for GENERIC entities "
        "(LLMs, Transformers) and upward for SPECIALIZED entities. "
        "Expect a shift from higher buckets toward mid-range.\n"
    )

    # ── Score breakdown (V2 only) ──
    h(2, "Score Component Breakdown (V2)")
    lines.append(
        "Technique, dataset, and category scores stored per edge. "
        "Methodology score not stored separately (included in final weight).\n"
    )
    lines.append(row("Score Component", "Sum across all edges", "Mean per edge"))
    lines.append(sep(3))
    # Compute from top_pairs as proxy — show note
    tech_sum = sum(p["technique_score"] or 0 for p in v2.top_pairs)
    ds_sum   = sum(p["dataset_score"]   or 0 for p in v2.top_pairs)
    cat_sum  = sum(p["category_score"]  or 0 for p in v2.top_pairs)
    n = len(v2.top_pairs) or 1
    lines.append(row("Technique (IDF-weighted)",
                      f"{tech_sum:.2f}", f"{tech_sum/n:.3f}"))
    lines.append(row("Dataset (flat ×2)",
                      f"{ds_sum:.2f}", f"{ds_sum/n:.3f}"))
    lines.append(row("Category (flat ×1)",
                      f"{cat_sum:.2f}", f"{cat_sum/n:.3f}"))
    lines.append("\n*Shown for top-10 edges only. Full breakdown available in DB.*\n")

    # ── Strongest paper pairs ──
    h(2, "Top 10 Strongest Paper Pairs (V2)")
    for i, p in enumerate(v2.top_pairs, 1):
        techs = ", ".join(p["shared_techs"][:4])
        if len(p["shared_techs"]) > 4:
            techs += f" +{len(p['shared_techs'])-4} more"
        cats = ", ".join(p["shared_cats"][:3])

        t_score = f"{p['technique_score']:.2f}" if p['technique_score'] is not None else "—"
        d_score = f"{p['dataset_score']:.2f}"   if p['dataset_score']   is not None else "—"
        c_score = f"{p['category_score']:.2f}"  if p['category_score']  is not None else "—"

        lines.append(f"**{i}. weight = {p['weight']:.2f}**  "
                     f"(technique={t_score} / dataset={d_score} / category={c_score})\n")
        lines.append(f"- A: {p['title_a']}\n")
        lines.append(f"- B: {p['title_b']}\n")
        if techs:
            lines.append(f"- Shared techniques: {techs}\n")
        if cats:
            lines.append(f"- Shared categories: {cats}\n")
        lines.append("")

    # ── V1 top pairs for comparison ──
    h(2, "Top 10 Strongest Paper Pairs (V1, for comparison)")
    for i, p in enumerate(v1.top_pairs, 1):
        techs = ", ".join(p["shared_techs"][:4])
        if len(p["shared_techs"]) > 4:
            techs += f" +{len(p['shared_techs'])-4} more"
        lines.append(f"**{i}. weight = {p['weight']:.2f}**\n")
        lines.append(f"- A: {p['title_a']}\n")
        lines.append(f"- B: {p['title_b']}\n")
        if techs:
            lines.append(f"- Shared: {techs}\n")
        lines.append("")

    # ── Centrality comparison ──
    h(2, "Top 10 Papers by Betweenness Centrality")
    lines.append(row("Rank", "Paper (truncated)", "V2 BC", "V2 Cluster", "V2 Neighbors"))
    lines.append(sep(5))
    for i, p in enumerate(v2.top_central, 1):
        lines.append(row(i, p["title"][:60], f"{p['bc']:.4f}", p["cluster_id"], p["neighbors"]))
    lines.append("")

    h(3, "V1 Centrality (for comparison)")
    lines.append(row("Rank", "Paper (truncated)", "V1 BC", "V1 Cluster", "V1 Neighbors"))
    lines.append(sep(5))
    for i, p in enumerate(v1.top_central, 1):
        lines.append(row(i, p["title"][:60], f"{p['bc']:.4f}", p["cluster_id"], p["neighbors"]))
    lines.append("")

    # ── Cluster comparison ──
    h(2, "Cluster Comparison")
    lines.append(row("Cluster ID", "V1 size", "V2 size"))
    lines.append(sep(3))
    all_cids = sorted(set(v1.clusters) | set(v2.clusters))
    for cid in all_cids[:15]:
        lines.append(row(cid, v1.clusters.get(cid, 0), v2.clusters.get(cid, 0)))
    if len(all_cids) > 15:
        lines.append(f"\n*{len(all_cids) - 15} more clusters not shown.*\n")
    lines.append("")

    # ── Interpretation ──
    h(2, "Interpretation")

    # Find papers that changed rank significantly
    v1_titles = [p["title"] for p in v1.top_central]
    v2_titles = [p["title"] for p in v2.top_central]

    new_entrants = [t for t in v2_titles if t not in v1_titles]
    dropped      = [t for t in v1_titles if t not in v2_titles]

    lines.append("**Centrality changes:**\n")
    if new_entrants:
        lines.append("Papers entering top-10 BC under V2 (not in V1 top-10):\n")
        for t in new_entrants:
            lines.append(f"- {t[:80]}\n")
    else:
        lines.append("- Top-10 by betweenness centrality is identical between V1 and V2.\n")

    if dropped:
        lines.append("\nPapers leaving top-10 BC under V2:\n")
        for t in dropped:
            lines.append(f"- {t[:80]}\n")
    lines.append("")

    lines.append("**Weight distribution shift:**\n")
    v1_high = v1.weight_buckets.get("4–8", 0) + v1.weight_buckets.get("8+", 0)
    v2_high = v2.weight_buckets.get("4–8", 0) + v2.weight_buckets.get("8+", 0)
    v1_low  = v1.weight_buckets.get("0–1", 0) + v1.weight_buckets.get("1–2", 0)
    v2_low  = v2.weight_buckets.get("0–1", 0) + v2.weight_buckets.get("1–2", 0)
    lines.append(
        f"- Edges with weight ≥ 4: {v1_high} → {v2_high} ({v2_high - v1_high:+d})\n"
        f"- Edges with weight < 2: {v1_low} → {v2_low} ({v2_low - v1_low:+d})\n"
        f"- Average weight: {v1.avg_weight:.3f} → {v2.avg_weight:.3f} "
        f"({v2.avg_weight - v1.avg_weight:+.3f})\n"
    )

    lines.append("\n**IDF formula applied:**\n")
    lines.append(
        "```\n"
        "idf(t) = ln(N / paper_count(t))\n"
        "GENERIC     idf < 3.00  →  base_weight × 0.25\n"
        "SHARED      idf < 3.69  →  base_weight × 1.00\n"
        "SPECIALIZED idf ≥ 3.69  →  base_weight × 2.00\n"
        "```\n"
    )

    path.write_text("\n".join(lines), encoding="utf-8")
    log.info("Report written: %s", path)


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    log.info("=== Graph V2 build ===")

    # Step 1: apply migration 009 first so score columns exist for all queries
    log.info("Step 1: applying migration 009 (score columns)")
    _apply_migration_009()

    # Step 2: capture v1 baseline (score columns will be NULL on old rows — expected)
    log.info("Step 2: capturing V1 baseline stats")
    with get_session() as session:
        v1 = _capture_snapshot(session, "V1")
    log.info(
        "V1 baseline: %d edges, avg_w=%.3f, max_w=%.1f, clusters=%d",
        v1.n_edges, v1.avg_weight, v1.max_weight, v1.n_clusters,
    )

    # Step 3: rebuild graph with IDF weighting
    log.info("Step 3: rebuilding graph (IDF-weighted)")
    with get_session() as session:
        build_stats = builder.build(session)
    log.info(
        "Build: %d pairs → %d edges (max_w=%.2f avg_w=%.2f isolated=%d)",
        build_stats.paper_pairs_evaluated, build_stats.paper_edges_created,
        build_stats.max_edge_weight, build_stats.avg_edge_weight, build_stats.isolated_papers,
    )

    # Step 4: recompute analytics
    log.info("Step 4: recomputing analytics")
    with get_session() as session:
        a_stats = analytics.run(session)
    log.info(
        "Analytics: %d papers, %d edges, %d clusters, %d techniques",
        a_stats.papers_in_graph, a_stats.total_edges, a_stats.clusters_found, a_stats.techniques_computed,
    )

    # Step 5: capture v2 snapshot
    log.info("Step 5: capturing V2 stats")
    with get_session() as session:
        v2 = _capture_snapshot(session, "V2")

    # Step 6: write report
    log.info("Step 6: writing report")
    _write_report(v1, v2, Path("outputs/graph_v2_report.md"))

    # Console summary
    print("\n" + "=" * 65)
    print("  GRAPH V2 BUILD COMPLETE")
    print("=" * 65)
    print(f"  {'Metric':<28} {'V1':>10}  {'V2':>10}  {'Δ':>8}")
    print("  " + "-" * 60)
    metrics = [
        ("Paper edges",        v1.n_edges,      v2.n_edges,      "d"),
        ("Avg edge weight",    v1.avg_weight,   v2.avg_weight,   ".3f"),
        ("Max edge weight",    v1.max_weight,   v2.max_weight,   ".2f"),
        ("Clusters",           v1.n_clusters,   v2.n_clusters,   "d"),
        ("Isolated papers",    v1.isolated,     v2.isolated,     "d"),
    ]
    for label, a, b, fmt in metrics:
        d = b - a
        sign = "+" if d >= 0 else ""
        print(f"  {label:<28} {a:>10{fmt}}  {b:>10{fmt}}  {sign}{d:{fmt}}")
    print()
    print("  Weight distribution:")
    for bucket in ["0–1", "1–2", "2–4", "4–8", "8+"]:
        v1c = v1.weight_buckets.get(bucket, 0)
        v2c = v2.weight_buckets.get(bucket, 0)
        bar = "█" * min(v2c // 50, 30)
        print(f"    {bucket:<6}  V1:{v1c:5d}  V2:{v2c:5d}  {bar}")
    print()
    print(f"  Report: outputs/graph_v2_report.md")
    print("=" * 65)


if __name__ == "__main__":
    main()
