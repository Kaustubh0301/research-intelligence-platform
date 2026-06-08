"""
Shared query helpers and data-shaping utilities for the v1 API.

All functions are pure (no FastAPI dependencies) so they can be
imported by any router without coupling concerns.
"""

from __future__ import annotations

import json
import math
from collections import defaultdict
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from db.models import (
    Author,
    Conference,
    ConferenceEdition,
    Paper,
    PaperAnalysisRecord,
    PaperAuthor,
    PaperCategory,
    PaperDataset,
    PaperGraphMetric,
    PaperMethodology,
    PaperTechnique,
)
from api.models import (
    AnalysisOut,
    AuthorOut,
    CategoryOut,
    DatasetOut,
    GraphMetrics,
    MethodologyOut,
    PaperDetail,
    PaperSummary,
    TechniqueOut,
)


# ── JSON helpers ──────────────────────────────────────────────────────────────

def json_list(raw: Optional[str]) -> list[str]:
    """
    Parse a JSON-encoded list stored in a Text column.
    Returns [] on any failure rather than raising.
    """
    if not raw:
        return []
    try:
        val = json.loads(raw)
        return val if isinstance(val, list) else []
    except (json.JSONDecodeError, TypeError):
        return []


def json_names(raw: Optional[str]) -> list[str]:
    """
    Parse a JSON array of objects that each have a 'name' key,
    OR a plain JSON array of strings.
    Used for top_cooccurring in TechniqueGraphMetric.
    """
    if not raw:
        return []
    try:
        val = json.loads(raw)
        if isinstance(val, list):
            result = []
            for item in val:
                if isinstance(item, dict):
                    result.append(item.get("name", ""))
                elif isinstance(item, str):
                    result.append(item)
            return [n for n in result if n]
    except (json.JSONDecodeError, TypeError):
        pass
    return []


# ── Base query factory ────────────────────────────────────────────────────────

def base_paper_query():
    """
    SELECT papers + conference short_name + edition year + graph metrics.
    Uses LEFT JOINs so papers without a conference or graph metrics are included.
    """
    return (
        select(
            Paper,
            Conference.short_name.label("conf_short"),
            ConferenceEdition.year.label("ed_year"),
            PaperGraphMetric,
        )
        .join(ConferenceEdition, Paper.conference_edition_id == ConferenceEdition.id, isouter=True)
        .join(Conference, ConferenceEdition.conference_id == Conference.id, isouter=True)
        .outerjoin(PaperGraphMetric, Paper.id == PaperGraphMetric.paper_id)
    )


# ── Model builders ────────────────────────────────────────────────────────────

def _graph_metrics(pgm: Optional[PaperGraphMetric]) -> Optional[GraphMetrics]:
    if pgm is None:
        return None
    return GraphMetrics(
        cluster_id             = pgm.cluster_id,
        degree_centrality      = round(pgm.degree_centrality, 6),
        betweenness_centrality = round(pgm.betweenness_centrality, 6),
        neighbors_count        = pgm.neighbors_count,
        total_edge_weight      = round(pgm.total_edge_weight, 4),
    )


def paper_summary(
    paper: Paper,
    conf_short: Optional[str],
    pgm: Optional[PaperGraphMetric],
    top_techniques: Optional[list[str]] = None,
) -> PaperSummary:
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
        pdf_url                    = paper.pdf_url,
        arxiv_id                   = paper.arxiv_id,
        openreview_id              = paper.openreview_id,
        cluster_id                 = pgm.cluster_id if pgm else None,
        degree_centrality          = round(pgm.degree_centrality, 6) if pgm else 0.0,
        top_techniques             = top_techniques or [],
    )


def build_paper_detail(
    session: Session,
    paper: Paper,
    conf_short: Optional[str],
    ed_year: Optional[int],
    pgm: Optional[PaperGraphMetric],
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
            id                  = a.id,
            full_name           = a.full_name,
            position            = pos,
            affiliation         = aff,
            semantic_scholar_id = a.semantic_scholar_id,
            homepage            = a.homepage,
        )
        for a, pos, aff in author_rows
    ]

    # Techniques (ordered: introduces first, then uses, then others)
    techs = session.scalars(
        select(PaperTechnique)
        .where(PaperTechnique.paper_id == paper.id)
        .order_by(PaperTechnique.role, PaperTechnique.name)
    ).all()

    # Datasets
    datasets = session.scalars(
        select(PaperDataset).where(PaperDataset.paper_id == paper.id)
    ).all()

    # Categories (most confident first)
    cats = session.scalars(
        select(PaperCategory)
        .where(PaperCategory.paper_id == paper.id)
        .order_by(PaperCategory.confidence.desc())
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
            advantages  = json_list(analysis_row.advantages),
            limitations = json_list(analysis_row.limitations),
            future_work = json_list(analysis_row.future_work),
            use_cases   = json_list(analysis_row.use_cases),
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
        techniques                 = [
            TechniqueOut(name=t.name, canonical_name=t.canonical_name, role=t.role)
            for t in techs
        ],
        datasets                   = [
            DatasetOut(name=d.name, canonical_name=d.canonical_name, task=d.task, description=d.description)
            for d in datasets
        ],
        categories                 = [
            CategoryOut(name=c.name, canonical_name=c.canonical_name, confidence=c.confidence)
            for c in cats
        ],
        methodologies              = [MethodologyOut(name=m.name) for m in meths],
        analysis                   = analysis,
        graph_metrics              = _graph_metrics(pgm),
    )


# ── Batch technique fetch ─────────────────────────────────────────────────────

def fetch_top_techniques_batch(
    session: Session,
    paper_ids: list[str],
    per_paper: int = 3,
) -> dict[str, list[str]]:
    """
    Return a map of paper_id → [top canonical technique names].
    Uses a single query; post-filters to top N per paper in Python.
    Only includes rows where canonical_name is set.
    """
    if not paper_ids:
        return {}

    rows = session.execute(
        select(
            PaperTechnique.paper_id,
            PaperTechnique.canonical_name,
            func.count(PaperTechnique.id).label("cnt"),
        )
        .where(
            PaperTechnique.paper_id.in_(paper_ids),
            PaperTechnique.canonical_name.isnot(None),
        )
        .group_by(PaperTechnique.paper_id, PaperTechnique.canonical_name)
        .order_by(PaperTechnique.paper_id, func.count(PaperTechnique.id).desc())
    ).all()

    result: dict[str, list[str]] = defaultdict(list)
    for pid, canonical, _ in rows:
        if len(result[pid]) < per_paper:
            result[pid].append(canonical)
    return dict(result)


# ── Citation score (tiebreaker for search ranking) ───────────────────────────

def citation_log_boost(citation_count: Optional[int]) -> float:
    return math.log1p(citation_count or 0)
