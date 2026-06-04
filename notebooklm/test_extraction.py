"""
End-to-end extraction test.

Loads the saved validation_results.json (produced by validate_prompts.py),
runs it through extractor → normalizer, commits to the DB, and prints
a full inspection of what was written.

Run:
    python -m notebooklm.test_extraction

Does NOT call NotebookLM — uses already-captured responses.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("DATABASE_URL", "sqlite:///research_platform.db")

logging.basicConfig(level=logging.INFO, format="%(levelname)-8s %(message)s")
log = logging.getLogger(__name__)

from sqlalchemy import select

from db.migrate import run_migrations
from db.models import (
    NotebookPaperExtract, Paper,
    PaperAnalysisRecord, PaperCategory, PaperDataset,
    PaperMethodology, PaperTechnique,
)
from db.session import get_session
from notebooklm.extractor import extract_all
from notebooklm.normalizer import normalize

DIV = "=" * 72
RESULTS_PATH = Path(__file__).parent / "validation_results.json"

# The 5 paper IDs used during validation (same order as validate_prompts.py)
PAPER_IDS = [
    "f16b682e-2f02-4627-9aa1-c593e350f5f5",   # Gorilla
    "d4de18d9-5979-4720-b263-5dc62355d8b1",   # Refusal
    "bb8f3d18-8ad0-49a6-809c-969c3cdb1c6e",   # ALPHALLM
    "2cb2b38a-abec-4910-bfb6-2b21f1528bbb",   # KV Cache
    "575654ff-6791-42ff-82ce-e394d39b5332",   # Multistep Distillation
]

# Fake notebook/synthesis IDs for this offline test
FAKE_NOTEBOOK_ID   = "ffffffff-0000-0000-0000-000000000000"
FAKE_SYNTHESIS_IDS = {
    "summary":    "ffffffff-0000-0000-0000-000000000001",
    "techniques": "ffffffff-0000-0000-0000-000000000002",
    "datasets":   "ffffffff-0000-0000-0000-000000000003",
    "categories": "ffffffff-0000-0000-0000-000000000004",
    "use_cases":  "ffffffff-0000-0000-0000-000000000005",
}


def main() -> None:
    run_migrations()

    print(DIV)
    print("Step 1 — Load saved validation responses")
    print(DIV)
    assert RESULTS_PATH.exists(), f"Run validate_prompts.py first: {RESULTS_PATH}"
    raw = json.loads(RESULTS_PATH.read_text())
    responses = {k: v["answer"] for k, v in raw.items()}
    print(f"  Loaded {len(responses)} query responses from {RESULTS_PATH.name}")
    for q, text in responses.items():
        print(f"    {q:12s} : {len(text)} chars")

    print()
    print(DIV)
    print("Step 2 — Build candidate list from DB")
    print(DIV)
    with get_session() as s:
        candidates = [(pid, s.get(Paper, pid).title) for pid in PAPER_IDS]
    for pid, title in candidates:
        print(f"  {pid[:8]}…  {title[:65]}")

    print()
    print(DIV)
    print("Step 3 — Extract (parse responses into typed objects)")
    print(DIV)
    result = extract_all(responses, candidates)

    print(f"  summaries    : {len(result.summaries)}")
    print(f"  techniques   : {len(result.techniques)}")
    print(f"  datasets     : {len(result.datasets)}")
    print(f"  categories   : {len(result.categories)}")
    print(f"  use_cases    : {len(result.use_cases)}")
    print(f"  unmatched    : {result.unmatched}")

    print()
    print("  Title match report:")
    all_parsed = (
        result.summaries + result.techniques +
        result.datasets  + result.categories + result.use_cases
    )
    seen = set()
    for p in all_parsed:
        if p.raw_title in seen:
            continue
        seen.add(p.raw_title)
        match_str = p.paper_id[:8] if p.paper_id else "NO MATCH"
        print(f"    {p.match_score:.2f}  {match_str}  {p.raw_title[:58]}")

    # Show parsed detail for 1 paper (Gorilla) to confirm field parsing
    gorilla_id = PAPER_IDS[0]
    g_sum = next((s for s in result.summaries  if s.paper_id == gorilla_id), None)
    g_tec = next((t for t in result.techniques if t.paper_id == gorilla_id), None)
    g_dat = next((d for d in result.datasets   if d.paper_id == gorilla_id), None)
    g_cat = next((c for c in result.categories if c.paper_id == gorilla_id), None)
    g_uc  = next((u for u in result.use_cases  if u.paper_id == gorilla_id), None)

    print()
    print("  Gorilla parsed fields:")
    if g_sum:
        print(f"    summary      : {g_sum.summary[:90]}")
        print(f"    advantages   : {g_sum.advantages}")
        print(f"    limitations  : {g_sum.limitations}")
        print(f"    future_work  : {g_sum.future_work}")
    if g_tec:
        print(f"    introduces   : {g_tec.introduces}")
        print(f"    uses         : {g_tec.uses}")
    if g_dat:
        print(f"    datasets     : {[(d.name, d.task[:40]) for d in g_dat.datasets]}")
    if g_cat:
        print(f"    categories   : {g_cat.categories}")
        print(f"    methodologies: {g_cat.methodologies}")
    if g_uc:
        print(f"    use_cases    : {g_uc.use_cases}")

    print()
    print(DIV)
    print("Step 4 — Normalize (write to DB)")
    print(DIV)

    # Clear any previous test runs for these papers so counts are clean
    with get_session() as s:
        for pid in PAPER_IDS:
            s.query(PaperAnalysisRecord).filter_by(paper_id=pid).delete()
            s.query(PaperTechnique).filter_by(paper_id=pid).delete()
            s.query(PaperDataset).filter_by(paper_id=pid).delete()
            s.query(PaperCategory).filter_by(paper_id=pid).delete()
            s.query(PaperMethodology).filter_by(paper_id=pid).delete()
            s.query(NotebookPaperExtract).filter_by(paper_id=pid).delete()
        s.commit()
    print("  Cleared previous test rows.")

    with get_session() as s:
        stats = normalize(
            session       = s,
            result        = result,
            notebook_id   = FAKE_NOTEBOOK_ID,
            synthesis_ids = FAKE_SYNTHESIS_IDS,
        )
        s.commit()

    print(f"  papers_processed     : {stats.papers_processed}")
    print(f"  analyses_written     : {stats.analyses_written}")
    print(f"  techniques_written   : {stats.techniques_written}")
    print(f"  datasets_written     : {stats.datasets_written}")
    print(f"  categories_written   : {stats.categories_written}")
    print(f"  methodologies_written: {stats.methodologies_written}")
    print(f"  extracts_written     : {stats.extracts_written}")
    print(f"  skipped_no_match     : {stats.skipped_no_match}")
    if stats.errors:
        print(f"  ERRORS: {stats.errors}")
    else:
        print(f"  errors               : none")

    print()
    print(DIV)
    print("Step 5 — Inspect DB rows written")
    print(DIV)
    with get_session() as s:
        for pid in PAPER_IDS:
            paper = s.get(Paper, pid)
            print(f"\n  {paper.title[:65]}")

            analysis = s.scalar(select(PaperAnalysisRecord).where(PaperAnalysisRecord.paper_id == pid))
            if analysis:
                print(f"    analysis.summary     : {(analysis.summary or '')[:80]}")
                print(f"    analysis.limitations : {analysis.limitations}")
                print(f"    analysis.future_work : {analysis.future_work}")
                print(f"    analysis.use_cases   : {analysis.use_cases}")
                print(f"    analysis.model       : {analysis.model}")
            else:
                print("    analysis             : MISSING")

            techs = s.scalars(select(PaperTechnique).where(PaperTechnique.paper_id == pid)).all()
            introduces = [t.name for t in techs if t.role == "introduces"]
            uses       = [t.name for t in techs if t.role == "uses"]
            print(f"    techniques.introduces: {introduces}")
            print(f"    techniques.uses      : {uses[:4]}")

            datasets = s.scalars(select(PaperDataset).where(PaperDataset.paper_id == pid)).all()
            print(f"    datasets             : {[(d.name, (d.task or '')[:35]) for d in datasets]}")

            cats = s.scalars(select(PaperCategory).where(PaperCategory.paper_id == pid)).all()
            print(f"    categories           : {[c.name for c in cats]}")

            meths = s.scalars(select(PaperMethodology).where(PaperMethodology.paper_id == pid)).all()
            print(f"    methodologies        : {[m.name for m in meths]}")

        extracts = s.scalars(
            select(NotebookPaperExtract).where(
                NotebookPaperExtract.notebook_id == FAKE_NOTEBOOK_ID
            )
        ).all()
        print(f"\n  notebook_paper_extracts written : {len(extracts)}")
        type_counts: dict[str, int] = {}
        for e in extracts:
            type_counts[e.extract_type] = type_counts.get(e.extract_type, 0) + 1
        for t, n in sorted(type_counts.items()):
            print(f"    {t:20s} : {n}")

    print()
    print(DIV)
    print("ALL STEPS COMPLETE")
    print(DIV)


if __name__ == "__main__":
    main()
