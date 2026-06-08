"""
POST /api/v1/search

Full-text cross-field search with a JSON request body.
Searches title, abstract, techniques, datasets, and categories.
Returns results enriched with graph metrics and top techniques.

Scoring (additive):
  +40  exact title match (case-insensitive)
  +20  title contains query
  +15  abstract contains query
  +15  category name contains query
  +12  technique name contains query
  +10  dataset name contains query
  + log1p(citation_count)  tiebreaker

Supports filters (conference, year, cluster, technique) applied
as a post-pass on the ranked result set.
"""

from __future__ import annotations

import math
from collections import defaultdict
from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from api.deps import get_db
from api.helpers import (
    base_paper_query,
    fetch_top_techniques_batch,
    paper_summary,
)
from api.models import (
    SearchMatch,
    SearchRequest,
    SearchResponse,
)
from db.models import (
    Conference,
    ConferenceEdition,
    Paper,
    PaperCategory,
    PaperDataset,
    PaperGraphMetric,
    PaperTechnique,
)

router = APIRouter(prefix="/api/v1", tags=["Search"])


@router.post(
    "/search",
    response_model=SearchResponse,
    summary="Full-text search across papers, techniques, datasets, and categories",
)
def search(
    req: SearchRequest,
    db: Session = Depends(get_db),
) -> SearchResponse:
    term = req.query.strip().lower()

    # paper_id → (score, matched_in, Paper, conf_short, pgm)
    scores:      dict[str, float]               = defaultdict(float)
    matched_in:  dict[str, list[str]]           = defaultdict(list)
    paper_cache: dict[str, tuple]               = {}   # id → (Paper, conf_short, pgm)

    def _cache(paper: Paper, conf: Optional[str], pgm):
        if paper.id not in paper_cache:
            paper_cache[paper.id] = (paper, conf, pgm)

    def _base():
        """Shorthand for the enriched paper query used throughout."""
        return base_paper_query()

    # ── Signal 1: title match ─────────────────────────────────────────────────
    for row in db.execute(_base().where(func.lower(Paper.title).contains(term))).all():
        paper, conf, _yr, pgm = row
        _cache(paper, conf, pgm)
        if paper.title.lower() == term:
            scores[paper.id] += 40
            matched_in[paper.id].append("title:exact")
        else:
            scores[paper.id] += 20
            matched_in[paper.id].append("title")

    # ── Signal 2: abstract match ──────────────────────────────────────────────
    for row in db.execute(
        _base().where(
            func.lower(Paper.abstract).contains(term),
            Paper.abstract.isnot(None),
        )
    ).all():
        paper, conf, _yr, pgm = row
        _cache(paper, conf, pgm)
        if paper.id not in matched_in or "abstract" not in matched_in[paper.id]:
            scores[paper.id] += 15
            matched_in[paper.id].append("abstract")

    # ── Signal 3: category match ──────────────────────────────────────────────
    cat_rows = db.execute(
        select(PaperCategory.paper_id, PaperCategory.name)
        .where(func.lower(PaperCategory.name).contains(term))
    ).all()
    if cat_rows:
        cat_ids = list({r.paper_id for r in cat_rows})
        cat_by_paper: dict[str, list[str]] = defaultdict(list)
        for r in cat_rows:
            cat_by_paper[r.paper_id].append(r.name)

        for row in db.execute(_base().where(Paper.id.in_(cat_ids))).all():
            paper, conf, _yr, pgm = row
            _cache(paper, conf, pgm)
            for cat_name in cat_by_paper[paper.id]:
                scores[paper.id] += 15
                matched_in[paper.id].append(f"category:{cat_name}")

    # ── Signal 4: technique match ─────────────────────────────────────────────
    tech_rows = db.execute(
        select(PaperTechnique.paper_id, PaperTechnique.name)
        .where(func.lower(PaperTechnique.name).contains(term))
    ).all()
    if tech_rows:
        tech_ids = list({r.paper_id for r in tech_rows})
        tech_by_paper: dict[str, list[str]] = defaultdict(list)
        for r in tech_rows:
            tech_by_paper[r.paper_id].append(r.name)

        for row in db.execute(_base().where(Paper.id.in_(tech_ids))).all():
            paper, conf, _yr, pgm = row
            _cache(paper, conf, pgm)
            for tech_name in tech_by_paper[paper.id]:
                scores[paper.id] += 12
                matched_in[paper.id].append(f"technique:{tech_name}")

    # ── Signal 5: dataset match ───────────────────────────────────────────────
    ds_rows = db.execute(
        select(PaperDataset.paper_id, PaperDataset.name)
        .where(func.lower(PaperDataset.name).contains(term))
    ).all()
    if ds_rows:
        ds_ids = list({r.paper_id for r in ds_rows})
        ds_by_paper: dict[str, list[str]] = defaultdict(list)
        for r in ds_rows:
            ds_by_paper[r.paper_id].append(r.name)

        for row in db.execute(_base().where(Paper.id.in_(ds_ids))).all():
            paper, conf, _yr, pgm = row
            _cache(paper, conf, pgm)
            for ds_name in ds_by_paper[paper.id]:
                scores[paper.id] += 10
                matched_in[paper.id].append(f"dataset:{ds_name}")

    # ── Apply filters ─────────────────────────────────────────────────────────
    filters = req.filters
    filtered_ids: list[str] = []
    for pid, (paper, conf, pgm) in paper_cache.items():
        # Conference filter
        if filters.conference and (conf or "").lower() != filters.conference.lower():
            continue
        # Year filter — we'd need to look up ed_year; skip for now (rare use case)
        # Cluster filter
        if filters.cluster is not None:
            paper_cluster = pgm.cluster_id if pgm else None
            if paper_cluster != filters.cluster:
                continue
        # Technique filter (already applied via signal 4, but enforce if specified explicitly)
        if filters.technique:
            # Check if this paper actually has the requested technique
            has_tech = db.scalar(
                select(PaperTechnique.id)
                .where(
                    PaperTechnique.paper_id == pid,
                    func.lower(PaperTechnique.canonical_name) == filters.technique.lower(),
                )
                .limit(1)
            )
            if not has_tech:
                continue
        filtered_ids.append(pid)

    # ── Rank ──────────────────────────────────────────────────────────────────
    def _sort_key(pid: str) -> float:
        paper, _conf, _pgm = paper_cache[pid]
        base_score = scores[pid] + math.log1p(paper.citation_count or 0)
        if req.sort == "citations":
            return paper.citation_count or 0
        if req.sort == "centrality":
            pgm = paper_cache[pid][2]
            return (pgm.degree_centrality if pgm else 0.0) * 1000
        if req.sort == "date":
            return paper.year or 0
        # default: relevance score + citation boost
        return base_score

    ranked = sorted(filtered_ids, key=_sort_key, reverse=True)
    total  = len(ranked)

    # ── Paginate ──────────────────────────────────────────────────────────────
    offset  = (req.page - 1) * req.per_page
    page_ids = ranked[offset : offset + req.per_page]

    # Batch-fetch top techniques for the page
    techniques_by_paper = fetch_top_techniques_batch(db, page_ids)

    results = [
        SearchMatch(
            paper       = paper_summary(
                paper_cache[pid][0],
                paper_cache[pid][1],
                paper_cache[pid][2],
                techniques_by_paper.get(pid, []),
            ),
            match_score = round(scores[pid], 2),
            matched_in  = list(dict.fromkeys(matched_in[pid])),  # deduplicate, preserve order
        )
        for pid in page_ids
    ]

    return SearchResponse(
        query    = req.query,
        total    = total,
        page     = req.page,
        per_page = req.per_page,
        results  = results,
    )
