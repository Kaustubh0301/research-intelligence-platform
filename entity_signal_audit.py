"""
Entity signal audit — read-only.

For every canonical technique, calculates:
  - paper_count          : distinct papers that use it
  - pct_of_papers        : paper_count / total_papers * 100
  - graph_degree_contrib : number of paper-pair edges the technique
                           directly contributes to (i.e. it appears in
                           the shared_techniques JSON of that edge)

Groups techniques into three tiers:
  Core      : paper_count >= 5
  Shared    : paper_count >= 2
  Singleton : paper_count == 1

Outputs:
  outputs/entity_signal_audit.csv
  outputs/entity_signal_summary.md

Does NOT modify any database table or schema.

Run:
  export DATABASE_URL=sqlite:///research_platform.db
  python entity_signal_audit.py
"""

from __future__ import annotations

import csv
import json
import os
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path


# ── Tier thresholds ───────────────────────────────────────────────────────────

CORE_THRESHOLD     = 5
SHARED_THRESHOLD   = 2

# ── Data types ────────────────────────────────────────────────────────────────

@dataclass
class TechniqueSignal:
    canonical_name:       str
    paper_count:          int
    pct_of_papers:        float   # paper_count / total_papers * 100
    graph_degree_contrib: int     # paper-pair edges this technique appears in
    tier:                 str     # Core | Shared | Singleton


# ── Tier assignment ───────────────────────────────────────────────────────────

def _tier(paper_count: int) -> str:
    if paper_count >= CORE_THRESHOLD:
        return "Core"
    if paper_count >= SHARED_THRESHOLD:
        return "Shared"
    return "Singleton"


# ── Data loading ──────────────────────────────────────────────────────────────

def load_signals() -> tuple[list[TechniqueSignal], int]:
    """
    Returns (records, total_papers).

    paper_count and graph_degree_contrib are derived from:
      - paper_techniques (one row per paper × canonical technique)
      - paper_relationships.shared_techniques (JSON array per edge)

    technique_graph_metrics.usage_count is used as the source of truth for
    paper_count rather than re-counting paper_techniques rows, because the
    graph builder already de-duped canonical names when it built the metrics.
    """
    from sqlalchemy import text
    from db.session import engine

    with engine.connect() as conn:

        # Total paper count
        total_papers: int = conn.execute(
            text("SELECT COUNT(*) FROM papers")
        ).scalar_one()

        # paper_count per canonical from technique_graph_metrics
        usage_rows = conn.execute(
            text("SELECT canonical_name, usage_count FROM technique_graph_metrics")
        ).fetchall()
        usage_map: dict[str, int] = {r.canonical_name: r.usage_count for r in usage_rows}

        # For techniques not yet in technique_graph_metrics (shouldn't happen,
        # but defensive), fall back to counting paper_techniques directly.
        fallback_rows = conn.execute(
            text("""
                SELECT COALESCE(canonical_name, name) AS canon,
                       COUNT(DISTINCT paper_id)       AS cnt
                FROM   paper_techniques
                GROUP  BY canon
            """)
        ).fetchall()
        for r in fallback_rows:
            if r.canon not in usage_map:
                usage_map[r.canon] = r.cnt

        # Graph degree contribution:
        # For each paper-pair edge, parse shared_techniques JSON and credit
        # each technique with +1 for that edge.
        degree_contrib: dict[str, int] = defaultdict(int)

        edge_rows = conn.execute(
            text("SELECT shared_techniques FROM paper_relationships")
        ).fetchall()

        for row in edge_rows:
            raw = row[0]
            if not raw:
                continue
            try:
                names = json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                continue
            for name in names:
                if isinstance(name, str) and name:
                    degree_contrib[name] += 1

    # Build records
    all_canonicals = set(usage_map.keys()) | set(degree_contrib.keys())
    records: list[TechniqueSignal] = []

    for canon in all_canonicals:
        paper_count = usage_map.get(canon, 0)
        records.append(TechniqueSignal(
            canonical_name       = canon,
            paper_count          = paper_count,
            pct_of_papers        = round(100.0 * paper_count / total_papers, 1)
                                   if total_papers else 0.0,
            graph_degree_contrib = degree_contrib.get(canon, 0),
            tier                 = _tier(paper_count),
        ))

    records.sort(key=lambda r: (-r.paper_count, -r.graph_degree_contrib, r.canonical_name))
    return records, total_papers


# ── CSV output ────────────────────────────────────────────────────────────────

CSV_FIELDS = [
    "canonical_name",
    "tier",
    "paper_count",
    "pct_of_papers",
    "graph_degree_contrib",
]


def write_csv(records: list[TechniqueSignal], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for r in records:
            writer.writerow({
                "canonical_name":       r.canonical_name,
                "tier":                 r.tier,
                "paper_count":          r.paper_count,
                "pct_of_papers":        f"{r.pct_of_papers:.1f}",
                "graph_degree_contrib": r.graph_degree_contrib,
            })
    print(f"  Wrote {path}")


# ── Markdown output ───────────────────────────────────────────────────────────

def write_markdown(
    records: list[TechniqueSignal],
    total_papers: int,
    path: Path,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    core      = [r for r in records if r.tier == "Core"]
    shared    = [r for r in records if r.tier == "Shared"]
    singletons = [r for r in records if r.tier == "Singleton"]

    total_edges_touched = sum(r.graph_degree_contrib for r in records)

    def row(*cells) -> str:
        return "| " + " | ".join(str(c) for c in cells) + " |"

    def sep(n: int) -> str:
        return "| " + " | ".join(["---"] * n) + " |"

    lines: list[str] = []

    lines.append("# Entity Signal Audit — `paper_techniques`\n")
    lines.append("> Read-only. No schema changes.\n")

    # ── Tier summary ──
    lines.append("## Tier Summary\n")
    lines.append(row("Tier", "Threshold", "Count", "% of total techniques",
                      "Total graph_degree_contrib"))
    lines.append(sep(5))
    for tier, group, thresh in [
        ("Core",      core,       f"paper_count ≥ {CORE_THRESHOLD}"),
        ("Shared",    shared,     f"paper_count ≥ {SHARED_THRESHOLD}"),
        ("Singleton", singletons, "paper_count = 1"),
    ]:
        pct  = f"{100 * len(group) / len(records):.1f}%" if records else "0%"
        gdc  = sum(r.graph_degree_contrib for r in group)
        lines.append(row(tier, thresh, len(group), pct, gdc))
    lines.append("")

    # ── Graph coverage note ──
    lines.append("## Graph Degree Contribution\n")
    lines.append(
        f"Of the {total_edges_touched} technique-attributed graph contributions "
        f"across all {len([r for r in records if r.graph_degree_contrib > 0])} "
        f"techniques that appear in any edge:\n"
    )
    core_gdc      = sum(r.graph_degree_contrib for r in core)
    shared_gdc    = sum(r.graph_degree_contrib for r in shared)
    singleton_gdc = sum(r.graph_degree_contrib for r in singletons)

    if total_edges_touched:
        lines.append(
            f"- **Core** techniques account for "
            f"**{100 * core_gdc / total_edges_touched:.1f}%** of edge contributions\n"
            f"- **Shared** techniques: "
            f"**{100 * shared_gdc / total_edges_touched:.1f}%**\n"
            f"- **Singleton** techniques: "
            f"**{100 * singleton_gdc / total_edges_touched:.1f}%**\n"
        )
    lines.append("")

    # ── Core tier ──
    lines.append(f"## Core Techniques ({len(core)} — paper_count ≥ {CORE_THRESHOLD})\n")
    lines.append(
        "High-signal entities: appear in many papers and drive most cross-paper edges. "
        "These are the candidates for IDF down-weighting in graph v2.\n"
    )
    lines.append(row("Canonical Name", "Papers", "% Papers", "Graph Degree Contrib"))
    lines.append(sep(4))
    for r in core:
        lines.append(row(r.canonical_name, r.paper_count,
                          f"{r.pct_of_papers:.1f}%", r.graph_degree_contrib))
    lines.append("")

    # ── Shared tier ──
    lines.append(f"## Shared Techniques ({len(shared)} — paper_count ≥ {SHARED_THRESHOLD})\n")
    lines.append(
        "Medium-signal entities: appear in at least 2 papers. "
        "Useful for cross-paper edges but less dominant than Core. "
        "These should retain current graph weight; IDF will naturally boost them "
        "relative to Core.\n"
    )
    lines.append(row("Canonical Name", "Papers", "% Papers", "Graph Degree Contrib"))
    lines.append(sep(4))
    for r in shared:
        lines.append(row(r.canonical_name, r.paper_count,
                          f"{r.pct_of_papers:.1f}%", r.graph_degree_contrib))
    lines.append("")

    # ── Singleton tier ──
    lines.append(f"## Singleton Techniques ({len(singletons)} — paper_count = 1)\n")
    lines.append(
        "Low-signal entities for the graph: they appear in only one paper so they "
        "can never create a cross-paper edge. Their current graph_degree_contrib "
        "is 0 for almost all. Decision needed: keep for search/display, or prune "
        "from graph weighting.\n"
    )
    # Show only the ones with a non-zero graph_degree_contrib (edge case: a
    # singleton canonical that still appears in shared_techniques JSON due to
    # an earlier normalization run mismatch), then the rest as a count.
    contributing_singletons = [r for r in singletons if r.graph_degree_contrib > 0]
    zero_singletons         = [r for r in singletons if r.graph_degree_contrib == 0]

    if contributing_singletons:
        lines.append(
            f"**{len(contributing_singletons)} singletons unexpectedly contribute "
            f"to graph edges** (normalization mismatch — the canonical stored in "
            f"`paper_relationships.shared_techniques` differs from the current "
            f"`canonical_name` in `paper_techniques`):\n"
        )
        lines.append(row("Canonical Name", "Papers", "Graph Degree Contrib"))
        lines.append(sep(3))
        for r in contributing_singletons:
            lines.append(row(r.canonical_name, r.paper_count, r.graph_degree_contrib))
        lines.append("")

    lines.append(
        f"Remaining **{len(zero_singletons)} singletons** have graph_degree_contrib = 0. "
        f"Not listed individually (see CSV).\n"
    )

    # ── Key observations ──
    lines.append("## Key Observations\n")

    # Which technique contributes the most edges?
    top_by_gdc = sorted(records, key=lambda r: -r.graph_degree_contrib)[:5]
    lines.append(
        "**Top 5 techniques by graph degree contribution** "
        "(these single-handedly connect the most paper pairs):\n"
    )
    lines.append(row("Canonical Name", "Tier", "Papers", "Graph Degree Contrib"))
    lines.append(sep(4))
    for r in top_by_gdc:
        lines.append(row(r.canonical_name, r.tier, r.paper_count, r.graph_degree_contrib))
    lines.append("")

    singleton_pct = 100 * len(singletons) / len(records) if records else 0
    lines.append(
        f"- **{len(singletons)} singletons ({singleton_pct:.0f}%)** — "
        f"these cannot contribute to cross-paper edges at current corpus size. "
        f"With a larger corpus, some will graduate to Shared or Core.\n"
        f"- **{len(core)} Core entities** drive the majority of graph connectivity. "
        f"IDF weighting will down-weight these, giving Shared entities more relative influence.\n"
        f"- **{len(contributing_singletons)} singletons appear in graph edges** — "
        f"indicates the graph was built before the latest normalization pass ran; "
        f"rebuild graph to fix.\n"
    )

    path.write_text("\n".join(lines), encoding="utf-8")
    print(f"  Wrote {path}")


# ── Console summary ───────────────────────────────────────────────────────────

def print_console_summary(
    records: list[TechniqueSignal],
    total_papers: int,
) -> None:
    core      = [r for r in records if r.tier == "Core"]
    shared    = [r for r in records if r.tier == "Shared"]
    singletons = [r for r in records if r.tier == "Singleton"]

    print("\n" + "=" * 65)
    print("  ENTITY SIGNAL AUDIT")
    print("=" * 65)
    print(f"  Total papers            : {total_papers}")
    print(f"  Total canonical techs   : {len(records)}")
    print()
    print(f"  {'Tier':<12} {'Count':>6}  {'% techs':>8}  {'Total GDC':>10}")
    print("  " + "-" * 45)
    for tier, group in [("Core", core), ("Shared", shared), ("Singleton", singletons)]:
        pct = f"{100 * len(group) / len(records):.1f}%" if records else "0%"
        gdc = sum(r.graph_degree_contrib for r in group)
        print(f"  {tier:<12} {len(group):>6}  {pct:>8}  {gdc:>10}")
    print()

    print("  Core techniques (paper_count >= 5):")
    print(f"  {'Canonical Name':<45} {'Papers':>6}  {'GDC':>5}")
    print("  " + "-" * 62)
    for r in core:
        print(f"  {r.canonical_name:<45} {r.paper_count:>6}  {r.graph_degree_contrib:>5}")
    print()

    print("  Shared techniques (paper_count 2-4):")
    print(f"  {'Canonical Name':<45} {'Papers':>6}  {'GDC':>5}")
    print("  " + "-" * 62)
    for r in shared:
        print(f"  {r.canonical_name:<45} {r.paper_count:>6}  {r.graph_degree_contrib:>5}")
    print()

    top5 = sorted(records, key=lambda r: -r.graph_degree_contrib)[:5]
    print("  Top 5 by graph degree contribution:")
    print(f"  {'Canonical Name':<45} {'Tier':<10} {'Papers':>6}  {'GDC':>5}")
    print("  " + "-" * 70)
    for r in top5:
        print(f"  {r.canonical_name:<45} {r.tier:<10} {r.paper_count:>6}  {r.graph_degree_contrib:>5}")
    print("=" * 65)


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    if not os.environ.get("DATABASE_URL"):
        os.environ["DATABASE_URL"] = "sqlite:///research_platform.db"

    print("Loading technique signals from database…")
    records, total_papers = load_signals()
    print(f"  Loaded {len(records)} canonical techniques across {total_papers} papers")

    print("Writing outputs…")
    write_csv(records, Path("outputs/entity_signal_audit.csv"))
    write_markdown(records, total_papers, Path("outputs/entity_signal_summary.md"))

    print_console_summary(records, total_papers)


if __name__ == "__main__":
    main()
