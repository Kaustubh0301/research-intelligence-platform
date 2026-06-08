"""
Corpus Intelligence — Technique Evolution

Builds a directed technique influence graph from role annotations:

  Directed edge A → B means: a paper introduced A while also using B,
  implying A was built on top of B.

  in_degree(B)  = number of distinct introduced techniques built on B
                  → high in_degree = foundational importance
  out_degree(A) = number of distinct foundations A relied on when introduced
                  → high out_degree = derivative / synthesizing technique

Classification uses percentile ranks, not fixed thresholds:
  Foundational   — in_degree in top FOUNDATIONAL_PERCENTILE of all
                   techniques with in_degree > 0
  Cutting-edge   — introduced + out_degree in top CUTTING_EDGE_PERCENTILE
                   of introduced techniques with out_degree > 0
  Isolated       — introduced + out_degree = 0 (no visible foundations)
  Versatile      — never introduced, but in_degree > 0 (foundation-only)
  Pure-user      — only used; in_degree = 0, never introduced

Self-loop edges (A → A) are excluded.

Outputs:
  outputs/corpus_intel/technique_evolution.csv
  outputs/corpus_intel/technique_evolution.md

Read-only. No DB writes. No schema changes.

Run:
  export DATABASE_URL=sqlite:///research_platform.db
  python -m corpus_intel.technique_evolution
"""

from __future__ import annotations

import csv
import math
import os
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import text

from corpus_intel._queries import (
    corpus_size,
    idf_tier,
    paper_titles,
    role_aggregation,
)

# ── Output paths ──────────────────────────────────────────────────────────────

_OUT_DIR = Path("outputs/corpus_intel")
CSV_PATH = _OUT_DIR / "technique_evolution.csv"
MD_PATH  = _OUT_DIR / "technique_evolution.md"

# ── Classification percentile knobs ──────────────────────────────────────────
# Techniques whose in_degree ranks at or above this percentile (among techniques
# with in_degree > 0) are classified Foundational.
FOUNDATIONAL_PERCENTILE = 0.75

# Introduced techniques whose out_degree ranks at or above this percentile
# (among introduced techniques with out_degree > 0) are classified Cutting-edge.
CUTTING_EDGE_PERCENTILE = 0.75

# ── Data structures ───────────────────────────────────────────────────────────

@dataclass
class TechniqueNode:
    canonical_name:          str
    in_degree:               int     # distinct introduced techniques that depend on this one
    out_degree:              int     # raw distinct foundations this was built on when introduced
    normalized_out_degree:   float   # out_degree ÷ max(introduced_by_count, 1) — corrects for
                                     # cross-product inflation when one paper introduces many variants
    foundation_score:        float   # normalized in_degree ÷ max_in_degree (0.0–1.0)
    derivative_score:        float   # normalized out_degree ÷ max_out_degree (0.0–1.0)
    introduced_by_count:     int     # papers that introduce this technique
    foundation_use_count:    int     # papers that use this as a foundation for something new
    classification:          str
    idf_score:               float
    idf_tier:                str
    # Edge lists for report — not written to CSV
    built_on:     list[str] = field(default_factory=list, repr=False)  # foundations A depended on
    built_upon_by: list[str] = field(default_factory=list, repr=False) # techniques that depend on A


@dataclass
class TechniqueEdge:
    source: str   # introduced technique (A)
    target: str   # foundation technique (B): A was built on B
    weight: int   # papers where this A→B relationship appears


# ── Graph construction ────────────────────────────────────────────────────────

def build_influence_graph(
    conn,
) -> tuple[list[TechniqueNode], list[TechniqueEdge], int]:
    """
    Build the directed technique influence graph.

    For each paper P:
      intro_set(P) = techniques P introduces
      uses_set(P)  = techniques P uses (excluding what P also introduces)
      Edges: for every (A in intro_set, B in uses_set): A → B (weight++)

    Self-loops (A → A) are excluded.

    Returns (nodes, edges, n_papers).
    """
    n_papers = corpus_size(conn)
    agg_map  = role_aggregation(conn)

    # Per-paper technique sets — query directly so we have paper-level granularity.
    rows = conn.execute(text("""
        SELECT
            paper_id,
            TRIM(COALESCE(canonical_name, name)) AS canon,
            role
        FROM paper_techniques
        WHERE TRIM(COALESCE(canonical_name, name)) != ''
          AND COALESCE(canonical_name, name) IS NOT NULL
    """)).all()

    # Build per-paper {introduces: set, uses: set}
    paper_roles: dict[str, dict[str, set[str]]] = defaultdict(
        lambda: {"introduces": set(), "uses": set()}
    )
    for row in rows:
        if not row.canon:
            continue
        if row.role == "introduces":
            paper_roles[row.paper_id]["introduces"].add(row.canon)
        elif row.role == "uses":
            paper_roles[row.paper_id]["uses"].add(row.canon)

    # Build directed edge A → B with weight = paper count
    edge_weights: dict[tuple[str, str], int] = defaultdict(int)

    for pid, roles in paper_roles.items():
        intro_set = roles["introduces"]
        # Uses set: only techniques this paper uses but does NOT introduce.
        # This prevents an introducing paper from creating a self-loop via
        # the same canonical name appearing in both roles.
        uses_only = roles["uses"] - intro_set

        for a in intro_set:
            for b in uses_only:
                if a == b:
                    continue  # exclude self-loops (belt + suspenders)
                edge_weights[(a, b)] += 1

    # Materialise edge list
    edges: list[TechniqueEdge] = [
        TechniqueEdge(source=a, target=b, weight=w)
        for (a, b), w in edge_weights.items()
    ]
    edges.sort(key=lambda e: (-e.weight, e.source, e.target))

    # Compute in/out degree per technique
    in_degree:  dict[str, int] = defaultdict(int)
    out_degree: dict[str, int] = defaultdict(int)
    built_on_map:      dict[str, list[str]] = defaultdict(list)   # A → list of B
    built_upon_map:    dict[str, list[str]] = defaultdict(list)   # B → list of A

    for e in edges:
        out_degree[e.source] += 1
        in_degree[e.target]  += 1
        built_on_map[e.source].append(e.target)
        built_upon_map[e.target].append(e.source)

    # foundation_use_count: for each technique B, how many distinct papers
    # use B as a foundation when introducing something else.
    foundation_use_paper_count: dict[str, set[str]] = defaultdict(set)
    for pid, roles in paper_roles.items():
        uses_only = roles["uses"] - roles["introduces"]
        if roles["introduces"]:           # this paper introduces something
            for b in uses_only:
                foundation_use_paper_count[b].add(pid)

    # Percentile thresholds
    in_degrees_nonzero = [v for v in in_degree.values() if v > 0]

    # Cutting-edge threshold uses normalized_out_degree so that techniques
    # introduced by a single paper that happens to use many foundations are
    # not inflated over techniques synthesizing many foundations across
    # multiple introducing papers.
    norm_out_introduced_nonzero = [
        out_degree[canon] / max(agg.introduces_count, 1)
        for canon, agg in agg_map.items()
        if agg.introduces_count > 0 and out_degree.get(canon, 0) > 0
    ]

    def _percentile(values: list[float], p: float) -> float:
        if not values:
            return 0.0
        s = sorted(values)
        idx = p * (len(s) - 1)
        lo, hi = int(idx), min(int(idx) + 1, len(s) - 1)
        return s[lo] + (s[hi] - s[lo]) * (idx - lo)

    foundational_threshold  = _percentile(in_degrees_nonzero, FOUNDATIONAL_PERCENTILE)
    cutting_edge_threshold  = _percentile(norm_out_introduced_nonzero, CUTTING_EDGE_PERCENTILE)

    max_in  = max(in_degree.values(),  default=1)
    max_out = max(out_degree.values(), default=1)

    # Build all technique names seen (from agg_map)
    all_techniques = set(agg_map.keys())
    # Also include techniques that appear only as edge targets (foundations)
    for e in edges:
        all_techniques.add(e.target)

    nodes: list[TechniqueNode] = []
    for canon in all_techniques:
        agg  = agg_map.get(canon)
        ind  = in_degree.get(canon, 0)
        outd = out_degree.get(canon, 0)
        n_intro = agg.introduces_count if agg else 0
        n_fuse  = len(foundation_use_paper_count.get(canon, set()))

        idf_s, idf_t = idf_tier(agg.total_papers if agg else 0, n_papers)

        norm_outd = round(outd / max(n_intro, 1), 4)

        # Classification (evaluated in priority order)
        if ind > 0 and ind >= foundational_threshold:
            cls = "Foundational"
        elif n_intro > 0 and outd > 0 and norm_outd >= cutting_edge_threshold:
            cls = "Cutting-edge"
        elif n_intro > 0 and outd == 0:
            cls = "Isolated"
        elif n_intro == 0 and ind > 0:
            cls = "Versatile"
        else:
            cls = "Pure-user"

        f_score  = round(ind / max_in, 4)  if max_in  else 0.0
        d_score  = round(outd / max_out, 4) if max_out else 0.0

        nodes.append(TechniqueNode(
            canonical_name          = canon,
            in_degree               = ind,
            out_degree              = outd,
            normalized_out_degree   = norm_outd,
            foundation_score        = f_score,
            derivative_score        = d_score,
            introduced_by_count     = n_intro,
            foundation_use_count    = n_fuse,
            classification          = cls,
            idf_score               = idf_s,
            idf_tier                = idf_t,
            built_on                = sorted(set(built_on_map.get(canon, []))),
            built_upon_by           = sorted(set(built_upon_map.get(canon, []))),
        ))

    # Sort: Foundational first (desc in_degree), then Cutting-edge (desc out_degree),
    # then rest alphabetically.
    _cls_rank = {
        "Foundational": 0, "Cutting-edge": 1, "Isolated": 2,
        "Versatile": 3, "Pure-user": 4,
    }
    nodes.sort(key=lambda n: (
        _cls_rank.get(n.classification, 9),
        -n.in_degree,
        -n.normalized_out_degree,
        -n.out_degree,
        n.canonical_name,
    ))

    return nodes, edges, n_papers


# ── CSV output ────────────────────────────────────────────────────────────────

_CSV_FIELDS = [
    "canonical_name",
    "introduced_by_count",
    "in_degree",
    "out_degree",
    "normalized_out_degree",
    "foundation_score",
    "derivative_score",
    "classification",
    "idf_tier",
]


def write_csv(nodes: list[TechniqueNode], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=_CSV_FIELDS)
        writer.writeheader()
        for n in nodes:
            writer.writerow({
                "canonical_name":        n.canonical_name,
                "introduced_by_count":   n.introduced_by_count,
                "in_degree":             n.in_degree,
                "out_degree":            n.out_degree,
                "normalized_out_degree": n.normalized_out_degree,
                "foundation_score":      n.foundation_score,
                "derivative_score":      n.derivative_score,
                "classification":        n.classification,
                "idf_tier":              n.idf_tier,
            })


# ── Markdown helpers ──────────────────────────────────────────────────────────

def _shorten(s: str, max_len: int = 68) -> str:
    return s if len(s) <= max_len else s[:max_len - 1] + "…"


def _classification_table(nodes: list[TechniqueNode]) -> str:
    from collections import Counter
    counts = Counter(n.classification for n in nodes)
    order  = ["Foundational", "Cutting-edge", "Isolated", "Versatile", "Pure-user"]
    lines  = ["| Classification | Count | Description |", "|---|---:|---|"]
    descs  = {
        "Foundational":  "Many introduced techniques were built on top of this one",
        "Cutting-edge":  "Introduced + built on many foundations (high synthesis)",
        "Isolated":      "Introduced but built on no visible prior technique here",
        "Versatile":     "Never introduced; frequently used as a foundation by others",
        "Pure-user":     "Only used; neither introduced nor relied upon as a foundation",
    }
    total = len(nodes)
    for cls in order:
        n   = counts.get(cls, 0)
        pct = 100 * n / total if total else 0.0
        lines.append(f"| **{cls}** | {n} ({pct:.1f}%) | {descs[cls]} |")
    return "\n".join(lines)


def _foundational_table(nodes: list[TechniqueNode], n: int = 10) -> str:
    rows = [x for x in nodes if x.classification == "Foundational"]
    rows = sorted(rows, key=lambda x: (-x.in_degree, -x.foundation_use_count, x.canonical_name))
    if not rows:
        return "_No Foundational techniques at current corpus size._"
    lines = [
        "| Technique | In-degree | Foundation use (papers) | IDF tier |",
        "|---|---:|---:|:---:|",
    ]
    for r in rows[:n]:
        lines.append(
            f"| {r.canonical_name} | {r.in_degree} | {r.foundation_use_count} | {r.idf_tier} |"
        )
    return "\n".join(lines)


def _cutting_edge_table(nodes: list[TechniqueNode], n: int = 20) -> str:
    rows = [x for x in nodes if x.classification == "Cutting-edge"]
    rows = sorted(rows, key=lambda x: (-x.normalized_out_degree, -x.out_degree, x.canonical_name))
    if not rows:
        return "_No Cutting-edge techniques at current corpus size._"
    lines = [
        "| Technique | Norm out-degree | Raw out-degree | Introduced by (papers) | IDF tier |",
        "|---|---:|---:|---:|:---:|",
    ]
    for r in rows[:n]:
        lines.append(
            f"| {r.canonical_name} | {r.normalized_out_degree:.2f}"
            f" | {r.out_degree} | {r.introduced_by_count} | {r.idf_tier} |"
        )
    return "\n".join(lines)


def _isolated_table(nodes: list[TechniqueNode], n: int = 10) -> str:
    rows = [x for x in nodes if x.classification == "Isolated"]
    rows = sorted(rows, key=lambda x: (-x.introduced_by_count, x.canonical_name))
    if not rows:
        return "_No Isolated techniques at current corpus size._"
    lines = [
        "| Technique | Introduced by (papers) | IDF tier |",
        "|---|---:|:---:|",
    ]
    for r in rows[:n]:
        lines.append(
            f"| {r.canonical_name} | {r.introduced_by_count} | {r.idf_tier} |"
        )
    return "\n".join(lines)


def _evolution_chains(
    nodes: list[TechniqueNode],
    edges: list[TechniqueEdge],
    titles: dict[str, str],
    n_chains: int = 5,
) -> str:
    """
    Show sample evolution chains: for the top Cutting-edge techniques,
    display the foundation chain "A was built on: B1, B2, …".
    """
    cutting_edge = [x for x in nodes if x.classification == "Cutting-edge"]
    cutting_edge = sorted(cutting_edge, key=lambda x: (-x.normalized_out_degree, -x.out_degree, x.canonical_name))

    if not cutting_edge:
        foundational = [x for x in nodes if x.classification == "Foundational"]
        if not foundational:
            return "_No evolution chains detectable at current corpus size._"
        # Fallback: show foundation → built-upon relationships
        lines = ["**Top Foundational techniques and what was built on them:**\n"]
        for f in foundational[:n_chains]:
            if f.built_upon_by:
                built_on_names = ", ".join(f.built_upon_by[:5])
                lines.append(f"- **{f.canonical_name}** ← built upon by: {built_on_names}")
        return "\n".join(lines) if len(lines) > 1 else "_No evolution chains detectable at current corpus size._"

    # Build a lookup: edge source → list of (target, weight)
    edge_lookup: dict[str, list[tuple[str, int]]] = defaultdict(list)
    for e in edges:
        edge_lookup[e.source].append((e.target, e.weight))
    for k in edge_lookup:
        edge_lookup[k].sort(key=lambda x: -x[1])

    lines = []
    for ce in cutting_edge[:n_chains]:
        foundations = edge_lookup.get(ce.canonical_name, [])
        if not foundations:
            continue
        found_str = " → ".join(
            f"{b}" + (f" (×{w})" if w > 1 else "")
            for b, w in foundations[:6]
        )
        lines.append(f"- **{ce.canonical_name}** built on: {found_str}")

    return "\n".join(lines) if lines else "_No evolution chains detectable at current corpus size._"


# ── Markdown report ───────────────────────────────────────────────────────────

def write_report(
    nodes: list[TechniqueNode],
    edges: list[TechniqueEdge],
    n_papers: int,
    path: Path,
    titles: dict[str, str],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    from collections import Counter
    cls_counts = Counter(n.classification for n in nodes)

    # Unique techniques involved in at least one edge
    edge_sources = {e.source for e in edges}
    edge_targets = {e.target for e in edges}
    connected_techniques = len(edge_sources | edge_targets)

    md = f"""# Technique Evolution — Corpus Intelligence Report

**Generated:** {ts}
**Corpus:** {n_papers} papers
**Canonical techniques:** {len(nodes)}
**Directed influence edges:** {len(edges)} (unique A→B pairs)
**Techniques in at least one edge:** {connected_techniques}

> **How to read this report.** An edge A → B means: a paper introduced A
> while using B — implying A was built on B.  In-degree measures how many
> novel techniques depend on a given foundation.  Out-degree measures how
> many foundations a technique synthesized when it was introduced.
>
> **Corpus size caveat:** At {n_papers} papers from a single conference-year,
> chains are short and edge weights are mostly 1.  The structure is correct;
> density and chain depth improve automatically as the corpus grows.

---

## Classification

{_classification_table(nodes)}

**Percentile thresholds used:**
- Foundational: in\\_degree ≥ {FOUNDATIONAL_PERCENTILE:.0%} percentile of techniques with in\\_degree > 0
- Cutting-edge: normalized\\_out\\_degree ≥ {CUTTING_EDGE_PERCENTILE:.0%} percentile of introduced techniques with out\\_degree > 0

---

## Foundational Techniques ({cls_counts.get("Foundational", 0)})

These techniques have the highest in-degree in the influence graph — the most
novel contributions in this corpus were built on top of them.

{_foundational_table(nodes)}

---

## Cutting-Edge Techniques ({cls_counts.get("Cutting-edge", 0)})

These techniques were introduced in this corpus AND built on many prior
foundations — the highest-synthesis new contributions.

Ranked by **normalized out-degree** = raw out-degree ÷ introduced\\_by\\_count.
This corrects for cross-product inflation: when one paper introduces several
variant techniques (e.g. CLA2, CLA3, CLA4) while using the same foundation set,
raw out-degree is identical for each variant.  Normalized out-degree divides by
the number of papers that introduced the technique, yielding a per-paper average
foundations-relied-upon score.

> ⚠ **Variant inflation note:** Cutting-edge rankings may still be inflated by
> variant techniques introduced within a single paper (e.g. CLA2/CLA3/CLA4 all
> have introduced\\_by\\_count = 1, so normalization does not fully de-duplicate
> them).  Future corpus expansion and normalization audits are expected to reduce
> this effect as variant names are merged into canonical forms.

{_cutting_edge_table(nodes)}

---

## Isolated Techniques ({cls_counts.get("Isolated", 0)}) — top 10

Introduced in this corpus but built on no other technique visible here.
Either genuinely novel from scratch, or the foundations were not extracted.

{_isolated_table(nodes)}

---

## Evolution Chains

Sample chains showing what cutting-edge techniques were built on.
Format: **introduced technique** built on: foundation1 → foundation2 → …
Edge weight (×N) shown where the same A→B relationship appears in multiple papers.

{_evolution_chains(nodes, edges, titles)}

---

## Notes for Re-run After Corpus Expansion

- Edge count will grow quadratically as more papers introduce techniques on shared foundations.
- Chain depth will increase: currently most chains are length 1 (A built on B only).
- Foundational threshold will shift — techniques currently at the 75th percentile may
  drop to Versatile when the distribution widens with more papers.
- Isolated count will decrease as cross-paper adoption becomes visible.
"""
    path.write_text(md, encoding="utf-8")


# ── Console output ────────────────────────────────────────────────────────────

def print_console_table(
    nodes: list[TechniqueNode],
    edges: list[TechniqueEdge],
    n_papers: int,
) -> None:
    from collections import Counter
    cls_counts = Counter(n.classification for n in nodes)
    total = len(nodes)

    print(f"\n{'='*72}")
    print(f"  TECHNIQUE EVOLUTION  —  corpus: {n_papers} papers")
    print(f"  {len(edges)} directed edges  ·  {total} technique nodes")
    print(f"{'='*72}\n")

    print("Classification distribution:")
    for cls in ["Foundational", "Cutting-edge", "Isolated", "Versatile", "Pure-user"]:
        n   = cls_counts.get(cls, 0)
        pct = 100 * n / total if total else 0.0
        bar = "█" * int(pct / 2.5)
        print(f"  {cls:<14} {n:>4}  ({pct:>5.1f}%)  {bar}")
    print()

    foundational = sorted(
        [x for x in nodes if x.classification == "Foundational"],
        key=lambda x: (-x.in_degree, x.canonical_name),
    )
    if foundational:
        print("Top Foundational (highest in-degree — many techniques built on these):")
        print(f"  {'Technique':<46} {'In°':>4} {'FndUse':>7} {'Tier'}")
        print(f"  {'-'*46} {'-'*4} {'-'*7} {'-'*12}")
        for r in foundational[:10]:
            print(
                f"  {r.canonical_name[:46]:<46} {r.in_degree:>4}"
                f" {r.foundation_use_count:>7} {r.idf_tier}"
            )
        print()

    cutting = sorted(
        [x for x in nodes if x.classification == "Cutting-edge"],
        key=lambda x: (-x.normalized_out_degree, -x.out_degree, x.canonical_name),
    )
    if cutting:
        print("Top Cutting-edge (introduced + highest normalized out-degree — high-synthesis):")
        print(f"  {'Technique':<46} {'NormOut°':>9} {'Out°':>5} {'Intro':>6} {'Tier'}")
        print(f"  {'-'*46} {'-'*9} {'-'*5} {'-'*6} {'-'*12}")
        for r in cutting[:20]:
            print(
                f"  {r.canonical_name[:46]:<46} {r.normalized_out_degree:>9.2f}"
                f" {r.out_degree:>5} {r.introduced_by_count:>6} {r.idf_tier}"
            )
        print()

    print("Top edges by weight (A → B means 'A was introduced while using B'):")
    print(f"  {'Introduced (A)':<36} → {'Foundation (B)':<36} {'Papers':>6}")
    print(f"  {'-'*36}   {'-'*36} {'-'*6}")
    for e in edges[:15]:
        print(
            f"  {e.source[:36]:<36} → {e.target[:36]:<36} {e.weight:>6}"
        )
    print()


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    if not os.environ.get("DATABASE_URL"):
        os.environ["DATABASE_URL"] = "sqlite:///research_platform.db"

    from db.session import engine

    print("Connecting to database…")
    with engine.connect() as conn:
        print("Building influence graph…")
        nodes, edges, n_papers = build_influence_graph(conn)
        titles = paper_titles(conn)

    print_console_table(nodes, edges, n_papers)

    write_csv(nodes, CSV_PATH)
    print(f"CSV  → {CSV_PATH}  ({len(nodes)} rows)")

    write_report(nodes, edges, n_papers, MD_PATH, titles)
    print(f"MD   → {MD_PATH}")
    print()


if __name__ == "__main__":
    main()
