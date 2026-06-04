"""
Topic assigner — maps papers to notebook topics via keyword scoring.

Three-pass algorithm (per architecture report §4.2):
  Pass 1 — Hard conference domain rules
           CVPR/ICCV/ECCV → vision domain bias
           ACL/EMNLP      → nlp domain bias
           Others         → no constraint

  Pass 2 — Keyword scoring on title + abstract
           Primary match  = 2 pts per hit
           Secondary match = 1 pt per hit
           Score normalised by vocabulary size so large vocabularies
           don't dominate small ones.

  Pass 3 — Fallback + overflow
           Below-threshold papers → broadest domain topic
           Notebook-full papers   → next instance or sibling topic

Public entry points:
  assign_papers(paper_ids, session) → list[Assignment]
  assign_paper(paper, session)      → list[Assignment]   (1–2 per paper)
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models import Conference, ConferenceEdition, Notebook, NotebookPaper, Paper

log = logging.getLogger(__name__)

_KEYWORDS_PATH = Path(__file__).parent / "topic_keywords.json"

# Score thresholds (normalised 0–1)
_PRIMARY_THRESHOLD   = 0.08   # top-1 assignment
_SECONDARY_THRESHOLD = 0.04   # top-2 assignment (multi-topic papers)

# Per-domain fallback topic (used when no topic scores above threshold)
_DOMAIN_FALLBACK: dict[str, str] = {
    "llm":        "llm-architectures",
    "agentic":    "agentic-ai",
    "safety":     "ai-safety",
    "vision":     "vision-language",
    "nlp":        "dialogue-qa",
    "core-ml":    "optimization-training",
    "applications": "scientific-discovery",
}

# Conference → forced domain (Pass 1)
_CONF_DOMAIN: dict[str, str] = {
    "CVPR":  "vision",
    "ICCV":  "vision",
    "ECCV":  "vision",
    "ACL":   "nlp",
    "EMNLP": "nlp",
}


# ── Data structures ───────────────────────────────────────────────────────────

@dataclass
class Assignment:
    paper_id:   str
    topic_slug: str
    confidence: str          # "high" | "medium" | "low"
    score:      float        # normalised score (diagnostic only)
    reason:     str          # human-readable explanation


@dataclass
class _TopicSpec:
    slug:       str
    name:       str
    domain:     str
    primary:    list[str]
    secondary:  list[str]
    fallback_conferences: list[str]


# ── Load vocabulary once at import ───────────────────────────────────────────

def _load_topics() -> dict[str, _TopicSpec]:
    raw = json.loads(_KEYWORDS_PATH.read_text())
    topics: dict[str, _TopicSpec] = {}
    for slug, data in raw.items():
        if slug.startswith("_"):
            continue
        topics[slug] = _TopicSpec(
            slug=slug,
            name=data["name"],
            domain=data["domain"],
            primary=[kw.lower() for kw in data["primary"]],
            secondary=[kw.lower() for kw in data["secondary"]],
            fallback_conferences=data.get("fallback_conferences", []),
        )
    return topics


_TOPICS: dict[str, _TopicSpec] = _load_topics()


# ── Scoring ───────────────────────────────────────────────────────────────────

def _tokenise(text: str) -> str:
    """Lower-case, collapse whitespace — ready for substring matching."""
    return re.sub(r"\s+", " ", text.lower().strip())


def _score(text: str, spec: _TopicSpec) -> float:
    """
    Return a normalised score in [0, 1] for how well `text` matches `spec`.

    Normalisation: raw_score / max_possible_score
    where max_possible_score = 2 * len(primary) + len(secondary).
    """
    t = _tokenise(text)
    raw = sum(2 for kw in spec.primary   if kw in t)
    raw += sum(1 for kw in spec.secondary if kw in t)
    max_possible = 2 * len(spec.primary) + len(spec.secondary)
    if max_possible == 0:
        return 0.0
    return raw / max_possible


def _allowed_topics(conf_short_name: Optional[str]) -> set[str]:
    """
    Pass 1: Return the set of topic slugs that are candidates for this paper.
    If the conference maps to a forced domain, restrict to that domain only.
    Otherwise return all topics.
    """
    if conf_short_name and conf_short_name.upper() in _CONF_DOMAIN:
        forced_domain = _CONF_DOMAIN[conf_short_name.upper()]
        return {slug for slug, spec in _TOPICS.items() if spec.domain == forced_domain}
    return set(_TOPICS.keys())


def _resolve_conference_name(session: Session, paper: Paper) -> Optional[str]:
    if not paper.conference_edition_id:
        return None
    edition = session.get(ConferenceEdition, paper.conference_edition_id)
    if not edition:
        return None
    conf = session.get(Conference, edition.conference_id)
    return conf.short_name if conf else None


# ── Notebook capacity helpers ─────────────────────────────────────────────────

def _get_or_create_notebook(
    session: Session,
    topic_slug: str,
    max_sources: int = 45,
) -> Notebook:
    """
    Return an active notebook for the topic with remaining capacity.
    Creates a new instance if none exist or all are full.
    """
    existing: list[Notebook] = list(session.scalars(
        select(Notebook)
        .where(Notebook.topic_slug == topic_slug, Notebook.status == "active")
        .order_by(Notebook.instance_number)
    ))
    for nb in existing:
        if nb.source_count < nb.max_sources:
            return nb

    # All existing are full, or none exist — create a new instance
    next_instance = (max(nb.instance_number for nb in existing) + 1) if existing else 1
    spec = _TOPICS[topic_slug]
    nb = Notebook(
        topic_slug=topic_slug,
        topic_name=spec.name,
        instance_number=next_instance,
        max_sources=max_sources,
        status="active",
    )
    session.add(nb)
    session.flush()   # populate nb.id
    log.info("Created notebook record: %s instance=%d", topic_slug, next_instance)
    return nb


# ── Core assignment logic ─────────────────────────────────────────────────────

def assign_paper(paper: Paper, session: Session) -> list[Assignment]:
    """
    Assign a single paper to 1–2 notebook topics.
    Writes NotebookPaper rows to the session (does not commit).
    Returns the list of Assignment objects for the caller to inspect.
    """
    conf_name = _resolve_conference_name(session, paper)
    search_text = f"{paper.title} {paper.abstract or ''}"

    # Pass 1: restrict candidate topics by conference
    candidates = _allowed_topics(conf_name)

    # Pass 2: score all candidates
    scores: list[tuple[float, str]] = []   # (score, slug)
    for slug in candidates:
        s = _score(search_text, _TOPICS[slug])
        if s > 0:
            scores.append((s, slug))
    scores.sort(reverse=True)

    assignments: list[Assignment] = []

    if scores and scores[0][0] >= _PRIMARY_THRESHOLD:
        top_score, top_slug = scores[0]
        confidence = "high" if top_score >= 0.15 else "medium"
        assignments.append(Assignment(
            paper_id=paper.id,
            topic_slug=top_slug,
            confidence=confidence,
            score=top_score,
            reason=f"keyword score {top_score:.3f} (top-1)",
        ))
        # Second topic if a different topic also scores above secondary threshold
        if len(scores) > 1:
            sec_score, sec_slug = scores[1]
            if sec_score >= _SECONDARY_THRESHOLD and sec_slug != top_slug:
                assignments.append(Assignment(
                    paper_id=paper.id,
                    topic_slug=sec_slug,
                    confidence="medium",
                    score=sec_score,
                    reason=f"keyword score {sec_score:.3f} (top-2)",
                ))
    else:
        # Pass 3 fallback: assign to broadest domain topic
        domain = _domain_for_conference(conf_name)
        fallback_slug = _DOMAIN_FALLBACK.get(domain, "llm-architectures")
        assignments.append(Assignment(
            paper_id=paper.id,
            topic_slug=fallback_slug,
            confidence="low",
            score=scores[0][0] if scores else 0.0,
            reason=f"fallback (best score {scores[0][0]:.3f} < threshold)" if scores else "fallback (no keyword matches)",
        ))

    # Write to DB (idempotent: skip if this paper is already in a notebook for this topic)
    for a in assignments:
        nb = _get_or_create_notebook(session, a.topic_slug)
        already = session.execute(
            select(NotebookPaper).where(
                NotebookPaper.notebook_id == nb.id,
                NotebookPaper.paper_id   == paper.id,
            )
        ).scalar_one_or_none()
        if already is None:
            session.add(NotebookPaper(
                notebook_id=nb.id,
                paper_id=paper.id,
                assigned_by="keyword",
                assignment_confidence=a.confidence,
                source_status="pending",
            ))
            nb.source_count += 1
            session.flush()
            log.debug(
                "Assigned %s → %s (conf=%s score=%.3f)",
                paper.title[:40], a.topic_slug, a.confidence, a.score,
            )

    return assignments


def assign_papers(
    paper_ids: list[str],
    session: Session,
) -> list[Assignment]:
    """Assign a batch of papers. Returns all Assignment objects produced."""
    all_assignments: list[Assignment] = []
    for pid in paper_ids:
        paper = session.get(Paper, pid)
        if paper is None:
            log.warning("assign_papers: paper %s not found", pid)
            continue
        # Skip if already assigned to any notebook
        already_assigned = session.execute(
            select(NotebookPaper).where(NotebookPaper.paper_id == pid).limit(1)
        ).scalar_one_or_none()
        if already_assigned is not None:
            log.debug("Paper %s already assigned, skipping", pid)
            continue
        results = assign_paper(paper, session)
        all_assignments.extend(results)
    return all_assignments


def _domain_for_conference(conf_name: Optional[str]) -> str:
    """Return the domain string for a conference name, defaulting to 'llm'."""
    if conf_name and conf_name.upper() in _CONF_DOMAIN:
        return _CONF_DOMAIN[conf_name.upper()]
    return "llm"

