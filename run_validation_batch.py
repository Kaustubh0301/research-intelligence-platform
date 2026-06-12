"""
Validation batch runner — processes exactly 30 pre-selected papers through
the full production pipeline (no abstract-only shortcuts):

  Stage 1: PDF download
  Stage 2: PDF extraction
  Stage 3: PDF segmentation
  Stage A: NotebookLM assign (targeted: validation IDs only)
  Stage B: NotebookLM provision (new notebooks only)
  Stage C: NotebookLM upload   (limit=60; only validation papers are pending)
  Stage D: NotebookLM synthesize
  Stage E: NotebookLM extract + normalize (entities)
"""

from __future__ import annotations

import logging
import os

os.environ.setdefault("DATABASE_URL", "sqlite:///research_platform.db")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

from sqlalchemy import select

from db.migrate import run_migrations
from db.models import Conference, ConferenceEdition, Notebook, NotebookPaper, Paper, PaperSection
from db.session import get_session
import notebooklm.assigner as assigner
from notebooklm.pipeline import run_provision, run_upload, run_synthesize, run_extract

# ── The 30 validation paper IDs (from pick_validation_papers.py) ──────────────
VALIDATION_IDS = [
    "25c5fe6da1f947b7b511ffb23f2a5a04",
    "efdef973e16448e8a290ebd1dad2fbeb",
    "9b2d4d4fcc974357a26b0b82a89bd876",
    "fae4a819676f4b178b299dc1a925f262",
    "69801988f0e14ff39db1f536c39a59f9",
    "89b7edc72fde49219e061f7754060399",
    "5a17eed4e1b2479dbdfb7c19537154fa",
    "9e4aec9d1e6b4f4786e2016a5074fed5",
    "9ca6e4fab8854babbffe449f85a978c0",
    "c5b22948e30646449e0dedac27c2f048",
    "230b8f9c4b724e639152dfac7f66f71e",
    "79fe029b736c4b1a8e15416b3f6c4916",
    "76460e07687d44c3b7d63f7ff6c744fe",
    "fb6008401ffd4dcb8c5974ec3b343e65",
    "2801f99bf2244b92ac11918649fdd759",
    "e927487c1a4b420c925ea5079167133f",
    "62dee7f0c7484f7f8103fd4b388e29a7",
    "842ea9f3288845d3a82e74477337a126",
    "5a085e3416074feea79723651b892c40",
    "14e76e1ef57b492e9147a8795e78f230",
    "5a63b19cda5c4382ba2306a6dadf4c9d",
    "b773dc8c7051452f868a53c47b576571",
    "781cafb418ce4c8e9b4b41636c4ab343",
    "b7220693f9bc4a0182cddf5f625d0298",
    "0040bbe0dc2b4733b2a36eb321fcfcde",
    "81cdc0d6ef6c44ec8d88572a39d7e666",
    "733cb5cc64ad47e9a1beb91b2b6440f1",
    "8697cb702218433783d3e4f5d76507ab",
    "569f464905614e2b94ff19de02e40dd2",
    "d5d7b1de1c0346a3b91d2b929591cf4f",
]


# ── Stage 1-3: PDF pipeline ───────────────────────────────────────────────────

def run_pdf_stages() -> dict:
    from pdf_pipeline.downloader import download_pdf
    from pdf_pipeline.extractor import extract_text
    from pdf_pipeline.segmenter import segment, quality_report
    from pdf_pipeline.store import save_download, save_extraction, save_sections

    run_migrations()
    results = {"downloaded": 0, "extracted": 0, "segmented": 0, "failures": []}

    # Resolve paper metadata
    with get_session() as s:
        papers = []
        for pid in VALIDATION_IDS:
            p = s.get(Paper, pid)
            if p is None:
                log.warning("Paper %s not found", pid)
                continue
            conf_name = "Unknown"
            if p.conference_edition_id:
                ed = s.get(ConferenceEdition, p.conference_edition_id)
                if ed:
                    c = s.get(Conference, ed.conference_id)
                    conf_name = c.short_name if c else "Unknown"
            papers.append({
                "id": p.id, "title": p.title, "pdf_url": p.pdf_url,
                "openreview_id": p.openreview_id or p.id,
                "year": p.year, "pdf_local_path": p.pdf_local_path,
                "conference": conf_name,
            })

    log.info("=" * 60)
    log.info("PDF PIPELINE — %d papers", len(papers))
    log.info("=" * 60)

    for idx, p in enumerate(papers, 1):
        log.info("[%d/%d] %s", idx, len(papers), p["title"][:70])

        # Check if already fully processed (downloaded + segmented)
        already_segmented = False
        if p["pdf_local_path"]:
            with get_session() as s:
                sec = s.execute(
                    select(PaperSection).where(PaperSection.paper_id == p["id"])
                ).scalar_one_or_none()
                if sec is not None:
                    already_segmented = True

        if already_segmented:
            log.info("  Already processed (has PDF + sections) — skipping")
            results["downloaded"] += 1
            results["extracted"] += 1
            results["segmented"] += 1
            continue

        # Stage 1: Download
        dl = download_pdf(
            paper_id=p["id"], title=p["title"], pdf_url=p["pdf_url"],
            conference=p["conference"], year=p["year"], paper_key=p["openreview_id"],
        )
        with get_session() as s:
            save_download(s, dl)

        if not dl.success:
            log.warning("  ✗ Download failed: %s", dl.error_msg)
            results["failures"].append({
                "id": p["id"], "title": p["title"][:60],
                "stage": "download", "error": dl.error_msg,
            })
            continue
        results["downloaded"] += 1
        log.info("  ✓ Download OK: %.0fKB", dl.size_kb)

        # Stage 2: Extract
        try:
            extraction = extract_text(p["id"], dl.local_path)
            with get_session() as s:
                save_extraction(s, extraction)
            results["extracted"] += 1
            log.info("  ✓ Extract OK: %d words", extraction.word_count)
        except Exception as exc:
            log.warning("  ✗ Extract failed: %s", exc)
            results["failures"].append({
                "id": p["id"], "title": p["title"][:60],
                "stage": "extract", "error": str(exc),
            })
            continue

        # Stage 3: Segment
        try:
            ps = segment(p["id"], extraction.full_text)
            with get_session() as s:
                save_sections(s, ps)
            results["segmented"] += 1
            qr = quality_report(ps)
            log.info("  ✓ Segment OK: %d%% coverage, sections=%s",
                     qr["coverage_pct"], ps.sections_found)
        except Exception as exc:
            log.warning("  ✗ Segment failed: %s", exc)
            results["failures"].append({
                "id": p["id"], "title": p["title"][:60],
                "stage": "segment", "error": str(exc),
            })

    return results


# ── Stage A: Assign (targeted — validation IDs only) ─────────────────────────

def run_assign_targeted() -> int:
    """Assign only the 30 validation papers (not all unassigned papers)."""
    with get_session() as session:
        assignments = assigner.assign_papers(VALIDATION_IDS, session)
        session.commit()
    log.info("Stage A: created %d assignments for %d papers",
             len(assignments), len(VALIDATION_IDS))
    return len(assignments)


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    log.info("=" * 60)
    log.info("VALIDATION BATCH: %d papers", len(VALIDATION_IDS))
    log.info("=" * 60)

    # PDF stages
    pdf = run_pdf_stages()
    log.info("")
    log.info("PDF SUMMARY: downloaded=%d  extracted=%d  segmented=%d  failures=%d",
             pdf["downloaded"], pdf["extracted"], pdf["segmented"], len(pdf["failures"]))
    for f in pdf["failures"]:
        log.warning("  FAIL [%s] %s — %s", f["stage"], f["title"], f["error"])

    # NotebookLM stage A — targeted assign
    log.info("")
    log.info("Stage A — Assign (targeted)")
    assigned = run_assign_targeted()

    # Stage B — Provision any new notebooks
    log.info("")
    log.info("Stage B — Provision")
    provisioned = run_provision()
    log.info("  Provisioned %d new notebooks", provisioned)

    # Stage C — Upload (limit covers all pending rows from our 30 papers)
    log.info("")
    log.info("Stage C — Upload")
    uploaded, upload_errors = run_upload(limit=60)
    log.info("  Uploaded=%d  errors=%d", uploaded, upload_errors)

    # Stage D — Synthesize
    log.info("")
    log.info("Stage D — Synthesize")
    synth_count = run_synthesize()
    log.info("  Syntheses=%d", synth_count)

    # Stage E — Extract + Normalize
    log.info("")
    log.info("Stage E — Extract + Normalize")
    nb_extracted, norm_errors = run_extract()
    log.info("  Notebooks extracted=%d  norm_errors=%d", nb_extracted, norm_errors)

    log.info("")
    log.info("=" * 60)
    log.info("VALIDATION BATCH COMPLETE")
    log.info("  PDF: downloaded=%d extracted=%d segmented=%d failures=%d",
             pdf["downloaded"], pdf["extracted"], pdf["segmented"], len(pdf["failures"]))
    log.info("  NLM: assigned=%d provisioned=%d uploaded=%d synth=%d",
             assigned, provisioned, uploaded, synth_count)
    log.info("  NLM extract: notebooks=%d  errors=%d", nb_extracted, norm_errors)
    log.info("=" * 60)
