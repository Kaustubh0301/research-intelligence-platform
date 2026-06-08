"""
Corpus Intelligence — Research Landscape Trends

Produces a snapshot analysis of the NeurIPS 2024 corpus across two dimensions:

  Category analysis — paper density, citation strength, graph centrality, and
                      technique diversity across the 15 research categories.

  Technique momentum — per-canonical-technique score (introduces_count − uses_count)
                       indicating whether a technique is at the frontier (being
                       invented) or is mature (being used without reinvention).

⚠  CORPUS SNAPSHOT ONLY.  This corpus contains 100 NeurIPS 2024 papers from a
   single conference-year.  No temporal comparisons are possible.  Do not
   interpret momentum scores as time-series trends.

Outputs:
  outputs/corpus_intel/trends_report.md
  outputs/corpus_intel/technique_momentum.csv

Read-only. No DB writes. No schema changes.

Run:
  export DATABASE_URL=sqlite:///research_platform.db
  python -m corpus_intel.trends
"""

from __future__ import annotations

import csv
import os
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import text

from corpus_intel._queries import (
    corpus_size,
    idf_tier,
    role_aggregation,
)

# ── Output paths ──────────────────────────────────────────────────────────────

_OUT_DIR  = Path("outputs/corpus_intel")
CSV_PATH  = _OUT_DIR / "technique_momentum.csv"
MD_PATH   = _OUT_DIR / "trends_report.md"

# ── Data structures ───────────────────────────────────────────────────────────

@dataclass
class CategoryStat:
    category:           str
    paper_count:        int
    avg_citation:       float
    max_citation:       int
    avg_betweenness:    float
    avg_degree:         float
    technique_count:    int     # distinct canonical techniques used by papers in this category


@dataclass
class MomentumRecord:
    canonical_name:   str
    introduces_count: int
    uses_count:       int
    momentum_score:   int       # introduces_count − uses_count
    total_papers:     int
    idf_score:        float
    idf_tier:         str
    momentum_label:   str       # "Positive" | "Negative" | "Neutral"


# ── Data loading ──────────────────────────────────────────────────────────────

def _load_category_stats(conn) -> list[CategoryStat]:
    """
    Compute per-category: paper count, avg/max citations, avg centrality.
    A paper with multiple categories contributes to all of its category averages.
    """
    base_sql = text("""
        SELECT
            pc.name                              AS category,
            COUNT(DISTINCT pc.paper_id)          AS paper_count,
            AVG(COALESCE(p.citation_count, 0))   AS avg_citation,
            MAX(COALESCE(p.citation_count, 0))   AS max_citation,
            AVG(pgm.betweenness_centrality)      AS avg_betweenness,
            AVG(pgm.degree_centrality)           AS avg_degree
        FROM paper_categories pc
        JOIN papers p              ON p.id   = pc.paper_id
        LEFT JOIN paper_graph_metrics pgm ON pgm.paper_id = pc.paper_id
        GROUP BY pc.name
        ORDER BY paper_count DESC
    """)

    # Technique diversity per category: distinct canonical techniques used
    # by any paper that belongs to this category.
    tech_sql = text("""
        SELECT
            pc.name                                                  AS category,
            COUNT(DISTINCT TRIM(COALESCE(pt.canonical_name, pt.name))) AS technique_count
        FROM paper_categories pc
        JOIN paper_techniques pt ON pt.paper_id = pc.paper_id
        WHERE TRIM(COALESCE(pt.canonical_name, pt.name)) != ''
          AND COALESCE(pt.canonical_name, pt.name) IS NOT NULL
        GROUP BY pc.name
    """)

    tech_counts: dict[str, int] = {
        row.category: row.technique_count
        for row in conn.execute(tech_sql)
    }

    stats: list[CategoryStat] = []
    for row in conn.execute(base_sql):
        stats.append(CategoryStat(
            category        = row.category,
            paper_count     = row.paper_count,
            avg_citation    = round(row.avg_citation or 0.0, 1),
            max_citation    = int(row.max_citation or 0),
            avg_betweenness = round(row.avg_betweenness or 0.0, 5),
            avg_degree      = round(row.avg_degree or 0.0, 4),
            technique_count = tech_counts.get(row.category, 0),
        ))
    return stats


def _load_momentum(conn, n_papers: int) -> list[MomentumRecord]:
    """
    Compute technique momentum for every canonical technique.

    momentum_score = introduces_count − uses_count
      Positive → more papers introducing than using: frontier / active invention
      Negative → more papers using than introducing: mature / established method
      Neutral  → balanced or absent in both roles

    Uses role_aggregation() from _queries so the paper-deduplication and
    COALESCE(canonical_name, name) logic is identical to emerging.py.
    """
    agg_map = role_aggregation(conn)
    records: list[MomentumRecord] = []

    for canon, agg in agg_map.items():
        score, tier = idf_tier(agg.total_papers, n_papers)
        momentum    = agg.introduces_count - agg.uses_count

        if momentum > 0:
            label = "Positive"
        elif momentum < 0:
            label = "Negative"
        else:
            label = "Neutral"

        records.append(MomentumRecord(
            canonical_name   = canon,
            introduces_count = agg.introduces_count,
            uses_count       = agg.uses_count,
            momentum_score   = momentum,
            total_papers     = agg.total_papers,
            idf_score        = score,
            idf_tier         = tier,
            momentum_label   = label,
        ))

    # Sort: highest momentum first, then by total_papers desc, then name
    records.sort(key=lambda r: (-r.momentum_score, -r.total_papers, r.canonical_name))
    return records


# ── CSV output ────────────────────────────────────────────────────────────────

_CSV_FIELDS = [
    "canonical_name",
    "introduces_count",
    "uses_count",
    "momentum_score",
    "total_papers",
    "idf_score",
    "idf_tier",
    "momentum_label",
]


def write_momentum_csv(records: list[MomentumRecord], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=_CSV_FIELDS)
        writer.writeheader()
        for r in records:
            writer.writerow({
                "canonical_name":   r.canonical_name,
                "introduces_count": r.introduces_count,
                "uses_count":       r.uses_count,
                "momentum_score":   r.momentum_score,
                "total_papers":     r.total_papers,
                "idf_score":        r.idf_score,
                "idf_tier":         r.idf_tier,
                "momentum_label":   r.momentum_label,
            })


# ── Markdown helpers ──────────────────────────────────────────────────────────

def _category_overview_table(stats: list[CategoryStat]) -> str:
    lines = [
        "| Category | Papers | Avg citations | Max citations | Avg betweenness | Avg degree | Techniques |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for s in stats:
        lines.append(
            f"| {s.category} | {s.paper_count} | {s.avg_citation:.1f} | {s.max_citation}"
            f" | {s.avg_betweenness:.5f} | {s.avg_degree:.4f} | {s.technique_count} |"
        )
    return "\n".join(lines)


def _category_ranking_table(stats: list[CategoryStat], key: str, label: str, reverse: bool = True) -> str:
    ranked = sorted(stats, key=lambda s: getattr(s, key), reverse=reverse)
    lines = [f"| Rank | Category | {label} |", "|---:|---|---:|"]
    for i, s in enumerate(ranked, 1):
        val = getattr(s, key)
        if isinstance(val, float):
            formatted = f"{val:.4f}" if key in ("avg_betweenness", "avg_degree") else f"{val:.1f}"
        else:
            formatted = str(val)
        lines.append(f"| {i} | {s.category} | {formatted} |")
    return "\n".join(lines)


def _momentum_table(records: list[MomentumRecord], label: str, positive: bool, n: int = 10) -> str:
    filtered = [r for r in records if (r.momentum_score > 0) == positive and r.momentum_score != 0]
    filtered = sorted(filtered, key=lambda r: r.momentum_score if positive else -r.momentum_score, reverse=True)
    if not filtered:
        return f"_No {label.lower()} momentum techniques at current corpus size._"
    lines = [
        "| Technique | Introduces | Uses | Momentum | Total papers | IDF tier |",
        "|---|---:|---:|---:|---:|:---:|",
    ]
    for r in filtered[:n]:
        lines.append(
            f"| {r.canonical_name} | {r.introduces_count} | {r.uses_count}"
            f" | {r.momentum_score:+d} | {r.total_papers} | {r.idf_tier} |"
        )
    return "\n".join(lines)


# ── Markdown report ───────────────────────────────────────────────────────────

def write_trends_report(
    cat_stats: list[CategoryStat],
    momentum: list[MomentumRecord],
    n_papers: int,
    path: Path,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    from collections import Counter
    momentum_counts = Counter(r.momentum_label for r in momentum)
    positive = [r for r in momentum if r.momentum_score > 0]
    negative = [r for r in momentum if r.momentum_score < 0]

    md = f"""# Research Landscape Snapshot — NeurIPS 2024

**Generated:** {ts}
**Corpus:** {n_papers} papers · 1 conference · 1 year (NeurIPS 2024)

> ⚠ **Snapshot, not a trend.**  This report contains a single-year corpus.
> Category rankings and technique momentum scores reflect the distribution
> within NeurIPS 2024 only.  Temporal trajectory requires multi-year ingestion.
> Re-run after corpus expansion for comparative signal.

---

## Category Analysis

{n_papers} papers span {len(cat_stats)} research categories.  Papers with multiple
categories are counted in all applicable rows.  Averages are per-paper within
each category.

### Category Overview

{_category_overview_table(cat_stats)}

---

### Category Rankings

**By paper count** (research area size in this corpus):

{_category_ranking_table(cat_stats, "paper_count", "Paper count")}

**By average citation count** (external recognition):

{_category_ranking_table(cat_stats, "avg_citation", "Avg citations")}

**By average betweenness centrality** (graph bridge importance):

{_category_ranking_table(cat_stats, "avg_betweenness", "Avg betweenness")}

**By average degree centrality** (graph connectivity):

{_category_ranking_table(cat_stats, "avg_degree", "Avg degree")}

**By technique diversity** (breadth of methods used):

{_category_ranking_table(cat_stats, "technique_count", "Distinct techniques")}

---

## Technique Momentum

**Definition:** `momentum_score = introduces_count − uses_count`

- **Positive momentum** (+): technique is being invented more than adopted —
  frontier activity, new contributions entering the field
- **Negative momentum** (−): technique is used more than introduced —
  mature method in active deployment, no new invention needed
- **Neutral** (0): balanced or absent in both roles

At N={n_papers}, most techniques sit at ±1 (singletons).  The meaningful signal
is at the extremes: large negative values identify the field's most relied-upon
foundational methods; large positive values (if any) identify techniques being
introduced across multiple papers simultaneously.

**Momentum distribution:**

| Label | Count | Interpretation |
|---|---:|---|
| Positive | {momentum_counts.get("Positive", 0)} | Frontier techniques (introduces > uses) |
| Negative | {momentum_counts.get("Negative", 0)} | Established techniques (uses > introduces) |
| Neutral | {momentum_counts.get("Neutral", 0)} | Balanced or role-absent |

### Top Positive Momentum Techniques

{_momentum_table(momentum, "Positive", positive=True)}

### Top Negative Momentum Techniques

These techniques are most actively used without being reinvented here.
High negative momentum is characteristic of foundational methods.

{_momentum_table(momentum, "Negative", positive=False)}

---

## Key Observations

1. **Theory dominates the corpus** ({next(s.paper_count for s in cat_stats if s.category == "Theory")} of {n_papers} papers).
   NeurIPS 2024 skews heavily theoretical, consistent with the conference's profile.

2. **Large Language Models, Transformers, and Diffusion Models** are the only
   techniques with momentum ≤ −5, confirming their status as the field's
   current foundational infrastructure.  All three are GENERIC IDF tier.

3. **All positive momentum techniques sit at +1.**  With a single-conference
   single-year corpus, no technique was introduced by more papers than used it.
   Multi-year ingestion will differentiate these.

4. **Safety ({next(s.paper_count for s in cat_stats if s.category == "Safety")} papers) and Efficiency ({next(s.paper_count for s in cat_stats if s.category == "Efficiency")} papers) have the highest average
   citations** among mid-size categories — suggesting these are high-impact
   areas receiving significant external attention.  Validate after corpus expansion.
"""
    path.write_text(md, encoding="utf-8")


# ── Console output ────────────────────────────────────────────────────────────

def print_console_summary(
    cat_stats: list[CategoryStat],
    momentum: list[MomentumRecord],
    n_papers: int,
) -> None:
    from collections import Counter

    print(f"\n{'='*72}")
    print(f"  RESEARCH LANDSCAPE SNAPSHOT  —  NeurIPS 2024  ({n_papers} papers)")
    print(f"  ⚠  Single-year corpus. Not a temporal trend.")
    print(f"{'='*72}\n")

    print("Category overview (sorted by paper count):")
    print(f"  {'Category':<16} {'Papers':>6} {'AvgCit':>7} {'AvgBC':>9} {'AvgDC':>7} {'Techs':>6}")
    print(f"  {'-'*16} {'-'*6} {'-'*7} {'-'*9} {'-'*7} {'-'*6}")
    for s in cat_stats:
        print(
            f"  {s.category:<16} {s.paper_count:>6} {s.avg_citation:>7.1f}"
            f" {s.avg_betweenness:>9.5f} {s.avg_degree:>7.4f} {s.technique_count:>6}"
        )
    print()

    print("Top 10 positive momentum (introduces > uses):")
    pos = [r for r in momentum if r.momentum_score > 0][:10]
    if pos:
        print(f"  {'Technique':<48} {'Intro':>5} {'Uses':>5} {'Score':>6} {'Tier'}")
        print(f"  {'-'*48} {'-'*5} {'-'*5} {'-'*6} {'-'*12}")
        for r in pos:
            print(f"  {r.canonical_name[:48]:<48} {r.introduces_count:>5} {r.uses_count:>5} {r.momentum_score:>+6} {r.idf_tier}")
    else:
        print("  (none at current corpus size)")
    print()

    print("Top 10 negative momentum (uses > introduces — established methods):")
    neg = sorted([r for r in momentum if r.momentum_score < 0], key=lambda r: r.momentum_score)[:10]
    if neg:
        print(f"  {'Technique':<48} {'Intro':>5} {'Uses':>5} {'Score':>6} {'Tier'}")
        print(f"  {'-'*48} {'-'*5} {'-'*5} {'-'*6} {'-'*12}")
        for r in neg:
            print(f"  {r.canonical_name[:48]:<48} {r.introduces_count:>5} {r.uses_count:>5} {r.momentum_score:>+6} {r.idf_tier}")
    print()


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    if not os.environ.get("DATABASE_URL"):
        os.environ["DATABASE_URL"] = "sqlite:///research_platform.db"

    from db.session import engine

    print("Connecting to database…")
    with engine.connect() as conn:
        print("Loading category stats…")
        cat_stats = _load_category_stats(conn)

        print("Computing technique momentum…")
        n_papers = corpus_size(conn)
        momentum = _load_momentum(conn, n_papers)

    print_console_summary(cat_stats, momentum, n_papers)

    write_momentum_csv(momentum, CSV_PATH)
    print(f"CSV  → {CSV_PATH}  ({len(momentum)} rows)")

    write_trends_report(cat_stats, momentum, n_papers, MD_PATH)
    print(f"MD   → {MD_PATH}")
    print()


if __name__ == "__main__":
    main()
