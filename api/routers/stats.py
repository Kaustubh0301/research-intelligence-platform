"""
GET /api/v1/stats

Dashboard aggregates: corpus counts, top techniques, cluster overview,
top papers by citation, conference breakdown.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from api.deps import get_db
from api.models import (
    ClusterStat,
    ConferenceStat,
    StatsResponse,
    TechniqueStat,
    TopPaper,
)
from api.helpers import fetch_primary_categories_batch
from db.models import (
    Conference,
    ConferenceEdition,
    EntityRelationship,
    Paper,
    PaperCategory,
    PaperGraphMetric,
    PaperRelationship,
    PaperTechnique,
)

router = APIRouter(prefix="/api/v1", tags=["Stats"])


@router.get("/stats", response_model=StatsResponse, summary="Dashboard corpus statistics")
def get_stats(db: Session = Depends(get_db)) -> StatsResponse:
    """
    Returns all data needed to render the dashboard:
    - Scalar counts (papers, edges, techniques, clusters)
    - Top 15 techniques by unique paper count
    - Cluster overview with paper count + avg centrality
    - Top 10 papers by citation count (with graph metrics)
    - Conference breakdown for the donut chart
    """

    # ── Scalar counts ─────────────────────────────────────────────────────────
    total_papers = db.scalar(select(func.count()).select_from(Paper)) or 0

    total_edges = db.scalar(select(func.count()).select_from(PaperRelationship)) or 0

    total_techniques = db.scalar(
        select(func.count(PaperTechnique.canonical_name.distinct()))
        .where(PaperTechnique.canonical_name.isnot(None))
    ) or 0

    total_clusters = db.scalar(
        select(func.count(PaperGraphMetric.cluster_id.distinct()))
        .where(PaperGraphMetric.cluster_id.isnot(None))
    ) or 0

    # ── Top techniques ────────────────────────────────────────────────────────
    tech_rows = db.execute(
        select(
            PaperTechnique.canonical_name,
            func.count(PaperTechnique.paper_id.distinct()).label("paper_count"),
        )
        .where(PaperTechnique.canonical_name.isnot(None))
        .group_by(PaperTechnique.canonical_name)
        .order_by(func.count(PaperTechnique.paper_id.distinct()).desc())
        .limit(15)
    ).all()

    top_techniques = [
        TechniqueStat(canonical_name=row.canonical_name, paper_count=row.paper_count)
        for row in tech_rows
    ]

    # ── Cluster overview ──────────────────────────────────────────────────────
    cluster_rows = db.execute(
        select(
            PaperGraphMetric.cluster_id,
            func.count(PaperGraphMetric.paper_id).label("paper_count"),
            func.avg(PaperGraphMetric.degree_centrality).label("avg_degree"),
            func.avg(PaperGraphMetric.betweenness_centrality).label("avg_betweenness"),
        )
        .where(PaperGraphMetric.cluster_id.isnot(None))
        .group_by(PaperGraphMetric.cluster_id)
        .order_by(PaperGraphMetric.cluster_id)
    ).all()

    clusters = [
        ClusterStat(
            cluster_id      = row.cluster_id,
            paper_count     = row.paper_count,
            avg_degree      = round(row.avg_degree or 0.0, 4),
            avg_betweenness = round(row.avg_betweenness or 0.0, 4),
        )
        for row in cluster_rows
    ]

    # ── Top papers by citation ────────────────────────────────────────────────
    top_paper_rows = db.execute(
        select(
            Paper.id,
            Paper.title,
            Paper.citation_count,
            Paper.presentation_type,
            Conference.short_name.label("conf_short"),
            ConferenceEdition.year.label("ed_year"),
            PaperGraphMetric.cluster_id,
            PaperGraphMetric.degree_centrality,
        )
        .join(ConferenceEdition, Paper.conference_edition_id == ConferenceEdition.id, isouter=True)
        .join(Conference, ConferenceEdition.conference_id == Conference.id, isouter=True)
        .outerjoin(PaperGraphMetric, Paper.id == PaperGraphMetric.paper_id)
        .order_by(Paper.citation_count.desc())
        .limit(10)
    ).all()

    top_paper_ids = [row.id for row in top_paper_rows]
    categories_by_paper = fetch_primary_categories_batch(db, top_paper_ids)

    top_papers = [
        TopPaper(
            id                = row.id,
            title             = row.title,
            citation_count    = row.citation_count or 0,
            conference        = row.conf_short,
            year              = row.ed_year,
            presentation_type = row.presentation_type,
            cluster_id        = row.cluster_id,
            degree_centrality = round(row.degree_centrality or 0.0, 4),
            primary_category  = categories_by_paper.get(row.id),
        )
        for row in top_paper_rows
    ]

    # ── Conference breakdown ──────────────────────────────────────────────────
    conf_rows = db.execute(
        select(
            Conference.short_name,
            ConferenceEdition.year,
            func.count(Paper.id).label("count"),
        )
        .join(ConferenceEdition, Paper.conference_edition_id == ConferenceEdition.id)
        .join(Conference, ConferenceEdition.conference_id == Conference.id)
        .group_by(Conference.short_name, ConferenceEdition.year)
        .order_by(Conference.short_name, ConferenceEdition.year)
    ).all()

    conferences = [
        ConferenceStat(short_name=row.short_name, year=row.year, count=row.count)
        for row in conf_rows
    ]

    return StatsResponse(
        total_papers     = total_papers,
        total_edges      = total_edges,
        total_techniques = total_techniques,
        total_clusters   = total_clusters,
        conferences      = conferences,
        clusters         = clusters,
        top_techniques   = top_techniques,
        top_papers       = top_papers,
    )
