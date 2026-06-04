"""
Citation Enrichment Pipeline
============================
For each paper in the database that has not yet been enriched, query
Semantic Scholar by title and write back:
  - semantic_scholar_id
  - citation_count
  - influential_citation_count
  - last_enriched_at

Resumable:  papers with last_enriched_at already set are skipped unless
            --force is passed.

Rate limits: Semantic Scholar unauthenticated = ~1 req/s shared pool.
             The pipeline uses a fixed inter-request delay plus
             exponential back-off on 429 responses.
             Pass --api-key to use 100 req/s (free key from
             https://api.semanticscholar.org).

Usage:
    python -m ingestion.enrich_citations
    python -m ingestion.enrich_citations --limit 50 --delay 1.2
    python -m ingestion.enrich_citations --force --api-key YOUR_KEY
    python -m ingestion.enrich_citations --report-only
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import requests
from sqlalchemy import select

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

if not os.environ.get("DATABASE_URL"):
    os.environ["DATABASE_URL"] = "sqlite:///research_platform.db"

from db.models import Paper
from db.session import get_session, ping

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# ── Semantic Scholar ───────────────────────────────────────────────────────────

S2_SEARCH_URL = "https://api.semanticscholar.org/graph/v1/paper/search/bulk"
S2_FIELDS     = "paperId,title,citationCount,influentialCitationCount,year"

MAX_RETRIES   = 5
BACKOFF_BASE  = 2   # seconds; doubles each retry


@dataclass
class S2Match:
    paper_id:               str
    citation_count:         int
    influential_citation_count: int
    matched_title:          str


@dataclass
class EnrichmentResult:
    enriched:      list[tuple[str, S2Match]] = field(default_factory=list)   # (local_title, match)
    failed:        list[str]                 = field(default_factory=list)   # local titles
    skipped:       int                       = 0


# ── Semantic Scholar client ────────────────────────────────────────────────────

def _s2_search(title: str, year: int | None, api_key: str | None, delay: float) -> S2Match | None:
    """
    Search S2 for a paper by title. Returns the best match or None.

    Matching rules:
      1. Take the top-1 result from the API.
      2. Accept only if the returned year matches ± 1 (tolerates preprint lag).
      3. Accept only if title similarity is high enough (≥ 0.75 word-overlap ratio).
    """
    headers = {"x-api-key": api_key} if api_key else {}
    params  = {
        "query":  title,
        "fields": S2_FIELDS,
        "limit":  5,       # fetch candidates; pick best by title overlap below
    }

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.get(S2_SEARCH_URL, params=params, headers=headers, timeout=15)
        except requests.RequestException as exc:
            log.warning("Network error (attempt %d/%d): %s", attempt, MAX_RETRIES, exc)
            time.sleep(BACKOFF_BASE ** attempt)
            continue

        if resp.status_code == 200:
            break

        if resp.status_code == 429:
            wait = BACKOFF_BASE ** attempt
            log.warning("Rate limited — sleeping %ds (attempt %d/%d)", wait, attempt, MAX_RETRIES)
            time.sleep(wait)
            continue

        if resp.status_code in (500, 502, 503, 504):
            wait = BACKOFF_BASE ** attempt
            log.warning("S2 server error %d — sleeping %ds", resp.status_code, wait)
            time.sleep(wait)
            continue

        log.error("Unexpected S2 status %d for %r", resp.status_code, title[:60])
        return None
    else:
        log.error("Giving up on %r after %d attempts", title[:60], MAX_RETRIES)
        return None

    time.sleep(delay)   # polite inter-request gap after every successful call

    hits = resp.json().get("data", [])
    if not hits:
        return None

    def _tokens(s: str) -> set[str]:
        return {w.lower().strip(".,:-()[]") for w in s.split() if len(w) > 2}

    local_tok = _tokens(title)

    # ── Pick the candidate with the highest title overlap ─────
    best_hit     = None
    best_overlap = 0.0

    for hit in hits:
        # Year guard: allow ±1 year to tolerate preprint lag
        if year and hit.get("year"):
            if abs(hit["year"] - year) > 1:
                continue

        s2_tok = _tokens(hit.get("title", ""))
        if not local_tok or not s2_tok:
            continue
        overlap = len(local_tok & s2_tok) / max(len(local_tok), len(s2_tok))
        if overlap > best_overlap:
            best_overlap = overlap
            best_hit     = hit

    if best_hit is None or best_overlap < 0.75:
        log.debug(
            "Best overlap %.2f < 0.75 — no match for: %r",
            best_overlap, title[:60],
        )
        return None

    return S2Match(
        paper_id=best_hit["paperId"],
        citation_count=best_hit.get("citationCount") or 0,
        influential_citation_count=best_hit.get("influentialCitationCount") or 0,
        matched_title=best_hit.get("title", ""),
    )


# ── Core enrichment logic ──────────────────────────────────────────────────────

def enrich(
    limit:   int | None = None,
    force:   bool       = False,
    delay:   float      = 1.5,
    api_key: str | None = None,
) -> EnrichmentResult:
    result = EnrichmentResult()

    with get_session() as session:
        query = select(Paper).order_by(Paper.created_at)
        if not force:
            query = query.where(Paper.last_enriched_at.is_(None))
        if limit:
            query = query.limit(limit)

        papers = session.scalars(query).all()

        total = len(papers)
        log.info("Papers to enrich: %d%s", total, "  (forced re-run)" if force else "")

        for i, paper in enumerate(papers, 1):
            log.info("[%d/%d] %s", i, total, paper.title[:70])

            match = _s2_search(paper.title, paper.year, api_key, delay)

            if match is None:
                log.warning("  ✗ No match found")
                result.failed.append(paper.title)
                # Still stamp last_enriched_at so a plain re-run skips it.
                # Use --force to retry failures.
                paper.last_enriched_at = datetime.now(timezone.utc)
                continue

            log.info(
                "  ✓ citations=%d  influential=%d  s2id=%s",
                match.citation_count,
                match.influential_citation_count,
                match.paper_id,
            )

            paper.semantic_scholar_id         = match.paper_id
            paper.citation_count              = match.citation_count
            paper.influential_citation_count  = match.influential_citation_count
            paper.last_enriched_at            = datetime.now(timezone.utc)

            result.enriched.append((paper.title, match))

        # session commits on __exit__

    return result


# ── Report ─────────────────────────────────────────────────────────────────────

def print_report(result: EnrichmentResult | None = None) -> None:
    DIV = "─" * 56

    # Always re-read from DB for an accurate snapshot
    with get_session() as session:
        all_papers = session.scalars(
            select(Paper).order_by(Paper.citation_count.desc())
        ).all()
        stats = {
            "total":    len(all_papers),
            "enriched": sum(1 for p in all_papers if p.last_enriched_at is not None),
            "matched":  sum(1 for p in all_papers if p.semantic_scholar_id is not None),
            "failed":   sum(1 for p in all_papers if p.last_enriched_at is not None and p.semantic_scholar_id is None),
        }
        top20 = [
            {"title": p.title, "citations": p.citation_count, "influential": p.influential_citation_count}
            for p in all_papers[:20]
            if p.semantic_scholar_id is not None
        ]

    print()
    print(DIV)
    print(" Citation Enrichment Report")
    print(DIV)
    print(f"  Total papers in DB   : {stats['total']}")
    print(f"  Enriched (attempted) : {stats['enriched']}")
    print(f"  Matched via S2       : {stats['matched']}")
    print(f"  Failed / no match    : {stats['failed']}")
    if stats['enriched']:
        pct = stats['matched'] / stats['enriched'] * 100
        print(f"  Match rate           : {pct:.1f}%")

    if result and result.failed:
        print()
        print(f" Failed matches ({len(result.failed)})")
        print(DIV)
        for title in result.failed:
            print(f"  ✗  {title[:70]}")

    print()
    print(f" Top 20 most-cited papers")
    print(DIV)
    if top20:
        for rank, p in enumerate(top20, 1):
            print(f"  {rank:>2}. [{p['citations']:>5} citations | {p['influential']:>4} influential]")
            print(f"       {p['title'][:68]}")
    else:
        print("  (no citation data yet — run enrichment first)")

    print(DIV)


# ── CLI ────────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Enrich papers with Semantic Scholar citation data.")
    parser.add_argument("--limit",       type=int,   default=None,  help="Max papers to process this run")
    parser.add_argument("--delay",       type=float, default=1.5,   help="Seconds between S2 requests (default: 1.5)")
    parser.add_argument("--force",       action="store_true",       help="Re-enrich papers that were already processed")
    parser.add_argument("--api-key",     type=str,   default=None,  help="Semantic Scholar API key (raises limit to 100 req/s)")
    parser.add_argument("--report-only", action="store_true",       help="Skip enrichment; just print the current report")
    args = parser.parse_args()

    if not ping():
        log.error("Cannot reach the database. Check DATABASE_URL.")
        sys.exit(1)

    if args.report_only:
        print_report()
        return

    start  = time.perf_counter()
    result = enrich(
        limit=args.limit,
        force=args.force,
        delay=args.delay,
        api_key=args.api_key,
    )
    elapsed = time.perf_counter() - start
    log.info("Enrichment finished in %.1fs", elapsed)

    print_report(result)


if __name__ == "__main__":
    main()