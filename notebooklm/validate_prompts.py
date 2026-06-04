"""
Prompt format validation — runs before extractor.py is built.

Creates a 5-paper notebook, sends all 5 query types, saves every raw
response to disk, and prints a format-compliance report so the extractor
can be written against observed (not assumed) output.

Run:
    python -m notebooklm.validate_prompts
"""

from __future__ import annotations

import json
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
from notebooklm.client import (
    add_source, create_notebook, delete_notebook,
    health_check, query_notebook,
)
from notebooklm.source_prep import build_source

# ── 5 papers (all with regex-v3 sections) ────────────────────────────────────
PAPER_IDS = [
    "f16b682e-2f02-4627-9aa1-c593e350f5f5",   # Gorilla
    "d4de18d9-5979-4720-b263-5dc62355d8b1",   # Refusal
    "bb8f3d18-8ad0-49a6-809c-969c3cdb1c6e",   # ALPHALLM
    "2cb2b38a-abec-4910-bfb6-2b21f1528bbb",   # KV Cache
    "575654ff-6791-42ff-82ce-e394d39b5332",   # Multistep Distillation
]

# ── Proposed rigid prompt format ──────────────────────────────────────────────
#
# Design principles:
#   1. One PAPER: line per block, using the exact source title.
#   2. Each field is a distinct ALL-CAPS label followed by colon.
#   3. Multi-value fields use " | " as separator.
#   4. Empty fields must be written as NONE (not omitted).
#   5. Blocks are terminated by === on its own line.
#   6. No markdown, no bullets, no bold — just labels and values.
#
# === was chosen as block separator because:
#   - It never appears in academic prose.
#   - It is visually distinct from field separators.
#   - It is easy to split on in Python: response.split("\n===\n")

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

DIV = "=" * 72


def run_validation() -> None:
    print(DIV)
    print("NotebookLM Prompt Format Validation")
    print(DIV)

    assert health_check(), "Auth failed — run: nlm login"

    # ── Build source documents ────────────────────────────────────────────────
    print("\nBuilding source documents...")
    docs = []
    with get_session() as s:
        for pid in PAPER_IDS:
            doc = build_source(s, pid)
            assert doc is not None, f"Paper {pid} not in DB"
            docs.append(doc)
            print(f"  {doc.title[:60]}  [{doc.mode}, {doc.char_count:,}c]")

    # ── Create notebook ───────────────────────────────────────────────────────
    print("\nCreating validation notebook...")
    nb = create_notebook("Prompt Format Validation — 5 NeurIPS Papers")
    print(f"  id={nb.notebook_id}  url={nb.url}")

    # ── Upload sources ────────────────────────────────────────────────────────
    print("\nUploading 5 sources...")
    for i, doc in enumerate(docs, 1):
        ok = add_source(nb.notebook_id, doc.text, doc.title[:80])
        print(f"  [{i}/5] {'OK' if ok else 'FAIL'}  {doc.title[:55]}")
        time.sleep(3)

    print("\nWaiting 20s for all sources to index...")
    time.sleep(20)

    # ── Run all 5 query types ─────────────────────────────────────────────────
    results: dict[str, dict] = {}
    for qname, prompt in PROMPTS.items():
        print(f"\nQuerying: {qname}...")
        result = query_notebook(nb.notebook_id, prompt)
        results[qname] = {
            "prompt":    prompt,
            "answer":    result.answer,
            "citations": result.citations,
        }
        print(f"  answer={len(result.answer)}c  citation_refs={len(result.citations)}  unique_sources={len(set(result.citations.values()))}")
        time.sleep(5)

    # ── Save raw output ───────────────────────────────────────────────────────
    out_path = Path(__file__).parent / "validation_results.json"
    out_path.write_text(json.dumps(results, indent=2))
    print(f"\nRaw results saved to {out_path}")

    # ── Print full raw responses ──────────────────────────────────────────────
    for qname, data in results.items():
        print(f"\n{DIV}")
        print(f"QUERY: {qname}  |  {len(data['answer'])} chars  |  {len(set(data['citations'].values()))} sources cited")
        print(DIV)
        print(data["answer"])

    # ── Format compliance check ───────────────────────────────────────────────
    print(f"\n{DIV}")
    print("FORMAT COMPLIANCE REPORT")
    print(DIV)
    for qname, data in results.items():
        answer = data["answer"]
        blocks = [b.strip() for b in answer.split("===") if b.strip()]
        paper_lines   = sum(1 for b in blocks if b.startswith("PAPER:"))
        missing_paper = sum(1 for b in blocks if not b.startswith("PAPER:"))
        expected = len(PAPER_IDS)
        print(f"\n  {qname}:")
        print(f"    blocks found      : {len(blocks)}  (expected {expected})")
        print(f"    start with PAPER: : {paper_lines}")
        print(f"    missing PAPER:    : {missing_paper}")
        # Check each expected field label is present
        labels = {
            "summary":    ["SUMMARY:", "ADVANTAGE:", "LIMITATION:", "FUTURE_WORK:"],
            "techniques": ["INTRODUCES:", "USES:"],
            "datasets":   ["DATASET:"],
            "categories": ["CATEGORIES:", "METHODOLOGY:"],
            "use_cases":  ["USE_CASE:"],
        }
        for label in labels.get(qname, []):
            count = sum(1 for b in blocks if label in b)
            status = "OK" if count == expected else f"PARTIAL ({count}/{expected})"
            print(f"    {label:<20} {status}")

    # ── Cleanup ───────────────────────────────────────────────────────────────
    print(f"\n{DIV}")
    delete_notebook(nb.notebook_id)
    print("Notebook deleted.")


if __name__ == "__main__":
    run_validation()
