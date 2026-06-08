"""
GET /api/v1/techniques

Technique browser: canonical technique names, usage counts, role breakdown,
and top co-occurring techniques. Used by the search filter combobox.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from api.deps import get_db
from api.helpers import json_names
from api.models import TechniqueItem, TechniquesResponse
from db.models import PaperTechnique, TechniqueGraphMetric

router = APIRouter(prefix="/api/v1", tags=["Techniques"])


@router.get(
    "/techniques",
    response_model=TechniquesResponse,
    summary="Canonical technique list with usage counts and co-occurrence data",
)
def list_techniques(
    q:          Optional[str] = Query(None, description="Substring search on technique name"),
    min_papers: int           = Query(1, ge=1, description="Minimum papers to include"),
    sort:       str           = Query("usage", description="usage | papers"),
    page:       int           = Query(1, ge=1),
    per_page:   int           = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> TechniquesResponse:
    """
    Returns canonical techniques from technique_graph_metrics (built by build_graph_v2.py).
    Falls back to a live aggregate from paper_techniques if graph metrics are not populated.
    """

    # Check if graph metrics table is populated
    metric_count = db.scalar(select(func.count()).select_from(TechniqueGraphMetric)) or 0

    if metric_count > 0:
        # Preferred path: use pre-computed metrics
        metric_q = select(TechniqueGraphMetric).where(
            TechniqueGraphMetric.usage_count >= min_papers
        )
        if q:
            metric_q = metric_q.where(
                func.lower(TechniqueGraphMetric.canonical_name).contains(q.lower())
            )
        if sort == "papers":
            metric_q = metric_q.order_by(TechniqueGraphMetric.connected_papers_count.desc())
        else:
            metric_q = metric_q.order_by(TechniqueGraphMetric.usage_count.desc())

        # Count total before pagination
        all_rows = db.scalars(metric_q).all()
        total = len(all_rows)
        offset = (page - 1) * per_page
        page_rows = all_rows[offset : offset + per_page]

        # Role breakdown per technique (batch query for the page)
        canonical_names = [row.canonical_name for row in page_rows]
        role_counts: dict[str, dict[str, int]] = {name: {"introduces": 0, "uses": 0} for name in canonical_names}
        if canonical_names:
            role_rows = db.execute(
                select(
                    PaperTechnique.canonical_name,
                    PaperTechnique.role,
                    func.count(PaperTechnique.id).label("cnt"),
                )
                .where(
                    PaperTechnique.canonical_name.in_(canonical_names),
                    PaperTechnique.role.in_(["introduces", "uses"]),
                )
                .group_by(PaperTechnique.canonical_name, PaperTechnique.role)
            ).all()
            for row in role_rows:
                if row.canonical_name in role_counts:
                    role_counts[row.canonical_name][row.role] = row.cnt

        techniques = [
            TechniqueItem(
                canonical_name         = row.canonical_name,
                usage_count            = row.usage_count,
                connected_papers_count = row.connected_papers_count,
                top_cooccurring        = json_names(row.top_cooccurring),
                introduces_count       = role_counts[row.canonical_name]["introduces"],
                uses_count             = role_counts[row.canonical_name]["uses"],
            )
            for row in page_rows
        ]

    else:
        # Fallback: aggregate directly from paper_techniques
        agg_q = (
            select(
                PaperTechnique.canonical_name,
                func.count(PaperTechnique.paper_id.distinct()).label("usage_count"),
            )
            .where(PaperTechnique.canonical_name.isnot(None))
            .group_by(PaperTechnique.canonical_name)
            .having(func.count(PaperTechnique.paper_id.distinct()) >= min_papers)
        )
        if q:
            agg_q = agg_q.where(
                func.lower(PaperTechnique.canonical_name).contains(q.lower())
            )
        agg_q = agg_q.order_by(func.count(PaperTechnique.paper_id.distinct()).desc())

        all_rows = db.execute(agg_q).all()
        total = len(all_rows)
        offset = (page - 1) * per_page
        page_rows_raw = all_rows[offset : offset + per_page]

        techniques = [
            TechniqueItem(
                canonical_name         = row.canonical_name,
                usage_count            = row.usage_count,
                connected_papers_count = 0,
                top_cooccurring        = [],
            )
            for row in page_rows_raw
        ]

    return TechniquesResponse(
        total      = total,
        page       = page,
        per_page   = per_page,
        techniques = techniques,
    )
