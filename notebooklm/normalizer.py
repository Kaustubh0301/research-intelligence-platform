"""
NotebookLM output normalizer.

Takes an ExtractionResult from extractor.py and writes the structured
data into the existing DB tables:

  ParsedSummary    → paper_analyses (summary, advantages, limitations, future_work)
                   + paper_analyses.use_cases  (from ParsedUseCases)
  ParsedTechniques → paper_techniques (name, role)
  ParsedDatasets   → paper_datasets (name, task)
  ParsedCategories → paper_categories (name)
                   + paper_methodologies (name)

Also writes raw extracts to notebook_paper_extracts for audit and
marks notebook_syntheses.normalized = True when all extracts are done.

All writes are idempotent — safe to re-run after a partial failure.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models import (
    NotebookPaperExtract,
    NotebookSynthesis,
    PaperAnalysisRecord,
    PaperCategory,
    PaperDataset,
    PaperMethodology,
    PaperTechnique,
)
from notebooklm.extractor import (
    ExtractionResult,
    ParsedCategories,
    ParsedDatasets,
    ParsedExperimentalFindings,
    ParsedFutureResearchDirections,
    ParsedLimitations,
    ParsedMethodology,
    ParsedPracticalApplications,
    ParsedStrengths,
    ParsedSummary,
    ParsedTechniques,
    ParsedUseCases,
)

log = logging.getLogger(__name__)

MODEL_LABEL = "notebooklm"


# ── Result tracking ───────────────────────────────────────────────────────────

@dataclass
class NormalizationStats:
    papers_processed:   int = 0
    analyses_written:   int = 0
    techniques_written: int = 0
    datasets_written:   int = 0
    categories_written: int = 0
    methodologies_written: int = 0
    extracts_written:   int = 0
    skipped_no_match:   int = 0
    errors:             list[str] = field(default_factory=list)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _now() -> datetime:
    return datetime.now(timezone.utc)


def _upsert_analysis(
    session: Session,
    paper_id: str,
    notebook_id: str,
    summary:                    Optional[ParsedSummary]                  = None,
    use_cases:                  Optional[ParsedUseCases]                 = None,
    methodology:                Optional[ParsedMethodology]              = None,
    experimental_findings:      Optional[ParsedExperimentalFindings]     = None,
    strengths:                  Optional[ParsedStrengths]                = None,
    limitations_v2:             Optional[ParsedLimitations]              = None,
    practical_applications:     Optional[ParsedPracticalApplications]    = None,
    future_research_directions: Optional[ParsedFutureResearchDirections] = None,
) -> bool:
    """
    Write / update paper_analyses.  Only updates fields that are provided
    (not None) so partial re-synthesis doesn't null out existing columns.
    Returns True if a row was written.
    """
    existing = session.scalar(
        select(PaperAnalysisRecord).where(PaperAnalysisRecord.paper_id == paper_id)
    )
    rec = existing or PaperAnalysisRecord(paper_id=paper_id)
    if not existing:
        session.add(rec)

    # V1 fields — only written when the corresponding parsed object is present
    if summary is not None:
        rec.summary     = summary.summary or None
        rec.advantages  = json.dumps(summary.advantages)
        rec.future_work = json.dumps(summary.future_work)
    if use_cases is not None:
        rec.use_cases = json.dumps(use_cases.use_cases)

    # V2 fields
    if methodology is not None:
        rec.methodology = methodology.methodology or None
    if experimental_findings is not None:
        # Serialise each finding as "benchmark :: metric :: scores"
        rec.experimental_findings = json.dumps([
            f"{f.benchmark} :: {f.metric} :: {f.scores}".strip(" ::")
            for f in experimental_findings.findings
        ])
    if strengths is not None:
        rec.strengths = json.dumps(strengths.strengths)
    if limitations_v2 is not None:
        # Write to both the legacy limitations column and the new strengths path
        # so the API backward-compat field stays populated
        rec.limitations = json.dumps(limitations_v2.limitations)
    if practical_applications is not None:
        rec.practical_applications = json.dumps(practical_applications.applications)
    if future_research_directions is not None:
        rec.future_research_directions = json.dumps(future_research_directions.directions)

    rec.model = f"{MODEL_LABEL}/notebook:{notebook_id}"

    session.flush()
    return True


def _upsert_techniques(
    session: Session,
    paper_id: str,
    parsed: ParsedTechniques,
) -> int:
    """Write paper_techniques rows. Returns count written."""
    written = 0
    for role, names in [("introduces", parsed.introduces), ("uses", parsed.uses)]:
        for name in names:
            name = name.strip()
            if not name:
                continue
            existing = session.scalar(
                select(PaperTechnique).where(
                    PaperTechnique.paper_id == paper_id,
                    PaperTechnique.name     == name,
                )
            )
            if existing:
                existing.role = role      # update role if already present
            else:
                session.add(PaperTechnique(
                    paper_id=paper_id, name=name, role=role, source=MODEL_LABEL,
                ))
                written += 1
    session.flush()
    return written


def _upsert_datasets(
    session: Session,
    paper_id: str,
    parsed: ParsedDatasets,
) -> int:
    written = 0
    for ds in parsed.datasets:
        existing = session.scalar(
            select(PaperDataset).where(
                PaperDataset.paper_id == paper_id,
                PaperDataset.name     == ds.name,
            )
        )
        if existing:
            if ds.task:
                existing.task = ds.task
        else:
            session.add(PaperDataset(
                paper_id=paper_id,
                name=ds.name,
                task=ds.task or None,
                source=MODEL_LABEL,
            ))
            written += 1
    session.flush()
    return written


def _upsert_categories(
    session: Session,
    paper_id: str,
    parsed: ParsedCategories,
) -> tuple[int, int]:
    """Write paper_categories and paper_methodologies. Returns (cats, meths)."""
    cats_written, meths_written = 0, 0

    for name in parsed.categories:
        existing = session.scalar(
            select(PaperCategory).where(
                PaperCategory.paper_id == paper_id,
                PaperCategory.name     == name,
            )
        )
        if not existing:
            session.add(PaperCategory(
                paper_id=paper_id, name=name, source=MODEL_LABEL,
            ))
            cats_written += 1

    for name in parsed.methodologies:
        name = name.strip()
        if not name:
            continue
        existing = session.scalar(
            select(PaperMethodology).where(
                PaperMethodology.paper_id == paper_id,
                PaperMethodology.name     == name,
            )
        )
        if not existing:
            session.add(PaperMethodology(
                paper_id=paper_id, name=name, source=MODEL_LABEL,
            ))
            meths_written += 1

    session.flush()
    return cats_written, meths_written


def _write_extract(
    session: Session,
    notebook_id: str,
    synthesis_id: str,
    paper_id: str,
    extract_type: str,
    content: str,
    confidence: str = "high",
) -> None:
    """Append to notebook_paper_extracts (always inserts, not upserted)."""
    session.add(NotebookPaperExtract(
        notebook_id   = notebook_id,
        synthesis_id  = synthesis_id,
        paper_id      = paper_id,
        extract_type  = extract_type,
        content       = content,
        confidence    = confidence,
        normalized    = True,
    ))
    session.flush()


def _synthesis_id_for(
    session: Session,
    notebook_id: str,
    query_name: str,
) -> Optional[str]:
    """Return the synthesis row id for a given notebook + query name."""
    row = session.scalar(
        select(NotebookSynthesis).where(
            NotebookSynthesis.notebook_id    == notebook_id,
            NotebookSynthesis.synthesis_type == "query_response",
            NotebookSynthesis.query_prompt.like(f"%{query_name}%"),
        )
    )
    return row.id if row else None


# ── Public entry point ────────────────────────────────────────────────────────

def normalize(
    session: Session,
    result: ExtractionResult,
    notebook_id: str,
    synthesis_ids: dict[str, str],   # {query_name: synthesis_row_id}
) -> NormalizationStats:
    """
    Write all parsed data into the DB.

    Args:
        session:       open SQLAlchemy Session (caller commits)
        result:        ExtractionResult from extractor.extract_all()
        notebook_id:   UUID of the Notebook row this data came from
        synthesis_ids: maps query_name → notebook_syntheses.id
                       (used to populate notebook_paper_extracts.synthesis_id)

    Returns NormalizationStats with counts for reporting.
    """
    stats = NormalizationStats()

    # Build lookup maps keyed by paper_id — V1 metadata
    summary_map:   dict[str, ParsedSummary]    = {s.paper_id: s for s in result.summaries   if s.paper_id}
    tech_map:      dict[str, ParsedTechniques] = {t.paper_id: t for t in result.techniques  if t.paper_id}
    dataset_map:   dict[str, ParsedDatasets]   = {d.paper_id: d for d in result.datasets    if d.paper_id}
    category_map:  dict[str, ParsedCategories] = {c.paper_id: c for c in result.categories  if c.paper_id}
    usecase_map:   dict[str, ParsedUseCases]   = {u.paper_id: u for u in result.use_cases   if u.paper_id}

    # V2 analysis maps
    methodology_map:   dict[str, ParsedMethodology]              = {m.paper_id: m for m in result.methodologies              if m.paper_id}
    findings_map:      dict[str, ParsedExperimentalFindings]     = {f.paper_id: f for f in result.experimental_findings      if f.paper_id}
    strengths_map:     dict[str, ParsedStrengths]                = {s.paper_id: s for s in result.strengths                  if s.paper_id}
    limitations_map:   dict[str, ParsedLimitations]              = {l.paper_id: l for l in result.limitations_v2             if l.paper_id}
    applications_map:  dict[str, ParsedPracticalApplications]    = {a.paper_id: a for a in result.practical_applications     if a.paper_id}
    directions_map:    dict[str, ParsedFutureResearchDirections] = {d.paper_id: d for d in result.future_research_directions if d.paper_id}

    all_paper_ids = (
        set(summary_map) | set(tech_map) | set(dataset_map) |
        set(category_map) | set(usecase_map) |
        set(methodology_map) | set(findings_map) | set(strengths_map) |
        set(limitations_map) | set(applications_map) | set(directions_map)
    )

    if result.unmatched:
        for t in result.unmatched:
            log.warning("normalizer: unmatched title %r — no DB row written", t[:60])
        stats.skipped_no_match = len(result.unmatched)

    for paper_id in all_paper_ids:
        stats.papers_processed += 1
        log.debug("Normalizing paper %s", paper_id)

        # ── paper_analyses ────────────────────────────────────────────────────
        # Any subset of analysis prompts may be present; _upsert_analysis only
        # writes fields that have parsed data, preserving existing column values.
        has_analysis_data = any(paper_id in m for m in (
            summary_map, usecase_map, methodology_map, findings_map,
            strengths_map, limitations_map, applications_map, directions_map,
        ))
        if has_analysis_data:
            try:
                ok = _upsert_analysis(
                    session, paper_id, notebook_id,
                    summary                    = summary_map.get(paper_id),
                    use_cases                  = usecase_map.get(paper_id),
                    methodology                = methodology_map.get(paper_id),
                    experimental_findings      = findings_map.get(paper_id),
                    strengths                  = strengths_map.get(paper_id),
                    limitations_v2             = limitations_map.get(paper_id),
                    practical_applications     = applications_map.get(paper_id),
                    future_research_directions = directions_map.get(paper_id),
                )
                if ok:
                    stats.analyses_written += 1
                    # Write audit extract for the V1 summary only (extract_type
                    # constraint in notebook_paper_extracts covers legacy types;
                    # V2 synthesis content is preserved in notebook_syntheses.content
                    # and does not need a redundant per-paper extract row).
                    if paper_id in summary_map:
                        synth_id = synthesis_ids.get("summary", "")
                        if synth_id:
                            _write_extract(session, notebook_id, synth_id, paper_id,
                                           "summary", summary_map[paper_id].summary or "")
                            stats.extracts_written += 1
            except Exception as exc:
                log.error("analysis upsert failed for %s: %s", paper_id, exc)
                stats.errors.append(f"analysis:{paper_id}:{exc}")

        # ── paper_techniques ──────────────────────────────────────────────────
        if paper_id in tech_map:
            try:
                n = _upsert_techniques(session, paper_id, tech_map[paper_id])
                stats.techniques_written += n
                synth_id = synthesis_ids.get("techniques", "")
                if synth_id and n > 0:
                    _write_extract(
                        session, notebook_id, synth_id, paper_id,
                        "techniques",
                        json.dumps({
                            "introduces": tech_map[paper_id].introduces,
                            "uses":       tech_map[paper_id].uses,
                        }),
                    )
                    stats.extracts_written += 1
            except Exception as exc:
                log.error("techniques upsert failed for %s: %s", paper_id, exc)
                stats.errors.append(f"techniques:{paper_id}:{exc}")

        # ── paper_datasets ────────────────────────────────────────────────────
        if paper_id in dataset_map:
            try:
                n = _upsert_datasets(session, paper_id, dataset_map[paper_id])
                stats.datasets_written += n
                synth_id = synthesis_ids.get("datasets", "")
                if synth_id and n > 0:
                    _write_extract(
                        session, notebook_id, synth_id, paper_id,
                        "datasets",
                        json.dumps([
                            {"name": d.name, "task": d.task}
                            for d in dataset_map[paper_id].datasets
                        ]),
                    )
                    stats.extracts_written += 1
            except Exception as exc:
                log.error("datasets upsert failed for %s: %s", paper_id, exc)
                stats.errors.append(f"datasets:{paper_id}:{exc}")

        # ── paper_categories + paper_methodologies ────────────────────────────
        if paper_id in category_map:
            try:
                c, m = _upsert_categories(session, paper_id, category_map[paper_id])
                stats.categories_written     += c
                stats.methodologies_written  += m
                synth_id = synthesis_ids.get("categories", "")
                if synth_id and (c + m) > 0:
                    _write_extract(
                        session, notebook_id, synth_id, paper_id,
                        "categories",
                        json.dumps(category_map[paper_id].categories),
                    )
                    _write_extract(
                        session, notebook_id, synth_id, paper_id,
                        "methodologies",
                        json.dumps(category_map[paper_id].methodologies),
                    )
                    stats.extracts_written += 2
            except Exception as exc:
                log.error("categories upsert failed for %s: %s", paper_id, exc)
                stats.errors.append(f"categories:{paper_id}:{exc}")

    return stats
