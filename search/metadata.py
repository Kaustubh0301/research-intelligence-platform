"""
search/metadata.py
──────────────────
Batch metadata helpers needed by search/retrieval.py.

These functions were previously in api/helpers.py.  They are duplicated
here (not imported from api/) so that the search/ package has no dependency
on api/.

Rules:
  - No imports from api/.
  - All IN queries use SQLAlchemy .in_() — SQLAlchemy handles chunking
    internally for ORM queries; sync.py handles manual chunking for raw SQL.
"""

from __future__ import annotations

import json
import math
from collections import defaultdict
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from db.models import (
    Conference,
    ConferenceEdition,
    Paper,
    PaperAnalysisRecord,
    PaperCategory,
    PaperGraphMetric,
    PaperTechnique,
)


# ── JSON helpers (no api/ import) ─────────────────────────────────────────────

def _json_list(raw: Optional[str]) -> list[str]:
    if not raw:
        return []
    try:
        val = json.loads(raw)
        return val if isinstance(val, list) else []
    except (json.JSONDecodeError, TypeError):
        return []


def citation_log_boost(citation_count: Optional[int]) -> float:
    return math.log1p(citation_count or 0)


# ── Base paper query ──────────────────────────────────────────────────────────

def base_paper_query():
    """SELECT papers + conf short_name + edition year + graph metrics."""
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


# ── Batch fetches ─────────────────────────────────────────────────────────────

def fetch_primary_categories_batch(
    session: Session,
    paper_ids: list[str],
) -> dict[str, str]:
    """Return paper_id → primary category name (highest-confidence row)."""
    if not paper_ids:
        return {}

    rows = session.execute(
        select(
            PaperCategory.paper_id,
            PaperCategory.canonical_name,
            PaperCategory.name,
            PaperCategory.confidence,
        )
        .where(PaperCategory.paper_id.in_(paper_ids))
        .order_by(PaperCategory.paper_id, PaperCategory.confidence.desc())
    ).all()

    result: dict[str, str] = {}
    for pid, canonical, name, _conf in rows:
        if pid not in result:
            result[pid] = canonical or name
    return result


def fetch_top_techniques_batch(
    session: Session,
    paper_ids: list[str],
    per_paper: int = 3,
) -> dict[str, list[str]]:
    """Return paper_id → [top canonical technique names]."""
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


def fetch_paper_metadata_batch(
    session: Session,
    paper_ids: list[str],
) -> dict[str, dict]:
    """
    Return a map of paper_id → metadata dict for the given IDs.

    Fetches: paper row, conf_short, edition year, graph metrics,
             top_techniques (≤3), categories (≤3), analysis fields.
    Used by retrieval.py to hydrate FTS candidate IDs into full result dicts.
    """
    if not paper_ids:
        return {}

    # Papers + conference + graph metrics
    paper_rows = session.execute(
        base_paper_query().where(Paper.id.in_(paper_ids))
    ).all()

    paper_map: dict[str, tuple] = {}
    for paper, conf_short, _ed_year, pgm in paper_rows:
        paper_map[paper.id] = (paper, conf_short, pgm)

    # Techniques
    techniques_map = fetch_top_techniques_batch(session, paper_ids)

    # Categories (top 3 per paper by confidence)
    cat_rows = session.execute(
        select(PaperCategory.paper_id, PaperCategory.name)
        .where(PaperCategory.paper_id.in_(paper_ids))
        .order_by(PaperCategory.paper_id, PaperCategory.confidence.desc())
    ).all()
    cats_by_paper: dict[str, list[str]] = defaultdict(list)
    for pid, cname in cat_rows:
        if len(cats_by_paper[pid]) < 3:
            cats_by_paper[pid].append(cname)

    # Analysis
    analysis_rows = session.execute(
        select(
            PaperAnalysisRecord.paper_id,
            PaperAnalysisRecord.summary,
            PaperAnalysisRecord.methodology,
            PaperAnalysisRecord.experimental_findings,
            PaperAnalysisRecord.strengths,
            PaperAnalysisRecord.limitations,
            PaperAnalysisRecord.practical_applications,
            PaperAnalysisRecord.future_research_directions,
            PaperAnalysisRecord.advantages,
        ).where(PaperAnalysisRecord.paper_id.in_(paper_ids))
    ).all()
    analysis_map = {r.paper_id: r for r in analysis_rows}

    result: dict[str, dict] = {}
    for pid in paper_ids:
        if pid not in paper_map:
            continue
        paper, conf, pgm = paper_map[pid]
        ar = analysis_map.get(pid)
        result[pid] = {
            "id":               paper.id,
            "title":            paper.title,
            "abstract":         paper.abstract or "",
            "year":             paper.year,
            "conference":       conf,
            "citation_count":   paper.citation_count or 0,
            "cluster_id":       pgm.cluster_id if pgm else None,
            "degree_centrality": round(pgm.degree_centrality, 6) if pgm else 0.0,
            "top_techniques":   techniques_map.get(pid, []),
            "categories":       cats_by_paper.get(pid, []),
            "summary":                    (ar.summary or "") if ar else "",
            "methodology":                (ar.methodology or "") if ar else "",
            "experimental_findings":      _json_list(ar.experimental_findings) if ar else [],
            "strengths":                  _json_list(ar.strengths) if ar else [],
            "limitations":                _json_list(ar.limitations) if ar else [],
            "practical_applications":     _json_list(ar.practical_applications) if ar else [],
            "future_research_directions": _json_list(ar.future_research_directions) if ar else [],
            "advantages":                 _json_list(ar.advantages) if ar else [],
        }
    return result
