"""
Relationship explainer — answers WHY two papers are related.

Derives a structured explanation entirely from existing DB data:
  - paper_relationships edge (shared entities, scores)
  - paper_techniques (role: introduces | uses, per paper)
  - paper_methodologies
  - paper_analyses (summary, advantages, limitations)

No LLM calls. No new DB tables.

Public entry point:
  explain(session, paper_id_a, paper_id_b) -> RelationshipExplanation | None
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models import (
    Paper,
    PaperAnalysisRecord,
    PaperMethodology,
    PaperRelationship,
    PaperTechnique,
)

# ── IDF thresholds (must match graph/builder.py) ──────────────────────────────
_IDF_GENERIC_CEILING = 3.00
_IDF_SHARED_CEILING  = 3.69


# ── Output types ──────────────────────────────────────────────────────────────

@dataclass
class ConceptSignal:
    name:          str
    signal_tier:   str    # GENERIC | SHARED | SPECIALIZED
    idf_score:     float
    paper_a_role:  str    # introduces | uses | absent
    paper_b_role:  str


@dataclass
class RelationshipExplanation:
    paper_a_id:    str
    paper_b_id:    str
    paper_a_title: str
    paper_b_title: str

    relationship_score: float
    technique_score:    Optional[float]
    dataset_score:      Optional[float]
    category_score:     Optional[float]

    shared_concepts:     list[ConceptSignal]   # sorted: SPECIALIZED first
    shared_categories:   list[str]
    shared_datasets:     list[str]
    shared_methodologies: list[str]

    differences:         list[str]   # one bullet per paper
    research_connection: str         # 1–2 sentence synthesis


# ── IDF helpers ───────────────────────────────────────────────────────────────

def _idf_tier(idf: float) -> str:
    if idf < _IDF_GENERIC_CEILING:
        return "GENERIC"
    if idf < _IDF_SHARED_CEILING:
        return "SHARED"
    return "SPECIALIZED"


def _load_technique_paper_counts(session: Session) -> dict[str, int]:
    from sqlalchemy import func
    rows = session.execute(
        select(
            PaperTechnique.canonical_name,
            func.count(PaperTechnique.paper_id.distinct()).label("cnt"),
        )
        .where(PaperTechnique.canonical_name.isnot(None))
        .group_by(PaperTechnique.canonical_name)
    ).all()
    return {r.canonical_name: r.cnt for r in rows}


# ── Entity helpers ────────────────────────────────────────────────────────────

def _technique_roles(session: Session, paper_id: str) -> dict[str, str]:
    """Return {canonical_name: role} for a paper's techniques."""
    rows = session.execute(
        select(PaperTechnique.canonical_name, PaperTechnique.role)
        .where(
            PaperTechnique.paper_id == paper_id,
            PaperTechnique.canonical_name.isnot(None),
        )
    ).all()
    # If a technique appears multiple times (different raw names), 'introduces' wins
    out: dict[str, str] = {}
    for canon, role in rows:
        if canon not in out or role == "introduces":
            out[canon] = role
    return out


def _methodologies(session: Session, paper_id: str) -> list[str]:
    return session.scalars(
        select(PaperMethodology.name).where(PaperMethodology.paper_id == paper_id)
    ).all()


def _analysis(session: Session, paper_id: str) -> Optional[PaperAnalysisRecord]:
    return session.scalar(
        select(PaperAnalysisRecord).where(PaperAnalysisRecord.paper_id == paper_id)
    )


def _first_sentence(text: Optional[str]) -> str:
    if not text:
        return ""
    # Split on ". " and take the first sentence
    for delim in (". ", ".\n"):
        idx = text.find(delim)
        if idx != -1:
            return text[: idx + 1].strip()
    return text[:200].strip()


# ── Difference generation ─────────────────────────────────────────────────────

def _generate_differences(
    session: Session,
    paper_a: Paper,
    paper_b: Paper,
    roles_a: dict[str, str],
    roles_b: dict[str, str],
    shared_techs: set[str],
) -> list[str]:
    """
    Return one bullet per paper describing what it distinctively does.

    Priority order:
      1. Techniques the paper *introduces* (novel contributions)
      2. Techniques it *uses* that the other doesn't share
      3. Unique methodologies
      4. First sentence of summary as fallback
    """
    differences: list[str] = []

    for paper, roles, other_roles in [
        (paper_a, roles_a, roles_b),
        (paper_b, roles_b, roles_a),
    ]:
        introduced = [
            t for t, r in roles.items()
            if r == "introduces" and t not in shared_techs
        ]
        unique_uses = [
            t for t, r in roles.items()
            if r != "introduces" and t not in shared_techs and t not in other_roles
        ]
        unique_meths = [
            m for m in _methodologies(session, paper.id)
            if m not in (_methodologies(session, (paper_b if paper.id == paper_a.id else paper_a).id))
        ]

        label = f"**{paper.title[:65]}{'…' if len(paper.title) > 65 else ''}**"

        if introduced:
            concepts = ", ".join(introduced[:2])
            differences.append(f"{label} — Introduces {concepts}")
        elif unique_uses:
            concepts = ", ".join(unique_uses[:2])
            differences.append(f"{label} — Applies {concepts}")
        elif unique_meths:
            meths = ", ".join(unique_meths[:2])
            differences.append(f"{label} — Uses {meths}")
        else:
            analysis = _analysis(session, paper.id)
            first = _first_sentence(analysis.summary if analysis else None)
            if first:
                differences.append(f"{label} — {first}")
            else:
                differences.append(f"{label} — {paper.title[:80]}")

    return differences


# ── Research connection synthesis ─────────────────────────────────────────────

# Category-set → connection template.
# Keys are frozensets of lowercase category names; matched by subset.
_CONNECTION_TEMPLATES: list[tuple[frozenset[str], str]] = [
    (frozenset({"llm", "safety"}),
     "Both investigate post-training alignment and safety of large language models"),
    (frozenset({"safety", "agentic-ai"}),
     "Both address safety constraints for autonomous language model agents"),
    (frozenset({"llm", "agentic-ai"}),
     "Both advance agentic reasoning and planning capabilities of large language models"),
    (frozenset({"llm", "efficiency"}),
     "Both improve the computational efficiency of large language model training or inference"),
    (frozenset({"llm", "nlp"}),
     "Both contribute to natural language understanding and generation with large models"),
    (frozenset({"rl", "llm"}),
     "Both connect reinforcement learning methods with language model training objectives"),
    (frozenset({"rl", "theory"}),
     "Both provide theoretical foundations for reinforcement learning algorithms"),
    (frozenset({"theory", "llm"}),
     "Both contribute formal theoretical analysis to the study of large language models"),
    (frozenset({"theory"}),
     "Both provide theoretical convergence or generalization analysis"),
    (frozenset({"vision", "llm"}),
     "Both bridge vision and language understanding in multimodal or cross-modal settings"),
    (frozenset({"rl"}),
     "Both advance reinforcement learning methodology and algorithms"),
    (frozenset({"llm"}),
     "Both study the behavior, training, or capabilities of large language models"),
    (frozenset({"safety"}),
     "Both address robustness, alignment, or safety properties of machine learning systems"),
    (frozenset({"efficiency"}),
     "Both target computational efficiency in model training or deployment"),
    (frozenset({"generative"}),
     "Both explore generative modeling approaches and their properties"),
    (frozenset({"graph"}),
     "Both apply or analyze graph-structured data and graph neural networks"),
]


def _generate_connection(
    shared_cats: list[str],
    shared_techs: list[str],
    shared_meths: list[str],
    roles_a: dict[str, str],
    roles_b: dict[str, str],
) -> str:
    cat_set = frozenset(c.lower() for c in shared_cats)

    # Find the best matching template (largest matching subset first)
    best_template: Optional[str] = None
    best_match_size = 0
    for key, template in _CONNECTION_TEMPLATES:
        if key <= cat_set and len(key) > best_match_size:
            best_template = template
            best_match_size = len(key)

    # Build the base sentence
    if best_template:
        base = best_template
    elif shared_cats:
        cats_str = " and ".join(shared_cats[:3])
        base = f"Both papers work in the intersection of {cats_str}"
    elif shared_techs:
        techs_str = " and ".join(shared_techs[:2])
        base = f"Both papers apply {techs_str}"
    else:
        base = "Both papers share overlapping research contributions"

    # Append shared methodology qualifier only when it adds new information
    if shared_meths and best_match_size > 0:
        meth = shared_meths[0].lower()
        generic_meths = {
            "theoretical analysis", "empirical evaluation",
            "empirical analysis", "fine-tuning",
        }
        # Skip if the methodology's key words are already in the template
        already_implied = any(word in base.lower() for word in meth.split() if len(word) > 4)
        if meth not in generic_meths and not already_implied:
            base = f"{base}, both employing {shared_meths[0].lower()}"

    # Add technique specificity for SPECIALIZED shared techniques
    specialized_shared = [
        t for t in shared_techs
        if t not in ("Transformers", "Large Language Models", "Diffusion Models")
    ]
    if specialized_shared and not best_template:
        techs_str = " and ".join(specialized_shared[:2])
        base = f"{base} through their shared use of {techs_str}"

    return base + "."


# ── Main entry point ──────────────────────────────────────────────────────────

def _json_list(raw: Optional[str]) -> list[str]:
    import json
    if not raw:
        return []
    try:
        v = json.loads(raw)
        return v if isinstance(v, list) else []
    except (json.JSONDecodeError, TypeError):
        return []


def explain(
    session: Session,
    paper_id_a: str,
    paper_id_b: str,
) -> Optional[RelationshipExplanation]:
    """
    Return a RelationshipExplanation for the pair, or None if no edge exists.

    The edge is looked up regardless of source/target ordering.
    """
    paper_a = session.get(Paper, paper_id_a)
    paper_b = session.get(Paper, paper_id_b)
    if not paper_a or not paper_b:
        return None

    # Look up the edge in either direction
    edge = session.scalar(
        select(PaperRelationship).where(
            (
                (PaperRelationship.source_paper_id == paper_id_a) &
                (PaperRelationship.target_paper_id == paper_id_b)
            ) | (
                (PaperRelationship.source_paper_id == paper_id_b) &
                (PaperRelationship.target_paper_id == paper_id_a)
            )
        )
    )
    if edge is None:
        return None

    # Parse shared entity lists from the edge
    shared_techs_list  = _json_list(edge.shared_techniques)
    shared_cats_list   = _json_list(edge.shared_categories)
    shared_ds_list     = _json_list(edge.shared_datasets)
    shared_meths_list  = _json_list(edge.shared_methodologies)
    shared_techs_set   = set(shared_techs_list)

    # Load per-paper technique roles
    roles_a = _technique_roles(session, paper_id_a)
    roles_b = _technique_roles(session, paper_id_b)

    # Load paper counts for IDF
    from sqlalchemy import func
    total_papers: int = session.scalar(
        select(func.count()).select_from(Paper)
    ) or 1
    tech_counts = _load_technique_paper_counts(session)

    # Build ConceptSignal list for shared techniques, SPECIALIZED first
    concepts: list[ConceptSignal] = []
    for tech in shared_techs_list:
        count = tech_counts.get(tech, 1)
        idf   = math.log(total_papers / count)
        tier  = _idf_tier(idf)
        concepts.append(ConceptSignal(
            name         = tech,
            signal_tier  = tier,
            idf_score    = round(idf, 3),
            paper_a_role = roles_a.get(tech, "absent"),
            paper_b_role = roles_b.get(tech, "absent"),
        ))
    # Sort: SPECIALIZED first, then SHARED, then GENERIC; within tier by idf desc
    tier_order = {"SPECIALIZED": 0, "SHARED": 1, "GENERIC": 2}
    concepts.sort(key=lambda c: (tier_order[c.signal_tier], -c.idf_score))

    # Differences
    differences = _generate_differences(
        session, paper_a, paper_b, roles_a, roles_b, shared_techs_set,
    )

    # Research connection
    connection = _generate_connection(
        shared_cats_list, shared_techs_list, shared_meths_list, roles_a, roles_b,
    )

    return RelationshipExplanation(
        paper_a_id           = paper_id_a,
        paper_b_id           = paper_id_b,
        paper_a_title        = paper_a.title,
        paper_b_title        = paper_b.title,
        relationship_score   = round(edge.weight, 2),
        technique_score      = edge.technique_score,
        dataset_score        = edge.dataset_score,
        category_score       = edge.category_score,
        shared_concepts      = concepts,
        shared_categories    = shared_cats_list,
        shared_datasets      = shared_ds_list,
        shared_methodologies = shared_meths_list,
        differences          = differences,
        research_connection  = connection,
    )
