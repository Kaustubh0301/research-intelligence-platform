"""
Shared query helpers and data-shaping utilities for the v1 API.

All functions are pure (no FastAPI dependencies) so they can be
imported by any router without coupling concerns.
"""

from __future__ import annotations

import json
import math
import re
from collections import defaultdict
from typing import Optional

# ── Query tokeniser ───────────────────────────────────────────────────────────

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


# Tokens so common in the ML/AI corpus that they add noise rather than signal
# when matched as substrings. Boosted at 0.2× instead of 0.5×.
# "ai" is here because it substring-matches "tr*ai*ning", "f*ai*rness", etc.
_GENERIC_TOKENS = frozenset({
    "ai", "ml",
    "model", "models",
    "learning",
    "network", "networks",
    "system", "systems",
    "method", "methods",
    "data", "dataset",
    "deep", "neural",
    "large", "new", "novel", "proposed",
    "based", "using", "approach",
    "training", "trained",
    "language", "task", "paper",
    "performance", "result", "results",
})


def _tokenize(query: str) -> list[str]:
    """Split a query into lowercase tokens, dropping stop words and length-1 tokens."""
    tokens = re.split(r"[\s\-_/.,;:!?()\[\]]+", query.lower())
    return [t for t in tokens if t and len(t) >= 2 and t not in _STOP_WORDS]


def _token_boost(token: str) -> float:
    """Return the score multiplier for a single query token."""
    return 0.2 if token in _GENERIC_TOKENS else 0.5

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from db.models import (
    Author,
    Conference,
    ConferenceEdition,
    Paper,
    PaperAnalysisRecord,
    PaperAuthor,
    PaperCategory,
    PaperDataset,
    PaperGraphMetric,
    PaperMethodology,
    PaperTechnique,
)
from api.models import (
    AnalysisOut,
    AuthorOut,
    CategoryOut,
    DatasetOut,
    ExperimentalFinding,
    GraphMetrics,
    MethodologyOut,
    PaperDetail,
    PaperSummary,
    TechniqueOut,
)


# ── JSON helpers ──────────────────────────────────────────────────────────────

def json_list(raw: Optional[str]) -> list[str]:
    """
    Parse a JSON-encoded list stored in a Text column.
    Returns [] on any failure rather than raising.
    """
    if not raw:
        return []
    try:
        val = json.loads(raw)
        return val if isinstance(val, list) else []
    except (json.JSONDecodeError, TypeError):
        return []


def parse_findings(raw: Optional[str]) -> list[ExperimentalFinding]:
    """
    Parse JSON array of 'benchmark :: metric :: scores' strings into
    ExperimentalFinding objects.  Gracefully handles missing parts.
    """
    items = json_list(raw)
    findings: list[ExperimentalFinding] = []
    for item in items:
        if not isinstance(item, str):
            continue
        parts = item.split(" :: ", 2)
        if len(parts) == 3:
            benchmark, metric, scores = parts
        elif len(parts) == 2:
            benchmark, metric, scores = parts[0], parts[1], ""
        else:
            benchmark, metric, scores = item, "", ""
        findings.append(ExperimentalFinding(
            benchmark=benchmark.strip(),
            metric=metric.strip(),
            scores=scores.strip(),
        ))
    return findings


def json_names(raw: Optional[str]) -> list[str]:
    """
    Parse a JSON array of objects that each have a 'name' key,
    OR a plain JSON array of strings.
    Used for top_cooccurring in TechniqueGraphMetric.
    """
    if not raw:
        return []
    try:
        val = json.loads(raw)
        if isinstance(val, list):
            result = []
            for item in val:
                if isinstance(item, dict):
                    result.append(item.get("name", ""))
                elif isinstance(item, str):
                    result.append(item)
            return [n for n in result if n]
    except (json.JSONDecodeError, TypeError):
        pass
    return []


# ── Base query factory ────────────────────────────────────────────────────────

def base_paper_query():
    """
    SELECT papers + conference short_name + edition year + graph metrics.
    Uses LEFT JOINs so papers without a conference or graph metrics are included.
    """
    return (
        select(
            Paper,
            Conference.short_name.label("conf_short"),
            ConferenceEdition.year.label("ed_year"),
            PaperGraphMetric,
        )
        .join(ConferenceEdition, Paper.conference_edition_id == ConferenceEdition.id, isouter=True)
        .join(Conference, ConferenceEdition.conference_id == Conference.id, isouter=True)
        .outerjoin(PaperGraphMetric, Paper.id == PaperGraphMetric.paper_id)
    )


# ── Model builders ────────────────────────────────────────────────────────────

def _graph_metrics(pgm: Optional[PaperGraphMetric]) -> Optional[GraphMetrics]:
    if pgm is None:
        return None
    return GraphMetrics(
        cluster_id             = pgm.cluster_id,
        degree_centrality      = round(pgm.degree_centrality, 6),
        betweenness_centrality = round(pgm.betweenness_centrality, 6),
        neighbors_count        = pgm.neighbors_count,
        total_edge_weight      = round(pgm.total_edge_weight, 4),
    )


def paper_summary(
    paper: Paper,
    conf_short: Optional[str],
    pgm: Optional[PaperGraphMetric],
    top_techniques: Optional[list[str]] = None,
    primary_category: Optional[str] = None,
) -> PaperSummary:
    abstract = paper.abstract or ""
    return PaperSummary(
        id                         = paper.id,
        title                      = paper.title,
        year                       = paper.year,
        conference                 = conf_short,
        presentation_type          = paper.presentation_type,
        citation_count             = paper.citation_count or 0,
        influential_citation_count = paper.influential_citation_count or 0,
        is_open_access             = paper.is_open_access or False,
        has_pdf                    = paper.pdf_local_path is not None,
        abstract_snippet           = abstract[:300] if abstract else None,
        pdf_url                    = paper.pdf_url,
        arxiv_id                   = paper.arxiv_id,
        openreview_id              = paper.openreview_id,
        cluster_id                 = pgm.cluster_id if pgm else None,
        degree_centrality          = round(pgm.degree_centrality, 6) if pgm else 0.0,
        top_techniques             = top_techniques or [],
        primary_category           = primary_category,
    )


def build_paper_detail(
    session: Session,
    paper: Paper,
    conf_short: Optional[str],
    ed_year: Optional[int],
    pgm: Optional[PaperGraphMetric],
) -> PaperDetail:
    # Authors
    author_rows = session.execute(
        select(Author, PaperAuthor.position, PaperAuthor.affiliation)
        .join(PaperAuthor, Author.id == PaperAuthor.author_id)
        .where(PaperAuthor.paper_id == paper.id)
        .order_by(PaperAuthor.position)
    ).all()
    authors = [
        AuthorOut(
            id                  = a.id,
            full_name           = a.full_name,
            position            = pos,
            affiliation         = aff,
            semantic_scholar_id = a.semantic_scholar_id,
            homepage            = a.homepage,
        )
        for a, pos, aff in author_rows
    ]

    # Techniques (ordered: introduces first, then uses, then others)
    techs = session.scalars(
        select(PaperTechnique)
        .where(PaperTechnique.paper_id == paper.id)
        .order_by(PaperTechnique.role, PaperTechnique.name)
    ).all()

    # Datasets
    datasets = session.scalars(
        select(PaperDataset).where(PaperDataset.paper_id == paper.id)
    ).all()

    # Categories (most confident first)
    cats = session.scalars(
        select(PaperCategory)
        .where(PaperCategory.paper_id == paper.id)
        .order_by(PaperCategory.confidence.desc())
    ).all()

    # Methodologies
    meths = session.scalars(
        select(PaperMethodology).where(PaperMethodology.paper_id == paper.id)
    ).all()

    # Analysis
    analysis_row = session.scalar(
        select(PaperAnalysisRecord).where(PaperAnalysisRecord.paper_id == paper.id)
    )
    analysis = None
    if analysis_row:
        analysis = AnalysisOut(
            # V2 fields
            summary                    = analysis_row.summary,
            methodology                = analysis_row.methodology,
            experimental_findings      = parse_findings(analysis_row.experimental_findings),
            strengths                  = json_list(analysis_row.strengths),
            limitations                = json_list(analysis_row.limitations),
            practical_applications     = json_list(analysis_row.practical_applications),
            future_research_directions = json_list(analysis_row.future_research_directions),
            # V1 legacy fields
            advantages  = json_list(analysis_row.advantages),
            future_work = json_list(analysis_row.future_work),
            use_cases   = json_list(analysis_row.use_cases),
            model       = analysis_row.model,
        )

    return PaperDetail(
        id                         = paper.id,
        title                      = paper.title,
        abstract                   = paper.abstract,
        year                       = paper.year,
        conference                 = conf_short,
        edition_year               = ed_year,
        presentation_type          = paper.presentation_type,
        citation_count             = paper.citation_count or 0,
        influential_citation_count = paper.influential_citation_count or 0,
        is_open_access             = paper.is_open_access or False,
        pdf_url                    = paper.pdf_url,
        openreview_id              = paper.openreview_id,
        semantic_scholar_id        = paper.semantic_scholar_id,
        arxiv_id                   = paper.arxiv_id,
        authors                    = authors,
        techniques                 = [
            TechniqueOut(name=t.name, canonical_name=t.canonical_name, role=t.role)
            for t in techs
        ],
        datasets                   = [
            DatasetOut(name=d.name, canonical_name=d.canonical_name, task=d.task, description=d.description)
            for d in datasets
        ],
        categories                 = [
            CategoryOut(name=c.name, canonical_name=c.canonical_name, confidence=c.confidence)
            for c in cats
        ],
        methodologies              = [MethodologyOut(name=m.name) for m in meths],
        analysis                   = analysis,
        graph_metrics              = _graph_metrics(pgm),
    )


# ── Batch primary-category fetch ─────────────────────────────────────────────

def fetch_primary_categories_batch(
    session: Session,
    paper_ids: list[str],
) -> dict[str, str]:
    """
    Return a map of paper_id → primary category name (highest-confidence row).
    Uses a single query; returns the canonical_name when set, else name.
    Papers with no category row are absent from the result dict.
    """
    if not paper_ids:
        return {}

    rows = session.execute(
        select(
            PaperCategory.paper_id,
            PaperCategory.canonical_name,
            PaperCategory.name,
            PaperCategory.confidence,
        )
        .where(PaperCategory.paper_id.in_(paper_ids))
        .order_by(PaperCategory.paper_id, PaperCategory.confidence.desc())
    ).all()

    result: dict[str, str] = {}
    for pid, canonical, name, _conf in rows:
        if pid not in result:          # keep only the highest-confidence row
            result[pid] = canonical or name
    return result


# ── Batch technique fetch ─────────────────────────────────────────────────────

def fetch_top_techniques_batch(
    session: Session,
    paper_ids: list[str],
    per_paper: int = 3,
) -> dict[str, list[str]]:
    """
    Return a map of paper_id → [top canonical technique names].
    Uses a single query; post-filters to top N per paper in Python.
    Only includes rows where canonical_name is set.
    """
    if not paper_ids:
        return {}

    rows = session.execute(
        select(
            PaperTechnique.paper_id,
            PaperTechnique.canonical_name,
            func.count(PaperTechnique.id).label("cnt"),
        )
        .where(
            PaperTechnique.paper_id.in_(paper_ids),
            PaperTechnique.canonical_name.isnot(None),
        )
        .group_by(PaperTechnique.paper_id, PaperTechnique.canonical_name)
        .order_by(PaperTechnique.paper_id, func.count(PaperTechnique.id).desc())
    ).all()

    result: dict[str, list[str]] = defaultdict(list)
    for pid, canonical, _ in rows:
        if len(result[pid]) < per_paper:
            result[pid].append(canonical)
    return dict(result)


# ── Citation score (tiebreaker for search ranking) ───────────────────────────

def citation_log_boost(citation_count: Optional[int]) -> float:
    return math.log1p(citation_count or 0)


# ── Shared retrieval for chat ─────────────────────────────────────────────────

def retrieve_papers_for_query(
    term: str,
    session: Session,
    limit: int = 5,
) -> list[dict]:
    # Delegate to FTS5-backed retrieval (falls back to LIKE automatically).
    from search.retrieval import retrieve_papers_for_query as _fts_retrieve
    return _fts_retrieve(term, session, limit)


def _retrieve_papers_for_query_legacy(
    term: str,
    session: Session,
    limit: int = 5,
) -> list[dict]:
    """Legacy LIKE-based implementation kept for rollback verification.

    Scoring (identical to search router):
      +40  exact title match
      +20  title contains
      +15  abstract contains
      +15  category match
      +12  technique match
      +10  dataset match
      + log1p(citation_count) tiebreaker

    Returns a list of dicts with keys:
      id, title, abstract, year, conference, citation_count,
      cluster_id, degree_centrality,
      top_techniques (list[str]),
      categories (list[str]),
      match_score, matched_in
    plus analysis context:
      summary, advantages, limitations
    """
    from db.models import PaperAnalysisRecord, PaperCategory, PaperDataset, PaperTechnique

    q_lower = term.strip().lower()

    scores:      dict[str, float]      = defaultdict(float)
    matched_in:  dict[str, list[str]]  = defaultdict(list)
    paper_cache: dict[str, tuple]      = {}  # id → (Paper, conf_short, pgm)

    def _cache(paper, conf, pgm):
        if paper.id not in paper_cache:
            paper_cache[paper.id] = (paper, conf, pgm)

    def _base():
        return base_paper_query()

    def _score_term(t: str, boost: float, tag: str) -> None:
        """
        Run all 5 signals for term `t` and accumulate into shared dicts.
        `boost` scales all point values (1.0 for the full phrase, 0.5 for tokens).
        `tag` prefixes matched_in labels to distinguish phrase vs token hits.
        """
        # Signal 1: title
        for row in session.execute(_base().where(
            func.lower(Paper.title).contains(t)
        )).all():
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

        # Signal 2: abstract
        for row in session.execute(
            _base().where(
                func.lower(Paper.abstract).contains(t),
                Paper.abstract.isnot(None),
            )
        ).all():
            paper, conf, _yr, pgm = row
            _cache(paper, conf, pgm)
            label = f"{tag}abstract"
            if label not in matched_in[paper.id]:
                scores[paper.id] += 15 * boost
                matched_in[paper.id].append(label)

        # Signal 3: category
        cat_rows = session.execute(
            select(PaperCategory.paper_id, PaperCategory.name)
            .where(func.lower(PaperCategory.name).contains(t))
        ).all()
        if cat_rows:
            cat_ids = list({r.paper_id for r in cat_rows})
            cat_by_paper: dict[str, list[str]] = defaultdict(list)
            for r in cat_rows:
                cat_by_paper[r.paper_id].append(r.name)
            for row in session.execute(_base().where(Paper.id.in_(cat_ids))).all():
                paper, conf, _yr, pgm = row
                _cache(paper, conf, pgm)
                for cat_name in cat_by_paper[paper.id]:
                    label = f"{tag}category:{cat_name}"
                    if label not in matched_in[paper.id]:
                        scores[paper.id] += 15 * boost
                        matched_in[paper.id].append(label)

        # Signal 4: technique
        tech_rows = session.execute(
            select(PaperTechnique.paper_id, PaperTechnique.name)
            .where(func.lower(PaperTechnique.name).contains(t))
        ).all()
        if tech_rows:
            tech_ids = list({r.paper_id for r in tech_rows})
            tech_by_paper: dict[str, list[str]] = defaultdict(list)
            for r in tech_rows:
                tech_by_paper[r.paper_id].append(r.name)
            for row in session.execute(_base().where(Paper.id.in_(tech_ids))).all():
                paper, conf, _yr, pgm = row
                _cache(paper, conf, pgm)
                for tech_name in tech_by_paper[paper.id]:
                    label = f"{tag}technique:{tech_name}"
                    if label not in matched_in[paper.id]:
                        scores[paper.id] += 12 * boost
                        matched_in[paper.id].append(label)

        # Signal 5: dataset
        ds_rows = session.execute(
            select(PaperDataset.paper_id, PaperDataset.name)
            .where(func.lower(PaperDataset.name).contains(t))
        ).all()
        if ds_rows:
            ds_ids = list({r.paper_id for r in ds_rows})
            ds_by_paper: dict[str, list[str]] = defaultdict(list)
            for r in ds_rows:
                ds_by_paper[r.paper_id].append(r.name)
            for row in session.execute(_base().where(Paper.id.in_(ds_ids))).all():
                paper, conf, _yr, pgm = row
                _cache(paper, conf, pgm)
                for ds_name in ds_by_paper[paper.id]:
                    label = f"{tag}dataset:{ds_name}"
                    if label not in matched_in[paper.id]:
                        scores[paper.id] += 10 * boost
                        matched_in[paper.id].append(label)

    # Full-phrase pass — original boosts (boost=1.0), no tag prefix
    _score_term(q_lower, boost=1.0, tag="")

    # Token pass — score each meaningful token at half boost
    # Only run when the query has multiple tokens (single-word queries already covered above)
    tokens = _tokenize(q_lower)
    extra_tokens = [t for t in dict.fromkeys(tokens) if t != q_lower]
    for tok in extra_tokens:
        _score_term(tok, boost=_token_boost(tok), tag="token:")

    if not paper_cache:
        return []

    # Rank by score + citation tiebreaker, take top N
    def _key(pid: str) -> float:
        paper, _conf, _pgm = paper_cache[pid]
        return scores[pid] + math.log1p(paper.citation_count or 0)

    ranked = sorted(paper_cache.keys(), key=_key, reverse=True)[:limit]

    # Batch-fetch top techniques
    techniques_by_paper = fetch_top_techniques_batch(session, ranked, per_paper=3)

    # Fetch categories (top 3 per paper)
    cat_all = session.execute(
        select(PaperCategory.paper_id, PaperCategory.name)
        .where(PaperCategory.paper_id.in_(ranked))
        .order_by(PaperCategory.paper_id, PaperCategory.confidence.desc())
    ).all()
    cats_by_paper: dict[str, list[str]] = defaultdict(list)
    for pid, cname in cat_all:
        if len(cats_by_paper[pid]) < 3:
            cats_by_paper[pid].append(cname)

    # Fetch analysis fields — V2 fields plus legacy advantages for compat
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
            "experimental_findings":      json_list(ar.experimental_findings) if ar else [],
            "strengths":                  json_list(ar.strengths) if ar else [],
            "limitations":                json_list(ar.limitations) if ar else [],
            "practical_applications":     json_list(ar.practical_applications) if ar else [],
            "future_research_directions": json_list(ar.future_research_directions) if ar else [],
            "advantages":                 json_list(ar.advantages) if ar else [],
        })

    return results
