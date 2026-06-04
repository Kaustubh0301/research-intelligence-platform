"""
Semantic Scholar bulk paper fetcher.

Used for conferences not on OpenReview: CVPR, ICCV, ECCV, ACL, EMNLP, AAAI, IJCAI.
Calls the /graph/v1/paper/search/bulk endpoint with venue + year filters.

Returns a list of RawPaper objects compatible with ingestion/store.py.
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass

import requests

from ingestion.fetch_openreview import RawPaper

log = logging.getLogger(__name__)

S2_BASE      = "https://api.semanticscholar.org/graph/v1"
S2_FIELDS    = "title,abstract,authors,year,venue,publicationDate,externalIds,isOpenAccess,openAccessPdf,citationCount,influentialCitationCount"
DEFAULT_DELAY = 2.0   # seconds between requests (unauthenticated)
PAGE_SIZE     = 100


def _get_headers() -> dict[str, str]:
    api_key = os.environ.get("S2_API_KEY", "")
    if api_key:
        return {"x-api-key": api_key}
    return {}


def _to_raw_paper(item: dict, year: int) -> RawPaper | None:
    title = (item.get("title") or "").strip()
    if not title:
        return None

    # External IDs
    ext      = item.get("externalIds") or {}
    s2_id    = item.get("paperId") or None
    arxiv_id = ext.get("ArXiv") or None
    doi      = ext.get("DOI") or None

    # Abstract
    abstract = (item.get("abstract") or "").strip()

    # Authors: list of {authorId, name}
    authors = [a.get("name", "") for a in (item.get("authors") or []) if a.get("name")]

    # PDF URL: prefer open-access PDF, fall back to S2 URL
    oap = item.get("openAccessPdf") or {}
    pdf_url = oap.get("url") or None

    return RawPaper(
        openreview_id=None,
        semantic_scholar_id=s2_id,
        arxiv_id=arxiv_id,
        doi=doi,
        title=title,
        abstract=abstract,
        authors=authors,
        year=year,
        pdf_url=pdf_url,
        presentation_type="other",
    )


def fetch_papers(
    venue: str,
    year: int,
    limit: int = 500,
    delay: float = DEFAULT_DELAY,
) -> list[RawPaper]:
    """
    Fetch up to `limit` papers for a given venue + year from Semantic Scholar.

    Args:
        venue:  S2 venue string, e.g. "CVPR", "ACL"
        year:   publication year
        limit:  maximum papers to return
        delay:  seconds to sleep between paginated requests
    """
    headers = _get_headers()
    papers: list[RawPaper] = []
    token: str | None = None

    log.info("Fetching S2 papers: venue=%s year=%d target=%d", venue, year, limit)

    while len(papers) < limit:
        params: dict = {
            "venue":  venue,
            "year":   f"{year}-{year}",
            "fields": S2_FIELDS,
            "limit":  min(PAGE_SIZE, limit - len(papers)),
        }
        if token:
            params["token"] = token

        try:
            resp = requests.get(
                f"{S2_BASE}/paper/search/bulk",
                params=params,
                headers=headers,
                timeout=30,
            )
            resp.raise_for_status()
        except requests.RequestException as exc:
            log.error("S2 request failed: %s", exc)
            break

        data  = resp.json()
        items = data.get("data", [])

        if not items:
            log.info("No more results at offset (got empty data).")
            break

        for item in items:
            rp = _to_raw_paper(item, year)
            if rp:
                papers.append(rp)
            if len(papers) >= limit:
                break

        token = data.get("token")
        if not token:
            log.info("No continuation token — all results fetched.")
            break

        log.info("  Fetched %d so far, continuing…", len(papers))
        time.sleep(delay)

    log.info("Fetched %d papers from S2 (venue=%s year=%d)", len(papers), venue, year)
    return papers[:limit]
