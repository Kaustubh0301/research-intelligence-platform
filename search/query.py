"""
Search and filter layer for the research platform.

All functions return plain dicts so callers have no ORM dependency.
Every function opens its own session — safe to call from scripts or notebooks.

Usage:
    from search.query import search_papers, top_cited

    results = search_papers(conference="NeurIPS", year=2024, min_citations=50)
    for r in results:
        print(r["title"], r["citation_count"])
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import func, select, or_

from db.models import Author, Conference, ConferenceEdition, Paper, PaperAuthor
from db.session import get_session


# ── Helpers ───────────────────────────────────────────────────────────────────

def _paper_to_dict(p: Paper, conf_short: str | None = None, conf_year: int | None = None) -> dict[str, Any]:
    return {
        "id":                      p.id,
        "title":                   p.title,
        "abstract":                p.abstract,
        "year":                    p.year,
        "conference":              conf_short,
        "edition_year":            conf_year,
        "presentation_type":       p.presentation_type,
        "citation_count":          p.citation_count,
        "influential_citation_count": p.influential_citation_count,
        "pdf_url":                 p.pdf_url,
        "pdf_local_path":          p.pdf_local_path,
        "openreview_id":           p.openreview_id,
        "semantic_scholar_id":     p.semantic_scholar_id,
        "arxiv_id":                p.arxiv_id,
        "is_open_access":          p.is_open_access,
    }


# ── Core search ───────────────────────────────────────────────────────────────

def search_papers(
    *,
    title:         str | None = None,
    conference:    str | None = None,
    year:          int | None = None,
    field:         str | None = None,
    min_citations: int | None = None,
    max_citations: int | None = None,
    presentation_type: str | None = None,
    has_pdf:       bool | None = None,
    limit:         int = 100,
    offset:        int = 0,
    order_by:      str = "citation_count",
    descending:    bool = True,
) -> list[dict[str, Any]]:
    """
    Flexible paper search with optional filters.

    Args:
        title:             substring match (case-insensitive)
        conference:        short name, e.g. "NeurIPS" (case-insensitive)
        year:              edition year
        field:             "ML" | "CV" | "NLP" | "AI"
        min_citations:     inclusive lower bound on citation_count
        max_citations:     inclusive upper bound on citation_count
        presentation_type: "oral" | "spotlight" | "poster" | "other"
        has_pdf:           True = only papers with downloaded PDFs
        limit:             max results to return (default 100, max 1000)
        offset:            pagination offset
        order_by:          "citation_count" | "year" | "title"
        descending:        sort direction (default True)

    Returns:
        List of paper dicts ordered by `order_by`.
    """
    limit = min(limit, 1000)

    with get_session() as s:
        q = (
            select(Paper, Conference.short_name, ConferenceEdition.year)
            .join(ConferenceEdition, Paper.conference_edition_id == ConferenceEdition.id, isouter=True)
            .join(Conference, ConferenceEdition.conference_id == Conference.id, isouter=True)
        )

        if title:
            q = q.where(func.lower(Paper.title).contains(title.lower()))

        if conference:
            q = q.where(func.lower(Conference.short_name) == conference.lower())

        if year:
            q = q.where(ConferenceEdition.year == year)

        if field:
            q = q.where(func.lower(Conference.field) == field.lower())

        if min_citations is not None:
            q = q.where(Paper.citation_count >= min_citations)

        if max_citations is not None:
            q = q.where(Paper.citation_count <= max_citations)

        if presentation_type:
            q = q.where(Paper.presentation_type == presentation_type)

        if has_pdf is True:
            q = q.where(Paper.pdf_local_path.is_not(None))
        elif has_pdf is False:
            q = q.where(Paper.pdf_local_path.is_(None))

        # Ordering
        sort_col = {
            "citation_count": Paper.citation_count,
            "year":           Paper.year,
            "title":          Paper.title,
        }.get(order_by, Paper.citation_count)

        q = q.order_by(sort_col.desc() if descending else sort_col.asc())
        q = q.offset(offset).limit(limit)

        rows = s.execute(q).all()
        return [_paper_to_dict(p, conf_short, ed_year) for p, conf_short, ed_year in rows]


def get_paper(paper_id: str) -> dict[str, Any] | None:
    """Fetch a single paper by ID. Returns None if not found."""
    with get_session() as s:
        q = (
            select(Paper, Conference.short_name, ConferenceEdition.year)
            .join(ConferenceEdition, Paper.conference_edition_id == ConferenceEdition.id, isouter=True)
            .join(Conference, ConferenceEdition.conference_id == Conference.id, isouter=True)
            .where(Paper.id == paper_id)
        )
        row = s.execute(q).first()
        if row is None:
            return None
        p, conf_short, ed_year = row
        return _paper_to_dict(p, conf_short, ed_year)


def top_cited(
    n: int = 20,
    conference: str | None = None,
    year: int | None = None,
) -> list[dict[str, Any]]:
    """Return the top-N papers by citation count."""
    return search_papers(conference=conference, year=year, limit=n, order_by="citation_count", descending=True)


def get_paper_authors(paper_id: str) -> list[dict[str, Any]]:
    """Return authors of a paper, ordered by position."""
    with get_session() as s:
        q = (
            select(Author, PaperAuthor.position, PaperAuthor.affiliation)
            .join(PaperAuthor, Author.id == PaperAuthor.author_id)
            .where(PaperAuthor.paper_id == paper_id)
            .order_by(PaperAuthor.position)
        )
        rows = s.execute(q).all()
        return [
            {
                "id":                  a.id,
                "full_name":           a.full_name,
                "position":            pos,
                "affiliation":         aff,
                "semantic_scholar_id": a.semantic_scholar_id,
                "homepage":            a.homepage,
            }
            for a, pos, aff in rows
        ]
