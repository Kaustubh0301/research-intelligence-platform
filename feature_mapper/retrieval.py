"""
feature_mapper/retrieval.py
───────────────────────────
Per-feature retrieval over three signals, fused with weighted RRF.

Signals:
  1. Dense semantic   — search/embeddings.py FAISS index (cosine ≥ 0.30)
  2. Technique match  — paper_techniques exact name match, tie-broken by
                        (match_count desc, citation_count desc). The citation
                        tie-breaker matters: most techniques appear in exactly
                        one corpus paper, so without it the within-signal order
                        is arbitrary and RRF degenerates to an arithmetic ladder
                        (observed in the validation run).
  3. Category match   — paper_categories exact name match.

Fusion: weighted Reciprocal Rank Fusion (k=60).

Public API:
    retrieve_for_feature(feature, session, top_k=5) → (papers, coverage_score, coverage_tier)
    retrieve_for_debug(feature_text, session)       → dict (raw per-signal results)
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from db.models import Paper, PaperCategory, PaperTechnique
from feature_mapper.models import Feature, PaperMatch
from search.embeddings import get_index
from search.metadata import fetch_paper_metadata_batch

# ── Fusion constants ──────────────────────────────────────────────────────────

RRF_K = 60
WEIGHT_DENSE = 1.0
WEIGHT_TECHNIQUE = 1.4   # technique match is the most precise signal
WEIGHT_CATEGORY = 0.7

_DENSE_K = 50            # candidates pulled from the FAISS index
_DEBUG_LIMIT = 20        # rows shown per signal in the debug endpoint

# Coverage scoring weights (Phase 1 two-component formula).
_COV_BREADTH_W = 0.6
_COV_QUALITY_W = 0.4
# Max achievable RRF score (all three signals rank a paper #1): used to
# normalize result_quality into [0, 1].
_MAX_RRF = WEIGHT_DENSE / RRF_K + WEIGHT_TECHNIQUE / RRF_K + WEIGHT_CATEGORY / RRF_K


# ── Signal retrieval ──────────────────────────────────────────────────────────

def _dense_scores(query_text: str) -> dict[str, float]:
    """paper_id → cosine similarity (already filtered to ≥ 0.30)."""
    return get_index().search(query_text, k=_DENSE_K)


def _technique_rows(names: list[str], session: Session):
    """Rows of (paper_id, match_count), ordered by (count desc, citations desc)."""
    if not names:
        return []
    return session.execute(
        select(
            PaperTechnique.paper_id,
            func.count(PaperTechnique.id).label("cnt"),
        )
        .join(Paper, Paper.id == PaperTechnique.paper_id)
        .where(func.lower(PaperTechnique.name).in_([n.lower() for n in names]))
        .group_by(PaperTechnique.paper_id)
        .order_by(func.count(PaperTechnique.id).desc(), Paper.citation_count.desc())
    ).all()


def _category_rows(names: list[str], session: Session):
    """Rows of (paper_id, match_count), ordered by (count desc, citations desc)."""
    if not names:
        return []
    return session.execute(
        select(
            PaperCategory.paper_id,
            func.count(PaperCategory.id).label("cnt"),
        )
        .join(Paper, Paper.id == PaperCategory.paper_id)
        .where(func.lower(PaperCategory.name).in_([n.lower() for n in names]))
        .group_by(PaperCategory.paper_id)
        .order_by(func.count(PaperCategory.id).desc(), Paper.citation_count.desc())
    ).all()


# ── Fusion ────────────────────────────────────────────────────────────────────

def _rrf_fuse(
    dense_ranked: list[str],
    tech_ranked: list[str],
    cat_ranked: list[str],
) -> dict[str, float]:
    """Weighted Reciprocal Rank Fusion across the three ranked id lists."""
    dense_pos = {pid: i for i, pid in enumerate(dense_ranked)}
    tech_pos = {pid: i for i, pid in enumerate(tech_ranked)}
    cat_pos = {pid: i for i, pid in enumerate(cat_ranked)}

    fused: dict[str, float] = {}
    for pid in set(dense_pos) | set(tech_pos) | set(cat_pos):
        score = 0.0
        if pid in dense_pos:
            score += WEIGHT_DENSE / (RRF_K + dense_pos[pid])
        if pid in tech_pos:
            score += WEIGHT_TECHNIQUE / (RRF_K + tech_pos[pid])
        if pid in cat_pos:
            score += WEIGHT_CATEGORY / (RRF_K + cat_pos[pid])
        fused[pid] = score
    return fused


def _coverage(
    dense: dict[str, float],
    tech: dict[str, float],
    cat: dict[str, float],
    top_fused: list[float],
) -> tuple[float, str]:
    signals = sum([
        1 if len(dense) >= 3 else 0,
        1 if len(tech) >= 2 else 0,
        1 if len(cat) >= 2 else 0,
    ])
    breadth = signals / 3
    quality = (sum(top_fused) / len(top_fused)) / _MAX_RRF if top_fused else 0.0
    quality = min(1.0, quality)
    score = round(_COV_BREADTH_W * breadth + _COV_QUALITY_W * quality, 3)

    if score > 0.65:
        tier = "strong"
    elif score > 0.40:
        tier = "moderate"
    elif score > 0.15:
        tier = "weak"
    else:
        tier = "novel"
    return score, tier


def _build_query_text(feature: Feature) -> str:
    return (
        f"{feature.name}. {feature.description}. "
        f"{' '.join(feature.matched_techniques)}"
    ).strip()


# ── Public: full retrieval for one feature ────────────────────────────────────

def retrieve_for_feature(
    feature: Feature,
    session: Session,
    top_k: int = 5,
) -> tuple[list[PaperMatch], float, str]:
    """
    Run all three signals for a feature, fuse with RRF, and return the top-K
    papers plus the coverage score and tier.
    """
    query_text = _build_query_text(feature)

    dense = _dense_scores(query_text)
    tech_rows = _technique_rows(feature.matched_techniques, session)
    cat_rows = _category_rows(feature.matched_categories, session)

    denom_tech = max(1, len(feature.matched_techniques))
    denom_cat = max(1, len(feature.matched_categories))
    tech = {r.paper_id: r.cnt / denom_tech for r in tech_rows}
    cat = {r.paper_id: r.cnt / denom_cat for r in cat_rows}

    dense_ranked = sorted(dense, key=lambda p: dense[p], reverse=True)
    tech_ranked = [r.paper_id for r in tech_rows]   # already ordered by the query
    cat_ranked = [r.paper_id for r in cat_rows]

    fused = _rrf_fuse(dense_ranked, tech_ranked, cat_ranked)
    ranked_ids = sorted(fused, key=lambda p: fused[p], reverse=True)[:top_k]

    cov_score, cov_tier = _coverage(dense, tech, cat, [fused[p] for p in ranked_ids])

    metadata = fetch_paper_metadata_batch(session, ranked_ids)

    papers: list[PaperMatch] = []
    for rank, pid in enumerate(ranked_ids, 1):
        m = metadata.get(pid)
        if not m:
            continue
        papers.append(
            PaperMatch(
                paper_id=pid,
                title=m["title"],
                year=m.get("year"),
                venue=m.get("conference"),
                abstract=(m.get("abstract") or "")[:300],
                top_techniques=m.get("top_techniques", []),
                categories=m.get("categories", []),
                rank=rank,
                rrf_score=round(fused[pid], 6),
                semantic_score=round(dense.get(pid, 0.0), 4) or None,
                technique_score=round(tech.get(pid, 0.0), 4) or None,
                category_score=round(cat.get(pid, 0.0), 4) or None,
                matched_techniques=feature.matched_techniques if pid in tech else [],
                matched_categories=feature.matched_categories if pid in cat else [],
            )
        )

    return papers, cov_score, cov_tier


# ── Public: debug — raw per-signal results for a free-text feature ───────────

def retrieve_for_debug(feature_text: str, session: Session) -> dict:
    """
    Run the three signals on a raw feature string (no LLM extraction) and
    return per-signal results plus the fused ranking, for validating retrieval
    quality during development.

    The raw string is normalized so technique/category signals fire just as
    they would in the real pipeline.
    """
    from feature_mapper.normalizer import normalize_terms

    matched_tech, matched_cat, _ = normalize_terms([feature_text], session)

    query_text = f"{feature_text}. {' '.join(matched_tech)}".strip()
    dense = _dense_scores(query_text)
    tech_rows = _technique_rows(matched_tech, session)
    cat_rows = _category_rows(matched_cat, session)

    denom_tech = max(1, len(matched_tech))
    denom_cat = max(1, len(matched_cat))
    tech = {r.paper_id: r.cnt / denom_tech for r in tech_rows}
    cat = {r.paper_id: r.cnt / denom_cat for r in cat_rows}

    dense_ranked = sorted(dense, key=lambda p: dense[p], reverse=True)
    tech_ranked = [r.paper_id for r in tech_rows]
    cat_ranked = [r.paper_id for r in cat_rows]

    fused = _rrf_fuse(dense_ranked, tech_ranked, cat_ranked)
    ranked_ids = sorted(fused, key=lambda p: fused[p], reverse=True)[:_DEBUG_LIMIT]

    # Titles for everything we'll show.
    show_ids = list(
        dict.fromkeys(
            dense_ranked[:_DEBUG_LIMIT] + tech_ranked[:_DEBUG_LIMIT]
            + cat_ranked[:_DEBUG_LIMIT] + ranked_ids
        )
    )
    meta = fetch_paper_metadata_batch(session, show_ids)

    def _title(pid: str) -> str | None:
        m = meta.get(pid)
        return m["title"] if m else None

    return {
        "query_text": query_text,
        "matched_techniques": matched_tech,
        "matched_categories": matched_cat,
        "dense_results": [
            {"paper_id": pid, "title": _title(pid), "score": round(dense[pid], 4)}
            for pid in dense_ranked[:_DEBUG_LIMIT]
        ],
        "technique_results": [
            {"paper_id": r.paper_id, "title": _title(r.paper_id), "match_count": r.cnt}
            for r in tech_rows[:_DEBUG_LIMIT]
        ],
        "category_results": [
            {"paper_id": r.paper_id, "title": _title(r.paper_id), "match_count": r.cnt}
            for r in cat_rows[:_DEBUG_LIMIT]
        ],
        "rrf_ranking": [
            {
                "paper_id": pid,
                "title": _title(pid),
                "rrf_score": round(fused[pid], 6),
                "rank": rank,
                "signals_fired": sum([pid in dense, pid in tech, pid in cat]),
            }
            for rank, pid in enumerate(ranked_ids, 1)
        ],
    }
