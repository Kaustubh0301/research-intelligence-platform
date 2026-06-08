"""
Paper endpoints for the v1 API.

GET  /api/v1/papers            - list with filters, sort, pagination + graph metrics
GET  /api/v1/papers/{id}       - full paper detail
GET  /api/v1/papers/{id}/related - related papers from graph edges
GET  /api/v1/papers/{id}/graph   - 1-hop ego-graph for mini-visualisation
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from api.deps import get_db
from api.helpers import (
    base_paper_query,
    build_paper_detail,
    fetch_top_techniques_batch,
    json_list,
    paper_summary,
)
from api.models import (
    GraphEdge,
    GraphMeta,
    GraphNode,
    GraphResponse,
    PaperDetail,
    PapersResponse,
    RelatedPaper,
    RelatedPapersResponse,
)
from db.models import (
    Conference,
    ConferenceEdition,
    Paper,
    PaperGraphMetric,
    PaperRelationship,
    PaperTechnique,
)

router = APIRouter(prefix="/api/v1", tags=["Papers"])


# ── GET /papers ───────────────────────────────────────────────────────────────

@router.get(
    "/papers",
    response_model=PapersResponse,
    summary="List and filter papers (with graph metrics and top techniques)",
)
def list_papers(
    title:             Optional[str]  = Query(None, description="Substring match on title"),
    conference:        Optional[str]  = Query(None, description="Short name e.g. NeurIPS"),
    year:              Optional[int]  = Query(None),
    cluster:           Optional[int]  = Query(None, description="Cluster ID (0, 1, 2 …)"),
    technique:         Optional[str]  = Query(None, description="Filter by canonical technique name"),
    min_citations:     Optional[int]  = Query(None, ge=0),
    presentation_type: Optional[str]  = Query(None),
    sort:              str            = Query("citations", description="citations | centrality | date | title"),
    page:              int            = Query(1, ge=1),
    per_page:          int            = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> PapersResponse:

    q = base_paper_query()

    # ── Filters ───────────────────────────────────────────────────────────────
    if title:
        q = q.where(func.lower(Paper.title).contains(title.lower()))

    if conference:
        q = q.where(func.lower(Conference.short_name) == conference.lower())

    if year:
        q = q.where(ConferenceEdition.year == year)

    if cluster is not None:
        q = q.where(PaperGraphMetric.cluster_id == cluster)

    if min_citations is not None:
        q = q.where(Paper.citation_count >= min_citations)

    if presentation_type:
        q = q.where(Paper.presentation_type == presentation_type.lower())

    # Technique filter: restrict to papers that use this canonical technique
    if technique:
        matching_paper_ids = db.scalars(
            select(PaperTechnique.paper_id)
            .where(
                func.lower(PaperTechnique.canonical_name) == technique.lower()
            )
            .distinct()
        ).all()
        if not matching_paper_ids:
            return PapersResponse(total=0, page=page, per_page=per_page, results=[])
        q = q.where(Paper.id.in_(matching_paper_ids))

    # ── Count (before pagination) ─────────────────────────────────────────────
    count_subq = q.subquery()
    total = db.scalar(select(func.count()).select_from(count_subq)) or 0

    # ── Sort ──────────────────────────────────────────────────────────────────
    sort_map = {
        "citations":  Paper.citation_count.desc(),
        "centrality": PaperGraphMetric.degree_centrality.desc(),
        "date":       Paper.year.desc(),
        "title":      Paper.title.asc(),
    }
    q = q.order_by(sort_map.get(sort, Paper.citation_count.desc()))

    # ── Pagination ────────────────────────────────────────────────────────────
    offset = (page - 1) * per_page
    q = q.offset(offset).limit(per_page)

    rows = db.execute(q).all()

    # ── Batch-fetch top techniques ────────────────────────────────────────────
    paper_ids = [row[0].id for row in rows]  # row = (Paper, conf_short, ed_year, PaperGraphMetric)
    techniques_by_paper = fetch_top_techniques_batch(db, paper_ids)

    results = [
        paper_summary(
            paper       = row[0],
            conf_short  = row[1],
            pgm         = row[3],
            top_techniques = techniques_by_paper.get(row[0].id, []),
        )
        for row in rows
    ]

    return PapersResponse(total=total, page=page, per_page=per_page, results=results)


# ── GET /papers/{id} ──────────────────────────────────────────────────────────

@router.get(
    "/papers/{paper_id}",
    response_model=PaperDetail,
    summary="Full paper detail with analysis, techniques, and graph metrics",
)
def get_paper(
    paper_id: str,
    db: Session = Depends(get_db),
) -> PaperDetail:
    row = db.execute(base_paper_query().where(Paper.id == paper_id)).first()
    if row is None:
        raise HTTPException(status_code=404, detail=f"Paper {paper_id!r} not found")

    paper, conf_short, ed_year, pgm = row
    return build_paper_detail(db, paper, conf_short, ed_year, pgm)


# ── GET /papers/{id}/related ──────────────────────────────────────────────────

@router.get(
    "/papers/{paper_id}/related",
    response_model=RelatedPapersResponse,
    summary="Papers related by shared techniques, datasets, and categories",
)
def get_related_papers(
    paper_id:   str,
    limit:      int   = Query(10, ge=1, le=50),
    min_weight: float = Query(1.0, ge=0.0),
    db: Session = Depends(get_db),
) -> RelatedPapersResponse:
    # Verify paper exists
    row = db.execute(base_paper_query().where(Paper.id == paper_id)).first()
    if row is None:
        raise HTTPException(status_code=404, detail=f"Paper {paper_id!r} not found")

    paper, _conf, _ed_year, pgm = row

    # Fetch edges — the table is undirected but stored with source < target,
    # so we query both directions and take the top by weight.
    edges = db.scalars(
        select(PaperRelationship)
        .where(
            or_(
                PaperRelationship.source_paper_id == paper_id,
                PaperRelationship.target_paper_id == paper_id,
            ),
            PaperRelationship.weight >= min_weight,
        )
        .order_by(PaperRelationship.weight.desc())
        .limit(limit)
    ).all()

    related: list[RelatedPaper] = []
    for edge in edges:
        neighbor_id = (
            edge.target_paper_id
            if edge.source_paper_id == paper_id
            else edge.source_paper_id
        )
        nb_row = db.execute(base_paper_query().where(Paper.id == neighbor_id)).first()
        if nb_row is None:
            continue
        nb_paper, nb_conf, _, nb_pgm = nb_row
        related.append(RelatedPaper(
            paper                = paper_summary(nb_paper, nb_conf, nb_pgm),
            weight               = round(edge.weight, 3),
            shared_techniques    = json_list(edge.shared_techniques),
            shared_datasets      = json_list(edge.shared_datasets),
            shared_categories    = json_list(edge.shared_categories),
            shared_methodologies = json_list(edge.shared_methodologies),
        ))

    # Graph metrics for the focal paper
    from api.helpers import _graph_metrics
    gm = _graph_metrics(pgm)

    return RelatedPapersResponse(
        paper_id     = paper_id,
        title        = paper.title,
        graph_metrics = gm,
        related      = related,
    )


# ── GET /papers/{id}/graph ────────────────────────────────────────────────────

@router.get(
    "/papers/{paper_id}/graph",
    response_model=GraphResponse,
    summary="1-hop ego-graph for the paper detail mini-visualisation",
)
def get_ego_graph(
    paper_id:   str,
    min_weight: float = Query(1.5, ge=0.0),
    max_neighbours: int = Query(30, ge=1, le=100),
    db: Session = Depends(get_db),
) -> GraphResponse:
    # Verify paper exists and fetch its metrics
    row = db.execute(base_paper_query().where(Paper.id == paper_id)).first()
    if row is None:
        raise HTTPException(status_code=404, detail=f"Paper {paper_id!r} not found")

    ego_paper, ego_conf, ego_year, ego_pgm = row

    # Fetch top edges (both directions, ordered by weight)
    edges = db.scalars(
        select(PaperRelationship)
        .where(
            or_(
                PaperRelationship.source_paper_id == paper_id,
                PaperRelationship.target_paper_id == paper_id,
            ),
            PaperRelationship.weight >= min_weight,
        )
        .order_by(PaperRelationship.weight.desc())
        .limit(max_neighbours)
    ).all()

    # Build node set: ego + neighbours
    neighbour_ids = set()
    for edge in edges:
        nid = (
            edge.target_paper_id
            if edge.source_paper_id == paper_id
            else edge.source_paper_id
        )
        neighbour_ids.add(nid)

    nodes: list[GraphNode] = [
        GraphNode(
            id                     = ego_paper.id,
            title                  = ego_paper.title,
            conference             = ego_conf,
            year                   = ego_year,
            citation_count         = ego_paper.citation_count or 0,
            cluster_id             = ego_pgm.cluster_id if ego_pgm else None,
            degree_centrality      = round(ego_pgm.degree_centrality, 6) if ego_pgm else 0.0,
            betweenness_centrality = round(ego_pgm.betweenness_centrality, 6) if ego_pgm else 0.0,
            is_ego                 = True,
        )
    ]

    for nid in neighbour_ids:
        nb_row = db.execute(base_paper_query().where(Paper.id == nid)).first()
        if nb_row is None:
            continue
        nb_paper, nb_conf, nb_year, nb_pgm = nb_row
        nodes.append(GraphNode(
            id                     = nb_paper.id,
            title                  = nb_paper.title,
            conference             = nb_conf,
            year                   = nb_year,
            citation_count         = nb_paper.citation_count or 0,
            cluster_id             = nb_pgm.cluster_id if nb_pgm else None,
            degree_centrality      = round(nb_pgm.degree_centrality, 6) if nb_pgm else 0.0,
            betweenness_centrality = round(nb_pgm.betweenness_centrality, 6) if nb_pgm else 0.0,
            is_ego                 = False,
        ))

    graph_edges = [
        GraphEdge(
            source = edge.source_paper_id,
            target = edge.target_paper_id,
            weight = round(edge.weight, 3),
        )
        for edge in edges
    ]

    weights = [e.weight for e in edges]
    return GraphResponse(
        nodes = nodes,
        edges = graph_edges,
        meta  = GraphMeta(
            node_count = len(nodes),
            edge_count = len(graph_edges),
            min_weight = round(min(weights), 3) if weights else 0.0,
            max_weight = round(max(weights), 3) if weights else 0.0,
        ),
    )
