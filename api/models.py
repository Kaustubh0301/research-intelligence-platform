"""
Pydantic response and request models for the v1 API.

These are distinct from the SQLAlchemy ORM models in db/models.py.
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


# ── Shared sub-models ─────────────────────────────────────────────────────────

class GraphMetrics(BaseModel):
    cluster_id:             Optional[int]   = None
    degree_centrality:      float           = 0.0
    betweenness_centrality: float           = 0.0
    neighbors_count:        int             = 0
    total_edge_weight:      float           = 0.0


class AuthorOut(BaseModel):
    id:                  str
    full_name:           str
    position:            int
    affiliation:         Optional[str] = None
    semantic_scholar_id: Optional[str] = None
    homepage:            Optional[str] = None


class TechniqueOut(BaseModel):
    name:           str
    canonical_name: Optional[str] = None
    role:           str  # introduces | uses | compares | critiques


class DatasetOut(BaseModel):
    name:           str
    canonical_name: Optional[str] = None
    task:           Optional[str] = None
    description:    Optional[str] = None


class CategoryOut(BaseModel):
    name:           str
    canonical_name: Optional[str] = None
    confidence:     float = 1.0


class MethodologyOut(BaseModel):
    name: str


class ExperimentalFinding(BaseModel):
    """Single structured result triple parsed from 'benchmark :: metric :: scores'."""
    benchmark: str
    metric:    str
    scores:    str


class AnalysisOut(BaseModel):
    # V2 fields
    summary:                    Optional[str]           = None
    methodology:                Optional[str]           = None
    experimental_findings:      list[ExperimentalFinding] = Field(default_factory=list)
    strengths:                  list[str]               = Field(default_factory=list)
    limitations:                list[str]               = Field(default_factory=list)
    practical_applications:     list[str]               = Field(default_factory=list)
    future_research_directions: list[str]               = Field(default_factory=list)
    # V1 legacy fields — kept for backward compatibility
    advantages:  list[str]  = Field(default_factory=list)
    future_work: list[str]  = Field(default_factory=list)
    use_cases:   list[str]  = Field(default_factory=list)
    model:       Optional[str] = None


# ── Paper list item ───────────────────────────────────────────────────────────

class PaperSummary(BaseModel):
    """Lightweight paper used in list/search results."""
    id:                       str
    title:                    str
    year:                     int
    conference:               Optional[str]   = None
    presentation_type:        Optional[str]   = None
    citation_count:           int             = 0
    influential_citation_count: int           = 0
    is_open_access:           bool            = False
    has_pdf:                  bool            = False
    abstract_snippet:         Optional[str]   = None  # first 300 chars
    pdf_url:                  Optional[str]   = None
    arxiv_id:                 Optional[str]   = None
    openreview_id:            Optional[str]   = None
    # Graph metrics (populated when paper_graph_metrics row exists)
    cluster_id:               Optional[int]   = None
    degree_centrality:        float           = 0.0
    # Top 3 canonical technique names
    top_techniques:           list[str]       = Field(default_factory=list)
    # Primary research category (highest-confidence paper_categories row)
    primary_category:         Optional[str]   = None


# ── Paper detail ──────────────────────────────────────────────────────────────

class PaperDetail(BaseModel):
    """Full paper record including all related tables."""
    id:                       str
    title:                    str
    abstract:                 Optional[str]   = None
    year:                     int
    conference:               Optional[str]   = None
    edition_year:             Optional[int]   = None
    presentation_type:        Optional[str]   = None
    citation_count:           int             = 0
    influential_citation_count: int           = 0
    is_open_access:           bool            = False
    pdf_url:                  Optional[str]   = None
    openreview_id:            Optional[str]   = None
    semantic_scholar_id:      Optional[str]   = None
    arxiv_id:                 Optional[str]   = None
    # Related data
    authors:       list[AuthorOut]      = Field(default_factory=list)
    techniques:    list[TechniqueOut]   = Field(default_factory=list)
    datasets:      list[DatasetOut]     = Field(default_factory=list)
    categories:    list[CategoryOut]    = Field(default_factory=list)
    methodologies: list[MethodologyOut] = Field(default_factory=list)
    analysis:      Optional[AnalysisOut] = None
    graph_metrics: Optional[GraphMetrics] = None


# ── Papers list response ──────────────────────────────────────────────────────

class PapersResponse(BaseModel):
    total:    int
    page:     int
    per_page: int
    results:  list[PaperSummary]


# ── Stats response ────────────────────────────────────────────────────────────

class TechniqueStat(BaseModel):
    canonical_name: str
    paper_count:    int


class ClusterStat(BaseModel):
    cluster_id:   int
    paper_count:  int
    avg_degree:   float
    avg_betweenness: float


class ConferenceStat(BaseModel):
    short_name: str
    year:       int
    count:      int


class TopPaper(BaseModel):
    id:                 str
    title:              str
    citation_count:     int
    conference:         Optional[str] = None
    year:               Optional[int] = None
    presentation_type:  Optional[str] = None
    cluster_id:         Optional[int] = None
    degree_centrality:  float         = 0.0
    primary_category:   Optional[str] = None


class StatsResponse(BaseModel):
    total_papers:     int
    total_edges:      int
    total_techniques: int
    total_clusters:   int
    conferences:      list[ConferenceStat]
    clusters:         list[ClusterStat]
    top_techniques:   list[TechniqueStat]
    top_papers:       list[TopPaper]


# ── Search ────────────────────────────────────────────────────────────────────

class SearchFilters(BaseModel):
    conference: Optional[str] = None
    year:       Optional[int] = None
    cluster:    Optional[int] = None
    technique:  Optional[str] = None


class SearchRequest(BaseModel):
    query:    str              = Field(..., min_length=1, description="Search query")
    filters:  SearchFilters    = Field(default_factory=SearchFilters)
    sort:     str              = Field("relevance", description="relevance | citations | centrality | date")
    page:     int              = Field(1, ge=1)
    per_page: int              = Field(20, ge=1, le=100)


class SearchMatch(BaseModel):
    paper:       PaperSummary
    match_score: float
    matched_in:  list[str]  # e.g. ["title", "technique:LoRA"]


class SearchResponse(BaseModel):
    query:   str
    total:   int
    page:    int
    per_page: int
    results: list[SearchMatch]


# ── Graph ─────────────────────────────────────────────────────────────────────

class GraphNode(BaseModel):
    id:                 str
    title:              str
    conference:         Optional[str] = None
    year:               Optional[int] = None
    citation_count:     int           = 0
    cluster_id:         Optional[int] = None
    degree_centrality:  float         = 0.0
    betweenness_centrality: float     = 0.0
    is_ego:             bool          = False  # true for ego-graph centre node


class GraphEdge(BaseModel):
    source: str
    target: str
    weight: float


class GraphMeta(BaseModel):
    node_count:  int
    edge_count:  int
    min_weight:  float
    max_weight:  float


class GraphResponse(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    meta:  GraphMeta


# ── Techniques ────────────────────────────────────────────────────────────────

class TechniqueItem(BaseModel):
    canonical_name:         str
    usage_count:            int
    connected_papers_count: int
    top_cooccurring:        list[str] = Field(default_factory=list)
    introduces_count:       int       = 0
    uses_count:             int       = 0


class TechniquesResponse(BaseModel):
    total:      int
    page:       int
    per_page:   int
    techniques: list[TechniqueItem]


# ── Related papers ────────────────────────────────────────────────────────────

class RelatedPaper(BaseModel):
    paper:               PaperSummary
    weight:              float
    shared_techniques:   list[str] = Field(default_factory=list)
    shared_datasets:     list[str] = Field(default_factory=list)
    shared_categories:   list[str] = Field(default_factory=list)
    shared_methodologies: list[str] = Field(default_factory=list)


class RelatedPapersResponse(BaseModel):
    paper_id:     str
    title:        str
    graph_metrics: Optional[GraphMetrics] = None
    related:      list[RelatedPaper]


# ── Chat ──────────────────────────────────────────────────────────────────────

class ConversationMessage(BaseModel):
    """A single prior turn in the conversation, sent by the client."""
    role:    Literal["user", "assistant"]
    content: str = Field(..., min_length=1)


class ChatRequest(BaseModel):
    message:         str                       = Field(..., min_length=1, description="User question")
    conversation_id: Optional[str]             = Field(None, description="Echo'd back unchanged")
    history:         list[ConversationMessage] = Field(
        default_factory=list,
        description="Prior turns, oldest first. Capped server-side at 10 turns.",
    )


class ChatSource(BaseModel):
    """A supporting paper returned alongside the assistant answer."""
    id:               str
    title:            str
    conference:       Optional[str] = None
    year:             int
    citation_count:   int           = 0
    cluster_id:       Optional[int] = None
    degree_centrality: float        = 0.0
    top_techniques:   list[str]     = Field(default_factory=list)
    categories:       list[str]     = Field(default_factory=list)
    match_score:      float         = 0.0
    matched_in:       list[str]     = Field(default_factory=list)
    abstract_snippet: Optional[str] = None


class ChatResponse(BaseModel):
    answer:          str
    sources:         list[ChatSource]
    conversation_id: str
