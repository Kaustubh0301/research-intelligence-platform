"""
Metrics dashboard CLI.

Usage:
    python -m metrics.dashboard                          # all dashboards
    python -m metrics.dashboard --metric per-conference
    python -m metrics.dashboard --metric per-year
    python -m metrics.dashboard --metric top-cited [--n 20]
    python -m metrics.dashboard --metric citations
    python -m metrics.dashboard --json                   # emit JSON instead of text
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv()

if not os.environ.get("DATABASE_URL"):
    os.environ["DATABASE_URL"] = "sqlite:///research_platform.db"

from sqlalchemy import func, select
from db.models import Conference, ConferenceEdition, Paper
from db.session import get_session


# ── Data fetchers ─────────────────────────────────────────────────────────────

def _fetch_all() -> list[dict[str, Any]]:
    """Load all papers with conference + year joined."""
    with get_session() as s:
        q = (
            select(
                Paper.id,
                Paper.title,
                Paper.year,
                Paper.citation_count,
                Paper.influential_citation_count,
                Paper.presentation_type,
                Paper.pdf_local_path,
                Conference.short_name.label("conference"),
                Conference.field,
                ConferenceEdition.year.label("edition_year"),
            )
            .join(ConferenceEdition, Paper.conference_edition_id == ConferenceEdition.id, isouter=True)
            .join(Conference, ConferenceEdition.conference_id == Conference.id, isouter=True)
        )
        rows = s.execute(q).mappings().all()
    return [dict(r) for r in rows]


# ── Metric: papers per conference ────────────────────────────────────────────

def papers_per_conference(papers: list[dict]) -> dict[str, Any]:
    counts: Counter = Counter()
    for p in papers:
        counts[p["conference"] or "Unknown"] += 1

    rows = sorted(counts.items(), key=lambda x: -x[1])
    total = sum(counts.values())

    result = {
        "metric":  "papers_per_conference",
        "total":   total,
        "rows":    [{"conference": k, "count": v} for k, v in rows],
    }
    return result


def print_papers_per_conference(data: dict) -> None:
    print(f"\n{'─'*50}")
    print(f" Papers per Conference  (total={data['total']})")
    print(f"{'─'*50}")
    max_count = data["rows"][0]["count"] if data["rows"] else 1
    for row in data["rows"]:
        bar = "█" * int(30 * row["count"] / max_count)
        print(f"  {row['conference']:<10} {row['count']:>5}  {bar}")
    print()


# ── Metric: papers per year ──────────────────────────────────────────────────

def papers_per_year(papers: list[dict]) -> dict[str, Any]:
    counts: Counter = Counter()
    for p in papers:
        counts[p["edition_year"] or p["year"]] += 1

    rows = sorted(counts.items())
    total = sum(counts.values())

    return {
        "metric": "papers_per_year",
        "total":  total,
        "rows":   [{"year": k, "count": v} for k, v in rows],
    }


def print_papers_per_year(data: dict) -> None:
    print(f"\n{'─'*50}")
    print(f" Papers per Year  (total={data['total']})")
    print(f"{'─'*50}")
    max_count = max((r["count"] for r in data["rows"]), default=1)
    for row in data["rows"]:
        bar = "█" * int(30 * row["count"] / max_count)
        print(f"  {row['year']}  {row['count']:>5}  {bar}")
    print()


# ── Metric: papers per conference × year ─────────────────────────────────────

def papers_per_conference_year(papers: list[dict]) -> dict[str, Any]:
    counts: Counter = Counter()
    for p in papers:
        key = (p["conference"] or "Unknown", p["edition_year"] or p["year"])
        counts[key] += 1

    rows = sorted(counts.items(), key=lambda x: (x[0][0], x[0][1]))
    return {
        "metric": "papers_per_conference_year",
        "rows":   [{"conference": k[0], "year": k[1], "count": v} for k, v in rows],
    }


# ── Metric: top cited papers ─────────────────────────────────────────────────

def top_cited_papers(papers: list[dict], n: int = 20) -> dict[str, Any]:
    ranked = sorted(papers, key=lambda p: p["citation_count"], reverse=True)[:n]
    return {
        "metric": "top_cited",
        "n":      n,
        "rows":   [
            {
                "rank":              i + 1,
                "title":             p["title"],
                "conference":        p["conference"],
                "year":              p["edition_year"] or p["year"],
                "citation_count":    p["citation_count"],
                "influential_count": p["influential_citation_count"],
                "presentation_type": p["presentation_type"],
            }
            for i, p in enumerate(ranked)
        ],
    }


def print_top_cited(data: dict) -> None:
    print(f"\n{'─'*80}")
    print(f" Top {data['n']} Cited Papers")
    print(f"{'─'*80}")
    print(f"  {'#':>3}  {'Cit':>6}  {'Inf':>5}  {'Conf':<8}  {'Year'}  Title")
    print(f"  {'─'*3}  {'─'*6}  {'─'*5}  {'─'*8}  {'─'*4}  {'─'*40}")
    for row in data["rows"]:
        conf = (row["conference"] or "?")[:8]
        print(
            f"  {row['rank']:>3}  {row['citation_count']:>6}  "
            f"{row['influential_count']:>5}  {conf:<8}  {row['year']}  "
            f"{row['title'][:50]}"
        )
    print()


# ── Metric: citation distribution ────────────────────────────────────────────

def citation_distribution(papers: list[dict]) -> dict[str, Any]:
    counts = [p["citation_count"] for p in papers if p["citation_count"] is not None]
    if not counts:
        return {"metric": "citation_distribution", "total": 0, "buckets": []}

    total = len(counts)
    mean  = sum(counts) / total
    srt   = sorted(counts)

    def pct(q: float) -> float:
        idx = int(q * (len(srt) - 1))
        return srt[idx]

    # Logarithmic buckets: 0, 1-9, 10-99, 100-999, 1000+
    buckets = [
        ("0",         lambda c: c == 0),
        ("1–9",       lambda c: 1 <= c <= 9),
        ("10–49",     lambda c: 10 <= c <= 49),
        ("50–99",     lambda c: 50 <= c <= 99),
        ("100–499",   lambda c: 100 <= c <= 499),
        ("500–999",   lambda c: 500 <= c <= 999),
        ("1000+",     lambda c: c >= 1000),
    ]
    bucket_counts = []
    for label, pred in buckets:
        n = sum(1 for c in counts if pred(c))
        bucket_counts.append({"range": label, "count": n, "pct": round(100 * n / total, 1)})

    return {
        "metric":      "citation_distribution",
        "total":       total,
        "mean":        round(mean, 1),
        "median":      pct(0.5),
        "p75":         pct(0.75),
        "p90":         pct(0.90),
        "p99":         pct(0.99),
        "max":         srt[-1],
        "buckets":     bucket_counts,
    }


def print_citation_distribution(data: dict) -> None:
    if data["total"] == 0:
        print("\nNo citation data available.")
        return
    print(f"\n{'─'*55}")
    print(f" Citation Distribution  (n={data['total']})")
    print(f"{'─'*55}")
    print(f"  Mean   : {data['mean']}")
    print(f"  Median : {data['median']}")
    print(f"  P75    : {data['p75']}")
    print(f"  P90    : {data['p90']}")
    print(f"  P99    : {data['p99']}")
    print(f"  Max    : {data['max']}")
    print()
    max_count = max((b["count"] for b in data["buckets"]), default=1)
    for b in data["buckets"]:
        bar = "█" * int(30 * b["count"] / max_count)
        print(f"  {b['range']:<10}  {b['count']:>5}  ({b['pct']:>5}%)  {bar}")
    print()


# ── CLI ───────────────────────────────────────────────────────────────────────

METRIC_CHOICES = ("per-conference", "per-year", "top-cited", "citations", "all")


def main() -> None:
    parser = argparse.ArgumentParser(description="Research platform metrics dashboard.")
    parser.add_argument(
        "--metric", "-m",
        choices=METRIC_CHOICES,
        default="all",
        help="Which metric to display (default: all)",
    )
    parser.add_argument("--n",    type=int, default=20,   help="Top-N for top-cited (default: 20)")
    parser.add_argument("--json", action="store_true",     help="Output raw JSON instead of formatted text")
    args = parser.parse_args()

    papers = _fetch_all()

    if not papers:
        print("No papers found in the database.")
        sys.exit(0)

    results: dict[str, Any] = {"total_papers": len(papers)}
    selected = args.metric

    if selected in ("per-conference", "all"):
        results["per_conference"] = papers_per_conference(papers)
    if selected in ("per-year", "all"):
        results["per_year"] = papers_per_year(papers)
    if selected in ("top-cited", "all"):
        results["top_cited"] = top_cited_papers(papers, n=args.n)
    if selected in ("citations", "all"):
        results["citation_distribution"] = citation_distribution(papers)

    if args.json:
        print(json.dumps(results, indent=2))
        return

    print(f"\n Research Intelligence Platform — Metrics")
    print(f" Total papers in DB: {len(papers)}")

    if "per_conference" in results:
        print_papers_per_conference(results["per_conference"])
    if "per_year" in results:
        print_papers_per_year(results["per_year"])
    if "top_cited" in results:
        print_top_cited(results["top_cited"])
    if "citation_distribution" in results:
        print_citation_distribution(results["citation_distribution"])


if __name__ == "__main__":
    main()
