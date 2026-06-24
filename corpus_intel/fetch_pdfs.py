"""
PDF fetcher and parser for conference papers.

Fetches PDFs from ACL Anthology or arXiv, extracts full text,
and writes to paper_sections table so Claude analysis uses full paper content.

Priority: ACL Anthology DOI > arXiv ID > skip

Usage:
    python -m corpus_intel.fetch_pdfs --conference ACL --year 2024
    python -m corpus_intel.fetch_pdfs --conference ACL --year 2024 --limit 50
"""

from __future__ import annotations

import argparse
import io
import logging
import os
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv()

if not os.environ.get("DATABASE_URL"):
    os.environ["DATABASE_URL"] = "sqlite:///research_platform.db"

import fitz  # PyMuPDF
import requests
from sqlalchemy import select

from db.session import get_session
from db.models import Conference, ConferenceEdition, Paper, PaperSection

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

_REQUEST_TIMEOUT = 30
_RETRY_DELAY = 5
_MAX_RETRIES = 3
_BATCH_SLEEP = 1  # seconds between every 10 papers

_HEADERS = {
    "User-Agent": "ResearchPlatform/1.0 (academic research; contact: research@example.com)"
}


# ── PDF source resolution ─────────────────────────────────────────────────────

def _acl_anthology_url(doi: str) -> str | None:
    """Convert ACL Anthology DOI to PDF URL."""
    if doi and doi.startswith("10.18653/v1/"):
        acl_id = doi[len("10.18653/v1/"):]
        return f"https://aclanthology.org/{acl_id}.pdf"
    return None


def _arxiv_url(arxiv_id: str) -> str | None:
    if arxiv_id:
        return f"https://arxiv.org/pdf/{arxiv_id}"
    return None


def _pdf_url_for(paper: Paper) -> tuple[str, str] | None:
    """Return (url, source_label) for the best available PDF, or None."""
    acl_url = _acl_anthology_url(paper.doi or "")
    if acl_url:
        return acl_url, "acl_anthology"
    arxiv_url = _arxiv_url(paper.arxiv_id or "")
    if arxiv_url:
        return arxiv_url, "arxiv"
    if paper.pdf_url:
        return paper.pdf_url, "pdf_url"
    return None


# ── PDF download ──────────────────────────────────────────────────────────────

def _download_pdf(url: str) -> bytes | None:
    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            resp = requests.get(url, headers=_HEADERS, timeout=_REQUEST_TIMEOUT)
            if resp.status_code == 200 and resp.content:
                return resp.content
            log.warning("HTTP %d for %s", resp.status_code, url)
            return None
        except requests.RequestException as exc:
            log.warning("Download failed (attempt %d/%d): %s", attempt, _MAX_RETRIES, exc)
            if attempt < _MAX_RETRIES:
                time.sleep(_RETRY_DELAY)
    return None


# ── PDF parsing ───────────────────────────────────────────────────────────────

_SECTION_PATTERNS = [
    (r"^abstract\b",            "abstract"),
    (r"^1\.?\s+introduction\b", "introduction"),
    (r"^related\s+work\b",      "related_work"),
    (r"^(2|3|4)\.?\s+.*(method|approach|model|framework|architecture)\b", "methodology"),
    (r"^(3|4|5)\.?\s+experiment", "experiments"),
    (r"^(4|5|6)\.?\s+result",    "results"),
    (r"^discussion\b",           "discussion"),
    (r"^conclusion\b",           "conclusion"),
    (r"^limitation\b",           "limitations"),
    (r"^future\b",               "future_work"),
]
_COMPILED = [(re.compile(p, re.IGNORECASE), name) for p, name in _SECTION_PATTERNS]


def _detect_section(heading: str) -> str | None:
    h = heading.strip().lower()
    for pattern, name in _COMPILED:
        if pattern.match(h):
            return name
    return None


def _parse_pdf(pdf_bytes: bytes) -> dict:
    """Extract full text and section breakdown from PDF bytes."""
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")

    pages_text: list[str] = []
    for page in doc:
        pages_text.append(page.get_text("text"))
    doc.close()

    full_text = "\n".join(pages_text).strip()
    if not full_text:
        return {"full_text": None}

    # Simple section detection: look for short lines that match section headings
    sections: dict[str, list[str]] = {}
    current_section: str | None = None
    current_lines: list[str] = []

    for line in full_text.splitlines():
        stripped = line.strip()
        if not stripped:
            if current_lines:
                current_lines.append("")
            continue

        # Candidate heading: short line (< 80 chars), not ending in period
        if len(stripped) < 80 and not stripped.endswith("."):
            detected = _detect_section(stripped)
            if detected:
                if current_section and current_lines:
                    sections[current_section] = "\n".join(current_lines).strip()
                current_section = detected
                current_lines = []
                continue

        if current_section:
            current_lines.append(stripped)

    if current_section and current_lines:
        sections[current_section] = "\n".join(current_lines).strip()

    result = {"full_text": full_text[:100_000]}  # cap at 100k chars
    for section_name in ("abstract", "introduction", "related_work", "methodology",
                         "experiments", "results", "discussion", "conclusion",
                         "limitations", "future_work"):
        result[section_name] = sections.get(section_name)

    result["word_count"] = len(full_text.split())
    result["sections_found"] = list(sections.keys())
    return result


# ── DB write ──────────────────────────────────────────────────────────────────

def _upsert_paper_section(session, paper_id: str, parsed: dict) -> None:
    import json
    existing = session.scalar(
        select(PaperSection).where(PaperSection.paper_id == paper_id)
    )
    if existing:
        rec = existing
    else:
        rec = PaperSection(paper_id=paper_id)
        session.add(rec)

    rec.full_text       = parsed.get("full_text")
    rec.abstract        = parsed.get("abstract")
    rec.introduction    = parsed.get("introduction")
    rec.related_work    = parsed.get("related_work")
    rec.methodology     = parsed.get("methodology")
    rec.experiments     = parsed.get("experiments")
    rec.results         = parsed.get("results")
    rec.discussion      = parsed.get("discussion")
    rec.conclusion      = parsed.get("conclusion")
    rec.limitations     = parsed.get("limitations")
    rec.future_work     = parsed.get("future_work")
    rec.word_count      = parsed.get("word_count")
    rec.sections_found  = json.dumps(parsed.get("sections_found", []))
    rec.segmenter_version = "fetch_pdfs/v1"
    session.flush()


# ── Runner ────────────────────────────────────────────────────────────────────

def run(conference: str, year: int, limit: int = 500, force: bool = False) -> None:
    with get_session() as session:
        conf_row = session.scalar(
            select(Conference).where(Conference.short_name == conference.upper())
        )
        if not conf_row:
            log.error("Conference %s not in DB", conference)
            sys.exit(1)

        edition = session.scalar(
            select(ConferenceEdition).where(
                ConferenceEdition.conference_id == conf_row.id,
                ConferenceEdition.year == year,
            )
        )
        if not edition:
            log.error("%s %d not in DB", conference, year)
            sys.exit(1)

        q = select(Paper).where(Paper.conference_edition_id == edition.id)
        if not force:
            already_done = session.scalars(select(PaperSection.paper_id)).all()
            q = q.where(Paper.id.notin_(already_done))
        q = q.limit(limit)

        papers = session.scalars(q).all()
        log.info("Fetching PDFs for %d %s %d papers", len(papers), conference, year)

        done = errors = skipped = 0
        for i, paper in enumerate(papers, 1):
            src = _pdf_url_for(paper)
            if src is None:
                log.info("[%d/%d] SKIP (no PDF source): %s", i, len(papers), paper.title[:60])
                skipped += 1
                continue

            url, source_label = src
            log.info("[%d/%d] %s → %s", i, len(papers), paper.title[:55], source_label)

            pdf_bytes = _download_pdf(url)
            if not pdf_bytes:
                log.warning("  → Download failed")
                errors += 1
                continue

            try:
                parsed = _parse_pdf(pdf_bytes)
            except Exception as exc:
                log.warning("  → PDF parse error: %s", exc)
                errors += 1
                continue

            if not parsed.get("full_text"):
                log.warning("  → No text extracted")
                errors += 1
                continue

            _upsert_paper_section(session, paper.id, parsed)
            session.commit()
            done += 1
            log.info("  → %d words, sections: %s", parsed.get("word_count", 0),
                     parsed.get("sections_found", []))

            if i % 10 == 0:
                time.sleep(_BATCH_SLEEP)

    log.info("Done. fetched=%d errors=%d skipped=%d", done, errors, skipped)


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch and parse PDFs for conference papers")
    parser.add_argument("--conference", "-c", required=True)
    parser.add_argument("--year",       "-y", type=int, required=True)
    parser.add_argument("--limit",      "-n", type=int, default=500)
    parser.add_argument("--force",      action="store_true", help="Re-fetch already parsed papers")
    args = parser.parse_args()
    run(args.conference, args.year, args.limit, args.force)


if __name__ == "__main__":
    main()
