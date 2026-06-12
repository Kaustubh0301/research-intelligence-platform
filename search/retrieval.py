"""
search/retrieval.py
───────────────────
FTS5-backed retrieval for chat and search.

Public API:
    retrieve_papers_for_query(term, session, limit) → list[dict]
    fts_score(term, session, candidate_ids) → dict[str, float]

Scoring model (same semantics as the legacy LIKE implementation):
    +40  exact title match
    +20  title FTS match (BM25 score from papers_fts, title column)
    +15  abstract FTS match (BM25 score from papers_fts, abstract column)
    +15  category entity match
    +12  technique entity match
    + log1p(citation_count) tiebreaker

Falls back to legacy LIKE-based retrieval when FTS tables are absent or
unhealthy.  See _retrieve_like_legacy().

Dependencies: search/fts.py, search/metadata.py only.  No api/ imports.
"""

from __future__ import annotations

import logging
import math
import re
from collections import defaultdict

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from search.fts import (
    query_entities_fts,
    query_papers_fts,
    query_papers_title_only,
    tables_exist,
    tables_healthy,
)
from search.metadata import (
    base_paper_query,
    citation_log_boost,
    fetch_paper_metadata_batch,
    fetch_top_techniques_batch,
)

log = logging.getLogger(__name__)

# ── Stop words / tokeniser (duplicated from api/helpers.py to avoid api/ dep) ─

_STOP_WORDS = frozenset({
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "shall", "can", "for", "in", "on", "at",
    "to", "of", "and", "or", "but", "not", "with", "from", "by", "as",
    "it", "its", "this", "that", "these", "those", "what", "which", "who",
    "when", "where", "how", "than", "more", "less", "some", "any", "all",
    "each", "both", "few", "very", "just", "also", "up", "about",
    "between", "after", "before", "over", "under",
})

_GENERIC_TOKENS = frozenset({
    "ai", "ml", "model", "models", "learning", "network", "networks",
    "system", "systems", "method", "methods", "data", "dataset",
    "deep", "neural", "large", "new", "novel", "proposed",
    "based", "using", "approach", "training", "trained",
    "language", "task", "paper", "performance", "result", "results",
})


def _tokenize(query: str) -> list[str]:
    tokens = re.split(r"[\s\-_/.,;:!?()\[\]]+", query.lower())
    return [t for t in tokens if t and len(t) >= 2 and t not in _STOP_WORDS]


def _token_boost(token: str) -> float:
    return 0.2 if token in _GENERIC_TOKENS else 0.5


# ── FTS-based scoring ─────────────────────────────────────────────────────────

def fts_score(
    term: str,
    session: Session,
    candidate_ids: list[str] | None = None,
) -> dict[str, float]:
    """
    Compute FTS5-based scores for all matching papers.

    If candidate_ids is given, only those papers are scored.
    Returns a dict of paper_id → score.

    Scoring per term pass:
        BM25 title hit  → proportional to BM25 score (scaled to ~+20 range)
        BM25 abstract   → proportional to BM25 score (scaled to ~+15 range)
        Technique match → +12
        Category match  → +15
    Exact title bonus: +20 added on top when BM25 hit is a title-only match.
    """
    q_lower = term.strip().lower()
    if not q_lower:
        return {}

    scores: dict[str, float] = defaultdict(float)

    def _score_one_term(t: str, boost: float) -> None:
        # Paper BM25 hits
        hits = query_papers_fts(session, t)
        title_ids = query_papers_title_only(session, t)

        for paper_id, bm25 in hits:
            if candidate_ids and paper_id not in candidate_ids:
                continue
            if paper_id in title_ids:
                # Title match: scale BM25 score to +20 base, add exact bonus
                scores[paper_id] += (20.0 + min(bm25, 20.0)) * boost
            else:
                # Abstract match: scale BM25 score to +15 base
                scores[paper_id] += (15.0 + min(bm25, 15.0)) * boost

        # Entity hits
        entity_hits = query_entities_fts(session, t)
        for paper_id, entity_type, _name in entity_hits:
            if candidate_ids and paper_id not in candidate_ids:
                continue
            if entity_type == "category":
                scores[paper_id] += 15.0 * boost
            elif entity_type == "technique":
                scores[paper_id] += 12.0 * boost

    _score_one_term(q_lower, boost=1.0)

    tokens = _tokenize(q_lower)
    extra = [t for t in dict.fromkeys(tokens) if t != q_lower]
    for tok in extra:
        _score_one_term(tok, boost=_token_boost(tok))

    return dict(scores)


def _build_matched_in(
    term: str,
    session: Session,
    paper_ids: list[str],
) -> dict[str, list[str]]:
    """
    Reconstruct matched_in labels for a set of paper_ids.

    Runs two FTS column-filter queries (title / abstract) plus the
    entity query.  Total: 3 extra queries per search term pass (vs 26 legacy).
    """
    matched: dict[str, list[str]] = defaultdict(list)

    q_lower = term.strip().lower()
    title_ids = query_papers_title_only(session, q_lower)
    abstract_ids = set()

    # Determine abstract hits = papers_fts hits that are NOT title-only
    fts_hits = {pid for pid, _ in query_papers_fts(session, q_lower)}
    abstract_ids = fts_hits - title_ids

    for pid in paper_ids:
        if pid in title_ids:
            matched[pid].append("title")
        if pid in abstract_ids:
            matched[pid].append("abstract")

    entity_hits = query_entities_fts(session, q_lower)
    for pid, entity_type, name in entity_hits:
        if pid in paper_ids:
            label = f"{entity_type}:{name}"
            if label not in matched[pid]:
                matched[pid].append(label)

    return matched


# ── Public entry point ────────────────────────────────────────────────────────

def retrieve_papers_for_query(
    term: str,
    session: Session,
    limit: int = 5,
) -> list[dict]:
    """
    Multi-signal retrieval for chat and search.  Uses FTS5 when available,
    falls back to legacy LIKE scanning automatically.

    Returns list of dicts with keys:
        id, title, abstract, year, conference, citation_count,
        cluster_id, degree_centrality,
        top_techniques, categories,
        match_score, matched_in,
        summary, methodology, experimental_findings,
        strengths, limitations, practical_applications,
        future_research_directions, advantages
    """
    if not term.strip():
        return []

    if not tables_exist(session):
        log.warning("FTS tables absent — falling back to LIKE retrieval")
        return _retrieve_like_legacy(term, session, limit)

    ok, msg = tables_healthy(session)
    if not ok:
        log.warning("FTS unhealthy (%s) — falling back to LIKE retrieval", msg)
        return _retrieve_like_legacy(term, session, limit)

    # FTS scoring
    raw_scores = fts_score(term, session)
    if not raw_scores:
        return []

    # Rank by score + citation tiebreaker
    candidate_ids = list(raw_scores.keys())
    metadata = fetch_paper_metadata_batch(session, candidate_ids)

    def _rank_key(pid: str) -> float:
        m = metadata.get(pid, {})
        return raw_scores[pid] + math.log1p(m.get("citation_count", 0) or 0)

    ranked = sorted(raw_scores.keys(), key=_rank_key, reverse=True)[:limit]

    # Build matched_in labels for top results only
    matched_in = _build_matched_in(term, session, ranked)

    results = []
    for pid in ranked:
        m = metadata.get(pid)
        if not m:
            continue
        results.append({
            **m,
            "match_score": round(raw_scores[pid], 2),
            "matched_in":  list(dict.fromkeys(matched_in.get(pid, []))),
        })

    return results


# ── Legacy fallback (LIKE-based, preserved for rollback) ─────────────────────

def _retrieve_like_legacy(
    term: str,
    session: Session,
    limit: int = 5,
) -> list[dict]:
    """
    Original LIKE '%term%' full-table-scan retrieval.

    Kept verbatim from api/helpers.py for rollback safety.
    Remove after FTS5 benchmark is verified.
    """
    import json
    from collections import defaultdict
    from db.models import (
        Paper, PaperCategory, PaperDataset, PaperTechnique, PaperAnalysisRecord,
    )

    q_lower = term.strip().lower()
    scores:      dict[str, float]      = defaultdict(float)
    matched_in:  dict[str, list[str]]  = defaultdict(list)
    paper_cache: dict[str, tuple]      = {}

    def _cache(paper, conf, pgm):
        if paper.id not in paper_cache:
            paper_cache[paper.id] = (paper, conf, pgm)

    def _bq():
        return base_paper_query()

    def _score_term(t: str, boost: float, tag: str) -> None:
        for row in session.execute(_bq().where(func.lower(Paper.title).contains(t))).all():
            paper, conf, _yr, pgm = row
            _cache(paper, conf, pgm)
            label = f"{tag}title"
            if paper.title.lower() == t:
                scores[paper.id] += 40 * boost
                if f"{tag}title:exact" not in matched_in[paper.id]:
                    matched_in[paper.id].append(f"{tag}title:exact")
            else:
                scores[paper.id] += 20 * boost
                if label not in matched_in[paper.id]:
                    matched_in[paper.id].append(label)

        for row in session.execute(
            _bq().where(func.lower(Paper.abstract).contains(t), Paper.abstract.isnot(None))
        ).all():
            paper, conf, _yr, pgm = row
            _cache(paper, conf, pgm)
            label = f"{tag}abstract"
            if label not in matched_in[paper.id]:
                scores[paper.id] += 15 * boost
                matched_in[paper.id].append(label)

        cat_rows = session.execute(
            select(PaperCategory.paper_id, PaperCategory.name)
            .where(func.lower(PaperCategory.name).contains(t))
        ).all()
        if cat_rows:
            cat_ids = list({r.paper_id for r in cat_rows})
            cat_by_paper: dict[str, list[str]] = defaultdict(list)
            for r in cat_rows:
                cat_by_paper[r.paper_id].append(r.name)
            for row in session.execute(_bq().where(Paper.id.in_(cat_ids))).all():
                paper, conf, _yr, pgm = row
                _cache(paper, conf, pgm)
                for cat_name in cat_by_paper[paper.id]:
                    label = f"{tag}category:{cat_name}"
                    if label not in matched_in[paper.id]:
                        scores[paper.id] += 15 * boost
                        matched_in[paper.id].append(label)

        tech_rows = session.execute(
            select(PaperTechnique.paper_id, PaperTechnique.name)
            .where(func.lower(PaperTechnique.name).contains(t))
        ).all()
        if tech_rows:
            tech_ids = list({r.paper_id for r in tech_rows})
            tech_by_paper: dict[str, list[str]] = defaultdict(list)
            for r in tech_rows:
                tech_by_paper[r.paper_id].append(r.name)
            for row in session.execute(_bq().where(Paper.id.in_(tech_ids))).all():
                paper, conf, _yr, pgm = row
                _cache(paper, conf, pgm)
                for tech_name in tech_by_paper[paper.id]:
                    label = f"{tag}technique:{tech_name}"
                    if label not in matched_in[paper.id]:
                        scores[paper.id] += 12 * boost
                        matched_in[paper.id].append(label)

        ds_rows = session.execute(
            select(PaperDataset.paper_id, PaperDataset.name)
            .where(func.lower(PaperDataset.name).contains(t))
        ).all()
        if ds_rows:
            ds_ids = list({r.paper_id for r in ds_rows})
            ds_by_paper: dict[str, list[str]] = defaultdict(list)
            for r in ds_rows:
                ds_by_paper[r.paper_id].append(r.name)
            for row in session.execute(_bq().where(Paper.id.in_(ds_ids))).all():
                paper, conf, _yr, pgm = row
                _cache(paper, conf, pgm)
                for ds_name in ds_by_paper[paper.id]:
                    label = f"{tag}dataset:{ds_name}"
                    if label not in matched_in[paper.id]:
                        scores[paper.id] += 10 * boost
                        matched_in[paper.id].append(label)

    _score_term(q_lower, boost=1.0, tag="")
    tokens = _tokenize(q_lower)
    extra_tokens = [t for t in dict.fromkeys(tokens) if t != q_lower]
    for tok in extra_tokens:
        _score_term(tok, boost=_token_boost(tok), tag="token:")

    if not paper_cache:
        return []

    def _key(pid: str) -> float:
        paper, _conf, _pgm = paper_cache[pid]
        return scores[pid] + math.log1p(paper.citation_count or 0)

    ranked = sorted(paper_cache.keys(), key=_key, reverse=True)[:limit]
    techniques_by_paper = fetch_top_techniques_batch(session, ranked, per_paper=3)

    cat_all = session.execute(
        select(PaperCategory.paper_id, PaperCategory.name)
        .where(PaperCategory.paper_id.in_(ranked))
        .order_by(PaperCategory.paper_id, PaperCategory.confidence.desc())
    ).all()
    cats_by_paper: dict[str, list[str]] = defaultdict(list)
    for pid, cname in cat_all:
        if len(cats_by_paper[pid]) < 3:
            cats_by_paper[pid].append(cname)

    analysis_rows = session.execute(
        select(
            PaperAnalysisRecord.paper_id,
            PaperAnalysisRecord.summary,
            PaperAnalysisRecord.methodology,
            PaperAnalysisRecord.experimental_findings,
            PaperAnalysisRecord.strengths,
            PaperAnalysisRecord.limitations,
            PaperAnalysisRecord.practical_applications,
            PaperAnalysisRecord.future_research_directions,
            PaperAnalysisRecord.advantages,
        ).where(PaperAnalysisRecord.paper_id.in_(ranked))
    ).all()
    analysis_by_paper = {r.paper_id: r for r in analysis_rows}

    def _jl(raw):
        if not raw:
            return []
        try:
            v = json.loads(raw)
            return v if isinstance(v, list) else []
        except Exception:
            return []

    results = []
    for pid in ranked:
        paper, conf, pgm = paper_cache[pid]
        ar = analysis_by_paper.get(pid)
        results.append({
            "id":               paper.id,
            "title":            paper.title,
            "abstract":         paper.abstract or "",
            "year":             paper.year,
            "conference":       conf,
            "citation_count":   paper.citation_count or 0,
            "cluster_id":       pgm.cluster_id if pgm else None,
            "degree_centrality": round(pgm.degree_centrality, 6) if pgm else 0.0,
            "top_techniques":   techniques_by_paper.get(pid, []),
            "categories":       cats_by_paper.get(pid, []),
            "match_score":      round(scores[pid], 2),
            "matched_in":       list(dict.fromkeys(matched_in[pid])),
            "summary":                    (ar.summary or "") if ar else "",
            "methodology":                (ar.methodology or "") if ar else "",
            "experimental_findings":      _jl(ar.experimental_findings) if ar else [],
            "strengths":                  _jl(ar.strengths) if ar else [],
            "limitations":                _jl(ar.limitations) if ar else [],
            "practical_applications":     _jl(ar.practical_applications) if ar else [],
            "future_research_directions": _jl(ar.future_research_directions) if ar else [],
            "advantages":                 _jl(ar.advantages) if ar else [],
        })

    return results
