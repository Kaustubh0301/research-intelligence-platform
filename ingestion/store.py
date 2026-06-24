"""
Database storage layer for the ingestion pipeline.

All upsert logic lives here. The functions are idempotent:
running the same ingestion twice produces no duplicates.

Duplicate-detection strategy:
  - Conference:        unique on short_name
  - ConferenceEdition: unique on (conference_id, year)
  - Author:            unique on full_name (within this pipeline;
                       S2 / ORCID enrichment happens later)
  - Paper:             unique on openreview_id; falls back to title+year
  - PaperAuthor:       composite PK (paper_id, author_id)
"""

from __future__ import annotations

import logging
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models import Author, Conference, ConferenceEdition, Paper, PaperAuthor
from ingestion.fetch_openreview import RawPaper

log = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────
# CONFERENCE
# ──────────────────────────────────────────────────────────────

def upsert_conference(
    session: Session,
    short_name: str,
    full_name: str,
    field: str,
    website: str | None = None,
) -> Conference:
    conf = session.scalar(select(Conference).where(Conference.short_name == short_name))
    if conf is None:
        conf = Conference(short_name=short_name, full_name=full_name, field=field, website=website)
        session.add(conf)
        session.flush()
        log.info("Created conference: %s", short_name)
    return conf


# ──────────────────────────────────────────────────────────────
# CONFERENCE EDITION
# ──────────────────────────────────────────────────────────────

def upsert_conference_edition(
    session: Session,
    conference: Conference,
    year: int,
    location: str | None = None,
    openreview_id: str | None = None,
) -> ConferenceEdition:
    edition = session.scalar(
        select(ConferenceEdition).where(
            ConferenceEdition.conference_id == conference.id,
            ConferenceEdition.year == year,
        )
    )
    if edition is None:
        edition = ConferenceEdition(
            conference_id=conference.id,
            year=year,
            location=location,
            openreview_id=openreview_id,
        )
        session.add(edition)
        session.flush()
        log.info("Created edition: %s %d", conference.short_name, year)
    return edition


# ──────────────────────────────────────────────────────────────
# AUTHOR
# ──────────────────────────────────────────────────────────────

def get_or_create_author(session: Session, full_name: str) -> Author:
    """
    Look up an author by full_name. Creates a new row if not found.

    Name is the only identifier available from OpenReview at this stage.
    Richer deduplication (ORCID, S2 ID) is deferred to an enrichment pass.
    """
    author = session.scalar(select(Author).where(Author.full_name == full_name))
    if author is None:
        author = Author(full_name=full_name)
        session.add(author)
        session.flush()
        log.debug("Created author: %s", full_name)
    return author


# ──────────────────────────────────────────────────────────────
# PAPER
# ──────────────────────────────────────────────────────────────

def upsert_paper(
    session: Session,
    raw: RawPaper,
    edition: ConferenceEdition,
) -> tuple[Paper, bool]:
    """
    Insert or update a paper.

    Returns (paper, created) where created=True means a new row was inserted.
    Primary dedup key: openreview_id.
    Secondary dedup key: (title, year) — catches re-runs where the ID changes.
    """
    # 1. Try by openreview_id
    paper = None
    if raw.openreview_id:
        paper = session.scalar(
            select(Paper).where(Paper.openreview_id == raw.openreview_id)
        )

    # 2. Try by semantic_scholar_id
    if paper is None and raw.semantic_scholar_id:
        paper = session.scalar(
            select(Paper).where(Paper.semantic_scholar_id == raw.semantic_scholar_id)
        )

    # 3. Fallback: same title + year
    if paper is None:
        paper = session.scalar(
            select(Paper).where(Paper.title == raw.title, Paper.year == raw.year)
        )

    if paper is not None:
        # Update mutable fields in case the paper was ingested before enrichment
        paper.abstract             = raw.abstract or paper.abstract
        paper.pdf_url              = raw.pdf_url  or paper.pdf_url
        paper.presentation_type    = raw.presentation_type
        paper.conference_edition_id = edition.id
        if raw.openreview_id:
            paper.openreview_id = raw.openreview_id
        if raw.semantic_scholar_id:
            paper.semantic_scholar_id = raw.semantic_scholar_id
        if raw.arxiv_id:
            paper.arxiv_id = raw.arxiv_id
        if raw.doi:
            paper.doi = raw.doi
        session.flush()
        return paper, False

    paper = Paper(
        conference_edition_id=edition.id,
        openreview_id=raw.openreview_id,
        semantic_scholar_id=raw.semantic_scholar_id,
        arxiv_id=raw.arxiv_id,
        doi=raw.doi,
        title=raw.title,
        abstract=raw.abstract,
        year=raw.year,
        presentation_type=raw.presentation_type,
        pdf_url=raw.pdf_url,
        is_open_access=True,
    )
    session.add(paper)
    session.flush()
    return paper, True


# ──────────────────────────────────────────────────────────────
# PAPER–AUTHOR LINKS
# ──────────────────────────────────────────────────────────────

def upsert_paper_authors(
    session: Session,
    paper: Paper,
    author_names: Sequence[str],
) -> None:
    """
    Ensure paper_authors rows exist for every author in `author_names`.
    Existing links are left intact; missing ones are added.
    """
    existing_author_ids = {
        link.author_id for link in
        session.scalars(
            select(PaperAuthor).where(PaperAuthor.paper_id == paper.id)
        ).all()
    }
    seen_this_batch: set[str] = set()

    for position, name in enumerate(author_names, start=1):
        name = name.strip()
        if not name:
            continue
        author = get_or_create_author(session, name)
        if author.id in existing_author_ids or author.id in seen_this_batch:
            continue
        seen_this_batch.add(author.id)
        link = PaperAuthor(
            paper_id=paper.id,
            author_id=author.id,
            position=position,
        )
        session.add(link)

    session.flush()
