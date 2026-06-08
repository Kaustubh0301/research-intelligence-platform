"""
Research Intelligence Platform — FastAPI search layer.

Run:
    cd /path/to/research-intelligence-platfrom
    source .venv/bin/activate
    export DATABASE_URL=sqlite:///research_platform.db
    uvicorn api.search:app --reload --port 8000

Interactive docs:  http://127.0.0.1:8000/docs
"""

from __future__ import annotations

import json
import os
from collections import defaultdict
from typing import Any, Generator, Optional

from fastapi import Depends, FastAPI, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, or_, select, text
from sqlalchemy.orm import Session

from graph.explainer import explain as _explain_relationship

from db.models import (
    Author,
    Conference,
    ConferenceEdition,
    EntityRelationship,
    Paper,
    PaperAnalysisRecord,
    PaperAuthor,
    PaperCategory,
    PaperDataset,
    PaperGraphMetric,
    PaperMethodology,
    PaperRelationship,
    PaperSection,
    PaperTechnique,
    TechniqueGraphMetric,
)
from db.session import get_session

# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Research Intelligence Platform",
    description=(
        "Query AI/ML research papers, analyses, techniques, datasets, and categories "
        "extracted from NeurIPS, ICML, ICLR, CVPR, ACL, and more."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)


# ── DB dependency ─────────────────────────────────────────────────────────────

def get_db() -> Generator[Session, None, None]:
    with get_session() as session:
        yield session


# ── Pydantic response models ──────────────────────────────────────────────────

class AuthorOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id:                  str
    full_name:           str
    position:            int
    affiliation:         Optional[str] = None
    semantic_scholar_id: Optional[str] = None
    homepage:            Optional[str] = None


class TechniqueOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    name:           str
    canonical_name: Optional[str] = None
    role:           str   # introduces | uses | compares | critiques


class DatasetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    name:           str
    canonical_name: Optional[str] = None
    task:           Optional[str] = None
    description:    Optional[str] = None


class CategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    name:           str
    canonical_name: Optional[str] = None
    confidence:     float = 1.0


class MethodologyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    name: str


class AnalysisOut(BaseModel):
    summary:     Optional[str]       = None
    advantages:  list[str]           = Field(default_factory=list)
    limitations: list[str]           = Field(default_factory=list)
    future_work: list[str]           = Field(default_factory=list)
    use_cases:   list[str]           = Field(default_factory=list)
    model:       Optional[str]       = None


class PaperSummary(BaseModel):
    """Lightweight paper representation used in list/search results."""
    model_config = ConfigDict(from_attributes=True)
    id:                       str
    title:                    str
    year:                     int
    conference:               Optional[str] = None
    presentation_type:        Optional[str] = None
    citation_count:           int           = 0
    influential_citation_count: int         = 0
    is_open_access:           bool          = False
    has_pdf:                  bool          = False
    abstract_snippet:         Optional[str] = None   # first 300 chars


class PaperDetail(BaseModel):
    """Full paper detail including all analysis tables."""
    model_config = ConfigDict(from_attributes=True)
    id:                       str
    title:                    str
    abstract:                 Optional[str] = None
    year:                     int
    conference:               Optional[str] = None
    edition_year:             Optional[int] = None
    presentation_type:        Optional[str] = None
    citation_count:           int           = 0
    influential_citation_count: int         = 0
    is_open_access:           bool          = False
    pdf_url:                  Optional[str] = None
    openreview_id:            Optional[str] = None
    semantic_scholar_id:      Optional[str] = None
    arxiv_id:                 Optional[str] = None
    # Related data
    authors:       list[AuthorOut]     = Field(default_factory=list)
    techniques:    list[TechniqueOut]  = Field(default_factory=list)
    datasets:      list[DatasetOut]    = Field(default_factory=list)
    categories:    list[CategoryOut]   = Field(default_factory=list)
    methodologies: list[MethodologyOut] = Field(default_factory=list)
    analysis:      Optional[AnalysisOut] = None


class PapersResponse(BaseModel):
    total:   int
    limit:   int
    offset:  int
    results: list[PaperSummary]


class FrequencyItem(BaseModel):
    name:        str
    count:       int
    paper_count: int


class FrequencyResponse(BaseModel):
    total:   int
    results: list[FrequencyItem]


class SearchMatch(BaseModel):
    """A paper returned by /search, with match metadata."""
    paper:       PaperSummary
    match_score: float
    matched_in:  list[str]   # e.g. ["title", "technique:LoRA"]


class SearchResponse(BaseModel):
    query:   str
    total:   int
    results: list[SearchMatch]


# ── Graph response models ─────────────────────────────────────────────────────

class RelatedPaper(BaseModel):
    paper:               PaperSummary
    weight:              float
    shared_techniques:   list[str] = Field(default_factory=list)
    shared_datasets:     list[str] = Field(default_factory=list)
    shared_categories:   list[str] = Field(default_factory=list)
    shared_methodologies: list[str] = Field(default_factory=list)


class RelatedPapersResponse(BaseModel):
    paper_id: str
    title:    str
    metrics:  Optional[dict] = None    # cluster_id, centrality scores
    related:  list[RelatedPaper]


class CooccurringEntity(BaseModel):
    name:               str
    co_occurrence_count: int
    weight:             float


class TechniqueRelatedResponse(BaseModel):
    technique:            str
    usage_count:          int
    connected_papers_count: int
    papers:               list[PaperSummary]
    co_occurring:         list[CooccurringEntity]


class ClusterSummary(BaseModel):
    cluster_id:           int
    paper_count:          int
    dominant_categories:  list[str]
    dominant_techniques:  list[str]
    top_papers:           list[PaperSummary]   # top 5 by betweenness centrality


class GraphStatsResponse(BaseModel):
    total_papers:          int
    total_paper_edges:     int
    total_entity_edges:    int
    entity_edge_breakdown: dict[str, int]
    isolated_papers:       int
    avg_edge_weight:       float
    max_edge_weight:       float
    cluster_count:         int
    largest_cluster_size:  int
    tracked_techniques:    int
    most_central_paper:    Optional[PaperSummary] = None


class TopClustersResponse(BaseModel):
    clusters: list[ClusterSummary]


# ── Relationship explanation models ──────────────────────────────────────────

class ConceptSignalOut(BaseModel):
    name:         str
    signal_tier:  str    # GENERIC | SHARED | SPECIALIZED
    idf_score:    float
    paper_a_role: str    # introduces | uses | absent
    paper_b_role: str


class RelationshipExplanationResponse(BaseModel):
    paper_a_id:    str
    paper_b_id:    str
    paper_a_title: str
    paper_b_title: str

    relationship_score: float
    technique_score:    Optional[float] = None
    dataset_score:      Optional[float] = None
    category_score:     Optional[float] = None

    shared_concepts:      list[ConceptSignalOut] = Field(default_factory=list)
    shared_categories:    list[str]              = Field(default_factory=list)
    shared_datasets:      list[str]              = Field(default_factory=list)
    shared_methodologies: list[str]              = Field(default_factory=list)

    differences:         list[str] = Field(default_factory=list)
    research_connection: str


# ── Internal helpers ──────────────────────────────────────────────────────────

def _json_list(raw: Optional[str]) -> list[str]:
    """Safely parse a JSON-encoded list stored in a Text column."""
    if not raw:
        return []
    try:
        val = json.loads(raw)
        return val if isinstance(val, list) else []
    except (json.JSONDecodeError, TypeError):
        return []


def _paper_summary(paper: Paper, conf_short: Optional[str]) -> PaperSummary:
    abstract = paper.abstract or ""
    return PaperSummary(
        id                         = paper.id,
        title                      = paper.title,
        year                       = paper.year,
        conference                 = conf_short,
        presentation_type          = paper.presentation_type,
        citation_count             = paper.citation_count or 0,
        influential_citation_count = paper.influential_citation_count or 0,
        is_open_access             = paper.is_open_access or False,
        has_pdf                    = paper.pdf_local_path is not None,
        abstract_snippet           = abstract[:300] if abstract else None,
    )


def _build_paper_detail(
    session: Session,
    paper: Paper,
    conf_short: Optional[str],
    ed_year: Optional[int],
) -> PaperDetail:
    # Authors
    author_rows = session.execute(
        select(Author, PaperAuthor.position, PaperAuthor.affiliation)
        .join(PaperAuthor, Author.id == PaperAuthor.author_id)
        .where(PaperAuthor.paper_id == paper.id)
        .order_by(PaperAuthor.position)
    ).all()
    authors = [
        AuthorOut(
            id=a.id, full_name=a.full_name, position=pos, affiliation=aff,
            semantic_scholar_id=a.semantic_scholar_id, homepage=a.homepage,
        )
        for a, pos, aff in author_rows
    ]

    # Techniques
    techs = session.scalars(
        select(PaperTechnique).where(PaperTechnique.paper_id == paper.id)
    ).all()

    # Datasets
    datasets = session.scalars(
        select(PaperDataset).where(PaperDataset.paper_id == paper.id)
    ).all()

    # Categories
    cats = session.scalars(
        select(PaperCategory).where(PaperCategory.paper_id == paper.id)
    ).all()

    # Methodologies
    meths = session.scalars(
        select(PaperMethodology).where(PaperMethodology.paper_id == paper.id)
    ).all()

    # Analysis
    analysis_row = session.scalar(
        select(PaperAnalysisRecord).where(PaperAnalysisRecord.paper_id == paper.id)
    )
    analysis = None
    if analysis_row:
        analysis = AnalysisOut(
            summary     = analysis_row.summary,
            advantages  = _json_list(analysis_row.advantages),
            limitations = _json_list(analysis_row.limitations),
            future_work = _json_list(analysis_row.future_work),
            use_cases   = _json_list(analysis_row.use_cases),
            model       = analysis_row.model,
        )

    return PaperDetail(
        id                         = paper.id,
        title                      = paper.title,
        abstract                   = paper.abstract,
        year                       = paper.year,
        conference                 = conf_short,
        edition_year               = ed_year,
        presentation_type          = paper.presentation_type,
        citation_count             = paper.citation_count or 0,
        influential_citation_count = paper.influential_citation_count or 0,
        is_open_access             = paper.is_open_access or False,
        pdf_url                    = paper.pdf_url,
        openreview_id              = paper.openreview_id,
        semantic_scholar_id        = paper.semantic_scholar_id,
        arxiv_id                   = paper.arxiv_id,
        authors                    = authors,
        techniques                 = [TechniqueOut(name=t.name, canonical_name=t.canonical_name, role=t.role) for t in techs],
        datasets                   = [DatasetOut(name=d.name, canonical_name=d.canonical_name, task=d.task, description=d.description) for d in datasets],
        categories                 = [CategoryOut(name=c.name, canonical_name=c.canonical_name, confidence=c.confidence) for c in cats],
        methodologies              = [MethodologyOut(name=m.name) for m in meths],
        analysis                   = analysis,
    )


def _base_paper_query():
    """Base SELECT that joins papers → conference_edition → conference."""
    return (
        select(Paper, Conference.short_name, ConferenceEdition.year)
        .join(ConferenceEdition, Paper.conference_edition_id == ConferenceEdition.id, isouter=True)
        .join(Conference, ConferenceEdition.conference_id == Conference.id, isouter=True)
    )


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/", include_in_schema=False)
def root():
    return {"message": "Research Intelligence Platform API", "docs": "/docs"}


# ── GET /papers ───────────────────────────────────────────────────────────────

@app.get(
    "/papers",
    response_model=PapersResponse,
    summary="List and filter papers",
    tags=["Papers"],
)
def list_papers(
    title:             Optional[str]  = Query(None, description="Substring search on title (case-insensitive)"),
    conference:        Optional[str]  = Query(None, description="Conference short name, e.g. NeurIPS"),
    year:              Optional[int]  = Query(None, description="Publication year, e.g. 2024"),
    min_citations:     Optional[int]  = Query(None, ge=0, description="Minimum citation count"),
    max_citations:     Optional[int]  = Query(None, ge=0, description="Maximum citation count"),
    presentation_type: Optional[str]  = Query(None, description="oral | spotlight | poster | other"),
    has_pdf:           Optional[bool] = Query(None, description="Only papers with downloaded PDFs"),
    has_analysis:      Optional[bool] = Query(None, description="Only papers with LLM analysis"),
    order_by:          str            = Query("citation_count", description="citation_count | year | title"),
    descending:        bool           = Query(True,  description="Sort direction"),
    limit:             int            = Query(20,  ge=1, le=200, description="Page size"),
    offset:            int            = Query(0,   ge=0,         description="Pagination offset"),
    db: Session = Depends(get_db),
) -> PapersResponse:
    q = _base_paper_query()

    if title:
        q = q.where(func.lower(Paper.title).contains(title.lower()))
    if conference:
        q = q.where(func.lower(Conference.short_name) == conference.lower())
    if year:
        q = q.where(ConferenceEdition.year == year)
    if min_citations is not None:
        q = q.where(Paper.citation_count >= min_citations)
    if max_citations is not None:
        q = q.where(Paper.citation_count <= max_citations)
    if presentation_type:
        q = q.where(Paper.presentation_type == presentation_type.lower())
    if has_pdf is True:
        q = q.where(Paper.pdf_local_path.is_not(None))
    elif has_pdf is False:
        q = q.where(Paper.pdf_local_path.is_(None))
    if has_analysis is True:
        q = q.where(
            Paper.id.in_(select(PaperAnalysisRecord.paper_id))
        )

    # Count total before pagination
    count_q = select(func.count()).select_from(q.subquery())
    total = db.scalar(count_q) or 0

    # Sort
    sort_map = {
        "citation_count": Paper.citation_count,
        "year":           Paper.year,
        "title":          Paper.title,
    }
    sort_col = sort_map.get(order_by, Paper.citation_count)
    q = q.order_by(sort_col.desc() if descending else sort_col.asc())
    q = q.offset(offset).limit(limit)

    rows = db.execute(q).all()
    return PapersResponse(
        total   = total,
        limit   = limit,
        offset  = offset,
        results = [_paper_summary(p, conf) for p, conf, _yr in rows],
    )


# ── GET /papers/{paper_id} ────────────────────────────────────────────────────

@app.get(
    "/papers/{paper_id}",
    response_model=PaperDetail,
    summary="Full paper detail with analysis",
    tags=["Papers"],
)
def get_paper(
    paper_id: str,
    db: Session = Depends(get_db),
) -> PaperDetail:
    q = _base_paper_query().where(Paper.id == paper_id)
    row = db.execute(q).first()
    if row is None:
        raise HTTPException(status_code=404, detail=f"Paper {paper_id!r} not found")
    paper, conf_short, ed_year = row
    return _build_paper_detail(db, paper, conf_short, ed_year)


# ── GET /techniques ───────────────────────────────────────────────────────────

@app.get(
    "/techniques",
    response_model=FrequencyResponse,
    summary="Techniques with paper frequency counts",
    tags=["Knowledge Graph"],
)
def list_techniques(
    role:   Optional[str] = Query(None, description="introduces | uses | compares | critiques"),
    search: Optional[str] = Query(None, description="Substring search on technique name"),
    limit:  int           = Query(50, ge=1, le=500),
    offset: int           = Query(0,  ge=0),
    db: Session = Depends(get_db),
) -> FrequencyResponse:
    q = (
        select(
            PaperTechnique.name,
            PaperTechnique.role,
            func.count(PaperTechnique.id).label("count"),
            func.count(PaperTechnique.paper_id.distinct()).label("paper_count"),
        )
        .group_by(PaperTechnique.name, PaperTechnique.role)
    )
    if role:
        q = q.where(PaperTechnique.role == role.lower())
    if search:
        q = q.where(func.lower(PaperTechnique.name).contains(search.lower()))

    # Total distinct names
    all_rows = db.execute(q.order_by(text("count DESC"))).all()
    # Collapse roles: aggregate paper_count per name
    name_counts: dict[str, int] = defaultdict(int)
    for row in all_rows:
        name_counts[row.name] += row.paper_count

    # Sorted by paper_count desc
    sorted_items = sorted(name_counts.items(), key=lambda x: x[1], reverse=True)
    total = len(sorted_items)
    page  = sorted_items[offset : offset + limit]

    return FrequencyResponse(
        total   = total,
        results = [FrequencyItem(name=name, count=cnt, paper_count=cnt) for name, cnt in page],
    )


# ── GET /datasets ─────────────────────────────────────────────────────────────

@app.get(
    "/datasets",
    response_model=FrequencyResponse,
    summary="Datasets with paper frequency counts",
    tags=["Knowledge Graph"],
)
def list_datasets(
    search: Optional[str] = Query(None, description="Substring search on dataset name"),
    limit:  int           = Query(50, ge=1, le=500),
    offset: int           = Query(0,  ge=0),
    db: Session = Depends(get_db),
) -> FrequencyResponse:
    q = (
        select(
            PaperDataset.name,
            func.count(PaperDataset.id).label("count"),
            func.count(PaperDataset.paper_id.distinct()).label("paper_count"),
        )
        .group_by(PaperDataset.name)
    )
    if search:
        q = q.where(func.lower(PaperDataset.name).contains(search.lower()))

    rows = db.execute(q.order_by(text("paper_count DESC"))).all()
    total = len(rows)
    page  = rows[offset : offset + limit]

    return FrequencyResponse(
        total   = total,
        results = [FrequencyItem(name=r.name, count=r.count, paper_count=r.paper_count) for r in page],
    )


# ── GET /categories ───────────────────────────────────────────────────────────

@app.get(
    "/categories",
    response_model=FrequencyResponse,
    summary="Research categories with paper frequency counts",
    tags=["Knowledge Graph"],
)
def list_categories(
    search: Optional[str] = Query(None, description="Substring search on category name"),
    limit:  int           = Query(50, ge=1, le=500),
    offset: int           = Query(0,  ge=0),
    db: Session = Depends(get_db),
) -> FrequencyResponse:
    q = (
        select(
            PaperCategory.name,
            func.count(PaperCategory.id).label("count"),
            func.count(PaperCategory.paper_id.distinct()).label("paper_count"),
        )
        .group_by(PaperCategory.name)
    )
    if search:
        q = q.where(func.lower(PaperCategory.name).contains(search.lower()))

    rows = db.execute(q.order_by(text("paper_count DESC"))).all()
    total = len(rows)
    page  = rows[offset : offset + limit]

    return FrequencyResponse(
        total   = total,
        results = [FrequencyItem(name=r.name, count=r.count, paper_count=r.paper_count) for r in page],
    )


# ── GET /methodologies ────────────────────────────────────────────────────────

@app.get(
    "/methodologies",
    response_model=FrequencyResponse,
    summary="Research methodologies with paper frequency counts",
    tags=["Knowledge Graph"],
)
def list_methodologies(
    search: Optional[str] = Query(None, description="Substring search on methodology name"),
    limit:  int           = Query(50, ge=1, le=500),
    offset: int           = Query(0,  ge=0),
    db: Session = Depends(get_db),
) -> FrequencyResponse:
    q = (
        select(
            PaperMethodology.name,
            func.count(PaperMethodology.id).label("count"),
            func.count(PaperMethodology.paper_id.distinct()).label("paper_count"),
        )
        .group_by(PaperMethodology.name)
    )
    if search:
        q = q.where(func.lower(PaperMethodology.name).contains(search.lower()))

    rows = db.execute(q.order_by(text("paper_count DESC"))).all()
    total = len(rows)
    page  = rows[offset : offset + limit]

    return FrequencyResponse(
        total   = total,
        results = [FrequencyItem(name=r.name, count=r.count, paper_count=r.paper_count) for r in page],
    )


# ── GET /search ───────────────────────────────────────────────────────────────

@app.get(
    "/search",
    response_model=SearchResponse,
    summary="Full-text cross-field search across papers, techniques, datasets, and categories",
    tags=["Search"],
)
def search(
    q:      str           = Query(..., min_length=2, description="Search query"),
    limit:  int           = Query(20, ge=1, le=100),
    offset: int           = Query(0,  ge=0),
    db: Session = Depends(get_db),
) -> SearchResponse:
    """
    Searches across four signal sources and returns ranked, deduplicated papers.

    Scoring (additive):
      +40  exact title match (case-insensitive)
      +20  title contains query
      +15  category name contains query
      +12  technique name contains query
      +10  dataset name contains query
      +log(citations+1)  citation boost (tiebreaker)

    Results are deduplicated by paper_id and sorted by score descending.
    """
    term = q.strip().lower()
    if not term:
        raise HTTPException(status_code=400, detail="Query must be non-empty")

    # Collect paper_id → (score, matched_in list, Paper, conf_short)
    scores:   dict[str, float]      = defaultdict(float)
    matches:  dict[str, list[str]]  = defaultdict(list)
    paper_cache: dict[str, tuple[Paper, Optional[str]]] = {}

    def _cache_paper(paper: Paper, conf: Optional[str]):
        if paper.id not in paper_cache:
            paper_cache[paper.id] = (paper, conf)

    # ── Signal 1: title match ──────────────────────────────────────────────
    title_rows = db.execute(
        _base_paper_query().where(func.lower(Paper.title).contains(term))
    ).all()
    for paper, conf, _yr in title_rows:
        _cache_paper(paper, conf)
        title_lower = paper.title.lower()
        if title_lower == term:
            scores[paper.id] += 40
            matches[paper.id].append("title:exact")
        else:
            scores[paper.id] += 20
            matches[paper.id].append("title")

    # ── Signal 2: category match ───────────────────────────────────────────
    cat_rows = db.execute(
        select(PaperCategory.paper_id, PaperCategory.name)
        .where(func.lower(PaperCategory.name).contains(term))
    ).all()
    cat_paper_ids = [r.paper_id for r in cat_rows]
    if cat_paper_ids:
        paper_rows = db.execute(
            _base_paper_query().where(Paper.id.in_(cat_paper_ids))
        ).all()
        cat_names_by_paper: dict[str, list[str]] = defaultdict(list)
        for r in cat_rows:
            cat_names_by_paper[r.paper_id].append(r.name)
        for paper, conf, _yr in paper_rows:
            _cache_paper(paper, conf)
            for name in cat_names_by_paper[paper.id]:
                scores[paper.id] += 15
                matches[paper.id].append(f"category:{name}")

    # ── Signal 3: technique match ──────────────────────────────────────────
    tech_rows = db.execute(
        select(PaperTechnique.paper_id, PaperTechnique.name)
        .where(func.lower(PaperTechnique.name).contains(term))
    ).all()
    tech_paper_ids = [r.paper_id for r in tech_rows]
    if tech_paper_ids:
        paper_rows = db.execute(
            _base_paper_query().where(Paper.id.in_(tech_paper_ids))
        ).all()
        tech_names_by_paper: dict[str, list[str]] = defaultdict(list)
        for r in tech_rows:
            tech_names_by_paper[r.paper_id].append(r.name)
        for paper, conf, _yr in paper_rows:
            _cache_paper(paper, conf)
            for name in tech_names_by_paper[paper.id]:
                scores[paper.id] += 12
                matches[paper.id].append(f"technique:{name}")

    # ── Signal 4: dataset match ────────────────────────────────────────────
    ds_rows = db.execute(
        select(PaperDataset.paper_id, PaperDataset.name)
        .where(func.lower(PaperDataset.name).contains(term))
    ).all()
    ds_paper_ids = [r.paper_id for r in ds_rows]
    if ds_paper_ids:
        paper_rows = db.execute(
            _base_paper_query().where(Paper.id.in_(ds_paper_ids))
        ).all()
        ds_names_by_paper: dict[str, list[str]] = defaultdict(list)
        for r in ds_rows:
            ds_names_by_paper[r.paper_id].append(r.name)
        for paper, conf, _yr in paper_rows:
            _cache_paper(paper, conf)
            for name in ds_names_by_paper[paper.id]:
                scores[paper.id] += 10
                matches[paper.id].append(f"dataset:{name}")

    # ── Rank and paginate ──────────────────────────────────────────────────
    import math
    ranked = sorted(
        scores.keys(),
        key=lambda pid: (
            scores[pid]
            + math.log1p(paper_cache[pid][0].citation_count or 0)
        ),
        reverse=True,
    )

    total  = len(ranked)
    page   = ranked[offset : offset + limit]

    results = []
    for pid in page:
        paper, conf = paper_cache[pid]
        results.append(SearchMatch(
            paper       = _paper_summary(paper, conf),
            match_score = round(scores[pid], 2),
            matched_in  = matches[pid],
        ))

    return SearchResponse(query=q, total=total, results=results)


# ── GET /papers/{id}/related ──────────────────────────────────────────────────

@app.get(
    "/papers/{paper_id}/related",
    response_model=RelatedPapersResponse,
    summary="Papers related by shared techniques, datasets, categories, and methodologies",
    tags=["Graph"],
)
def get_related_papers(
    paper_id: str,
    limit:     int           = Query(10, ge=1, le=50),
    min_weight: float        = Query(1.0, ge=0, description="Minimum edge weight to include"),
    db: Session = Depends(get_db),
) -> RelatedPapersResponse:
    paper_row = db.execute(
        _base_paper_query().where(Paper.id == paper_id)
    ).first()
    if paper_row is None:
        raise HTTPException(status_code=404, detail=f"Paper {paper_id!r} not found")
    paper, conf_short, _ = paper_row

    # Fetch edges in both directions
    edges = db.execute(
        select(PaperRelationship)
        .where(
            (PaperRelationship.source_paper_id == paper_id) |
            (PaperRelationship.target_paper_id == paper_id),
            PaperRelationship.weight >= min_weight,
        )
        .order_by(PaperRelationship.weight.desc())
        .limit(limit)
    ).scalars().all()

    related: list[RelatedPaper] = []
    for edge in edges:
        neighbor_id = (
            edge.target_paper_id
            if edge.source_paper_id == paper_id
            else edge.source_paper_id
        )
        nb_row = db.execute(_base_paper_query().where(Paper.id == neighbor_id)).first()
        if nb_row is None:
            continue
        nb_paper, nb_conf, _ = nb_row
        related.append(RelatedPaper(
            paper               = _paper_summary(nb_paper, nb_conf),
            weight              = edge.weight,
            shared_techniques   = _json_list(edge.shared_techniques),
            shared_datasets     = _json_list(edge.shared_datasets),
            shared_categories   = _json_list(edge.shared_categories),
            shared_methodologies = _json_list(edge.shared_methodologies),
        ))

    # Fetch graph metrics
    metrics_row = db.get(PaperGraphMetric, paper_id)
    metrics = None
    if metrics_row:
        metrics = {
            "cluster_id":             metrics_row.cluster_id,
            "degree_centrality":      round(metrics_row.degree_centrality, 4),
            "betweenness_centrality": round(metrics_row.betweenness_centrality, 4),
            "neighbors_count":        metrics_row.neighbors_count,
            "total_edge_weight":      metrics_row.total_edge_weight,
        }

    return RelatedPapersResponse(
        paper_id = paper_id,
        title    = paper.title,
        metrics  = metrics,
        related  = related,
    )


# ── GET /techniques/{name}/related ───────────────────────────────────────────

@app.get(
    "/techniques/{technique_name}/related",
    response_model=TechniqueRelatedResponse,
    summary="Papers using this technique and its co-occurring techniques",
    tags=["Graph"],
)
def get_technique_related(
    technique_name: str,
    limit:          int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> TechniqueRelatedResponse:
    # Look up by canonical_name (case-insensitive fallback to name)
    metric = db.scalar(
        select(TechniqueGraphMetric).where(
            TechniqueGraphMetric.canonical_name == technique_name
        )
    )
    if metric is None:
        # Try case-insensitive
        from sqlalchemy import func as sqlfunc
        metric = db.scalar(
            select(TechniqueGraphMetric).where(
                sqlfunc.lower(TechniqueGraphMetric.canonical_name) == technique_name.lower()
            )
        )
    if metric is None:
        raise HTTPException(
            status_code=404,
            detail=f"Technique {technique_name!r} not found in graph metrics. "
                   "Ensure build_graph has been run.",
        )

    canonical = metric.canonical_name

    # Papers using this technique (via canonical_name or name)
    paper_ids = db.scalars(
        select(PaperTechnique.paper_id)
        .where(
            (PaperTechnique.canonical_name == canonical) |
            (PaperTechnique.name == canonical)
        )
        .distinct()
        .limit(limit)
    ).all()

    papers: list[PaperSummary] = []
    for pid in paper_ids:
        row = db.execute(_base_paper_query().where(Paper.id == pid)).first()
        if row:
            p, conf, _ = row
            papers.append(_paper_summary(p, conf))
    papers.sort(key=lambda x: x.citation_count, reverse=True)

    # Co-occurring techniques
    cooccur_rows = db.execute(
        select(EntityRelationship)
        .where(
            EntityRelationship.entity_type == "technique",
            (EntityRelationship.source_entity == canonical) |
            (EntityRelationship.target_entity == canonical),
        )
        .order_by(EntityRelationship.co_occurrence_count.desc())
        .limit(20)
    ).scalars().all()

    co_occurring: list[CooccurringEntity] = []
    for er in cooccur_rows:
        other = er.target_entity if er.source_entity == canonical else er.source_entity
        co_occurring.append(CooccurringEntity(
            name                = other,
            co_occurrence_count = er.co_occurrence_count,
            weight              = er.weight,
        ))

    return TechniqueRelatedResponse(
        technique              = canonical,
        usage_count            = metric.usage_count,
        connected_papers_count = metric.connected_papers_count,
        papers                 = papers,
        co_occurring           = co_occurring,
    )


# ── GET /graph/stats ──────────────────────────────────────────────────────────

@app.get(
    "/graph/stats",
    response_model=GraphStatsResponse,
    summary="Overall knowledge graph statistics",
    tags=["Graph"],
)
def graph_stats(db: Session = Depends(get_db)) -> GraphStatsResponse:
    n_papers = db.execute(select(func.count()).select_from(Paper)).scalar() or 0
    n_edges  = db.execute(select(func.count()).select_from(PaperRelationship)).scalar() or 0
    n_ent    = db.execute(select(func.count()).select_from(EntityRelationship)).scalar() or 0

    if n_edges == 0:
        return GraphStatsResponse(
            total_papers=n_papers, total_paper_edges=0, total_entity_edges=0,
            entity_edge_breakdown={}, isolated_papers=n_papers,
            avg_edge_weight=0, max_edge_weight=0, cluster_count=0,
            largest_cluster_size=0, tracked_techniques=0,
        )

    avg_w = db.execute(select(func.avg(PaperRelationship.weight))).scalar() or 0.0
    max_w = db.execute(select(func.max(PaperRelationship.weight))).scalar() or 0.0

    entity_breakdown: dict[str, int] = {}
    for etype in ("technique", "dataset", "category", "methodology"):
        cnt = db.execute(
            select(func.count()).select_from(EntityRelationship)
            .where(EntityRelationship.entity_type == etype)
        ).scalar() or 0
        entity_breakdown[etype] = cnt

    isolated = db.execute(
        select(func.count()).select_from(PaperGraphMetric)
        .where(PaperGraphMetric.neighbors_count == 0)
    ).scalar() or 0

    cluster_counts = db.execute(
        select(
            PaperGraphMetric.cluster_id,
            func.count(PaperGraphMetric.paper_id).label("sz")
        )
        .group_by(PaperGraphMetric.cluster_id)
        .order_by(func.count(PaperGraphMetric.paper_id).desc())
    ).all()

    n_clusters    = len(cluster_counts)
    largest_sz    = cluster_counts[0].sz if cluster_counts else 0
    n_techniques  = db.execute(select(func.count()).select_from(TechniqueGraphMetric)).scalar() or 0

    # Most central paper
    top_bc = db.execute(
        select(PaperGraphMetric.paper_id)
        .order_by(PaperGraphMetric.betweenness_centrality.desc())
        .limit(1)
    ).scalar()
    most_central = None
    if top_bc:
        row = db.execute(_base_paper_query().where(Paper.id == top_bc)).first()
        if row:
            most_central = _paper_summary(row[0], row[1])

    return GraphStatsResponse(
        total_papers          = n_papers,
        total_paper_edges     = n_edges,
        total_entity_edges    = n_ent,
        entity_edge_breakdown = entity_breakdown,
        isolated_papers       = isolated,
        avg_edge_weight       = round(avg_w, 2),
        max_edge_weight       = float(max_w),
        cluster_count         = n_clusters,
        largest_cluster_size  = largest_sz,
        tracked_techniques    = n_techniques,
        most_central_paper    = most_central,
    )


# ── GET /graph/top-clusters ───────────────────────────────────────────────────

@app.get(
    "/graph/top-clusters",
    response_model=TopClustersResponse,
    summary="Top research clusters with dominant topics and representative papers",
    tags=["Graph"],
)
def top_clusters(
    limit:       int = Query(10, ge=1, le=50),
    min_papers:  int = Query(2, ge=1, description="Minimum cluster size to include"),
    db: Session = Depends(get_db),
) -> TopClustersResponse:
    cluster_rows = db.execute(
        select(
            PaperGraphMetric.cluster_id,
            func.count(PaperGraphMetric.paper_id).label("sz"),
        )
        .group_by(PaperGraphMetric.cluster_id)
        .having(func.count(PaperGraphMetric.paper_id) >= min_papers)
        .order_by(func.count(PaperGraphMetric.paper_id).desc())
        .limit(limit)
    ).all()

    clusters: list[ClusterSummary] = []
    for cr in cluster_rows:
        # Member paper IDs sorted by betweenness desc
        member_ids = db.scalars(
            select(PaperGraphMetric.paper_id)
            .where(PaperGraphMetric.cluster_id == cr.cluster_id)
            .order_by(PaperGraphMetric.betweenness_centrality.desc())
        ).all()

        # Top 5 papers (by betweenness)
        top_papers: list[PaperSummary] = []
        for pid in member_ids[:5]:
            row = db.execute(_base_paper_query().where(Paper.id == pid)).first()
            if row:
                top_papers.append(_paper_summary(row[0], row[1]))

        # Dominant categories (most frequent among cluster members)
        cat_counts: dict[str, int] = defaultdict(int)
        tech_counts: dict[str, int] = defaultdict(int)
        for pid in member_ids:
            for cat in db.scalars(
                select(PaperCategory.canonical_name).where(PaperCategory.paper_id == pid)
            ).all():
                if cat:
                    cat_counts[cat] += 1
            for tech in db.scalars(
                select(PaperTechnique.canonical_name)
                .where(PaperTechnique.paper_id == pid, PaperTechnique.canonical_name.isnot(None))
            ).all():
                tech_counts[tech] += 1

        dom_cats  = [c for c, _ in sorted(cat_counts.items(),  key=lambda x: -x[1])[:4]]
        dom_techs = [t for t, _ in sorted(tech_counts.items(), key=lambda x: -x[1])[:5]]

        clusters.append(ClusterSummary(
            cluster_id          = cr.cluster_id,
            paper_count         = cr.sz,
            dominant_categories = dom_cats,
            dominant_techniques = dom_techs,
            top_papers          = top_papers,
        ))

    return TopClustersResponse(clusters=clusters)


# ── GET /papers/{id}/explain/{other_id} ──────────────────────────────────────

@app.get(
    "/papers/{paper_id}/explain/{other_paper_id}",
    response_model=RelationshipExplanationResponse,
    summary="Explain WHY two papers are related",
    tags=["Graph"],
)
def explain_relationship(
    paper_id:       str,
    other_paper_id: str,
    db: Session = Depends(get_db),
) -> RelationshipExplanationResponse:
    """
    Returns a structured explanation of the relationship between two papers:

    - **relationship_score**: weighted graph edge score (IDF-adjusted)
    - **shared_concepts**: techniques both papers use, ranked by signal strength
      (SPECIALIZED > SHARED > GENERIC), each with per-paper role (introduces/uses)
    - **shared_categories**: research area tags both papers share
    - **shared_datasets** / **shared_methodologies**: other shared entities
    - **differences**: one bullet per paper describing what makes it distinctive
    - **research_connection**: 1–2 sentence synthesis of the research relationship

    Returns 404 if either paper is not found, or if no graph edge exists between them.
    """
    result = _explain_relationship(db, paper_id, other_paper_id)

    if result is None:
        # Distinguish between missing papers and missing edge
        if db.get(Paper, paper_id) is None:
            raise HTTPException(status_code=404, detail=f"Paper {paper_id!r} not found")
        if db.get(Paper, other_paper_id) is None:
            raise HTTPException(status_code=404, detail=f"Paper {other_paper_id!r} not found")
        raise HTTPException(
            status_code=404,
            detail=(
                f"No graph edge exists between {paper_id!r} and {other_paper_id!r}. "
                "These papers share no common techniques, datasets, categories, or methodologies."
            ),
        )

    return RelationshipExplanationResponse(
        paper_a_id           = result.paper_a_id,
        paper_b_id           = result.paper_b_id,
        paper_a_title        = result.paper_a_title,
        paper_b_title        = result.paper_b_title,
        relationship_score   = result.relationship_score,
        technique_score      = result.technique_score,
        dataset_score        = result.dataset_score,
        category_score       = result.category_score,
        shared_concepts      = [
            ConceptSignalOut(
                name         = c.name,
                signal_tier  = c.signal_tier,
                idf_score    = c.idf_score,
                paper_a_role = c.paper_a_role,
                paper_b_role = c.paper_b_role,
            )
            for c in result.shared_concepts
        ],
        shared_categories    = result.shared_categories,
        shared_datasets      = result.shared_datasets,
        shared_methodologies = result.shared_methodologies,
        differences          = result.differences,
        research_connection  = result.research_connection,
    )
