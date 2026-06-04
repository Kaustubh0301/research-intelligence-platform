"""
PDF Pipeline Orchestrator
=========================
Runs all four stages for a list of papers and emits a full
measurement report: timing, token usage, extraction quality, cost.
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy import select

from db.migrate import run_migrations
from db.models  import Base, Conference, ConferenceEdition, Paper, PaperSection, PaperAnalysisRecord
from db.session import engine, get_session
from pdf_pipeline.analyser   import DEFAULT_MODEL, analyse_with_retry
from pdf_pipeline.downloader import DownloadResult, download_pdf
from pdf_pipeline.extractor  import extract_text
from pdf_pipeline.segmenter  import PaperSections, build_llm_context, quality_report, segment
from pdf_pipeline.store      import save_analysis, save_download, save_extraction, save_sections

log = logging.getLogger(__name__)


# ── Per-paper measurement record ──────────────────────────────────────────────

@dataclass
class PaperMeasurement:
    paper_id:        str
    title:           str
    citation_count:  int

    # Stage 1
    download_ok:     bool  = False
    download_s:      float = 0.0
    pdf_kb:          int   = 0

    # Stage 2
    extract_ok:      bool  = False
    extract_ms:      int   = 0
    pdf_words:       int   = 0

    # Stage 3
    segment_ok:      bool  = False
    sections_found:  list  = field(default_factory=list)
    coverage_pct:    int   = 0
    llm_context_words: int = 0

    # Stage 4
    analyse_ok:      bool  = False
    analyse_ms:      int   = 0
    input_tokens:    int   = 0
    output_tokens:   int   = 0
    cost_usd:        float = 0.0
    error:           str | None = None


# ── Pipeline ──────────────────────────────────────────────────────────────────

def run(
    limit:      int  = 10,
    model:      str  = DEFAULT_MODEL,
    skip_llm:   bool = False,
    force:      bool = False,
) -> list[PaperMeasurement]:
    """
    Run the full pipeline on `limit` papers ordered by citation count (desc).

    Args:
        limit:    number of papers to process
        model:    Gemini model name for stage 4
        skip_llm: run stages 1-3 only (useful when no API key is available)
        force:    re-process papers that already have a pdf_local_path
    """
    run_migrations()   # create missing tables + add new columns

    # ── Select papers ─────────────────────────────────────────
    with get_session() as s:
        q = select(Paper).order_by(Paper.citation_count.desc())
        if not force:
            q = q.where(Paper.pdf_local_path.is_(None))
        q = q.limit(limit)
        rows = s.scalars(q).all()

        # Resolve conference short_name for each paper (for PDF directory naming)
        edition_cache: dict[str, str] = {}   # edition_id → short_name
        for p in rows:
            eid = p.conference_edition_id
            if eid and eid not in edition_cache:
                ed = s.get(ConferenceEdition, eid)
                if ed:
                    conf = s.get(Conference, ed.conference_id)
                    edition_cache[eid] = conf.short_name if conf else "Unknown"

        papers = [
            {
                "id":            p.id,
                "title":         p.title,
                "pdf_url":       p.pdf_url,
                "openreview_id": p.openreview_id or p.id,
                "year":          p.year,
                "citation_count":p.citation_count,
                "pdf_local_path":p.pdf_local_path,
                "conference":    edition_cache.get(p.conference_edition_id or "", "Unknown"),
            }
            for p in rows
        ]

    if not papers:
        log.info("No papers to process (all already done). Use --force to reprocess.")
        return []

    log.info("Processing %d papers through 4-stage PDF pipeline", len(papers))
    measurements: list[PaperMeasurement] = []

    for idx, p in enumerate(papers, 1):
        log.info("─" * 60)
        log.info("[%d/%d] %s", idx, len(papers), p["title"][:65])
        m = PaperMeasurement(
            paper_id=p["id"], title=p["title"],
            citation_count=p["citation_count"],
        )

        # ── Stage 1: Download ──────────────────────────────────
        log.info("  Stage 1 — Download")
        dl_result: DownloadResult = download_pdf(
            paper_id   = p["id"],
            title      = p["title"],
            pdf_url    = p["pdf_url"],
            conference = p["conference"],
            year       = p["year"],
            paper_key  = p["openreview_id"],
        )
        m.download_ok = dl_result.success
        m.download_s  = dl_result.elapsed_s
        m.pdf_kb      = dl_result.size_kb

        with get_session() as s:
            save_download(s, dl_result)

        if not dl_result.success:
            log.warning("  ✗ Download failed: %s", dl_result.error_msg)
            m.error = f"download: {dl_result.error_msg}"
            measurements.append(m)
            continue
        log.info("  ✓ %.0fKB in %.1fs", m.pdf_kb, m.download_s)

        pdf_path = dl_result.local_path

        # ── Stage 2: Extract ───────────────────────────────────
        log.info("  Stage 2 — Extract")
        try:
            extraction = extract_text(p["id"], pdf_path)
            m.extract_ok = True
            m.extract_ms = extraction.extraction_ms
            m.pdf_words  = extraction.word_count
            log.info("  ✓ %d words in %dms", m.pdf_words, m.extract_ms)
        except Exception as exc:
            log.warning("  ✗ Extraction failed: %s", exc)
            m.error = f"extract: {exc}"
            measurements.append(m)
            continue

        with get_session() as s:
            save_extraction(s, extraction)

        # ── Stage 3: Segment ───────────────────────────────────
        log.info("  Stage 3 — Segment")
        ps = segment(p["id"], extraction.full_text)
        qr = quality_report(ps)
        m.segment_ok         = True
        m.sections_found     = qr["sections_found"]
        m.coverage_pct       = qr["coverage_pct"]

        context              = build_llm_context(ps)
        m.llm_context_words  = len(context.split())

        log.info("  ✓ Sections: %s  (coverage %d%%)",
                 ", ".join(ps.sections_found), m.coverage_pct)
        log.info("    LLM context: %d words", m.llm_context_words)

        with get_session() as s:
            save_sections(s, ps)

        if skip_llm:
            log.info("  Stage 4 — Skipped (--skip-llm)")
            measurements.append(m)
            continue

        # ── Stage 4: Analyse ───────────────────────────────────
        log.info("  Stage 4 — Analyse (%s)", model)
        result = analyse_with_retry(title=p["title"], context=context, model=model)
        m.analyse_ms   = result.processing_ms
        m.input_tokens = result.input_tokens
        m.output_tokens= result.output_tokens
        m.cost_usd     = result.cost_usd

        if result.analysis:
            m.analyse_ok = True
            log.info(
                "  ✓ %dms | in=%d out=%d | $%.5f",
                m.analyse_ms, m.input_tokens, m.output_tokens, m.cost_usd,
            )
            log.info("    summary: %s", result.analysis.summary[:80])
        else:
            m.error = f"analyse: {result.error}"
            log.warning("  ✗ Analysis failed: %s", result.error)

        with get_session() as s:
            save_analysis(s, p["id"], result)

        measurements.append(m)

    return measurements


# ── Segment-only re-run ───────────────────────────────────────────────────────

def run_segment_only(
    limit: int = 10,
    force: bool = False,
) -> list[PaperMeasurement]:
    """
    Re-run stage 3 only (segmenter) on papers that already have full_text stored.

    Reads full_text from paper_sections, re-segments with the current segmenter
    version, and writes the result back.  Without --force, skips papers whose
    paper_sections row already has segmenter_version == SEGMENTER_VERSION.
    """
    from pdf_pipeline.segmenter import SEGMENTER_VERSION

    run_migrations()

    with get_session() as s:
        q = (
            select(Paper, PaperSection)
            .join(PaperSection, PaperSection.paper_id == Paper.id)
            .order_by(Paper.citation_count.desc())
        )
        if not force:
            q = q.where(
                (PaperSection.segmenter_version != SEGMENTER_VERSION)
                | PaperSection.segmenter_version.is_(None)
            )
        q = q.limit(limit)
        rows = s.execute(q).all()

        paper_data = [
            {
                "id":            p.id,
                "title":         p.title,
                "citation_count":p.citation_count,
                "full_text":     ps.full_text,
                "old_version":   ps.segmenter_version,
            }
            for p, ps in rows
        ]

    if not paper_data:
        log.info("All papers already at segmenter version %s. Use --force to re-run.", SEGMENTER_VERSION)
        return []

    log.info(
        "Re-segmenting %d papers with %s (--force=%s)",
        len(paper_data), SEGMENTER_VERSION, force,
    )
    measurements: list[PaperMeasurement] = []

    for idx, p in enumerate(paper_data, 1):
        log.info("─" * 60)
        log.info("[%d/%d] %s  (was %s)", idx, len(paper_data), p["title"][:55], p["old_version"])

        m = PaperMeasurement(
            paper_id=p["id"],
            title=p["title"],
            citation_count=p["citation_count"],
            download_ok=True,
            extract_ok=True,
        )

        if not p["full_text"]:
            log.warning("  ✗ No full_text in DB — run full pipeline first")
            m.error = "segment: no full_text stored"
            measurements.append(m)
            continue

        ps = segment(p["id"], p["full_text"])
        qr = quality_report(ps)
        m.segment_ok        = True
        m.sections_found    = qr["sections_found"]
        m.coverage_pct      = qr["coverage_pct"]
        m.llm_context_words = len(build_llm_context(ps).split())

        log.info(
            "  ✓ Sections: %s  (coverage %d%%)",
            ", ".join(ps.sections_found), m.coverage_pct,
        )

        with get_session() as s:
            save_sections(s, ps)

        measurements.append(m)

    return measurements


# ── Measurement report ────────────────────────────────────────────────────────

def print_report(measurements: list[PaperMeasurement]) -> None:
    if not measurements:
        print("No measurements to report.")
        return

    DIV = "─" * 64

    ok_dl  = [m for m in measurements if m.download_ok]
    ok_ext = [m for m in measurements if m.extract_ok]
    ok_seg = [m for m in measurements if m.segment_ok]
    ok_llm = [m for m in measurements if m.analyse_ok]

    print(f"\n{DIV}")
    print(" PDF Pipeline — Measurement Report")
    print(DIV)
    print(f"  Papers attempted          : {len(measurements)}")
    print(f"  Stage 1 ✓ Download        : {len(ok_dl)}/{len(measurements)}")
    print(f"  Stage 2 ✓ Extract         : {len(ok_ext)}/{len(measurements)}")
    print(f"  Stage 3 ✓ Segment         : {len(ok_seg)}/{len(measurements)}")
    print(f"  Stage 4 ✓ Analyse (LLM)   : {len(ok_llm)}/{len(measurements)}")

    if ok_dl:
        avg_kb = sum(m.pdf_kb for m in ok_dl) / len(ok_dl)
        avg_dl = sum(m.download_s for m in ok_dl) / len(ok_dl)
        print(f"\n  Avg PDF size              : {avg_kb:.0f} KB")
        print(f"  Avg download time         : {avg_dl:.1f}s")

    if ok_ext:
        avg_words = sum(m.pdf_words for m in ok_ext) / len(ok_ext)
        avg_ms    = sum(m.extract_ms for m in ok_ext) / len(ok_ext)
        print(f"  Avg extracted words       : {avg_words:.0f}")
        print(f"  Avg extraction time       : {avg_ms:.0f}ms")

    if ok_seg:
        avg_cov   = sum(m.coverage_pct for m in ok_seg) / len(ok_seg)
        avg_ctx   = sum(m.llm_context_words for m in ok_seg) / len(ok_seg)
        all_secs  = [s for m in ok_seg for s in m.sections_found]
        from collections import Counter
        sec_freq  = Counter(all_secs).most_common(10)
        print(f"  Avg section coverage      : {avg_cov:.0f}%")
        print(f"  Avg LLM context words     : {avg_ctx:.0f}")
        print(f"  Section frequency:")
        for sec, cnt in sec_freq:
            bar = "█" * cnt
            print(f"    {sec:<20} {bar} ({cnt})")

    if ok_llm:
        total_in    = sum(m.input_tokens  for m in ok_llm)
        total_out   = sum(m.output_tokens for m in ok_llm)
        total_cost  = sum(m.cost_usd      for m in ok_llm)
        avg_ms      = sum(m.analyse_ms    for m in ok_llm) / len(ok_llm)
        print(f"\n  Total input tokens        : {total_in:,}")
        print(f"  Total output tokens       : {total_out:,}")
        print(f"  Total LLM cost            : ${total_cost:.5f}")
        print(f"  Avg LLM latency           : {avg_ms:.0f}ms")
        print(f"  Cost per paper            : ${total_cost/len(ok_llm):.5f}")
        proj_1000 = total_cost / len(ok_llm) * 1000
        proj_5000 = total_cost / len(ok_llm) * 5000
        print(f"  Projected cost (1k papers): ${proj_1000:.3f}")
        print(f"  Projected cost (5k papers): ${proj_5000:.3f}")

    if any(m.error for m in measurements):
        print(f"\n  Errors:")
        for m in measurements:
            if m.error:
                print(f"    ✗ {m.title[:50]}: {m.error}")

    print(DIV)
    print(" Per-paper breakdown")
    print(DIV)
    header = f"  {'#':>2}  {'Citations':>9}  {'KB':>5}  {'Words':>6}  {'Cov%':>5}  {'CtxW':>5}  {'Tok↑':>6}  {'Cost$':>7}  Title"
    print(header)
    for i, m in enumerate(measurements, 1):
        print(
            f"  {i:>2}  {m.citation_count:>9}  {m.pdf_kb:>5}  {m.pdf_words:>6}  "
            f"{m.coverage_pct:>4}%  {m.llm_context_words:>5}  "
            f"{m.input_tokens:>6}  ${m.cost_usd:.5f}  {m.title[:38]}"
        )
    print(DIV)
