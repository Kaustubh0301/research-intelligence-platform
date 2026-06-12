"""
Graph builder: constructs paper_relationships and entity_relationships
from the normalized entity tables.

Algorithm (Graph V2)
────────────────────
1. Load every paper's canonical entity sets from DB.
2. Compute per-technique IDF weights:
       idf(t)        = ln(total_papers / paper_count(t))
       multiplier(t) = 0.25 if GENERIC  (idf < 3.00)
                     = 1.00 if SHARED   (3.00 ≤ idf < 3.69)
                     = 2.00 if SPECIALIZED (idf ≥ 3.69)
       idf_weight(t) = WEIGHT_TECHNIQUE * multiplier(t)
3. For each paper pair (i < j), intersect entity sets and compute:
       technique_score = Σ idf_weight(t)  for t in shared_techniques
       dataset_score   = WEIGHT_DATASET   * |shared_datasets|
       category_score  = WEIGHT_CATEGORY  * |shared_categories|
       methodology_score = WEIGHT_METHODOLOGY * |shared_methodologies|
       weight          = technique_score + dataset_score + category_score + methodology_score
   Write a paper_relationships row if weight > 0.
4. For each entity type, compute pairwise co-occurrence counts → entity_relationships.

Datasets / categories / methodologies keep flat weights (v2 scope: techniques only).
All four graph tables are truncated before rebuilding (derived data, always re-computable).
"""

from __future__ import annotations

import json
import logging
import math
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from itertools import combinations

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from db.models import (
    EntityRelationship,
    Paper,
    PaperCategory,
    PaperDataset,
    PaperMethodology,
    PaperRelationship,
    PaperTechnique,
)

log = logging.getLogger(__name__)

# ── Base edge weights ─────────────────────────────────────────────────────────
# Technique weight is the base; actual per-technique contribution is
# base × IDF multiplier (see _build_idf_weights).
WEIGHT_TECHNIQUE   = 3
WEIGHT_DATASET     = 2
WEIGHT_CATEGORY    = 1
WEIGHT_METHODOLOGY = 1

# ── IDF classification thresholds ────────────────────────────────────────────
# idf = ln(N / paper_count).  Scales automatically with corpus size.
_IDF_GENERIC_CEILING = 3.00   # below → GENERIC  (×0.25)
_IDF_SHARED_CEILING  = 3.69   # below → SHARED   (×1.00); above → SPECIALIZED (×2.00)

_MULT_GENERIC     = 0.25
_MULT_SHARED      = 1.00
_MULT_SPECIALIZED = 2.00


# ── IDF weight table ─────────────────────────────────────────────────────────

def _build_idf_weights(session: Session) -> dict[str, float]:
    """
    Return {canonical_name: effective_weight} for every canonical technique.

    effective_weight = WEIGHT_TECHNIQUE * multiplier(idf(t))

    Falls back to WEIGHT_TECHNIQUE * _MULT_SPECIALIZED for any technique
    not in the DB (shouldn't happen, but defensive).
    """
    total_papers: int = session.scalar(
        select(func.count()).select_from(Paper)
    ) or 1

    rows = session.execute(
        select(
            PaperTechnique.canonical_name,
            func.count(PaperTechnique.paper_id.distinct()).label("paper_count"),
        )
        .where(PaperTechnique.canonical_name.isnot(None))
        .group_by(PaperTechnique.canonical_name)
    ).all()

    weights: dict[str, float] = {}
    for row in rows:
        idf = math.log(total_papers / row.paper_count)
        if idf < _IDF_GENERIC_CEILING:
            mult = _MULT_GENERIC
        elif idf < _IDF_SHARED_CEILING:
            mult = _MULT_SHARED
        else:
            mult = _MULT_SPECIALIZED
        weights[row.canonical_name] = round(WEIGHT_TECHNIQUE * mult, 4)

    log.info(
        "IDF weights: %d techniques  "
        "(generic=%.0f%%, shared=%.0f%%, specialized=%.0f%%)",
        len(weights),
        100 * sum(1 for w in weights.values() if w < WEIGHT_TECHNIQUE * _MULT_SHARED) / max(len(weights), 1),
        100 * sum(1 for w in weights.values() if w == WEIGHT_TECHNIQUE * _MULT_SHARED) / max(len(weights), 1),
        100 * sum(1 for w in weights.values() if w > WEIGHT_TECHNIQUE * _MULT_SHARED) / max(len(weights), 1),
    )
    return weights


# ── Result types ─────────────────────────────────────────────────────────────

@dataclass
class BuildStats:
    papers_loaded:          int = 0
    paper_pairs_evaluated:  int = 0
    paper_edges_created:    int = 0
    entity_edges_created:   int = 0
    isolated_papers:        int = 0   # no edges at all
    max_edge_weight:        float = 0.0
    avg_edge_weight:        float = 0.0
    entity_breakdown:       dict[str, int] = field(default_factory=dict)


# ── Entity loading ─────────────────────────────────────────────────────────────

def _add_entity_ci(
    bucket: dict[str, str],
    canonical_name: "str | None",
    name: "str | None",
) -> None:
    """
    Insert one entity into a case-insensitive dedup bucket.

    bucket maps lower(display) → display.  When two rows resolve to the same
    lower-cased key, the row with a canonical_name wins so the display string
    is always the authoritative canonical form rather than a raw variant.
    """
    display = canonical_name or name
    if not display:
        return
    key = display.lower()
    existing = bucket.get(key)
    if existing is None:
        bucket[key] = display
    elif canonical_name and not existing == canonical_name:
        # Upgrade to canonical casing if we haven't stored it yet.
        bucket[key] = canonical_name


def _load_paper_entities(session: Session) -> dict[str, dict[str, set[str]]]:
    """
    Return {paper_id: {'techniques': set, 'datasets': set, 'categories': set, 'methodologies': set}}.

    Uses canonical_name where available; falls back to name.  Deduplication is
    case-insensitive: two rows whose names differ only by case (e.g. "Large
    Language Models" vs "Large language models") collapse to a single entry
    using the canonical display form.
    """
    paper_ids = session.scalars(select(Paper.id)).all()

    # Intermediate: per-paper, per-type  lower(name) → display
    buckets: dict[str, dict[str, dict[str, str]]] = {
        pid: {"techniques": {}, "datasets": {}, "categories": {}, "methodologies": {}}
        for pid in paper_ids
    }

    # Techniques
    for row in session.execute(
        select(PaperTechnique.paper_id, PaperTechnique.canonical_name, PaperTechnique.name)
    ).all():
        if row.paper_id in buckets:
            _add_entity_ci(buckets[row.paper_id]["techniques"], row.canonical_name, row.name)

    # Datasets
    for row in session.execute(
        select(PaperDataset.paper_id, PaperDataset.canonical_name, PaperDataset.name)
    ).all():
        if row.paper_id in buckets:
            _add_entity_ci(buckets[row.paper_id]["datasets"], row.canonical_name, row.name)

    # Categories
    for row in session.execute(
        select(PaperCategory.paper_id, PaperCategory.canonical_name, PaperCategory.name)
    ).all():
        if row.paper_id in buckets:
            _add_entity_ci(buckets[row.paper_id]["categories"], row.canonical_name, row.name)

    # Methodologies (no canonical_name column — use name directly)
    for row in session.execute(
        select(PaperMethodology.paper_id, PaperMethodology.name)
    ).all():
        if row.paper_id in buckets and row.name:
            _add_entity_ci(buckets[row.paper_id]["methodologies"], None, row.name)

    # Collapse buckets → sets of display strings
    entities: dict[str, dict[str, set[str]]] = {
        pid: {k: set(v.values()) for k, v in type_map.items()}
        for pid, type_map in buckets.items()
    }

    # Cross-table dedup: remove any category or methodology entry whose
    # lower-cased display string is already present in the technique set.
    # This prevents edges from recording the same concept twice under different
    # shared_* fields (e.g. shared_techniques=['Reinforcement learning'] AND
    # shared_categories=['Reinforcement learning'] after category alias mapping).
    for pid, type_map in entities.items():
        tech_lower = {t.lower() for t in type_map["techniques"]}
        type_map["categories"]    = {c for c in type_map["categories"]    if c.lower() not in tech_lower}
        type_map["methodologies"] = {m for m in type_map["methodologies"] if m.lower() not in tech_lower}

    return entities


# ── Paper-to-paper edges ──────────────────────────────────────────────────────

def _build_paper_relationships(
    session: Session,
    entities: dict[str, dict[str, set[str]]],
    idf_weights: dict[str, float],
) -> BuildStats:
    """
    Compute all paper-pair edges using IDF-weighted technique scores.

    technique_score = Σ idf_weights[t]  for t in shared_techniques
    dataset_score   = WEIGHT_DATASET   * |shared_datasets|
    category_score  = WEIGHT_CATEGORY  * |shared_categories|
    weight          = technique_score + dataset_score + category_score
                    + WEIGHT_METHODOLOGY * |shared_methodologies|
    """
    fallback_weight = round(WEIGHT_TECHNIQUE * _MULT_SPECIALIZED, 4)

    stats = BuildStats(papers_loaded=len(entities))
    paper_ids = sorted(entities.keys())
    n = len(paper_ids)
    total_weight = 0.0
    rows_to_insert = []

    for idx_a in range(n):
        for idx_b in range(idx_a + 1, n):
            a = paper_ids[idx_a]
            b = paper_ids[idx_b]

            ea = entities[a]
            eb = entities[b]

            shared_tech  = sorted(ea["techniques"]   & eb["techniques"])
            shared_ds    = sorted(ea["datasets"]      & eb["datasets"])
            shared_cat   = sorted(ea["categories"]    & eb["categories"])
            shared_meth  = sorted(ea["methodologies"] & eb["methodologies"])

            # IDF-weighted technique contribution (Graph V2)
            technique_score = sum(
                idf_weights.get(t, fallback_weight) for t in shared_tech
            )
            dataset_score    = float(WEIGHT_DATASET    * len(shared_ds))
            category_score   = float(WEIGHT_CATEGORY   * len(shared_cat))
            methodology_score = float(WEIGHT_METHODOLOGY * len(shared_meth))

            weight = technique_score + dataset_score + category_score + methodology_score

            stats.paper_pairs_evaluated += 1

            if weight > 0:
                rows_to_insert.append({
                    "source_paper_id":      a,
                    "target_paper_id":      b,
                    "shared_techniques":    json.dumps(shared_tech),
                    "shared_datasets":      json.dumps(shared_ds),
                    "shared_categories":    json.dumps(shared_cat),
                    "shared_methodologies": json.dumps(shared_meth),
                    "weight":               round(weight, 4),
                    "technique_score":      round(technique_score, 4),
                    "dataset_score":        round(dataset_score, 4),
                    "category_score":       round(category_score, 4),
                })
                total_weight += weight
                if weight > stats.max_edge_weight:
                    stats.max_edge_weight = weight

    for row in rows_to_insert:
        session.add(PaperRelationship(**row))
    session.flush()

    stats.paper_edges_created = len(rows_to_insert)
    stats.avg_edge_weight = total_weight / len(rows_to_insert) if rows_to_insert else 0.0

    connected = set()
    for row in rows_to_insert:
        connected.add(row["source_paper_id"])
        connected.add(row["target_paper_id"])
    stats.isolated_papers = n - len(connected)

    return stats


# ── Entity co-occurrence edges ─────────────────────────────────────────────────

def _build_entity_relationships(
    session: Session,
    entities: dict[str, dict[str, set[str]]],
    stats: BuildStats,
) -> None:
    """
    For each entity type, compute pairwise co-occurrence counts across papers
    and write to entity_relationships.
    """
    # co_counts[entity_type][frozenset({a, b})] = count
    co_counts: dict[str, dict[frozenset[str], int]] = {
        t: defaultdict(int)
        for t in ("techniques", "datasets", "categories", "methodologies")
    }

    for paper_entities in entities.values():
        for etype, entity_set in paper_entities.items():
            items = sorted(entity_set)    # sort for determinism
            for a, b in combinations(items, 2):
                # Enforce a < b lexicographically (already sorted)
                co_counts[etype][frozenset({a, b})] += 1

    # Write rows
    total = 0
    type_map = {
        "techniques":    "technique",
        "datasets":      "dataset",
        "categories":    "category",
        "methodologies": "methodology",
    }
    for etype, pairs in co_counts.items():
        db_type = type_map[etype]
        for pair, count in pairs.items():
            a, b = sorted(pair)
            session.add(EntityRelationship(
                source_entity       = a,
                target_entity       = b,
                entity_type         = db_type,
                co_occurrence_count = count,
                weight              = float(count),
            ))
            total += 1

    session.flush()
    stats.entity_edges_created = total
    stats.entity_breakdown = {
        type_map[t]: len(v) for t, v in co_counts.items()
    }


# ── Public entry point ─────────────────────────────────────────────────────────

def build(session: Session, force: bool = False) -> BuildStats:
    """
    Full graph rebuild.  Truncates all four graph tables, then repopulates.
    Idempotent: safe to re-run at any time.
    """
    log.info("Graph builder: truncating existing graph data")
    for model in (PaperRelationship, EntityRelationship):
        session.execute(delete(model))
    session.flush()

    log.info("Graph builder: loading entity sets for all papers")
    entities = _load_paper_entities(session)
    log.info("Graph builder: %d papers loaded", len(entities))

    log.info("Graph builder: computing IDF weights for techniques")
    idf_weights = _build_idf_weights(session)

    log.info("Graph builder: computing paper-to-paper edges (IDF-weighted)")
    stats = _build_paper_relationships(session, entities, idf_weights)
    log.info(
        "Graph builder: %d pairs evaluated → %d edges (max_w=%.0f avg_w=%.1f isolated=%d)",
        stats.paper_pairs_evaluated, stats.paper_edges_created,
        stats.max_edge_weight, stats.avg_edge_weight, stats.isolated_papers,
    )

    log.info("Graph builder: computing entity co-occurrence edges")
    _build_entity_relationships(session, entities, stats)
    log.info("Graph builder: %d entity edges created (%s)", stats.entity_edges_created, stats.entity_breakdown)

    session.commit()
    return stats
