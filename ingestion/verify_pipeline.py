"""
Smoke-test the full ingestion pipeline against a local SQLite database.

This verifies models, store logic, and deduplication without needing
a running PostgreSQL instance. Switch to Postgres by setting DATABASE_URL.

Usage:
    python ingestion/verify_pipeline.py
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# ── Use SQLite in-memory when no DATABASE_URL is set ─────────
if not os.environ.get("DATABASE_URL"):
    os.environ["DATABASE_URL"] = "sqlite:///:memory:"

logging.basicConfig(level=logging.INFO, format="%(levelname)-8s  %(message)s")
log = logging.getLogger(__name__)

from sqlalchemy import func, select

from db.models import Author, Base, Conference, ConferenceEdition, Paper, PaperAuthor
from db.session import engine, get_session
from ingestion.fetch_openreview import RawPaper
from ingestion.store import (
    upsert_conference,
    upsert_conference_edition,
    upsert_paper,
    upsert_paper_authors,
)


def make_raw(n: int) -> RawPaper:
    return RawPaper(
        openreview_id=f"or_id_{n}",
        title=f"Test Paper {n}: On the Properties of Neural Networks",
        authors=[f"Alice Author {n}", "Bob Shared"],  # Bob appears in all papers
        abstract=f"Abstract text for paper {n}. " * 10,
        year=2024,
        pdf_url=f"https://openreview.net/pdf?id=or_id_{n}",
        presentation_type="poster",
        keywords=["deep learning", "transformer"],
    )


def run_verification() -> None:
    log.info("Creating schema (SQLite in-memory)…")
    Base.metadata.create_all(engine)

    # ── Phase 1: Insert 5 papers ──────────────────────────────
    log.info("Phase 1: inserting 5 papers…")
    with get_session() as session:
        conf    = upsert_conference(session, "NeurIPS", "Neural Information Processing Systems", "ML", "https://neurips.cc")
        edition = upsert_conference_edition(session, conf, 2024, "Vancouver", "NeurIPS.cc/2024/Conference")
        for i in range(1, 6):
            paper, created = upsert_paper(session, make_raw(i), edition)
            upsert_paper_authors(session, paper, make_raw(i).authors)
            assert created, f"Paper {i} should be new"

    # ── Phase 2: Re-run same papers — no duplicates ───────────
    log.info("Phase 2: re-running same 5 papers (dedup check)…")
    with get_session() as session:
        conf    = upsert_conference(session, "NeurIPS", "Neural Information Processing Systems", "ML")
        edition = upsert_conference_edition(session, conf, 2024)
        for i in range(1, 6):
            paper, created = upsert_paper(session, make_raw(i), edition)
            upsert_paper_authors(session, paper, make_raw(i).authors)
            assert not created, f"Paper {i} should NOT be new on second run"

    # ── Assertions ────────────────────────────────────────────
    with get_session() as session:
        n_conferences = session.scalar(select(func.count()).select_from(Conference))
        n_editions    = session.scalar(select(func.count()).select_from(ConferenceEdition))
        n_papers      = session.scalar(select(func.count()).select_from(Paper))
        n_authors     = session.scalar(select(func.count()).select_from(Author))
        n_links       = session.scalar(select(func.count()).select_from(PaperAuthor))

    # 5 papers × 2 authors = 10 links, but "Bob Shared" is one author row
    # so authors = 5 (Alice_1..Alice_5) + 1 (Bob) = 6
    assert n_conferences == 1,  f"Expected 1 conference, got {n_conferences}"
    assert n_editions    == 1,  f"Expected 1 edition, got {n_editions}"
    assert n_papers      == 5,  f"Expected 5 papers, got {n_papers}"
    assert n_authors     == 6,  f"Expected 6 authors, got {n_authors}"
    assert n_links       == 10, f"Expected 10 paper_author links, got {n_links}"

    log.info("─" * 45)
    log.info("All assertions passed ✓")
    log.info("  conferences      : %d", n_conferences)
    log.info("  conference edits : %d", n_editions)
    log.info("  papers           : %d", n_papers)
    log.info("  authors          : %d  (Bob deduped across 5 papers)", n_authors)
    log.info("  paper_author rows: %d", n_links)
    log.info("─" * 45)
    log.info("Pipeline is ready. Set DATABASE_URL and run:")
    log.info("  python -m ingestion.run_ingestion --limit 100")


if __name__ == "__main__":
    run_verification()
