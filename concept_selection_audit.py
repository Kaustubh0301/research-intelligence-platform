"""
Concept selection audit — read-only.

For every canonical technique, calculates:
  paper_count          — distinct papers that use it
  graph_contribution   — number of paper-pair edges it directly contributes to
  idf_score            — ln(total_papers / paper_count)

Classifies each into:
  GENERIC     — idf < IDF_GENERIC_CEILING   (appears in many papers; noisy signal)
  SHARED      — IDF_GENERIC_CEILING <= idf < IDF_SHARED_CEILING   (moderate signal)
  SPECIALIZED — idf >= IDF_SHARED_CEILING   (rare; high signal)

Proposed weight multipliers:
  GENERIC     × MULT_GENERIC
  SHARED      × MULT_SHARED
  SPECIALIZED × MULT_SPECIALIZED

Outputs:
  outputs/concept_selection.csv

Prints a full proposal report to stdout.

Does NOT modify any database table or schema.

Run:
  export DATABASE_URL=sqlite:///research_platform.db
  python concept_selection_audit.py
"""

from __future__ import annotations

import csv
import json
import math
import os
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

# ── Classification thresholds (IDF = ln(N / paper_count)) ────────────────────
#
# At N=100 these correspond to:
#   GENERIC     : paper_count >= 5   (idf < 3.00)
#   SHARED      : paper_count  3–4   (3.00 <= idf < 3.69)
#   SPECIALIZED : paper_count <= 2   (idf >= 3.69)
#
# Thresholds scale automatically as corpus grows — no manual update needed.

IDF_GENERIC_CEILING = 3.00   # below this → GENERIC
IDF_SHARED_CEILING  = 3.69   # below this → SHARED; at or above → SPECIALIZED

# ── Proposed weight multipliers ───────────────────────────────────────────────

MULT_GENERIC     = 0.25
MULT_SHARED      = 1.00
MULT_SPECIALIZED = 2.00

# Current flat technique weight in graph/builder.py
CURRENT_WEIGHT_TECHNIQUE = 3


# ── Data types ────────────────────────────────────────────────────────────────

@dataclass
class ConceptRecord:
    canonical_name:    str
    paper_count:       int
    pct_of_papers:     float
    graph_contribution: int
    idf_score:         float
    classification:    str     # GENERIC | SHARED | SPECIALIZED
    proposed_weight:   float   # current_weight × multiplier


def _classify(idf: float) -> str:
    if idf < IDF_GENERIC_CEILING:
        return "GENERIC"
    if idf < IDF_SHARED_CEILING:
        return "SHARED"
    return "SPECIALIZED"


# ── Data loading ──────────────────────────────────────────────────────────────

def load_concepts() -> tuple[list[ConceptRecord], int]:
    """Returns (records sorted by paper_count desc, total_papers)."""
    from sqlalchemy import text
    from db.session import engine

    with engine.connect() as conn:

        total_papers: int = conn.execute(
            text("SELECT COUNT(*) FROM papers")
        ).scalar_one()

        # paper_count per canonical from technique_graph_metrics
        usage_rows = conn.execute(
            text("SELECT canonical_name, usage_count FROM technique_graph_metrics")
        ).fetchall()
        usage_map: dict[str, int] = {r.canonical_name: r.usage_count for r in usage_rows}

        # Fallback: any canonical not yet in metrics
        for r in conn.execute(text("""
            SELECT COALESCE(canonical_name, name) AS canon,
                   COUNT(DISTINCT paper_id)       AS cnt
            FROM   paper_techniques
            GROUP  BY canon
        """)).fetchall():
            if r.canon not in usage_map:
                usage_map[r.canon] = r.cnt

        # Graph contribution per canonical from shared_techniques JSON
        graph_contrib: dict[str, int] = defaultdict(int)
        for row in conn.execute(
            text("SELECT shared_techniques FROM paper_relationships")
        ).fetchall():
            raw = row[0]
            if not raw:
                continue
            try:
                names = json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                continue
            for name in names:
                if isinstance(name, str) and name:
                    graph_contrib[name] += 1

    records: list[ConceptRecord] = []
    for canon, paper_count in usage_map.items():
        idf  = math.log(total_papers / paper_count) if paper_count > 0 else 0.0
        cls  = _classify(idf)
        mult = {
            "GENERIC":     MULT_GENERIC,
            "SHARED":      MULT_SHARED,
            "SPECIALIZED": MULT_SPECIALIZED,
        }[cls]
        records.append(ConceptRecord(
            canonical_name     = canon,
            paper_count        = paper_count,
            pct_of_papers      = round(100.0 * paper_count / total_papers, 1)
                                  if total_papers else 0.0,
            graph_contribution = graph_contrib.get(canon, 0),
            idf_score          = round(idf, 3),
            classification     = cls,
            proposed_weight    = round(CURRENT_WEIGHT_TECHNIQUE * mult, 2),
        ))

    records.sort(key=lambda r: (-r.paper_count, -r.graph_contribution, r.canonical_name))
    return records, total_papers


# ── CSV output ────────────────────────────────────────────────────────────────

CSV_FIELDS = [
    "canonical_name",
    "classification",
    "paper_count",
    "pct_of_papers",
    "idf_score",
    "graph_contribution",
    "proposed_weight",
]


def write_csv(records: list[ConceptRecord], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for r in records:
            writer.writerow({
                "canonical_name":    r.canonical_name,
                "classification":    r.classification,
                "paper_count":       r.paper_count,
                "pct_of_papers":     f"{r.pct_of_papers:.1f}",
                "idf_score":         f"{r.idf_score:.3f}",
                "graph_contribution": r.graph_contribution,
                "proposed_weight":   f"{r.proposed_weight:.2f}",
            })
    print(f"  Wrote {path}")


# ── Console proposal report ───────────────────────────────────────────────────

def print_proposal(records: list[ConceptRecord], total_papers: int) -> None:
    by_cls: dict[str, list[ConceptRecord]] = defaultdict(list)
    for r in records:
        by_cls[r.classification].append(r)

    generic     = by_cls["GENERIC"]
    shared      = by_cls["SHARED"]
    specialized = by_cls["SPECIALIZED"]

    total_gdc = sum(r.graph_contribution for r in records)

    # ── Impact simulation ─────────────────────────────────────────────────────
    # For each classification, what fraction of graph edge weight comes from it
    # under current vs proposed weighting?

    def gdc_pct(group: list[ConceptRecord]) -> str:
        g = sum(r.graph_contribution for r in group)
        return f"{100 * g / total_gdc:.1f}%" if total_gdc else "0%"

    # Effective contribution after applying multiplier (proportional only)
    def effective_gdc(group: list[ConceptRecord]) -> float:
        mult = group[0].proposed_weight / CURRENT_WEIGHT_TECHNIQUE if group else 1.0
        return sum(r.graph_contribution * mult for r in group)

    total_eff = (
        effective_gdc(generic)
        + effective_gdc(shared)
        + effective_gdc(specialized)
    )

    def eff_pct(group: list[ConceptRecord]) -> str:
        eff = effective_gdc(group)
        return f"{100 * eff / total_eff:.1f}%" if total_eff else "0%"

    W = 68

    print()
    print("=" * W)
    print("  CONCEPT SELECTION AUDIT")
    print("=" * W)
    print(f"  Total papers          : {total_papers}")
    print(f"  Total techniques      : {len(records)}")
    print(f"  IDF formula           : ln(N / paper_count),  N = {total_papers}")
    print(f"  Classification cuts   : "
          f"GENERIC idf < {IDF_GENERIC_CEILING:.2f}  |  "
          f"SHARED idf < {IDF_SHARED_CEILING:.2f}  |  "
          f"SPECIALIZED idf ≥ {IDF_SHARED_CEILING:.2f}")
    print()

    # ── Per-classification breakdown ──────────────────────────────────────────
    print(f"  {'Class':<12} {'Count':>6}  {'Threshold':>30}  {'GDC now':>8}  {'GDC after':>9}")
    print("  " + "-" * (W - 2))

    rows = [
        ("GENERIC",     generic,     f"idf < {IDF_GENERIC_CEILING:.2f}  (paper_count ≥ 5)",
         MULT_GENERIC),
        ("SHARED",      shared,      f"{IDF_GENERIC_CEILING:.2f} ≤ idf < {IDF_SHARED_CEILING:.2f}  (paper_count 3–4)",
         MULT_SHARED),
        ("SPECIALIZED", specialized, f"idf ≥ {IDF_SHARED_CEILING:.2f}  (paper_count ≤ 2)",
         MULT_SPECIALIZED),
    ]
    for cls, group, thresh, _ in rows:
        print(
            f"  {cls:<12} {len(group):>6}  {thresh:>30}  "
            f"{gdc_pct(group):>8}  {eff_pct(group):>9}"
        )
    print()

    # ── Entity detail per classification ─────────────────────────────────────
    for cls, group, _, mult in rows:
        new_w = round(CURRENT_WEIGHT_TECHNIQUE * mult, 2)
        print(f"  {'─' * (W - 2)}")
        print(
            f"  {cls}  —  {len(group)} techniques  "
            f"(current weight {CURRENT_WEIGHT_TECHNIQUE}  →  proposed {new_w}  ×{mult})"
        )
        print(f"  {'─' * (W - 2)}")
        print(
            f"  {'Canonical Name':<44} {'Papers':>6}  "
            f"{'IDF':>6}  {'GDC now':>7}  {'GDC eff':>7}"
        )
        print("  " + "-" * (W - 2))
        for r in group:
            eff = round(r.graph_contribution * mult, 1)
            print(
                f"  {r.canonical_name:<44} {r.paper_count:>6}  "
                f"{r.idf_score:>6.3f}  {r.graph_contribution:>7}  {eff:>7}"
            )
        print()

    # ── Proposed rule summary ─────────────────────────────────────────────────
    print("=" * W)
    print("  PROPOSED WEIGHTING RULES")
    print("=" * W)
    print()
    print(f"  Current formula:")
    print(f"    edge_weight = {CURRENT_WEIGHT_TECHNIQUE} × |shared_techniques|")
    print(f"                + 2 × |shared_datasets|")
    print(f"                + 1 × |shared_categories|")
    print(f"                + 1 × |shared_methodologies|")
    print()
    print(f"  Proposed formula:")
    print(f"    For each shared technique t:")
    print(f"      idf(t)            = ln(N / paper_count(t))")
    print(f"      base_weight(t)    = {CURRENT_WEIGHT_TECHNIQUE}")
    print(f"      multiplier(t)     = class_multiplier(idf(t))")
    print(f"      contribution(t)   = base_weight × multiplier(t)")
    print()
    print(f"    class_multiplier rules:")
    print(f"      idf < {IDF_GENERIC_CEILING:.2f}  (GENERIC)      →  × {MULT_GENERIC}   "
          f"(current weight × {MULT_GENERIC})")
    print(f"      idf < {IDF_SHARED_CEILING:.2f}  (SHARED)       →  × {MULT_SHARED}   "
          f"(no change)")
    print(f"      idf ≥ {IDF_SHARED_CEILING:.2f}  (SPECIALIZED)  →  × {MULT_SPECIALIZED}   "
          f"(current weight × {MULT_SPECIALIZED})")
    print()

    # Concrete examples with current data
    print(f"  Concrete examples at N={total_papers}:")
    print(f"  {'Technique':<44} {'Papers':>6}  {'IDF':>6}  {'Class':<12} {'Old w':>5}  {'New w':>5}")
    print("  " + "-" * (W - 2))
    examples = sorted(
        [r for r in records if r.paper_count >= 2],
        key=lambda r: -r.paper_count
    )[:12]
    for r in examples:
        print(
            f"  {r.canonical_name:<44} {r.paper_count:>6}  "
            f"{r.idf_score:>6.3f}  {r.classification:<12} "
            f"{CURRENT_WEIGHT_TECHNIQUE:>5}  {r.proposed_weight:>5}"
        )
    print()

    # Impact on graph
    print(f"  Graph edge weight impact (technique component only):")
    print(f"    Current  : GENERIC contributes {gdc_pct(generic)} of all technique-GDC")
    print(f"    Proposed : GENERIC contributes {eff_pct(generic)} after multipliers")
    print(f"    SPECIALIZED gains             : {eff_pct(specialized)} (was {gdc_pct(specialized)})")
    print()
    print(f"  Thresholds scale automatically.")
    print(f"  At N=1000: GENERIC = paper_count ≥ 50, SHARED = 25–49, SPECIALIZED = ≤ 24.")
    print("=" * W)


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    if not os.environ.get("DATABASE_URL"):
        os.environ["DATABASE_URL"] = "sqlite:///research_platform.db"

    print("Loading concept signals from database…")
    records, total_papers = load_concepts()
    print(f"  Loaded {len(records)} canonical techniques across {total_papers} papers")

    print("Writing outputs…")
    write_csv(records, Path("outputs/concept_selection.csv"))

    print_proposal(records, total_papers)


if __name__ == "__main__":
    main()
