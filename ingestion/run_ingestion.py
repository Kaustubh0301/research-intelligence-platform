"""
Ingest papers for a target conference + year.

Usage:
    # ingest a specific conference+year
    python -m ingestion.run_ingestion --conference NeurIPS --year 2024 --limit 100

    # ingest all configured editions (use with care — large)
    python -m ingestion.run_ingestion --all --limit 100

    # list all configured conference editions
    python -m ingestion.run_ingestion --list

Environment:
    DATABASE_URL   (defaults to sqlite:///research_platform.db)
    S2_API_KEY     optional — raises S2 rate limit from 1 req/s to 100 req/s
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv()

if not os.environ.get("DATABASE_URL"):
    os.environ["DATABASE_URL"] = "sqlite:///research_platform.db"

from db.models import Base
from db.session import engine, get_session, ping
from ingestion.conferences_config import CONFERENCES, get_conference, get_edition, list_editions
from ingestion.fetch_openreview import fetch_papers as fetch_openreview
from ingestion.fetch_semantic_scholar import fetch_papers as fetch_s2
from ingestion.store import (
    upsert_conference,
    upsert_conference_edition,
    upsert_paper,
    upsert_paper_authors,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


def create_tables() -> None:
    Base.metadata.create_all(engine)
    log.info("Schema is up to date.")


def ingest_one(short_name: str, year: int, limit: int) -> dict:
    """Ingest a single conference edition. Returns counts dict."""
    conf_cfg = get_conference(short_name)
    ed_cfg   = get_edition(short_name, year)
    source   = conf_cfg["source"]

    log.info("─" * 60)
    log.info("Ingesting %s %d  (source=%s, limit=%d)", short_name, year, source, limit)

    # ── Fetch papers from the appropriate source ──────────────────
    if source == "openreview":
        invitation = ed_cfg["invitation"]
        raw_papers = fetch_openreview(invitation=invitation, year=year, limit=limit)
    else:
        s2_venue   = ed_cfg["s2_venue"]
        raw_papers = fetch_s2(venue=s2_venue, year=year, limit=limit)

    if not raw_papers:
        log.warning("No papers returned for %s %d. Skipping.", short_name, year)
        return {"inserted": 0, "updated": 0, "total": 0}

    log.info("Received %d papers — writing to database…", len(raw_papers))

    # ── Persist ───────────────────────────────────────────────────
    inserted = 0
    updated  = 0

    with get_session() as session:
        conference = upsert_conference(
            session,
            short_name=short_name,
            full_name=conf_cfg["full_name"],
            field=conf_cfg["field"],
            website=conf_cfg.get("website"),
        )
        edition = upsert_conference_edition(
            session,
            conference,
            year=year,
            location=ed_cfg.get("location"),
            openreview_id=ed_cfg.get("openreview_id"),
        )

        for i, raw in enumerate(raw_papers, 1):
            paper, created = upsert_paper(session, raw, edition)
            upsert_paper_authors(session, paper, raw.authors)

            if created:
                inserted += 1
            else:
                updated += 1

            if i % 50 == 0:
                log.info("  Progress: %d / %d", i, len(raw_papers))

    return {"inserted": inserted, "updated": updated, "total": inserted + updated}


def run(
    short_name: str | None,
    year: int | None,
    limit: int,
    ingest_all: bool,
) -> None:
    start = time.perf_counter()

    if not ping():
        log.error("Cannot reach the database. Check DATABASE_URL.")
        sys.exit(1)

    create_tables()

    if ingest_all:
        editions = list_editions()
    else:
        if not short_name or not year:
            log.error("--conference and --year are required unless --all is set.")
            sys.exit(1)
        editions = [(short_name.upper(), year)]

    total_inserted = 0
    total_updated  = 0

    for conf, yr in editions:
        try:
            counts = ingest_one(conf, yr, limit)
            total_inserted += counts["inserted"]
            total_updated  += counts["updated"]
        except KeyError as exc:
            log.error("Config error: %s", exc)
            if not ingest_all:
                sys.exit(1)

    elapsed = time.perf_counter() - start
    log.info("═" * 60)
    log.info("Ingestion complete in %.1fs", elapsed)
    log.info("  Papers inserted : %d", total_inserted)
    log.info("  Papers updated  : %d", total_updated)
    log.info("  Total           : %d", total_inserted + total_updated)


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest papers for a conference + year.")
    parser.add_argument("--conference", "-c", type=str,  help="Conference short name, e.g. NeurIPS")
    parser.add_argument("--year",       "-y", type=int,  help="Edition year, e.g. 2024")
    parser.add_argument("--limit",      "-n", type=int,  default=500, help="Max papers per edition (default: 500)")
    parser.add_argument("--all",        action="store_true", help="Ingest all configured editions")
    parser.add_argument("--list",       action="store_true", help="List all configured conference editions")
    args = parser.parse_args()

    if args.list:
        print("\nConfigured conference editions:")
        for conf, yr in list_editions():
            src = CONFERENCES[conf]["source"]
            print(f"  {conf:<8} {yr}  ({src})")
        print()
        return

    run(
        short_name=args.conference,
        year=args.year,
        limit=args.limit,
        ingest_all=args.all,
    )


if __name__ == "__main__":
    main()
