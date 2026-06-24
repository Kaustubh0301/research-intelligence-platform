"""
feature_mapper/models.py
────────────────────────
Pydantic data shapes for the feature-to-paper mapping pipeline.

Pure data types only — no imports from api/, db/, search/, or llm/.
These structs flow between the parser, extractor, normalizer, retrieval,
and the API router.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

# Allowed feature types — kept as a module constant so the extractor prompt
# and validation stay in sync.
FEATURE_TYPES = (
    "algorithm",
    "architecture",
    "training",
    "evaluation",
    "data",
    "infrastructure",
    "other",
)

COVERAGE_TIERS = ("strong", "moderate", "weak", "novel")


# ── Parsing ───────────────────────────────────────────────────────────────────

class RawSection(BaseModel):
    """A heading-delimited slice of the input document."""
    heading: str | None = None
    text: str


# ── Extraction ────────────────────────────────────────────────────────────────

class ExtractedFeature(BaseModel):
    """Raw LLM output for one feature, before corpus normalization."""
    name: str
    description: str
    source_section: str | None = None
    source_text: str = ""
    feature_type: str = "other"
    raw_terms: list[str] = Field(default_factory=list)


class Feature(BaseModel):
    """A normalized feature: LLM output + corpus-vocabulary signals."""
    id: str
    name: str
    description: str
    source_section: str | None = None
    source_text: str = ""
    feature_type: str = "other"
    matched_techniques: list[str] = Field(default_factory=list)
    matched_categories: list[str] = Field(default_factory=list)
    unrecognized_terms: list[str] = Field(default_factory=list)


# ── Retrieval ─────────────────────────────────────────────────────────────────

class PaperMatch(BaseModel):
    """One paper retrieved for a feature, with score breakdown."""
    paper_id: str
    title: str
    year: int | None = None
    venue: str | None = None
    abstract: str = ""
    top_techniques: list[str] = Field(default_factory=list)
    categories: list[str] = Field(default_factory=list)
    rank: int
    rrf_score: float
    semantic_score: float | None = None
    technique_score: float | None = None
    category_score: float | None = None
    matched_techniques: list[str] = Field(default_factory=list)
    matched_categories: list[str] = Field(default_factory=list)
    # Phase 2B — relevance explanation (None until the explainer runs)
    relevance_explanation: str | None = None
    similarity_points: list[str] = Field(default_factory=list)
    difference_points: list[str] = Field(default_factory=list)


class Recommendation(BaseModel):
    """An evidence-based recommendation for a feature (Phase 2C)."""
    rec_type: str  # 'missing_technique' | 'evaluation_suggestion'
    rank: int
    title: str
    body: str
    supporting_paper_ids: list[str] = Field(default_factory=list)
    supporting_paper_titles: list[str] = Field(default_factory=list)
    priority_score: float | None = None
    evidence_count: int = 0


class FeatureResult(BaseModel):
    """A feature plus its coverage assessment and retrieved papers."""
    feature: Feature
    coverage_score: float
    coverage_tier: str
    papers: list[PaperMatch] = Field(default_factory=list)
    recommendations: list[Recommendation] = Field(default_factory=list)


# ── API request / response ────────────────────────────────────────────────────

class AnalyzeRequest(BaseModel):
    text: str


class AnalyzeResponse(BaseModel):
    project_id: str
    title: str | None = None
    feature_count: int
    total_duration_ms: int
    features: list[FeatureResult] = Field(default_factory=list)


class ReportResponse(BaseModel):
    project_id: str
    title: str | None = None
    markdown: str
    sections: dict = Field(default_factory=dict)
    llm_model: str | None = None
    generation_ms: int | None = None
    generated_at: str | None = None


class DebugRequest(BaseModel):
    feature: str


class DebugSignalRow(BaseModel):
    paper_id: str
    title: str | None = None
    score: float | None = None
    match_count: int | None = None
    matched_names: list[str] = Field(default_factory=list)


class DebugRrfRow(BaseModel):
    paper_id: str
    title: str | None = None
    rrf_score: float
    rank: int
    signals_fired: int


class DebugResponse(BaseModel):
    query_text: str
    dense_results: list[DebugSignalRow] = Field(default_factory=list)
    technique_results: list[DebugSignalRow] = Field(default_factory=list)
    category_results: list[DebugSignalRow] = Field(default_factory=list)
    rrf_ranking: list[DebugRrfRow] = Field(default_factory=list)
