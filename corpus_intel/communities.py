"""
Corpus Intelligence — Research Community Profiles

Profiles each graph cluster as a research community: its defining categories,
characteristic techniques, citation strength, graph cohesion, and bridge papers
that connect it to other communities.

⚠  CORPUS SNAPSHOT.  NeurIPS 2024 only (100 papers, 3 clusters).  Community
   structure will stabilise and differentiate with corpus expansion.

Outputs:
  outputs/corpus_intel/community_profiles.md
  outputs/corpus_intel/community_bridges.csv

Read-only. No DB writes. No schema changes.

Run:
  export DATABASE_URL=sqlite:///research_platform.db
  python -m corpus_intel.communities
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

# IDF threshold — mirrors graph/builder.py and _queries.py exactly.
# Techniques below this IDF score are GENERIC and excluded from identity statements.
_IDF_GENERIC_CEILING = 3.00

_OUT_DIR  = Path("outputs/corpus_intel")
MD_PATH   = _OUT_DIR / "community_profiles.md"
CSV_PATH  = _OUT_DIR / "community_bridges.csv"

# Minimum bridge_strength (fraction of edges crossing cluster boundaries)
# to qualify as a bridge paper in the CSV output.
_BRIDGE_STRENGTH_THRESHOLD = 0.30


# ── Data structures ───────────────────────────────────────────────────────────

@dataclass
class ClusterProfile:
    cluster_id:          int
    paper_count:         int
    avg_citation:        float
    avg_betweenness:     float
    avg_degree:          float
    intra_avg_weight:    float    # average edge weight within this cluster
    inter_avg_weight:    float    # average weight of edges from this cluster to others
    cohesion_ratio:      float    # intra_avg_weight / inter_avg_weight; >1 = more internally cohesive
    dominant_categories: list[tuple[str, int]]   # (name, paper_count) sorted desc
    dominant_techniques: list[tuple[str, int]]   # (name, paper_count) sorted desc; GENERIC excluded
    generic_techniques:  list[tuple[str, int]]   # GENERIC tier techniques shown separately
    bridge_paper_count:  int
    identity:            str      # deterministic rule-based community description


@dataclass
class BridgePaper:
    paper_id:                str
    title:                   str
    cluster_id:              int
    betweenness_centrality:  float
    degree_centrality:       float
    citation_count:          int
    cross_cluster_edge_count: int
    total_degree:            int
    bridge_strength:         float   # cross_cluster_edge_count / total_degree


@dataclass
class TopPaper:
    paper_id:               str
    title:                  str
    betweenness_centrality: float
    citation_count:         int


# ── Data loading ──────────────────────────────────────────────────────────────

def _load_edge_map(conn) -> dict[str, dict[str, float]]:
    """
    Return {paper_id: {neighbour_paper_id: weight}} from paper_relationships.
    Used to compute cross-cluster edge counts in Python.
    """
    rows = conn.execute(text("""
        SELECT source_paper_id, target_paper_id, weight
        FROM paper_relationships
    """)).all()
    edge_map: dict[str, dict[str, float]] = defaultdict(dict)
    for r in rows:
        edge_map[r.source_paper_id][r.target_paper_id] = r.weight
        edge_map[r.target_paper_id][r.source_paper_id] = r.weight
    return dict(edge_map)


def _load_paper_meta(conn) -> dict[str, dict]:
    """
    Return {paper_id: {title, citation_count, cluster_id, betweenness_centrality,
                       degree_centrality, neighbors_count}} for all papers.
    """
    rows = conn.execute(text("""
        SELECT
            p.id, p.title,
            COALESCE(p.citation_count, 0) AS citation_count,
            pgm.cluster_id,
            pgm.betweenness_centrality,
            pgm.degree_centrality,
            pgm.neighbors_count
        FROM papers p
        JOIN paper_graph_metrics pgm ON pgm.paper_id = p.id
    """)).all()
    return {
        r.id: {
            "title":                  r.title,
            "citation_count":         r.citation_count,
            "cluster_id":             r.cluster_id,
            "betweenness_centrality": r.betweenness_centrality,
            "degree_centrality":      r.degree_centrality,
            "neighbors_count":        r.neighbors_count,
        }
        for r in rows
    }


def _load_category_distribution(conn) -> dict[int, list[tuple[str, int]]]:
    """Return {cluster_id: [(category, paper_count), ...]} sorted by paper_count desc."""
    rows = conn.execute(text("""
        SELECT pgm.cluster_id, pc.name AS category, COUNT(DISTINCT pc.paper_id) AS n
        FROM paper_categories pc
        JOIN paper_graph_metrics pgm ON pgm.paper_id = pc.paper_id
        GROUP BY pgm.cluster_id, pc.name
        ORDER BY pgm.cluster_id, n DESC
    """)).all()
    result: dict[int, list[tuple[str, int]]] = defaultdict(list)
    for r in rows:
        result[r.cluster_id].append((r.category, r.n))
    return dict(result)


def _load_technique_distribution(
    conn, n_papers: int
) -> dict[int, tuple[list[tuple[str, int]], list[tuple[str, int]]]]:
    """
    Return {cluster_id: (non_generic_techniques, generic_techniques)}
    where each list is [(canonical_name, paper_count), ...] sorted desc.

    GENERIC = idf(paper_count) < _IDF_GENERIC_CEILING, i.e. paper_count such that
    ln(n_papers / paper_count) < 3.00.  At N=100 this means paper_count >= 5.
    """
    rows = conn.execute(text("""
        SELECT
            pgm.cluster_id,
            TRIM(COALESCE(pt.canonical_name, pt.name)) AS canon,
            COUNT(DISTINCT pt.paper_id) AS cluster_paper_count
        FROM paper_techniques pt
        JOIN paper_graph_metrics pgm ON pgm.paper_id = pt.paper_id
        WHERE TRIM(COALESCE(pt.canonical_name, pt.name)) != ''
          AND COALESCE(pt.canonical_name, pt.name) IS NOT NULL
        GROUP BY pgm.cluster_id, canon
        ORDER BY pgm.cluster_id, cluster_paper_count DESC
    """)).all()

    # Corpus-wide paper_count per technique (for IDF computation)
    corpus_counts = conn.execute(text("""
        SELECT
            TRIM(COALESCE(canonical_name, name)) AS canon,
            COUNT(DISTINCT paper_id) AS n
        FROM paper_techniques
        WHERE TRIM(COALESCE(canonical_name, name)) != ''
          AND COALESCE(canonical_name, name) IS NOT NULL
        GROUP BY canon
    """)).all()
    corpus_paper_count: dict[str, int] = {r.canon: r.n for r in corpus_counts}

    result: dict[int, tuple[list, list]] = {}
    cluster_rows: dict[int, list] = defaultdict(list)
    for r in rows:
        cluster_rows[r.cluster_id].append((r.canon, r.cluster_paper_count))

    for cid, entries in cluster_rows.items():
        generic, non_generic = [], []
        for canon, count in entries:
            corpus_n = corpus_paper_count.get(canon, count)
            idf = math.log(n_papers / corpus_n) if corpus_n > 0 and n_papers > 0 else 0.0
            if idf < _IDF_GENERIC_CEILING:
                generic.append((canon, count))
            else:
                non_generic.append((canon, count))
        result[cid] = (non_generic, generic)

    return result


def _cohesion_stats(conn) -> dict[int, tuple[float, float]]:
    """
    Return {cluster_id: (intra_avg_weight, inter_avg_weight)} per cluster.
    inter_avg_weight is the average weight of edges from this cluster to other clusters.
    """
    intra_rows = conn.execute(text("""
        SELECT s.cluster_id, AVG(pr.weight) AS avg_w
        FROM paper_relationships pr
        JOIN paper_graph_metrics s ON s.paper_id = pr.source_paper_id
        JOIN paper_graph_metrics t ON t.paper_id = pr.target_paper_id
        WHERE s.cluster_id = t.cluster_id
        GROUP BY s.cluster_id
    """)).all()
    intra: dict[int, float] = {r.cluster_id: r.avg_w for r in intra_rows}

    inter_rows = conn.execute(text("""
        SELECT s.cluster_id, AVG(pr.weight) AS avg_w
        FROM paper_relationships pr
        JOIN paper_graph_metrics s ON s.paper_id = pr.source_paper_id
        JOIN paper_graph_metrics t ON t.paper_id = pr.target_paper_id
        WHERE s.cluster_id <> t.cluster_id
        GROUP BY s.cluster_id
    """)).all()
    inter: dict[int, float] = {r.cluster_id: r.avg_w for r in inter_rows}

    return {
        cid: (
            round(intra.get(cid, 0.0), 4),
            round(inter.get(cid, 0.0), 4),
        )
        for cid in set(list(intra.keys()) + list(inter.keys()))
    }


def _top_papers_by_bc(conn, cluster_id: int, n: int = 5) -> list[TopPaper]:
    rows = conn.execute(text("""
        SELECT p.id, p.title, pgm.betweenness_centrality,
               COALESCE(p.citation_count, 0) AS citation_count
        FROM papers p
        JOIN paper_graph_metrics pgm ON pgm.paper_id = p.id
        WHERE pgm.cluster_id = :cid
        ORDER BY pgm.betweenness_centrality DESC
        LIMIT :n
    """), {"cid": cluster_id, "n": n}).all()
    return [TopPaper(r.id, r.title, r.betweenness_centrality, r.citation_count) for r in rows]


# ── Community identity ────────────────────────────────────────────────────────

def _generate_identity(
    cluster_id: int,
    paper_count: int,
    dominant_categories: list[tuple[str, int]],
    dominant_techniques: list[tuple[str, int]],
    avg_citation: float,
    corpus_avg_citation: float,
) -> str:
    """
    Generate a deterministic rule-based community identity statement.

    Rules (applied in order):
    1. Satellite cluster (< 5 papers): special minimal description.
    2. Single-category dominant (>= 80% of papers): "[cat]-dominated community"
    3. Dual-category dominant (top-2 together >= 60%): "[cat1] and [cat2] community"
    4. Multi-category: "[cat1], [cat2], and [cat3] community"
    5. Append technique focus from top non-GENERIC techniques.
    6. Append citation profile if avg > 1.5x corpus average.
    """
    if paper_count < 5:
        cat_labels = " and ".join(c for c, _ in dominant_categories[:2]) if dominant_categories else "Unknown"
        return (
            f"Satellite cluster: {cat_labels} ({paper_count} paper{'s' if paper_count != 1 else ''}"
            f" — insufficient for stable profiling)."
        )

    total = paper_count
    top_cats = dominant_categories[:4]
    primary_count = top_cats[0][1] if top_cats else 0
    secondary_count = top_cats[1][1] if len(top_cats) > 1 else 0

    if primary_count / total >= 0.80:
        cat_phrase = f"{top_cats[0][0]}-dominated"
    elif (primary_count + secondary_count) / total >= 0.60:
        cat_phrase = f"{top_cats[0][0]} and {top_cats[1][0]}"
    elif len(top_cats) >= 3:
        cat_phrase = f"{top_cats[0][0]}, {top_cats[1][0]}, and {top_cats[2][0]}"
    else:
        cat_phrase = top_cats[0][0] if top_cats else "Mixed"

    parts = [f"{cat_phrase} research community"]

    if dominant_techniques:
        t1 = dominant_techniques[0][0].lower()
        if len(dominant_techniques) >= 2:
            t2 = dominant_techniques[1][0].lower()
            parts.append(f"focused on {t1} and {t2}")
        else:
            parts.append(f"focused on {t1}")

    if avg_citation >= corpus_avg_citation * 1.5:
        parts.append(f"with high external impact (avg {avg_citation:.0f} citations)")
    elif avg_citation <= corpus_avg_citation * 0.35:
        parts.append("with foundational theoretical focus (low citation count)")

    return " ".join(parts) + "."


# ── Core analysis ─────────────────────────────────────────────────────────────

def build_profiles(conn) -> tuple[list[ClusterProfile], list[BridgePaper], float]:
    """
    Build community profiles and bridge paper list.

    Returns (profiles, bridge_papers, corpus_avg_citation).
    """
    n_papers = conn.execute(text("SELECT COUNT(*) FROM papers")).scalar() or 1
    corpus_avg_cit = conn.execute(
        text("SELECT AVG(COALESCE(citation_count, 0)) FROM papers")
    ).scalar() or 0.0

    paper_meta   = _load_paper_meta(conn)
    edge_map     = _load_edge_map(conn)
    cat_dist     = _load_category_distribution(conn)
    tech_dist    = _load_technique_distribution(conn, n_papers)
    cohesion     = _cohesion_stats(conn)

    # Build per-cluster paper lists and cross-cluster edge counts
    cluster_papers: dict[int, list[str]] = defaultdict(list)
    for pid, meta in paper_meta.items():
        cluster_papers[meta["cluster_id"]].append(pid)

    # Cross-cluster edges per paper
    cross_edge_count: dict[str, int] = {}
    for pid, meta in paper_meta.items():
        my_cluster = meta["cluster_id"]
        neighbours = edge_map.get(pid, {})
        cross = sum(
            1 for nbr in neighbours
            if paper_meta[nbr]["cluster_id"] != my_cluster
        )
        cross_edge_count[pid] = cross

    # Assemble profiles
    profiles: list[ClusterProfile] = []
    all_cluster_ids = sorted(cluster_papers.keys())

    for cid in all_cluster_ids:
        pids = cluster_papers[cid]
        n = len(pids)

        avg_cit = sum(paper_meta[p]["citation_count"] for p in pids) / n if n else 0.0
        avg_bc  = sum(paper_meta[p]["betweenness_centrality"] for p in pids) / n if n else 0.0
        avg_dc  = sum(paper_meta[p]["degree_centrality"] for p in pids) / n if n else 0.0

        intra_w, inter_w = cohesion.get(cid, (0.0, 0.0))
        cohesion_ratio   = round(intra_w / inter_w, 3) if inter_w else 0.0

        non_generic, generic = tech_dist.get(cid, ([], []))
        categories           = cat_dist.get(cid, [])

        bridge_count = sum(
            1 for p in pids
            if (
                cross_edge_count.get(p, 0) /
                max(paper_meta[p]["neighbors_count"], 1)
            ) >= _BRIDGE_STRENGTH_THRESHOLD
        )

        identity = _generate_identity(
            cluster_id         = cid,
            paper_count        = n,
            dominant_categories = categories,
            dominant_techniques = non_generic,
            avg_citation       = avg_cit,
            corpus_avg_citation = corpus_avg_cit,
        )

        profiles.append(ClusterProfile(
            cluster_id          = cid,
            paper_count         = n,
            avg_citation        = round(avg_cit, 1),
            avg_betweenness     = round(avg_bc, 5),
            avg_degree          = round(avg_dc, 4),
            intra_avg_weight    = intra_w,
            inter_avg_weight    = inter_w,
            cohesion_ratio      = cohesion_ratio,
            dominant_categories = categories[:8],
            dominant_techniques = non_generic[:10],
            generic_techniques  = generic[:5],
            bridge_paper_count  = bridge_count,
            identity            = identity,
        ))

    # Bridge papers
    bridge_papers: list[BridgePaper] = []
    for pid, meta in paper_meta.items():
        total_deg = meta["neighbors_count"]
        cross     = cross_edge_count.get(pid, 0)
        strength  = round(cross / total_deg, 3) if total_deg else 0.0
        if strength >= _BRIDGE_STRENGTH_THRESHOLD:
            bridge_papers.append(BridgePaper(
                paper_id                 = pid,
                title                    = meta["title"],
                cluster_id               = meta["cluster_id"],
                betweenness_centrality   = meta["betweenness_centrality"],
                degree_centrality        = meta["degree_centrality"],
                citation_count           = meta["citation_count"],
                cross_cluster_edge_count = cross,
                total_degree             = total_deg,
                bridge_strength          = strength,
            ))

    bridge_papers.sort(key=lambda b: (-b.bridge_strength, -b.betweenness_centrality))
    return profiles, bridge_papers, corpus_avg_cit


# ── CSV output ────────────────────────────────────────────────────────────────

_CSV_FIELDS = [
    "paper_id",
    "title",
    "cluster_id",
    "betweenness_centrality",
    "degree_centrality",
    "citation_count",
    "cross_cluster_edge_count",
    "total_degree",
    "bridge_strength",
]


def write_bridges_csv(bridges: list[BridgePaper], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=_CSV_FIELDS)
        writer.writeheader()
        for b in bridges:
            writer.writerow({
                "paper_id":                b.paper_id,
                "title":                   b.title,
                "cluster_id":              b.cluster_id,
                "betweenness_centrality":  b.betweenness_centrality,
                "degree_centrality":       b.degree_centrality,
                "citation_count":          b.citation_count,
                "cross_cluster_edge_count": b.cross_cluster_edge_count,
                "total_degree":            b.total_degree,
                "bridge_strength":         b.bridge_strength,
            })


# ── Markdown helpers ──────────────────────────────────────────────────────────

def _shorten(s: str, n: int = 75) -> str:
    return s if len(s) <= n else s[:n - 1] + "…"


def _cluster_section(
    profile: ClusterProfile,
    top_papers: list[TopPaper],
    bridges_in_cluster: list[BridgePaper],
    cluster_label: str,
) -> str:
    is_satellite = profile.paper_count < 5

    cat_rows = "\n".join(
        f"| {cat} | {n} | {100*n/profile.paper_count:.0f}% |"
        for cat, n in profile.dominant_categories[:8]
    )

    tech_rows = "\n".join(
        f"| {name} | {n} |"
        for name, n in profile.dominant_techniques[:8]
    ) or "_No SHARED/SPECIALIZED techniques in top results._"

    generic_note = ""
    if profile.generic_techniques:
        names = ", ".join(f"{n} ({c}p)" for n, c in profile.generic_techniques)
        generic_note = f"\n> **GENERIC tier** (suppressed in identity, shown for completeness): {names}\n"

    top_paper_rows = "\n".join(
        f"| {_shorten(p.title, 72)} | {p.betweenness_centrality:.5f} | {p.citation_count} |"
        for p in top_papers
    )

    bridge_rows = "\n".join(
        f"| {_shorten(b.title, 60)} | {b.cross_cluster_edge_count} | {b.bridge_strength:.2f} | {b.betweenness_centrality:.5f} |"
        for b in bridges_in_cluster[:5]
    ) or "_None above bridge_strength threshold._"

    satellite_warning = (
        "\n> ⚠ **Satellite cluster**: only 2 papers. Community statistics are not"
        " meaningful at this size. Expect this cluster to merge or grow with corpus expansion.\n"
        if is_satellite else ""
    )

    return f"""## Cluster {profile.cluster_id} — {cluster_label}

{satellite_warning}
> {profile.identity}

### Overview

| Metric | Value |
|---|---|
| Papers | {profile.paper_count} |
| Average citations | {profile.avg_citation:.1f} |
| Average betweenness centrality | {profile.avg_betweenness:.5f} |
| Average degree centrality | {profile.avg_degree:.4f} |
| Intra-cluster avg edge weight | {profile.intra_avg_weight:.3f} |
| Inter-cluster avg edge weight | {profile.inter_avg_weight:.3f} |
| Cohesion ratio (intra/inter) | {profile.cohesion_ratio:.3f} |
| Bridge papers (strength ≥ {_BRIDGE_STRENGTH_THRESHOLD}) | {profile.bridge_paper_count} |

### Dominant Categories

| Category | Papers | % of cluster |
|---|---:|---:|
{cat_rows}

### Dominant Techniques (SHARED / SPECIALIZED IDF tier)

| Technique | Papers in cluster |
|---|---:|
{tech_rows}
{generic_note}
### Top 5 Papers by Betweenness Centrality

| Title | Betweenness | Citations |
|---|---:|---:|
{top_paper_rows}

### Top Bridge Papers (highest bridge\\_strength)

Bridge strength = cross-cluster edges ÷ total neighbors.

| Title | Cross-cluster edges | Bridge strength | Betweenness |
|---|---:|---:|---:|
{bridge_rows}
"""


def _cluster_label(profile: ClusterProfile) -> str:
    """Short label derived from top categories — used as section heading."""
    if profile.paper_count < 5:
        cats = " + ".join(c for c, _ in profile.dominant_categories[:2])
        return f"Satellite ({cats})"
    top = profile.dominant_categories
    if top and top[0][1] / profile.paper_count >= 0.80:
        return f"{top[0][0]}-dominated"
    if len(top) >= 2:
        return f"{top[0][0]} + {top[1][0]}"
    return top[0][0] if top else "Mixed"


# ── Markdown report ───────────────────────────────────────────────────────────

def write_community_profiles(
    profiles: list[ClusterProfile],
    bridges: list[BridgePaper],
    corpus_avg_cit: float,
    n_papers: int,
    path: Path,
    top_papers_map: dict[int, list[TopPaper]],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    # Inter-cluster edge summary (0↔1, 0↔2, 1↔2)
    inter_summary_lines = []
    for p in profiles:
        for q in profiles:
            if q.cluster_id <= p.cluster_id:
                continue
            inter_summary_lines.append(
                f"| Cluster {p.cluster_id} ↔ Cluster {q.cluster_id} | "
                f"{p.cluster_id} and {q.cluster_id} | (see bridge papers) |"
            )

    cluster_sections = []
    for profile in profiles:
        label            = _cluster_label(profile)
        top_papers       = top_papers_map.get(profile.cluster_id, [])
        bridges_in       = [b for b in bridges if b.cluster_id == profile.cluster_id]
        cluster_sections.append(_cluster_section(profile, top_papers, bridges_in, label))

    overview_rows = "\n".join(
        f"| {p.cluster_id} | {_cluster_label(p)} | {p.paper_count} | "
        f"{p.avg_citation:.1f} | {p.avg_betweenness:.5f} | {p.cohesion_ratio:.3f} |"
        for p in profiles
    )

    identity_rows = "\n".join(
        f"| Cluster {p.cluster_id} | {p.identity} |"
        for p in profiles
    )

    bridge_count_total = len(bridges)

    md = f"""# Community Profiles — NeurIPS 2024

**Generated:** {ts}
**Corpus:** {n_papers} papers · 1 conference · 1 year (NeurIPS 2024)
**Clusters:** {len(profiles)} (detected by greedy modularity on Graph V2)

> ⚠ **Snapshot only.** Community structure at N={n_papers} is coarse.
> With 3 clusters, two large and one satellite, boundaries are broad.
> Profiles will differentiate substantially after corpus expansion.

---

## Cluster Overview

| Cluster | Label | Papers | Avg citations | Avg betweenness | Cohesion ratio |
|---|---|---:|---:|---:|---:|
{overview_rows}

---

## Community Identities

| Cluster | Identity |
|---|---|
{identity_rows}

---

## Bridge Papers

{bridge_count_total} papers have bridge\\_strength ≥ {_BRIDGE_STRENGTH_THRESHOLD}
(at least {int(_BRIDGE_STRENGTH_THRESHOLD*100)}% of their edges connect to papers in other clusters).
Full list in `community_bridges.csv`.

---

{"---".join(cluster_sections)}
"""
    path.write_text(md, encoding="utf-8")


# ── Console output ────────────────────────────────────────────────────────────

def print_console_summary(
    profiles: list[ClusterProfile],
    bridges: list[BridgePaper],
    n_papers: int,
) -> None:
    print(f"\n{'='*72}")
    print(f"  COMMUNITY PROFILES  —  NeurIPS 2024  ({n_papers} papers, {len(profiles)} clusters)")
    print(f"  ⚠  Snapshot only. 3-cluster partition is coarse at current corpus size.")
    print(f"{'='*72}\n")

    print(f"  {'Cluster':<10} {'Label':<30} {'Papers':>6} {'AvgCit':>7} {'AvgBC':>9} {'Cohesion':>9} {'Bridges':>8}")
    print(f"  {'-'*10} {'-'*30} {'-'*6} {'-'*7} {'-'*9} {'-'*9} {'-'*8}")
    for p in profiles:
        label = _cluster_label(p)
        print(
            f"  {p.cluster_id:<10} {label:<30} {p.paper_count:>6} "
            f"{p.avg_citation:>7.1f} {p.avg_betweenness:>9.5f} "
            f"{p.cohesion_ratio:>9.3f} {p.bridge_paper_count:>8}"
        )
    print()

    print("Community identities:")
    for p in profiles:
        print(f"  Cluster {p.cluster_id}: {p.identity}")
    print()

    print(f"Top bridge papers (bridge_strength >= {_BRIDGE_STRENGTH_THRESHOLD}):")
    print(f"  {'Title':<62} {'Cls':>3} {'Strength':>9} {'BC':>9}")
    print(f"  {'-'*62} {'-'*3} {'-'*9} {'-'*9}")
    for b in bridges[:10]:
        print(
            f"  {b.title[:62]:<62} {b.cluster_id:>3} "
            f"{b.bridge_strength:>9.3f} {b.betweenness_centrality:>9.5f}"
        )
    print()


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    if not os.environ.get("DATABASE_URL"):
        os.environ["DATABASE_URL"] = "sqlite:///research_platform.db"

    from db.session import engine

    print("Connecting to database…")
    with engine.connect() as conn:
        print("Building community profiles…")
        profiles, bridges, corpus_avg_cit = build_profiles(conn)

        n_papers = conn.execute(text("SELECT COUNT(*) FROM papers")).scalar() or 0

        # Load top papers per cluster for the markdown
        top_papers_map: dict[int, list[TopPaper]] = {}
        for p in profiles:
            top_papers_map[p.cluster_id] = _top_papers_by_bc(conn, p.cluster_id)

    print_console_summary(profiles, bridges, n_papers)

    write_bridges_csv(bridges, CSV_PATH)
    print(f"CSV  → {CSV_PATH}  ({len(bridges)} rows)")

    write_community_profiles(profiles, bridges, corpus_avg_cit, n_papers, MD_PATH, top_papers_map)
    print(f"MD   → {MD_PATH}")
    print()


if __name__ == "__main__":
    main()
