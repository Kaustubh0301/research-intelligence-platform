"""
End-to-end smoke test: DB → source_prep → assign → create notebook → upload → query.

Not part of the production pipeline. Run manually:
    python -m notebooklm.smoke_test
"""

from __future__ import annotations

import logging
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("DATABASE_URL", "sqlite:///research_platform.db")

logging.basicConfig(level=logging.INFO, format="%(levelname)-8s %(message)s")
log = logging.getLogger(__name__)

from db.session import get_session
from notebooklm.assigner import assign_papers
from notebooklm.client import (
    add_source, create_notebook, delete_notebook,
    health_check, query_notebook,
)
from notebooklm.source_prep import build_source

PAPER_IDS = [
    "f16b682e-2f02-4627-9aa1-c593e350f5f5",   # Gorilla         (1,248 citations)
    "d4de18d9-5979-4720-b263-5dc62355d8b1",   # Refusal         (716)
    "bb8f3d18-8ad0-49a6-809c-969c3cdb1c6e",   # ALPHALLM        (150)
]

QUERY = (
    "For each paper in this notebook, provide a 2-sentence summary. "
    "Then state the single most important technical contribution. "
    "Format exactly as:\n"
    "PAPER: [exact paper title]\n"
    "SUMMARY: [2 sentences]\n"
    "CONTRIBUTION: [1 sentence]\n"
    "---\n"
    "Repeat this block for every paper."
)

DIV = "=" * 70


def main() -> None:
    print(DIV)
    print("STEP 0 — Health check")
    print(DIV)
    if not health_check():
        log.error("Auth failed. Run: nlm login")
        sys.exit(1)
    print("  OK — authenticated\n")

    # ── Step 1: source_prep ───────────────────────────────────────────────────
    print(DIV)
    print("STEP 1 — Build source documents from DB")
    print(DIV)
    docs = []
    with get_session() as s:
        for pid in PAPER_IDS:
            doc = build_source(s, pid)
            if doc is None:
                log.error("Paper %s not found in DB", pid)
                sys.exit(1)
            docs.append(doc)
            print(f"  {doc.title[:58]:58s}")
            print(f"    mode={doc.mode}  sections={doc.sections_included}  chars={doc.char_count:,}")
    print()

    # ── Step 2: assign (dry-run, no commit needed for smoke test) ─────────────
    print(DIV)
    print("STEP 2 — Keyword assignment (dry-run, no DB write)")
    print(DIV)
    with get_session() as s:
        # Clear any existing assignments for these papers so we can preview
        from sqlalchemy import select, delete
        from db.models import NotebookPaper
        existing = s.execute(
            select(NotebookPaper).where(NotebookPaper.paper_id.in_(PAPER_IDS))
        ).scalars().all()
        if existing:
            print(f"  {len(existing)} existing assignment(s) found — showing topic for first paper only")
        else:
            from notebooklm.assigner import assign_paper
            from db.models import Paper
            for pid in PAPER_IDS:
                paper = s.get(Paper, pid)
                from notebooklm.assigner import _TOPICS, _score
                text = f"{paper.title} {paper.abstract or ''}"
                scores = sorted(
                    [(_score(text, spec), slug) for slug, spec in _TOPICS.items() if _score(text, spec) > 0],
                    reverse=True,
                )
                top = scores[:2] if len(scores) >= 2 else scores
                assignments_str = " + ".join(f"{sl}({sc:.3f})" for sc, sl in top)
                print(f"  {paper.title[:55]:55s} -> {assignments_str}")
    print()

    # ── Step 3: create notebook ───────────────────────────────────────────────
    print(DIV)
    print("STEP 3 — Create notebook")
    print(DIV)
    nb = create_notebook("Smoke Test — NeurIPS 2024 LLM Papers (auto-delete)")
    print(f"  notebook_id = {nb.notebook_id}")
    print(f"  url         = {nb.url}")
    print()

    # ── Step 4: upload sources ────────────────────────────────────────────────
    print(DIV)
    print("STEP 4 — Upload sources")
    print(DIV)
    for i, doc in enumerate(docs, 1):
        print(f"  [{i}/{len(docs)}] {doc.title[:60]} ({doc.char_count:,}c)...")
        ok = add_source(nb.notebook_id, doc.text, doc.title[:80])
        print(f"        -> {'OK' if ok else 'FAILED'}")
        if i < len(docs):
            time.sleep(3)

    print()
    print("  Waiting 15s for NotebookLM to index all sources...")
    time.sleep(15)
    print()

    # ── Step 5: query ─────────────────────────────────────────────────────────
    print(DIV)
    print("STEP 5 — Query")
    print(DIV)
    print(f"  prompt ({len(QUERY)}c):")
    print(f"    {QUERY[:120]}...")
    print()

    result = query_notebook(nb.notebook_id, QUERY)

    print(f"  answer length    : {len(result.answer)} chars")
    print(f"  citation refs    : {len(result.citations)}")
    print(f"  unique sources   : {len(set(result.citations.values()))}")
    print()
    print("--- RAW ANSWER ---")
    print(result.answer)
    print("--- END ANSWER ---")
    print()
    print("Citation map (first 6):")
    for k, v in list(result.citations.items())[:6]:
        print(f"  [{k}] -> {v}")

    # ── Step 6: clean up ──────────────────────────────────────────────────────
    print()
    print(DIV)
    print("STEP 6 — Delete test notebook")
    print(DIV)
    deleted = delete_notebook(nb.notebook_id)
    print(f"  deleted = {deleted}")
    print()
    print(DIV)
    print("SMOKE TEST COMPLETE")
    print(DIV)


if __name__ == "__main__":
    main()
