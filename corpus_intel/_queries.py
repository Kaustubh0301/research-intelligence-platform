"""
Shared read-only SQL query helpers for the corpus_intel package.

All functions accept a SQLAlchemy Connection (engine.connect()) and return
plain Python data structures.  No writes are performed anywhere in this module.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from sqlalchemy import text

# IDF tier thresholds — must mirror graph/builder.py exactly.
# If thresholds change in the graph builder, update them here too.
_IDF_GENERIC_CEILING = 3.00   # idf < 3.00  → GENERIC     (paper_count ≥ 5 at N=100)
_IDF_SHARED_CEILING  = 3.69   # idf < 3.69  → SHARED;  ≥ → SPECIALIZED

TIER_GENERIC     = "GENERIC"
TIER_SHARED      = "SHARED"
TIER_SPECIALIZED = "SPECIALIZED"


# ── Role aggregation ──────────────────────────────────────────────────────────

@dataclass
class RoleAggregation:
    """
    Per-canonical-technique role data aggregated across all papers.

    Sets deduplicate paper IDs — a paper is counted once per role even if
    multiple raw technique names normalise to the same canonical_name.
    """
    canonical_name:    str
    introducing_papers: set[str] = field(default_factory=set, repr=False)
    using_papers:       set[str] = field(default_factory=set, repr=False)
    comparing_papers:   set[str] = field(default_factory=set, repr=False)
    critiquing_papers:  set[str] = field(default_factory=set, repr=False)

    @property
    def introduces_count(self) -> int:
        return len(self.introducing_papers)

    @property
    def uses_count(self) -> int:
        return len(self.using_papers)

    @property
    def compares_count(self) -> int:
        return len(self.comparing_papers)

    @property
    def critiques_count(self) -> int:
        return len(self.critiquing_papers)

    @property
    def total_papers(self) -> int:
        """Distinct papers referencing this technique in any role."""
        return len(
            self.introducing_papers
            | self.using_papers
            | self.comparing_papers
            | self.critiquing_papers
        )

    @property
    def cross_adoption_count(self) -> int:
        """
        Papers that *use* this technique where the using paper is not the same
        paper that introduced it.  This is the correct signal for EMERGING
        classification: a different paper has adopted what another introduced.
        """
        return len(self.using_papers - self.introducing_papers)

    @property
    def adoption_ratio(self) -> float:
        """cross_adoption_count / (introduces + uses). 0.0 if neither role present."""
        denom = self.introduces_count + self.uses_count
        return round(self.cross_adoption_count / denom, 3) if denom else 0.0


def role_aggregation(conn) -> dict[str, RoleAggregation]:
    """
    Return {canonical_name: RoleAggregation} for every canonical technique.

    Uses COALESCE(canonical_name, name) so un-normalised rows are still counted.
    Strips whitespace from canonical names; skips blank values.
    """
    sql = text("""
        SELECT
            TRIM(COALESCE(canonical_name, name)) AS canon,
            role,
            paper_id
        FROM paper_techniques
        WHERE TRIM(COALESCE(canonical_name, name)) != ''
          AND COALESCE(canonical_name, name) IS NOT NULL
    """)

    result: dict[str, RoleAggregation] = {}

    for row in conn.execute(sql):
        canon = row.canon
        if not canon:
            continue
        if canon not in result:
            result[canon] = RoleAggregation(canonical_name=canon)
        agg  = result[canon]
        pid  = row.paper_id
        role = row.role
        if role == "introduces":
            agg.introducing_papers.add(pid)
        elif role == "uses":
            agg.using_papers.add(pid)
        elif role == "compares":
            agg.comparing_papers.add(pid)
        elif role == "critiques":
            agg.critiquing_papers.add(pid)

    return result


# ── IDF tier ──────────────────────────────────────────────────────────────────

def idf_tier(paper_count: int, total_papers: int) -> tuple[float, str]:
    """
    Return (idf_score, tier_label) for a technique appearing in paper_count papers.

    Mirrors the classification in graph/builder.py _build_idf_weights().
    Returns (0.0, SPECIALIZED) for degenerate inputs.
    """
    if total_papers <= 0 or paper_count <= 0:
        return (0.0, TIER_SPECIALIZED)
    idf = math.log(total_papers / paper_count)
    if idf < _IDF_GENERIC_CEILING:
        tier = TIER_GENERIC
    elif idf < _IDF_SHARED_CEILING:
        tier = TIER_SHARED
    else:
        tier = TIER_SPECIALIZED
    return (round(idf, 4), tier)


# ── Corpus helpers ────────────────────────────────────────────────────────────

def corpus_size(conn) -> int:
    """Total number of papers in the papers table."""
    return conn.execute(text("SELECT COUNT(*) FROM papers")).scalar() or 0


def paper_titles(conn) -> dict[str, str]:
    """Return {paper_id: title} for all papers."""
    rows = conn.execute(text("SELECT id, title FROM papers")).all()
    return {row.id: row.title for row in rows}
