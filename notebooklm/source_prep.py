"""
Source preparation for NotebookLM uploads.

Assembles a structured text document for each paper from DB data.
This is what gets uploaded as a NotebookLM source — not the raw PDF.

Two modes:
  - Full:          abstract + sections from paper_sections (preferred)
  - Abstract-only: just abstract from papers.abstract (fallback when no PDF)

Returns a SourceDocument with the text and which mode was used.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models import Author, Conference, ConferenceEdition, Paper, PaperAuthor, PaperSection


# Sections included in the upload, in display order.
# Keys match PaperSection column names.
_SECTION_ORDER = [
    ("abstract",               "ABSTRACT"),
    ("introduction",           "INTRODUCTION"),
    ("methodology",            "METHODOLOGY"),
    ("experiments",            "EXPERIMENTS"),
    ("results",                "RESULTS"),
    ("results_from_experiments", "RESULTS"),   # v3 synthetic field — same label
    ("discussion",             "DISCUSSION"),
    ("conclusion",             "CONCLUSION"),
    ("limitations",            "LIMITATIONS"),
    ("future_work",            "FUTURE WORK"),
]

# PaperSection does not have results_from_experiments as a column;
# it is a computed attribute set by the segmenter on the in-memory object
# but not persisted separately.  The experiments column may contain it
# if v3 merged it in.  We only emit labelled sections that exist as
# actual PaperSection columns.
_PERSISTED_SECTION_FIELDS = {
    "abstract", "introduction", "related_work", "methodology",
    "experiments", "results", "discussion", "conclusion",
    "limitations", "future_work",
}


@dataclass
class SourceDocument:
    paper_id:   str
    title:      str
    text:       str
    char_count: int
    mode:       str          # "full" | "abstract_only"
    sections_included: list[str]


def build_source(session: Session, paper_id: str) -> Optional[SourceDocument]:
    """
    Build a NotebookLM-uploadable source document for the given paper.

    Returns None if the paper does not exist.
    Returns a SourceDocument with mode='abstract_only' if no paper_sections row.
    """
    paper = session.get(Paper, paper_id)
    if paper is None:
        return None

    # Resolve conference name and year
    conf_label = _resolve_conference(session, paper)

    # Resolve author list (up to 6, ordered by position)
    authors = session.execute(
        select(Author.full_name)
        .join(PaperAuthor, PaperAuthor.author_id == Author.id)
        .where(PaperAuthor.paper_id == paper_id)
        .order_by(PaperAuthor.position)
        .limit(6)
    ).scalars().all()
    author_str = ", ".join(authors) if authors else "Unknown"

    # Header block (always present)
    header_lines = [
        f"PAPER: {paper.title}",
        f"AUTHORS: {author_str}",
        f"CONFERENCE: {conf_label}",
        f"CITATIONS: {paper.citation_count}",
        "",
    ]

    # Try to build a full source from paper_sections
    ps = session.execute(
        select(PaperSection).where(PaperSection.paper_id == paper_id)
    ).scalar_one_or_none()

    if ps is not None:
        return _build_full(paper, header_lines, ps)

    # Fallback: abstract only
    return _build_abstract_only(paper, header_lines)


def _build_full(
    paper: Paper,
    header_lines: list[str],
    ps: PaperSection,
) -> SourceDocument:
    body_lines: list[str] = []
    sections_included: list[str] = []

    for field_name, label in _SECTION_ORDER:
        if field_name not in _PERSISTED_SECTION_FIELDS:
            continue
        text = getattr(ps, field_name, None)
        if not text:
            continue
        # Skip duplicate RESULTS label if we already included results
        if field_name == "results" and "results" in sections_included:
            continue
        body_lines += [f"{label}:", text, ""]
        sections_included.append(field_name)

    full_text = "\n".join(header_lines + body_lines).rstrip()
    return SourceDocument(
        paper_id=paper.id,
        title=paper.title,
        text=full_text,
        char_count=len(full_text),
        mode="full",
        sections_included=sections_included,
    )


def _build_abstract_only(
    paper: Paper,
    header_lines: list[str],
) -> SourceDocument:
    abstract = paper.abstract or ""
    body_lines: list[str] = []
    sections_included: list[str] = []

    if abstract:
        body_lines += ["ABSTRACT:", abstract, ""]
        sections_included.append("abstract")

    full_text = "\n".join(header_lines + body_lines).rstrip()
    return SourceDocument(
        paper_id=paper.id,
        title=paper.title,
        text=full_text,
        char_count=len(full_text),
        mode="abstract_only",
        sections_included=sections_included,
    )


def _resolve_conference(session: Session, paper: Paper) -> str:
    """Return a human-readable 'CONFERENCE YEAR' string for the paper."""
    if not paper.conference_edition_id:
        return f"Unknown {paper.year}"
    edition = session.get(ConferenceEdition, paper.conference_edition_id)
    if edition is None:
        return f"Unknown {paper.year}"
    conf = session.get(Conference, edition.conference_id)
    name = conf.short_name if conf else "Unknown"
    return f"{name} {edition.year}"
