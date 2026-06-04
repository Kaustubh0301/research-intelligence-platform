"""
Stage DB Store
==============
Idempotent upserts for all four pipeline stages.
All functions take an open SQLAlchemy Session — callers handle commit/rollback.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models import (
    Paper, PaperSection, PaperDataset,
    PaperAnalysisRecord, PipelineError,
)
from pdf_pipeline.analyser import AnalysisResult, PaperAnalysis
from pdf_pipeline.downloader import DownloadResult
from pdf_pipeline.extractor import RawExtraction
from pdf_pipeline.segmenter import PaperSections

log = logging.getLogger(__name__)


# ── Stage 1: persist download result ──────────────────────────────────────────

def save_download(session: Session, result: DownloadResult) -> None:
    paper = session.get(Paper, result.paper_id)
    if paper is None:
        log.error("save_download: paper %s not found", result.paper_id)
        return
    if result.success and result.local_path:
        paper.pdf_local_path = str(result.local_path)
    elif not result.success:
        _log_error(session, result.paper_id, "download",
                   result.error_type or "unknown", result.error_msg)
    session.flush()


# ── Stage 2: persist extraction result ────────────────────────────────────────

def save_extraction(session: Session, extraction: RawExtraction) -> None:
    paper = session.get(Paper, extraction.paper_id)
    if paper is None:
        return
    paper.pdf_word_count   = extraction.word_count
    paper.pdf_extracted_at = datetime.now(timezone.utc)
    session.flush()


# ── Stage 3: persist section segmentation ─────────────────────────────────────

def save_sections(session: Session, ps: PaperSections) -> None:
    existing = session.scalar(
        select(PaperSection).where(PaperSection.paper_id == ps.paper_id)
    )
    if existing:
        row = existing
    else:
        row = PaperSection(paper_id=ps.paper_id)
        session.add(row)

    for field in (
        "abstract", "introduction", "related_work", "methodology",
        "experiments", "results", "discussion", "conclusion",
        "limitations", "future_work", "full_text",
    ):
        setattr(row, field, getattr(ps, field, None))

    row.sections_found    = json.dumps(ps.sections_found)
    row.word_count        = ps.word_count
    row.segmenter_version = ps.segmenter_version
    session.flush()


# ── Stage 4: persist LLM analysis ─────────────────────────────────────────────

def save_analysis(
    session:  Session,
    paper_id: str,
    result:   AnalysisResult,
) -> None:
    if not result.analysis:
        _log_error(session, paper_id, "analyse",
                   "analysis_failed", result.error)
        return

    a = result.analysis

    # ── paper_analyses ────────────────────────────────────────
    existing = session.scalar(
        select(PaperAnalysisRecord).where(PaperAnalysisRecord.paper_id == paper_id)
    )
    rec = existing or PaperAnalysisRecord(paper_id=paper_id)
    if not existing:
        session.add(rec)

    rec.summary       = a.summary
    rec.advantages    = json.dumps(a.advantages)
    rec.limitations   = json.dumps([l for l in a.limitations])
    rec.future_work   = json.dumps(a.future_work)
    rec.use_cases     = json.dumps(a.use_cases)
    rec.model         = result.model
    rec.input_tokens  = result.input_tokens
    rec.output_tokens = result.output_tokens
    rec.cost_usd      = result.cost_usd
    rec.processing_ms = result.processing_ms

    # ── paper_datasets ────────────────────────────────────────
    for ds in a.datasets:
        exists = session.scalar(
            select(PaperDataset).where(
                PaperDataset.paper_id == paper_id,
                PaperDataset.name     == ds.name,
            )
        )
        if not exists:
            session.add(PaperDataset(
                paper_id=paper_id,
                name=ds.name,
                description=ds.description or None,
                task=ds.task or None,
            ))

    session.flush()


# ── Error log ─────────────────────────────────────────────────────────────────

def _log_error(
    session:    Session,
    paper_id:   str | None,
    stage:      str,
    error_type: str,
    error_msg:  str | None,
    retryable:  bool = True,
) -> None:
    session.add(PipelineError(
        paper_id=paper_id,
        stage=stage,
        error_type=error_type,
        error_msg=error_msg,
        retryable=retryable,
    ))
    session.flush()
