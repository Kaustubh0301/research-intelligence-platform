"""
SQLAlchemy ORM models.
Covers: conferences, editions, authors, papers, paper_authors,
        paper_sections, paper_datasets, paper_analyses, pipeline_errors.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean, CheckConstraint, Date, DateTime, ForeignKey,
    SmallInteger, String, Text, UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


# ──────────────────────────────────────────────────────────────
# CONFERENCES
# ──────────────────────────────────────────────────────────────

class Conference(Base):
    __tablename__ = "conferences"

    id:         Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    short_name: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)
    full_name:  Mapped[str] = mapped_column(Text, nullable=False)
    field:      Mapped[str] = mapped_column(String(10), nullable=False)   # ML / CV / NLP / AI
    website:    Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    editions: Mapped[list[ConferenceEdition]] = relationship(back_populates="conference")

    def __repr__(self) -> str:
        return f"<Conference {self.short_name}>"


# ──────────────────────────────────────────────────────────────
# CONFERENCE EDITIONS
# ──────────────────────────────────────────────────────────────

class ConferenceEdition(Base):
    __tablename__ = "conference_editions"
    __table_args__ = (UniqueConstraint("conference_id", "year"),)

    id:               Mapped[str]      = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    conference_id:    Mapped[str]      = mapped_column(UUID(as_uuid=False), ForeignKey("conferences.id", ondelete="RESTRICT"), nullable=False)
    year:             Mapped[int]      = mapped_column(SmallInteger, nullable=False)
    location:         Mapped[str|None] = mapped_column(Text)
    openreview_id:    Mapped[str|None] = mapped_column(Text)        # NeurIPS.cc/2024/Conference
    total_submitted:  Mapped[int|None] = mapped_column(SmallInteger)
    total_accepted:   Mapped[int|None] = mapped_column(SmallInteger)
    created_at:       Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    conference: Mapped[Conference]  = relationship(back_populates="editions")
    papers:     Mapped[list[Paper]] = relationship(back_populates="conference_edition")

    def __repr__(self) -> str:
        return f"<ConferenceEdition {self.conference_id}/{self.year}>"


# ──────────────────────────────────────────────────────────────
# AUTHORS
# ──────────────────────────────────────────────────────────────

class Author(Base):
    __tablename__ = "authors"

    id:                  Mapped[str]      = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    full_name:           Mapped[str]      = mapped_column(Text, nullable=False)
    semantic_scholar_id: Mapped[str|None] = mapped_column(Text, unique=True)
    openalex_id:         Mapped[str|None] = mapped_column(Text, unique=True)
    orcid:               Mapped[str|None] = mapped_column(Text, unique=True)
    homepage:            Mapped[str|None] = mapped_column(Text)
    primary_affiliation: Mapped[str|None] = mapped_column(Text)
    created_at:          Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    paper_links: Mapped[list[PaperAuthor]] = relationship(back_populates="author")

    def __repr__(self) -> str:
        return f"<Author {self.full_name!r}>"


# ──────────────────────────────────────────────────────────────
# PAPERS
# ──────────────────────────────────────────────────────────────

class Paper(Base):
    __tablename__ = "papers"

    id:                       Mapped[str]      = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    conference_edition_id:    Mapped[str|None] = mapped_column(UUID(as_uuid=False), ForeignKey("conference_editions.id", ondelete="SET NULL"))
    semantic_scholar_id:      Mapped[str|None] = mapped_column(Text, unique=True)
    openalex_id:              Mapped[str|None] = mapped_column(Text, unique=True)
    openreview_id:            Mapped[str|None] = mapped_column(Text, unique=True)
    arxiv_id:                 Mapped[str|None] = mapped_column(Text, unique=True)
    doi:                      Mapped[str|None] = mapped_column(Text, unique=True)

    title:                    Mapped[str]      = mapped_column(Text, nullable=False)
    abstract:                 Mapped[str|None] = mapped_column(Text)
    year:                     Mapped[int]      = mapped_column(SmallInteger, nullable=False)
    publication_date:         Mapped[datetime|None] = mapped_column(Date)
    presentation_type:        Mapped[str|None] = mapped_column(
        String(20),
        CheckConstraint("presentation_type IN ('oral','spotlight','poster','workshop','demo','other')")
    )

    pdf_url:                  Mapped[str|None] = mapped_column(Text)
    is_open_access:           Mapped[bool]     = mapped_column(Boolean, default=False)
    citation_count:           Mapped[int]      = mapped_column(default=0)
    influential_citation_count: Mapped[int]    = mapped_column(default=0)

    last_enriched_at:   Mapped[datetime|None] = mapped_column(DateTime(timezone=True))
    # PDF pipeline columns
    pdf_local_path:     Mapped[str|None]      = mapped_column(Text)
    pdf_word_count:     Mapped[int|None]      = mapped_column()
    pdf_extracted_at:   Mapped[datetime|None] = mapped_column(DateTime(timezone=True))

    created_at:         Mapped[datetime]      = mapped_column(DateTime(timezone=True), default=_now)
    updated_at:         Mapped[datetime]      = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)

    conference_edition: Mapped[ConferenceEdition|None] = relationship(back_populates="papers")
    author_links:       Mapped[list[PaperAuthor]]      = relationship(back_populates="paper", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Paper {self.title[:50]!r}>"


# ──────────────────────────────────────────────────────────────
# PAPER ↔ AUTHOR  (join table)
# ──────────────────────────────────────────────────────────────

class PaperAuthor(Base):
    __tablename__ = "paper_authors"

    paper_id:          Mapped[str]      = mapped_column(UUID(as_uuid=False), ForeignKey("papers.id",   ondelete="CASCADE"), primary_key=True)
    author_id:         Mapped[str]      = mapped_column(UUID(as_uuid=False), ForeignKey("authors.id",  ondelete="CASCADE"), primary_key=True)
    position:          Mapped[int]      = mapped_column(SmallInteger, nullable=False)  # 1 = first author
    is_corresponding:  Mapped[bool]     = mapped_column(Boolean, default=False)
    affiliation:       Mapped[str|None] = mapped_column(Text)

    paper:  Mapped[Paper]  = relationship(back_populates="author_links")
    author: Mapped[Author] = relationship(back_populates="paper_links")

    def __repr__(self) -> str:
        return f"<PaperAuthor paper={self.paper_id} author={self.author_id} pos={self.position}>"


# ──────────────────────────────────────────────────────────────
# PAPER SECTIONS  (stage 3 output)
# ──────────────────────────────────────────────────────────────

class PaperSection(Base):
    __tablename__ = "paper_sections"

    id:                 Mapped[str]      = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    paper_id:           Mapped[str]      = mapped_column(UUID(as_uuid=False), ForeignKey("papers.id", ondelete="CASCADE"), nullable=False, unique=True)

    abstract:           Mapped[str|None] = mapped_column(Text)
    introduction:       Mapped[str|None] = mapped_column(Text)
    related_work:       Mapped[str|None] = mapped_column(Text)
    methodology:        Mapped[str|None] = mapped_column(Text)
    experiments:        Mapped[str|None] = mapped_column(Text)
    results:            Mapped[str|None] = mapped_column(Text)
    discussion:         Mapped[str|None] = mapped_column(Text)
    conclusion:         Mapped[str|None] = mapped_column(Text)
    limitations:        Mapped[str|None] = mapped_column(Text)
    future_work:        Mapped[str|None] = mapped_column(Text)
    full_text:          Mapped[str|None] = mapped_column(Text)

    sections_found:     Mapped[str|None] = mapped_column(Text)   # JSON array string
    word_count:         Mapped[int|None] = mapped_column()
    segmenter_version:  Mapped[str|None] = mapped_column(Text)
    segmented_at:       Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    def __repr__(self) -> str:
        return f"<PaperSection paper={self.paper_id} sections={self.sections_found}>"


# ──────────────────────────────────────────────────────────────
# PAPER DATASETS  (extracted by LLM from experiments section)
# ──────────────────────────────────────────────────────────────

class PaperDataset(Base):
    __tablename__ = "paper_datasets"
    __table_args__ = (UniqueConstraint("paper_id", "name"),)

    id:             Mapped[str]      = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    paper_id:       Mapped[str]      = mapped_column(UUID(as_uuid=False), ForeignKey("papers.id", ondelete="CASCADE"), nullable=False)
    name:           Mapped[str]      = mapped_column(Text, nullable=False)   # original extracted value
    canonical_name: Mapped[str|None] = mapped_column(Text)                  # normalized form
    description:    Mapped[str|None] = mapped_column(Text)
    task:           Mapped[str|None] = mapped_column(Text)
    source:         Mapped[str]      = mapped_column(Text, default="auto")

    def __repr__(self) -> str:
        return f"<PaperDataset {self.name!r} paper={self.paper_id}>"


# ──────────────────────────────────────────────────────────────
# PAPER ANALYSES  (stage 4 LLM output)
# ──────────────────────────────────────────────────────────────

class PaperAnalysisRecord(Base):
    __tablename__ = "paper_analyses"

    id:             Mapped[str]      = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    paper_id:       Mapped[str]      = mapped_column(UUID(as_uuid=False), ForeignKey("papers.id", ondelete="CASCADE"), nullable=False, unique=True)

    summary:        Mapped[str|None] = mapped_column(Text)
    advantages:     Mapped[str|None] = mapped_column(Text)   # JSON array — legacy, kept for backward compat
    limitations:    Mapped[str|None] = mapped_column(Text)   # JSON array — populated by V2 limitations prompt
    future_work:    Mapped[str|None] = mapped_column(Text)   # JSON array — legacy, kept for backward compat
    use_cases:      Mapped[str|None] = mapped_column(Text)   # JSON array — legacy, kept for backward compat

    # V2 analysis fields (Analysis V2, 2026-06-08)
    methodology:                Mapped[str|None] = mapped_column(Text)   # prose, 150-250 words
    experimental_findings:      Mapped[str|None] = mapped_column(Text)   # JSON array of "name :: metric :: score" strings
    strengths:                  Mapped[str|None] = mapped_column(Text)   # JSON array, replaces advantages
    practical_applications:     Mapped[str|None] = mapped_column(Text)   # JSON array, replaces use_cases
    future_research_directions: Mapped[str|None] = mapped_column(Text)   # JSON array, replaces future_work

    model:          Mapped[str|None] = mapped_column(Text)
    input_tokens:   Mapped[int|None] = mapped_column()
    output_tokens:  Mapped[int|None] = mapped_column()
    cost_usd:       Mapped[float|None] = mapped_column()
    processing_ms:  Mapped[int|None] = mapped_column()

    created_at:     Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at:     Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)

    def __repr__(self) -> str:
        return f"<PaperAnalysis paper={self.paper_id} model={self.model}>"


# ──────────────────────────────────────────────────────────────
# PAPER CATEGORIES  (from LLM analysis)
# ──────────────────────────────────────────────────────────────

class PaperCategory(Base):
    __tablename__ = "paper_categories"
    __table_args__ = (UniqueConstraint("paper_id", "name"),)

    id:         Mapped[str]      = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    paper_id:   Mapped[str]      = mapped_column(UUID(as_uuid=False), ForeignKey("papers.id", ondelete="CASCADE"), nullable=False)
    name:           Mapped[str]      = mapped_column(Text, nullable=False)   # original extracted value
    canonical_name: Mapped[str|None] = mapped_column(Text)                  # normalized form
    confidence:     Mapped[float]    = mapped_column(default=1.0)
    source:         Mapped[str]      = mapped_column(Text, default="auto")   # "auto" | "manual"

    def __repr__(self) -> str:
        return f"<PaperCategory {self.name!r} paper={self.paper_id}>"


# ──────────────────────────────────────────────────────────────
# PAPER TECHNIQUES  (from LLM analysis)
# ──────────────────────────────────────────────────────────────

class PaperTechnique(Base):
    __tablename__ = "paper_techniques"
    __table_args__ = (UniqueConstraint("paper_id", "name"),)

    id:       Mapped[str]      = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    paper_id: Mapped[str]      = mapped_column(UUID(as_uuid=False), ForeignKey("papers.id", ondelete="CASCADE"), nullable=False)
    name:           Mapped[str]      = mapped_column(Text, nullable=False)   # original extracted value
    canonical_name: Mapped[str|None] = mapped_column(Text)                  # normalized form
    role:           Mapped[str]      = mapped_column(
        String(20),
        CheckConstraint("role IN ('introduces','uses','compares','critiques')"),
        default="uses",
    )
    source:   Mapped[str]      = mapped_column(Text, default="auto")

    def __repr__(self) -> str:
        return f"<PaperTechnique {self.name!r} role={self.role} paper={self.paper_id}>"


# ──────────────────────────────────────────────────────────────
# PAPER METHODOLOGIES  (from LLM analysis)
# ──────────────────────────────────────────────────────────────

class PaperMethodology(Base):
    __tablename__ = "paper_methodologies"
    __table_args__ = (UniqueConstraint("paper_id", "name"),)

    id:       Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    paper_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("papers.id", ondelete="CASCADE"), nullable=False)
    name:     Mapped[str] = mapped_column(Text, nullable=False)   # e.g. "Supervised Learning"
    source:   Mapped[str] = mapped_column(Text, default="auto")

    def __repr__(self) -> str:
        return f"<PaperMethodology {self.name!r} paper={self.paper_id}>"


# ──────────────────────────────────────────────────────────────
# NOTEBOOKS  (one per topic × instance in NotebookLM)
# ──────────────────────────────────────────────────────────────

class Notebook(Base):
    __tablename__ = "notebooks"
    __table_args__ = (UniqueConstraint("topic_slug", "instance_number"),)

    id:              Mapped[str]      = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    topic_slug:      Mapped[str]      = mapped_column(String(60), nullable=False)   # 'agentic-ai'
    topic_name:      Mapped[str]      = mapped_column(Text, nullable=False)         # human-readable
    instance_number: Mapped[int]      = mapped_column(SmallInteger, nullable=False, default=1)
    notebooklm_id:   Mapped[str|None] = mapped_column(String(64))                    # NotebookLM notebook UUID (used in API calls)
    notebooklm_url:  Mapped[str|None] = mapped_column(Text)                         # browser URL in NotebookLM
    source_count:    Mapped[int]      = mapped_column(SmallInteger, nullable=False, default=0)
    max_sources:     Mapped[int]      = mapped_column(SmallInteger, nullable=False, default=45)
    status:          Mapped[str]      = mapped_column(
        String(10),
        CheckConstraint("status IN ('active','full','archived')"),
        default="active",
    )
    last_synced_at:  Mapped[datetime|None] = mapped_column(DateTime(timezone=True))
    created_at:      Mapped[datetime]      = mapped_column(DateTime(timezone=True), default=_now)

    paper_links:   Mapped[list[NotebookPaper]]     = relationship(back_populates="notebook", cascade="all, delete-orphan")
    syntheses:     Mapped[list[NotebookSynthesis]]  = relationship(back_populates="notebook", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Notebook {self.topic_slug}-{self.instance_number} status={self.status}>"


# ──────────────────────────────────────────────────────────────
# NOTEBOOK ↔ PAPER  (many-to-many with upload state)
# ──────────────────────────────────────────────────────────────

class NotebookPaper(Base):
    __tablename__ = "notebook_papers"

    notebook_id:           Mapped[str]           = mapped_column(UUID(as_uuid=False), ForeignKey("notebooks.id", ondelete="CASCADE"), primary_key=True)
    paper_id:              Mapped[str]           = mapped_column(UUID(as_uuid=False), ForeignKey("papers.id",    ondelete="CASCADE"), primary_key=True)
    assigned_by:           Mapped[str]           = mapped_column(String(20), default="keyword")   # keyword|manual|notebooklm
    assignment_confidence: Mapped[str]           = mapped_column(String(10), default="medium")    # high|medium|low
    source_status:         Mapped[str]           = mapped_column(
        String(20),
        CheckConstraint("source_status IN ('pending','uploaded','abstract_only','error','removed')"),
        default="pending",
    )
    upload_attempted_at:   Mapped[datetime|None] = mapped_column(DateTime(timezone=True))
    upload_completed_at:   Mapped[datetime|None] = mapped_column(DateTime(timezone=True))

    notebook: Mapped[Notebook] = relationship(back_populates="paper_links")
    paper:    Mapped[Paper]    = relationship()

    def __repr__(self) -> str:
        return f"<NotebookPaper notebook={self.notebook_id[:8]} paper={self.paper_id[:8]} status={self.source_status}>"


# ──────────────────────────────────────────────────────────────
# NOTEBOOK SYNTHESES  (query responses from NotebookLM)
# ──────────────────────────────────────────────────────────────

class NotebookSynthesis(Base):
    __tablename__ = "notebook_syntheses"
    __table_args__ = (UniqueConstraint("notebook_id", "synthesis_type", "query_prompt"),)

    id:             Mapped[str]      = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    notebook_id:    Mapped[str]      = mapped_column(UUID(as_uuid=False), ForeignKey("notebooks.id", ondelete="CASCADE"), nullable=False)
    synthesis_type: Mapped[str]      = mapped_column(
        String(20),
        CheckConstraint("synthesis_type IN ('faq','study_guide','briefing','overview','query_response')"),
        nullable=False,
    )
    query_prompt:   Mapped[str|None] = mapped_column(Text)    # the question asked (for query_response)
    content:        Mapped[str]      = mapped_column(Text, nullable=False)
    word_count:     Mapped[int|None] = mapped_column()
    normalized:     Mapped[bool]     = mapped_column(Boolean, default=False)
    created_at:     Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    notebook: Mapped[Notebook]                      = relationship(back_populates="syntheses")
    extracts: Mapped[list[NotebookPaperExtract]]    = relationship(back_populates="synthesis", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<NotebookSynthesis notebook={self.notebook_id[:8]} type={self.synthesis_type}>"


# ──────────────────────────────────────────────────────────────
# NOTEBOOK PAPER EXTRACTS  (per-paper data parsed from syntheses)
# ──────────────────────────────────────────────────────────────

class NotebookPaperExtract(Base):
    __tablename__ = "notebook_paper_extracts"

    id:             Mapped[str]  = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    notebook_id:    Mapped[str]  = mapped_column(UUID(as_uuid=False), ForeignKey("notebooks.id", ondelete="CASCADE"), nullable=False)
    synthesis_id:   Mapped[str]  = mapped_column(UUID(as_uuid=False), ForeignKey("notebook_syntheses.id", ondelete="CASCADE"), nullable=False)
    paper_id:       Mapped[str]  = mapped_column(UUID(as_uuid=False), ForeignKey("papers.id", ondelete="CASCADE"), nullable=False)
    extract_type:   Mapped[str]  = mapped_column(
        String(32),
        CheckConstraint(
            "extract_type IN ("
            "'summary','techniques','methodologies','limitations','datasets',"
            "'categories','future_work',"
            "'methodology','experimental_findings','strengths',"
            "'practical_applications','future_research_directions'"
            ")"
        ),
        nullable=False,
    )
    content:        Mapped[str]      = mapped_column(Text, nullable=False)
    confidence:     Mapped[str]      = mapped_column(String(10), default="medium")
    normalized:     Mapped[bool]     = mapped_column(Boolean, default=False)
    created_at:     Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    notebook:  Mapped[Notebook]         = relationship()
    synthesis: Mapped[NotebookSynthesis] = relationship(back_populates="extracts")
    paper:     Mapped[Paper]            = relationship()

    def __repr__(self) -> str:
        return f"<NotebookPaperExtract paper={self.paper_id[:8]} type={self.extract_type} conf={self.confidence}>"


# ──────────────────────────────────────────────────────────────
# KNOWLEDGE GRAPH TABLES
# ──────────────────────────────────────────────────────────────

class PaperRelationship(Base):
    """
    Undirected weighted edge between two papers.
    source_paper_id < target_paper_id (enforced by builder) to keep one row per pair.
    weight = 3*|shared_techniques| + 2*|shared_datasets| + |shared_categories| + |shared_methodologies|
    """
    __tablename__ = "paper_relationships"
    __table_args__ = (UniqueConstraint("source_paper_id", "target_paper_id"),)

    id:                  Mapped[str]   = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    source_paper_id:     Mapped[str]   = mapped_column(UUID(as_uuid=False), ForeignKey("papers.id", ondelete="CASCADE"), nullable=False)
    target_paper_id:     Mapped[str]   = mapped_column(UUID(as_uuid=False), ForeignKey("papers.id", ondelete="CASCADE"), nullable=False)
    shared_techniques:   Mapped[str|None] = mapped_column(Text)          # JSON array of canonical names
    shared_datasets:     Mapped[str|None] = mapped_column(Text)          # JSON array
    shared_categories:   Mapped[str|None] = mapped_column(Text)          # JSON array
    shared_methodologies: Mapped[str|None] = mapped_column(Text)         # JSON array
    weight:              Mapped[float] = mapped_column(default=0.0)      # final combined weight
    # Graph v2 per-component diagnostics (NULL on rows written before migration 009)
    technique_score:     Mapped[float|None] = mapped_column()            # IDF-weighted technique contribution
    dataset_score:       Mapped[float|None] = mapped_column()            # flat dataset contribution
    category_score:      Mapped[float|None] = mapped_column()            # flat category contribution
    created_at:          Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    source_paper: Mapped[Paper] = relationship(foreign_keys=[source_paper_id])
    target_paper: Mapped[Paper] = relationship(foreign_keys=[target_paper_id])

    def __repr__(self) -> str:
        return f"<PaperRelationship {self.source_paper_id[:8]}↔{self.target_paper_id[:8]} w={self.weight}>"


class EntityRelationship(Base):
    """
    Co-occurrence edge between two entities of the same type.
    source_entity < target_entity (alphabetical, enforced by builder).
    weight = number of papers where both entities appear together.
    """
    __tablename__ = "entity_relationships"
    __table_args__ = (UniqueConstraint("source_entity", "target_entity", "entity_type"),)

    id:                  Mapped[str]   = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    source_entity:       Mapped[str]   = mapped_column(Text, nullable=False)
    target_entity:       Mapped[str]   = mapped_column(Text, nullable=False)
    entity_type:         Mapped[str]   = mapped_column(
        String(20),
        CheckConstraint("entity_type IN ('technique','dataset','category','methodology')"),
        nullable=False,
    )
    co_occurrence_count: Mapped[int]   = mapped_column(default=1)
    weight:              Mapped[float] = mapped_column(default=1.0)
    created_at:          Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    def __repr__(self) -> str:
        return f"<EntityRelationship {self.source_entity[:20]}↔{self.target_entity[:20]} type={self.entity_type} w={self.weight}>"


class PaperGraphMetric(Base):
    """Per-paper graph analytics: centrality scores and cluster membership."""
    __tablename__ = "paper_graph_metrics"

    paper_id:              Mapped[str]        = mapped_column(UUID(as_uuid=False), ForeignKey("papers.id", ondelete="CASCADE"), primary_key=True)
    degree_centrality:     Mapped[float]      = mapped_column(default=0.0)
    betweenness_centrality: Mapped[float]     = mapped_column(default=0.0)
    cluster_id:            Mapped[int|None]   = mapped_column()
    neighbors_count:       Mapped[int]        = mapped_column(default=0)
    total_edge_weight:     Mapped[float]      = mapped_column(default=0.0)
    updated_at:            Mapped[datetime]   = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)

    paper: Mapped[Paper] = relationship()

    def __repr__(self) -> str:
        return f"<PaperGraphMetric paper={self.paper_id[:8]} cluster={self.cluster_id} bc={self.betweenness_centrality:.3f}>"


class TechniqueGraphMetric(Base):
    """Per-canonical-technique graph analytics."""
    __tablename__ = "technique_graph_metrics"

    canonical_name:          Mapped[str]        = mapped_column(Text, primary_key=True)
    usage_count:             Mapped[int]        = mapped_column(default=0)   # papers using this technique
    connected_papers_count:  Mapped[int]        = mapped_column(default=0)   # papers reachable via shared technique edges
    top_cooccurring:         Mapped[str|None]   = mapped_column(Text)        # JSON: [{name, count}, ...]
    updated_at:              Mapped[datetime]   = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)

    def __repr__(self) -> str:
        return f"<TechniqueGraphMetric {self.canonical_name[:40]} usage={self.usage_count}>"


# ──────────────────────────────────────────────────────────────
# PIPELINE ERRORS  (append-only error log)
# ──────────────────────────────────────────────────────────────

class PipelineError(Base):
    __tablename__ = "pipeline_errors"

    id:         Mapped[str]       = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    paper_id:   Mapped[str|None]  = mapped_column(UUID(as_uuid=False), ForeignKey("papers.id"), nullable=True)
    stage:      Mapped[str]       = mapped_column(Text, nullable=False)
    error_type: Mapped[str]       = mapped_column(Text, nullable=False)
    error_msg:  Mapped[str|None]  = mapped_column(Text)
    retryable:  Mapped[bool]      = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime]  = mapped_column(DateTime(timezone=True), default=_now)

    def __repr__(self) -> str:
        return f"<PipelineError stage={self.stage} type={self.error_type}>"
