"""
api/routers/feature_map.py
──────────────────────────
Feature-to-Paper mapping API (Phase 1 — parallel).

Endpoints:
    POST /api/v1/feature-map/analyze  — document → features → paper matches
    POST /api/v1/feature-map/debug    — raw per-signal retrieval for one feature

Per-feature processing (retrieval → explain → recommend) runs in a
ThreadPoolExecutor so all N features are processed concurrently.  Each worker
thread owns its own SQLAlchemy session; the main thread commits persisted rows
after all workers complete.
"""

from __future__ import annotations

import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.deps import get_db
from db.models import FmFeature, FmPaperMatch, FmProject, FmRecommendation, FmReport
from db.session import SessionLocal
from feature_mapper.explain_and_recommend import explain_and_recommend
from feature_mapper.extractor import extract_features
from feature_mapper.models import (
    AnalyzeRequest,
    AnalyzeResponse,
    DebugRequest,
    DebugResponse,
    Feature,
    FeatureResult,
    ReportResponse,
)
from feature_mapper.parser import extract_title, parse
from feature_mapper.report import generate_report
from feature_mapper.retrieval import retrieve_for_debug, retrieve_for_feature
from llm.providers import AnthropicProvider

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/feature-map", tags=["FeatureMap"])

_MIN_WORDS = 50
_MAX_CHARS = 50_000
# Cap concurrent LLM calls to avoid hammering the proxy.
# Each branch makes 2 sequential calls (explain + recommend); 5 parallel branches
# means up to 10 in-flight calls — tune down if the proxy rate-limits.
_MAX_WORKERS = 5


@dataclass
class _FeatureTiming:
    """Per-feature latency breakdown used for benchmark logging."""
    position: int
    name: str
    retrieval_ms: int
    explain_recommend_ms: int  # merged single LLM call
    total_ms: int


def _process_feature(
    position: int,
    feature: Feature,
) -> tuple[FeatureResult, _FeatureTiming]:
    """
    Run retrieval → explain+recommend (single LLM call) for one feature.

    Opens its own SQLAlchemy session so it is safe to call from a worker
    thread.  The session is read-only (SELECT only); all writes happen on the
    main thread after this function returns.

    Raises on retrieval failure.  explain_and_recommend is fail-soft and
    never raises.
    """
    t_branch = time.monotonic()
    session = SessionLocal()
    try:
        t0 = time.monotonic()
        papers, cov_score, cov_tier = retrieve_for_feature(feature, session)
        retrieval_ms = int((time.monotonic() - t0) * 1000)

        t0 = time.monotonic()
        papers, recommendations = explain_and_recommend(feature, papers, session)
        explain_recommend_ms = int((time.monotonic() - t0) * 1000)

        result = FeatureResult(
            feature=feature,
            coverage_score=cov_score,
            coverage_tier=cov_tier,
            papers=papers,
            recommendations=recommendations,
        )
    finally:
        session.close()

    timing = _FeatureTiming(
        position=position,
        name=feature.name,
        retrieval_ms=retrieval_ms,
        explain_recommend_ms=explain_recommend_ms,
        total_ms=int((time.monotonic() - t_branch) * 1000),
    )
    return result, timing


def _json_or_none(values: list[str]) -> str | None:
    return json.dumps(values) if values else None


@router.post("/analyze", response_model=AnalyzeResponse)
def analyze(request: AnalyzeRequest, db: Session = Depends(get_db)) -> AnalyzeResponse:
    text = (request.text or "").strip()
    if not text:
        raise HTTPException(status_code=422, detail="text is required")
    if len(text.split()) < _MIN_WORDS:
        raise HTTPException(
            status_code=422,
            detail=f"text too short — provide at least {_MIN_WORDS} words",
        )
    if len(text) > _MAX_CHARS:
        raise HTTPException(
            status_code=413,
            detail=f"text too long — limit is {_MAX_CHARS} characters",
        )

    t_total = time.monotonic()

    # 1. Parse
    sections = parse(text)
    if not sections:
        raise HTTPException(status_code=422, detail="no analysable content found in text")
    title = extract_title(text)

    # 2. Extract features (1 LLM call)
    t0 = time.monotonic()
    try:
        features = extract_features(sections, db)
    except Exception as exc:  # noqa: BLE001
        log.exception("Feature extraction failed")
        raise HTTPException(status_code=502, detail=f"feature extraction failed: {exc}")
    extraction_ms = int((time.monotonic() - t0) * 1000)

    if not features:
        raise HTTPException(status_code=422, detail="no features could be extracted")

    log.info(
        "feature_mapper.extract: %d features in %dms",
        len(features), extraction_ms,
    )

    # 3. Process all features concurrently: retrieve → explain → recommend.
    #    Each worker opens its own read-only session.  Exceptions propagate;
    #    fail-soft is handled inside explain_feature / generate_recommendations.
    workers = min(len(features), _MAX_WORKERS)
    results_by_pos: dict[int, FeatureResult] = {}
    timings: list[_FeatureTiming] = []

    with ThreadPoolExecutor(max_workers=workers) as pool:
        future_to_pos = {
            pool.submit(_process_feature, i, f): i
            for i, f in enumerate(features)
        }
        for fut in as_completed(future_to_pos):
            pos = future_to_pos[fut]
            try:
                feature_result, timing = fut.result()
            except Exception as exc:
                log.exception("Feature processing failed at position %d", pos)
                raise HTTPException(
                    status_code=502,
                    detail=f"feature processing failed: {exc}",
                ) from exc
            results_by_pos[pos] = feature_result
            timings.append(timing)

    # Reassemble in original extraction order.
    feature_results: list[FeatureResult] = [
        results_by_pos[i] for i in range(len(features))
    ]

    duration_ms = int((time.monotonic() - t_total) * 1000)

    # ── Timing log ────────────────────────────────────────────────────────────
    timings.sort(key=lambda t: t.position)
    for tm in timings:
        log.info(
            "feature_mapper.feature[%d] %r  retrieval=%dms  explain_recommend=%dms  "
            "branch_total=%dms",
            tm.position, tm.name,
            tm.retrieval_ms, tm.explain_recommend_ms, tm.total_ms,
        )
    # Per-stage aggregates across all branches (useful for benchmarking).
    if timings:
        log.info(
            "feature_mapper.summary  n_features=%d  extract=%dms  "
            "max_retrieval=%dms  max_explain_recommend=%dms  "
            "max_branch=%dms  total_request=%dms  workers=%d",
            len(timings), extraction_ms,
            max(t.retrieval_ms for t in timings),
            max(t.explain_recommend_ms for t in timings),
            max(t.total_ms for t in timings),
            duration_ms, workers,
        )

    # 4. Persist (single transaction; nothing written if any step above raised)
    project = FmProject(
        title=title,
        input_text=text,
        feature_count=len(feature_results),
        total_duration_ms=duration_ms,
        llm_model=AnthropicProvider.MODEL,
    )
    db.add(project)
    db.flush()  # assign project.id

    for position, fr in enumerate(feature_results):
        feat_row = FmFeature(
            project_id=project.id,
            position=position,
            name=fr.feature.name,
            description=fr.feature.description,
            source_section=fr.feature.source_section,
            source_text=fr.feature.source_text,
            feature_type=fr.feature.feature_type,
            matched_techniques=_json_or_none(fr.feature.matched_techniques),
            matched_categories=_json_or_none(fr.feature.matched_categories),
            unrecognized_terms=_json_or_none(fr.feature.unrecognized_terms),
            coverage_score=fr.coverage_score,
            coverage_tier=fr.coverage_tier,
        )
        db.add(feat_row)
        db.flush()  # assign feat_row.id

        for p in fr.papers:
            db.add(
                FmPaperMatch(
                    feature_id=feat_row.id,
                    paper_id=p.paper_id,
                    rank=p.rank,
                    semantic_score=p.semantic_score,
                    technique_score=p.technique_score,
                    category_score=p.category_score,
                    rrf_score=p.rrf_score,
                    matched_techniques=_json_or_none(p.matched_techniques),
                    matched_categories=_json_or_none(p.matched_categories),
                    relevance_explanation=p.relevance_explanation,
                    similarity_points=_json_or_none(p.similarity_points),
                    difference_points=_json_or_none(p.difference_points),
                )
            )

        for rec in fr.recommendations:
            db.add(
                FmRecommendation(
                    feature_id=feat_row.id,
                    rec_type=rec.rec_type,
                    rank=rec.rank,
                    title=rec.title,
                    body=rec.body,
                    supporting_paper_ids=_json_or_none(rec.supporting_paper_ids),
                    priority_score=rec.priority_score,
                    evidence_count=rec.evidence_count,
                )
            )

    # get_db() commits on context exit.

    return AnalyzeResponse(
        project_id=project.id,
        title=title,
        feature_count=len(feature_results),
        total_duration_ms=duration_ms,
        features=feature_results,
    )


@router.post("/debug", response_model=DebugResponse)
def debug(request: DebugRequest, db: Session = Depends(get_db)) -> DebugResponse:
    """Inspect the three retrieval signals + fused ranking for a raw feature string."""
    feature_text = (request.feature or "").strip()
    if not feature_text:
        raise HTTPException(status_code=422, detail="feature is required")

    result = retrieve_for_debug(feature_text, db)
    return DebugResponse(**result)


# ── Research report (Phase 3) ─────────────────────────────────────────────────

def _report_to_response(project: FmProject, report: FmReport) -> ReportResponse:
    try:
        sections = json.loads(report.sections) if report.sections else {}
    except (json.JSONDecodeError, TypeError):
        sections = {}
    return ReportResponse(
        project_id=project.id,
        title=project.title,
        markdown=report.markdown_content,
        sections=sections,
        llm_model=report.llm_model,
        generation_ms=report.generation_ms,
        generated_at=report.updated_at.isoformat() if report.updated_at else None,
    )


@router.post("/projects/{project_id}/report", response_model=ReportResponse)
def create_report(project_id: str, db: Session = Depends(get_db)) -> ReportResponse:
    """Generate (or regenerate) the project-level research report from persisted data."""
    project = db.get(FmProject, project_id)
    if not project:
        raise HTTPException(status_code=404, detail=f"project {project_id} not found")

    result = generate_report(project_id, db)
    if result is None:
        raise HTTPException(status_code=422, detail="project has no features to report on")
    markdown, sections, model_used, ms = result

    report = db.execute(
        select(FmReport).where(FmReport.project_id == project_id)
    ).scalar_one_or_none()
    if report is None:
        report = FmReport(project_id=project_id)
        db.add(report)
    report.markdown_content = markdown
    report.sections = json.dumps(sections)
    report.llm_model = model_used
    report.generation_ms = ms
    db.flush()

    return _report_to_response(project, report)


@router.get("/projects/{project_id}/report", response_model=ReportResponse)
def get_report(project_id: str, db: Session = Depends(get_db)) -> ReportResponse:
    """Fetch the persisted research report for a project."""
    project = db.get(FmProject, project_id)
    if not project:
        raise HTTPException(status_code=404, detail=f"project {project_id} not found")
    report = db.execute(
        select(FmReport).where(FmReport.project_id == project_id)
    ).scalar_one_or_none()
    if report is None:
        raise HTTPException(
            status_code=404,
            detail="no report generated yet — POST to this endpoint to create one",
        )
    return _report_to_response(project, report)
