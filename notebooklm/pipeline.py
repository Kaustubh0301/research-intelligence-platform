"""
NotebookLM pipeline orchestrator — 5-stage batch analysis pipeline.

Stages:
  A — Assign:     keyword-score papers → notebook_papers rows
  B — Provision:  create NotebookLM notebooks → store notebooklm_id + url
  C — Upload:     push source documents to NotebookLM
  D — Synthesize: query each notebook with 5 prompts → notebook_syntheses rows
  E — Extract:    parse synthesis responses → paper_analyses, categories, etc.

Each stage is independently resumable by checking DB state before acting.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select, func

from db.models import (
    Notebook,
    NotebookPaper,
    NotebookSynthesis,
    Paper,
)
from db.session import get_session
from notebooklm import assigner, client, extractor, normalizer, source_prep

log = logging.getLogger(__name__)


# ── Validated query prompts (from validate_prompts.py, confirmed 100% compliant) ──

PROMPTS: dict[str, str] = {

    "summary": (
        "For each paper in this notebook, complete these fields.\n"
        "Use the EXACT paper title as it appears in the source.\n"
        "Format strictly as shown — no markdown, no bullets:\n\n"
        "PAPER: [exact title]\n"
        "SUMMARY: [2 sentences]\n"
        "ADVANTAGE: [key strength] | [key strength]\n"
        "LIMITATION: [key weakness] | [key weakness]\n"
        "FUTURE_WORK: [one direction] | [one direction]\n"
        "===\n\n"
        "Rules:\n"
        "- If a field has no content, write NONE.\n"
        "- Do not add any text before the first PAPER: line.\n"
        "- Do not add any text after the last ===.\n"
        "- Repeat the block for EVERY paper in the notebook."
    ),

    "techniques": (
        "For each paper in this notebook, list technical methods.\n"
        "Use the EXACT paper title as it appears in the source.\n"
        "Format strictly as shown — no markdown, no bullets:\n\n"
        "PAPER: [exact title]\n"
        "INTRODUCES: [new method or model name] | [name]\n"
        "USES: [existing method the paper builds on] | [name]\n"
        "===\n\n"
        "Rules:\n"
        "- INTRODUCES = novel contributions the paper presents.\n"
        "- USES = existing prior work methods the paper applies.\n"
        "- Use short technical names, not full sentences.\n"
        "- If none, write NONE.\n"
        "- Repeat the block for EVERY paper in the notebook."
    ),

    "datasets": (
        "For each paper in this notebook, list every dataset used in experiments.\n"
        "Use the EXACT paper title as it appears in the source.\n"
        "Format strictly as shown — one DATASET line per dataset:\n\n"
        "PAPER: [exact title]\n"
        "DATASET: [dataset name] :: [what task or metric it evaluates]\n"
        "===\n\n"
        "Rules:\n"
        "- Use the canonical dataset name (e.g. ImageNet, not 'the image benchmark').\n"
        "- If no datasets are mentioned, write: DATASET: NONE\n"
        "- Repeat the block for EVERY paper in the notebook."
    ),

    "categories": (
        "Assign research category tags and methodology labels to each paper.\n"
        "Use the EXACT paper title as it appears in the source.\n"
        "Format strictly as shown — no markdown, no bullets:\n\n"
        "PAPER: [exact title]\n"
        "CATEGORIES: [tag] | [tag]\n"
        "METHODOLOGY: [approach name] | [approach name]\n"
        "===\n\n"
        "Rules:\n"
        "- CATEGORIES must come ONLY from this list:\n"
        "  LLM | Vision | Multimodal | Agentic-AI | Safety | Efficiency |\n"
        "  NLP | RL | Theory | Graph | Biomedical | Robotics | Code |\n"
        "  Retrieval | Generative\n"
        "- METHODOLOGY = high-level methodological approach (e.g. 'Fine-tuning',\n"
        "  'Mechanistic interpretability', 'Knowledge distillation').\n"
        "- 1–3 values per field. If unsure write NONE.\n"
        "- Repeat the block for EVERY paper in the notebook."
    ),

    "use_cases": (
        "For each paper in this notebook, describe practical use cases.\n"
        "Use the EXACT paper title as it appears in the source.\n"
        "Format strictly as shown — no markdown, no bullets:\n\n"
        "PAPER: [exact title]\n"
        "USE_CASE: [concrete 1-sentence application]\n"
        "USE_CASE: [second application if applicable]\n"
        "===\n\n"
        "Rules:\n"
        "- USE_CASE lines describe real-world applications, not research contributions.\n"
        "- Write at least 1 and at most 3 USE_CASE lines per paper.\n"
        "- Do not repeat the method name — describe the downstream use.\n"
        "- Repeat the block for EVERY paper in the notebook."
    ),
}

_UPLOAD_BATCH_SIZE = 10
_UPLOAD_SLEEP_S   = 3
_QUERY_SLEEP_S    = 5


# ── Stats ─────────────────────────────────────────────────────────────────────

@dataclass
class PipelineStats:
    assigned:       int = 0
    provisioned:    int = 0
    uploaded:       int = 0
    upload_errors:  int = 0
    skipped_upload: int = 0
    synthesized:    int = 0
    extracted:      int = 0
    norm_errors:    int = 0
    errors:         list[str] = field(default_factory=list)

    def __str__(self) -> str:
        lines = [
            "Pipeline results:",
            f"  Stage A — assigned:       {self.assigned}",
            f"  Stage B — provisioned:    {self.provisioned}",
            f"  Stage C — uploaded:       {self.uploaded}  "
            f"(errors: {self.upload_errors}, skipped: {self.skipped_upload})",
            f"  Stage D — synthesized:    {self.synthesized}",
            f"  Stage E — extracted:      {self.extracted}  "
            f"(norm errors: {self.norm_errors})",
        ]
        if self.errors:
            lines.append(f"  Errors ({len(self.errors)}):")
            for e in self.errors[:10]:
                lines.append(f"    - {e}")
        return "\n".join(lines)


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ── Stage A — Assign ──────────────────────────────────────────────────────────

def run_assign(force: bool = False) -> int:
    """
    Find papers not yet in notebook_papers and run keyword assignment.
    Returns count of new Assignment objects created.
    """
    with get_session() as session:
        if force:
            unassigned_ids = session.scalars(select(Paper.id)).all()
        else:
            unassigned_ids = session.scalars(
                select(Paper.id)
                .outerjoin(NotebookPaper, NotebookPaper.paper_id == Paper.id)
                .where(NotebookPaper.paper_id == None)
            ).all()

        if not unassigned_ids:
            log.info("Stage A: no unassigned papers found")
            return 0

        log.info("Stage A: assigning %d papers", len(unassigned_ids))
        assignments = assigner.assign_papers(list(unassigned_ids), session)
        session.commit()
        log.info("Stage A: created %d assignments", len(assignments))
        return len(assignments)


# ── Stage B — Provision ───────────────────────────────────────────────────────

def run_provision(
    notebook_id: Optional[str] = None,
    force: bool = False,
) -> int:
    """
    Create NotebookLM notebooks for DB Notebook rows that lack a notebooklm_id.
    Stores both notebooklm_id (API identifier) and notebooklm_url (browser URL).
    Returns count of notebooks provisioned.
    """
    provisioned = 0

    with get_session() as session:
        q = select(Notebook).where(Notebook.status == "active")
        if not force:
            q = q.where(Notebook.notebooklm_id == None)
        if notebook_id:
            q = q.where(Notebook.id == notebook_id)

        notebooks = session.scalars(q).all()
        if not notebooks:
            log.info("Stage B: no notebooks need provisioning")
            return 0

        log.info("Stage B: provisioning %d notebooks", len(notebooks))
        for nb in notebooks:
            try:
                info = client.create_notebook(nb.topic_name)
                nb.notebooklm_id  = info.notebook_id
                nb.notebooklm_url = info.url
                session.commit()
                provisioned += 1
                log.info(
                    "Stage B: provisioned %s → nlm_id=%s",
                    nb.topic_slug, info.notebook_id,
                )
            except client.ClientError as exc:
                log.error("Stage B: failed to provision %s: %s", nb.topic_slug, exc)
                session.rollback()

    return provisioned


# ── Stage C — Upload ──────────────────────────────────────────────────────────

def run_upload(
    limit: int = 10,
    notebook_id: Optional[str] = None,
    force: bool = False,
) -> tuple[int, int]:
    """
    Upload pending source documents to NotebookLM.
    Processes at most `limit` rows; sleeps _UPLOAD_SLEEP_S every _UPLOAD_BATCH_SIZE.
    Returns (uploaded, errors).
    """
    uploaded = 0
    errors   = 0

    with get_session() as session:
        q = (
            select(NotebookPaper)
            .join(Notebook, Notebook.id == NotebookPaper.notebook_id)
            .where(
                Notebook.notebooklm_id != None,
            )
        )
        if not force:
            q = q.where(NotebookPaper.source_status == "pending")
        if notebook_id:
            q = q.where(NotebookPaper.notebook_id == notebook_id)
        q = q.limit(limit)

        rows = session.scalars(q).all()
        if not rows:
            log.info("Stage C: no pending uploads")
            return 0, 0

        log.info("Stage C: uploading %d sources (limit=%d)", len(rows), limit)

        for i, np_row in enumerate(rows):
            nb = session.get(Notebook, np_row.notebook_id)
            paper = session.get(Paper, np_row.paper_id)
            paper_title = paper.title if paper else np_row.paper_id

            # Mark attempt before network call so stale attempts are detectable on resume
            np_row.upload_attempted_at = _now()
            session.flush()

            doc = source_prep.build_source(session, np_row.paper_id)
            if doc is None:
                log.error("Stage C: build_source returned None for paper %s", np_row.paper_id)
                np_row.source_status = "error"
                session.commit()
                errors += 1
                continue

            title = doc.title[:80]
            try:
                ok = client.add_source(nb.notebooklm_id, doc.text, title)
                if ok:
                    # Preserve abstract_only distinction
                    np_row.source_status = (
                        "abstract_only" if doc.mode == "abstract_only" else "uploaded"
                    )
                    np_row.upload_completed_at = _now()
                    uploaded += 1
                    log.info(
                        "Stage C: uploaded %s → notebook %s (mode=%s)",
                        paper_title[:50], nb.topic_slug, doc.mode,
                    )
                else:
                    np_row.source_status = "error"
                    errors += 1
                    log.warning("Stage C: add_source returned False for %s", paper_title[:50])
            except client.ClientError as exc:
                np_row.source_status = "error"
                errors += 1
                log.error("Stage C: upload failed for %s: %s", paper_title[:50], exc)

            session.commit()

            # Throttle between batches
            if (i + 1) % _UPLOAD_BATCH_SIZE == 0 and (i + 1) < len(rows):
                log.info("Stage C: batch complete, sleeping %ds", _UPLOAD_SLEEP_S)
                time.sleep(_UPLOAD_SLEEP_S)

    return uploaded, errors


# ── Stage D — Synthesize ──────────────────────────────────────────────────────

def run_synthesize(
    notebook_id: Optional[str] = None,
    force: bool = False,
) -> int:
    """
    For each notebook where all sources are uploaded, send 5 query prompts
    and store responses as NotebookSynthesis rows.
    Returns count of synthesis rows written.
    """
    synthesized = 0

    with get_session() as session:
        # Find notebooks that have uploads and no remaining pending rows
        q = select(Notebook).where(
            Notebook.notebooklm_id != None,
            Notebook.status == "active",
        )
        if notebook_id:
            q = q.where(Notebook.id == notebook_id)

        for nb in session.scalars(q).all():
            # Check readiness: must have at least one uploaded/abstract_only row
            # and zero pending rows
            pending_count = session.scalar(
                select(func.count())
                .select_from(NotebookPaper)
                .where(
                    NotebookPaper.notebook_id   == nb.id,
                    NotebookPaper.source_status == "pending",
                )
            )
            uploaded_count = session.scalar(
                select(func.count())
                .select_from(NotebookPaper)
                .where(
                    NotebookPaper.notebook_id == nb.id,
                    NotebookPaper.source_status.in_(["uploaded", "abstract_only"]),
                )
            )
            if pending_count > 0 or uploaded_count == 0:
                log.info(
                    "Stage D: skipping notebook %s (pending=%d, uploaded=%d)",
                    nb.topic_slug, pending_count, uploaded_count,
                )
                continue

            log.info("Stage D: querying notebook %s (%d sources)", nb.topic_slug, uploaded_count)

            for key, prompt_text in PROMPTS.items():
                # Skip if synthesis row already exists (UniqueConstraint also guards this)
                existing = session.scalar(
                    select(NotebookSynthesis).where(
                        NotebookSynthesis.notebook_id    == nb.id,
                        NotebookSynthesis.synthesis_type == "query_response",
                        NotebookSynthesis.query_prompt   == key,
                    )
                )
                if existing and not force:
                    log.debug("Stage D: synthesis %s/%s already exists, skipping", nb.topic_slug, key)
                    continue

                try:
                    result = client.query_notebook(nb.notebooklm_id, prompt_text)
                    row = NotebookSynthesis(
                        notebook_id    = nb.id,
                        synthesis_type = "query_response",
                        query_prompt   = key,
                        content        = result.answer,
                        word_count     = len(result.answer.split()),
                        normalized     = False,
                    )
                    if existing and force:
                        # Overwrite: delete old row first (UniqueConstraint prevents duplicate)
                        session.delete(existing)
                        session.flush()
                    session.add(row)
                    session.commit()
                    synthesized += 1
                    log.info("Stage D: wrote synthesis %s/%s (%d words)", nb.topic_slug, key, row.word_count)
                except client.ClientError as exc:
                    log.error("Stage D: query failed for %s/%s: %s", nb.topic_slug, key, exc)
                    session.rollback()

                time.sleep(_QUERY_SLEEP_S)

    return synthesized


# ── Stage E — Extract ─────────────────────────────────────────────────────────

def run_extract(
    notebook_id: Optional[str] = None,
    force: bool = False,
) -> tuple[int, int]:
    """
    For each notebook with un-normalized synthesis rows, parse all 5 responses
    and write structured data to paper_analyses, paper_techniques, etc.
    Returns (notebooks_extracted, norm_errors).
    """
    extracted   = 0
    norm_errors = 0

    with get_session() as session:
        # Find notebooks that have at least one un-normalized synthesis row
        q = (
            select(Notebook)
            .join(NotebookSynthesis, NotebookSynthesis.notebook_id == Notebook.id)
            .where(NotebookSynthesis.normalized == False)
            .distinct()
        )
        if notebook_id:
            q = q.where(Notebook.id == notebook_id)

        notebooks = session.scalars(q).all()
        if not notebooks:
            log.info("Stage E: no un-normalized synthesis rows found")
            return 0, 0

        log.info("Stage E: extracting from %d notebooks", len(notebooks))

        for nb in notebooks:
            synth_rows = session.scalars(
                select(NotebookSynthesis).where(NotebookSynthesis.notebook_id == nb.id)
            ).all()

            # Build inputs for extract_all
            responses     = {r.query_prompt: r.content  for r in synth_rows if r.query_prompt}
            synthesis_ids = {r.query_prompt: r.id        for r in synth_rows if r.query_prompt}

            # Build title candidates from notebook_papers for fuzzy title matching
            np_rows = session.scalars(
                select(NotebookPaper).where(NotebookPaper.notebook_id == nb.id)
            ).all()
            candidates: list[tuple[str, str]] = []
            for np_row in np_rows:
                paper = session.get(Paper, np_row.paper_id)
                if paper:
                    candidates.append((paper.id, paper.title))

            if not candidates:
                log.warning("Stage E: notebook %s has no papers in DB, skipping", nb.topic_slug)
                continue

            if not responses:
                log.warning("Stage E: notebook %s has no synthesis content, skipping", nb.topic_slug)
                continue

            log.info(
                "Stage E: extracting notebook %s (%d responses, %d candidates)",
                nb.topic_slug, len(responses), len(candidates),
            )

            try:
                result = extractor.extract_all(responses, candidates)

                if result.unmatched:
                    log.warning(
                        "Stage E: %d unmatched titles in %s: %s",
                        len(result.unmatched), nb.topic_slug,
                        [t[:40] for t in result.unmatched[:3]],
                    )

                norm_stats = normalizer.normalize(session, result, nb.id, synthesis_ids)

                # Mark all synthesis rows for this notebook as normalized
                for r in synth_rows:
                    r.normalized = True

                session.commit()
                extracted += 1

                log.info(
                    "Stage E: notebook %s done — analyses=%d techniques=%d "
                    "datasets=%d categories=%d methodologies=%d extracts=%d",
                    nb.topic_slug,
                    norm_stats.analyses_written,
                    norm_stats.techniques_written,
                    norm_stats.datasets_written,
                    norm_stats.categories_written,
                    norm_stats.methodologies_written,
                    norm_stats.extracts_written,
                )

                if norm_stats.errors:
                    norm_errors += len(norm_stats.errors)
                    for e in norm_stats.errors:
                        log.error("Stage E normalizer error: %s", e)

            except Exception as exc:
                log.error("Stage E: extraction failed for notebook %s: %s", nb.topic_slug, exc)
                session.rollback()
                norm_errors += 1

    return extracted, norm_errors


# ── Orchestrator ──────────────────────────────────────────────────────────────

_ALL_STAGES = ["assign", "provision", "upload", "synthesize", "extract"]


def run(
    limit: int = 10,
    notebook_id: Optional[str] = None,
    force: bool = False,
    stages: Optional[list[str]] = None,
) -> PipelineStats:
    """
    Run the full NotebookLM pipeline (or a subset of stages).

    Args:
        limit:       Max upload operations in Stage C per invocation.
        notebook_id: Restrict all stages to one DB notebook UUID.
        force:       Re-run stages even if already marked complete.
        stages:      List of stage names to run (default: all 5).

    Returns PipelineStats with counts for each stage.
    """
    active = set(stages or _ALL_STAGES)
    stats  = PipelineStats()

    # Auth check before any network calls
    if active & {"provision", "upload", "synthesize"}:
        if not client.health_check():
            msg = "NotebookLM auth check failed — run `nlm login` to re-authenticate"
            log.error(msg)
            stats.errors.append(msg)
            return stats

    if "assign" in active:
        log.info("=== Stage A: Assign ===")
        stats.assigned = run_assign(force=force)

    if "provision" in active:
        log.info("=== Stage B: Provision ===")
        stats.provisioned = run_provision(notebook_id=notebook_id, force=force)

    if "upload" in active:
        log.info("=== Stage C: Upload (limit=%d) ===", limit)
        stats.uploaded, stats.upload_errors = run_upload(
            limit=limit, notebook_id=notebook_id, force=force,
        )

    if "synthesize" in active:
        log.info("=== Stage D: Synthesize ===")
        stats.synthesized = run_synthesize(notebook_id=notebook_id, force=force)

    if "extract" in active:
        log.info("=== Stage E: Extract ===")
        stats.extracted, stats.norm_errors = run_extract(
            notebook_id=notebook_id, force=force,
        )

    return stats
