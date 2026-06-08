"""
OpenReview fetcher — returns a list of normalised paper dicts
for a given conference invitation string.

Kept as a pure data-fetch module with no DB dependency so it
can be tested and reused independently.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import openreview

log = logging.getLogger(__name__)

OPENREVIEW_BASE = "https://api2.openreview.net"


@dataclass
class RawPaper:
    openreview_id:     str | None
    title:             str
    authors:           list[str]
    abstract:          str
    year:              int
    pdf_url:           str | None
    presentation_type: str          # poster / oral / spotlight / other
    keywords:          list[str] = field(default_factory=list)
    semantic_scholar_id: str | None = None
    arxiv_id:          str | None = None
    doi:               str | None = None


def _parse_field(content: dict[str, Any], key: str, default: Any = "") -> Any:
    """Handles both dict-wrapped values (API v2) and plain values."""
    val = content.get(key, default)
    if isinstance(val, dict):
        return val.get("value", default)
    return val if val is not None else default


def _infer_presentation_type(venue: str) -> str:
    v = venue.lower()
    if "oral"      in v: return "oral"
    if "spotlight" in v: return "spotlight"
    if "poster"    in v: return "poster"
    if "workshop"  in v: return "workshop"
    return "other"


def _is_accepted(venue: str) -> bool:
    """Accept only notes with a venue that indicates acceptance (poster/oral/spotlight).
    Rejects: submitted, withdrawn, desk rejected."""
    v = venue.lower().strip()
    if not v:
        return False
    _REJECT_TERMS = ("submitted", "withdrawn", "desk rejected", "rejected")
    return not any(term in v for term in _REJECT_TERMS)


def fetch_papers(
    invitation: str,
    year: int,
    limit: int = 100,
    batch_size: int = 200,
) -> list[RawPaper]:
    """
    Fetch up to `limit` accepted papers for the given OpenReview invitation.

    Args:
        invitation:  e.g. 'NeurIPS.cc/2024/Conference/-/Submission'
        year:        publication year to stamp on every paper
        limit:       maximum number of accepted papers to return
        batch_size:  how many notes to pull per API call
    """
    client = openreview.api.OpenReviewClient(baseurl=OPENREVIEW_BASE)

    papers: list[RawPaper] = []
    offset = 0

    log.info("Fetching from OpenReview: %s  (target=%d)", invitation, limit)

    while len(papers) < limit:
        notes = client.get_notes(
            invitation=invitation,
            limit=batch_size,
            offset=offset,
        )
        if not notes:
            log.info("No more notes at offset %d — stopping.", offset)
            break

        for note in notes:
            c = note.content
            venue = _parse_field(c, "venue", "")

            if not _is_accepted(venue):
                continue

            title    = _parse_field(c, "title", "").strip()
            abstract = _parse_field(c, "abstract", "").strip()
            authors  = _parse_field(c, "authors", [])
            keywords = _parse_field(c, "keywords", [])

            if not title:
                continue

            papers.append(RawPaper(
                openreview_id=note.id,
                title=title,
                authors=authors if isinstance(authors, list) else [authors],
                abstract=abstract,
                year=year,
                pdf_url=f"https://openreview.net/pdf?id={note.id}",
                presentation_type=_infer_presentation_type(venue),
                keywords=keywords if isinstance(keywords, list) else [],
            ))

            if len(papers) >= limit:
                break

        offset += batch_size

    log.info("Fetched %d accepted papers.", len(papers))
    return papers[:limit]
