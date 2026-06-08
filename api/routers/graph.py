"""
Graph visualisation endpoints for the v1 API.

GET /api/v1/graph           - full paper graph (nodes + edges) for react-force-graph
GET /api/v1/graph/clusters  - cluster membership summary
GET /api/v1/graph/techniques - technique entity co-occurrence graph
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from api.deps import get_db
from api.helpers import json_names
from api.models import (
    GraphEdge,
    GraphMeta,
    GraphNode,
    GraphResponse,
)
from db.models import (
    Conference,
    ConferenceEdition,
    EntityRelationship,
    Paper,
    PaperGraphMetric,
    PaperRelationship,
    TechniqueGraphMetric,
)

router = APIRouter(prefix="/api/v1", tags=["Graph"])


# ── GET /graph ────────────────────────────────────────────────────────────────

@router.get(
    "/graph",
    response_model=GraphResponse,
    summary="Full paper knowledge graph for visualisation (nodes + weighted edges)",
)
def get_full_graph(
    min_weight: float        = Query(1.5, ge=0.0, description="Minimum edge weight to include"),
    cluster:    Optional[int] = Query(None, description="Filter to a single cluster"),
    db: Session = Depends(get_db),
) -> GraphResponse:
    """
    Returns all paper nodes (with centrality + cluster) and edges above
    the weight threshold. Designed to be consumed by react-force-graph-2d.

    At 100 papers / 2,916 edges the payload is ~150 KB.
    At 400 papers with min_weight=2.0 the payload stays under ~500 KB.

    Use `cluster` to restrict to a single cluster for a focused view.
    """

    # ── Nodes ─────────────────────────────────────────────────────────────────
    node_q = (
        select(
            Paper.id,
            Paper.title,
            Paper.citation_count,
            Paper.year,
            Conference.short_name.label("conference"),
            PaperGraphMetric.cluster_id,
            PaperGraphMetric.degree_centrality,
            PaperGraphMetric.betweenness_centrality,
        )
        .join(ConferenceEdition, Paper.conference_edition_id == ConferenceEdition.id, isouter=True)
        .join(Conference, ConferenceEdition.conference_id == Conference.id, isouter=True)
        .outerjoin(PaperGraphMetric, Paper.id == PaperGraphMetric.paper_id)
    )
    if cluster is not None:
        node_q = node_q.where(PaperGraphMetric.cluster_id == cluster)

    node_rows = db.execute(node_q).all()

    nodes = [
        GraphNode(
            id                     = row.id,
            title                  = row.title,
            conference             = row.conference,
            year                   = row.year,
            citation_count         = row.citation_count or 0,
            cluster_id             = row.cluster_id,
            degree_centrality      = round(row.degree_centrality or 0.0, 6),
            betweenness_centrality = round(row.betweenness_centrality or 0.0, 6),
        )
        for row in node_rows
    ]

    # ── Edges ─────────────────────────────────────────────────────────────────
    # Collect the paper IDs in this view (may be filtered by cluster)
    node_ids = {n.id for n in nodes}

    edge_q = (
        select(
            PaperRelationship.source_paper_id,
            PaperRelationship.target_paper_id,
            PaperRelationship.weight,
        )
        .where(PaperRelationship.weight >= min_weight)
        .order_by(PaperRelationship.weight.desc())
    )

    edge_rows = db.execute(edge_q).all()

    # If cluster-filtered, keep only edges where BOTH endpoints are in the node set
    edges = [
        GraphEdge(
            source = row.source_paper_id,
            target = row.target_paper_id,
            weight = round(row.weight, 3),
        )
        for row in edge_rows
        if row.source_paper_id in node_ids and row.target_paper_id in node_ids
    ]

    weights = [e.weight for e in edges]
    return GraphResponse(
        nodes = nodes,
        edges = edges,
        meta  = GraphMeta(
            node_count = len(nodes),
            edge_count = len(edges),
            min_weight = round(min(weights), 3) if weights else 0.0,
            max_weight = round(max(weights), 3) if weights else 0.0,
        ),
    )


# ── GET /graph/clusters ───────────────────────────────────────────────────────

class ClusterDetail:
    pass


from pydantic import BaseModel
from typing import Optional as Opt

class ClusterInfo(BaseModel):
    cluster_id:    int
    paper_count:   int
    avg_degree:    float
    avg_betweenness: float


class ClustersResponse(BaseModel):
    clusters: list[ClusterInfo]


@router.get(
    "/graph/clusters",
    response_model=ClustersResponse,
    summary="Cluster membership statistics",
)
def get_clusters(db: Session = Depends(get_db)) -> ClustersResponse:
    rows = db.execute(
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

    return ClustersResponse(
        clusters=[
            ClusterInfo(
                cluster_id      = row.cluster_id,
                paper_count     = row.paper_count,
                avg_degree      = round(row.avg_degree or 0.0, 4),
                avg_betweenness = round(row.avg_betweenness or 0.0, 4),
            )
            for row in rows
        ]
    )


# ── GET /graph/techniques ─────────────────────────────────────────────────────

class TechniqueGraphNode(BaseModel):
    name:                   str
    usage_count:            int
    connected_papers_count: int
    top_cooccurring:        list[str]


class TechniqueGraphEdge(BaseModel):
    source:             str
    target:             str
    co_occurrence_count: int
    weight:             float


class TechniqueGraphResponse(BaseModel):
    nodes: list[TechniqueGraphNode]
    edges: list[TechniqueGraphEdge]
    meta:  GraphMeta


@router.get(
    "/graph/techniques",
    response_model=TechniqueGraphResponse,
    summary="Technique entity co-occurrence graph",
)
def get_technique_graph(
    min_usage:  int   = Query(2, ge=1, description="Minimum papers a technique must appear in"),
    min_weight: float = Query(1.0, ge=0.0, description="Minimum co-occurrence weight"),
    db: Session = Depends(get_db),
) -> TechniqueGraphResponse:

    # Nodes
    node_rows = db.execute(
        select(TechniqueGraphMetric)
        .where(TechniqueGraphMetric.usage_count >= min_usage)
        .order_by(TechniqueGraphMetric.usage_count.desc())
    ).scalars().all()

    nodes = [
        TechniqueGraphNode(
            name                   = tgm.canonical_name,
            usage_count            = tgm.usage_count,
            connected_papers_count = tgm.connected_papers_count,
            top_cooccurring        = json_names(tgm.top_cooccurring),
        )
        for tgm in node_rows
    ]

    node_names = {n.name for n in nodes}

    # Edges
    edge_rows = db.execute(
        select(EntityRelationship)
        .where(
            EntityRelationship.entity_type == "technique",
            EntityRelationship.weight >= min_weight,
        )
        .order_by(EntityRelationship.weight.desc())
    ).scalars().all()

    edges = [
        TechniqueGraphEdge(
            source              = er.source_entity,
            target              = er.target_entity,
            co_occurrence_count = er.co_occurrence_count,
            weight              = round(er.weight, 3),
        )
        for er in edge_rows
        if er.source_entity in node_names and er.target_entity in node_names
    ]

    weights = [e.weight for e in edges]
    return TechniqueGraphResponse(
        nodes = nodes,
        edges = edges,
        meta  = GraphMeta(
            node_count = len(nodes),
            edge_count = len(edges),
            min_weight = round(min(weights), 3) if weights else 0.0,
            max_weight = round(max(weights), 3) if weights else 0.0,
        ),
    )
