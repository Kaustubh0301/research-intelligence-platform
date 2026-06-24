"""
scripts/benchmark_retrieval.py
───────────────────────────────
Compare keyword-only vs hybrid retrieval for the S1-S7 semantic/paraphrase queries.

Usage:
    cd ~/research-intelligence-platfrom
    python scripts/benchmark_retrieval.py

Output: side-by-side table showing top-5 results for each query under both modes.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(override=True)

_hf_cache = str(ROOT / ".hf_cache")
os.makedirs(_hf_cache, exist_ok=True)
os.environ.setdefault("HF_HOME", _hf_cache)
os.environ.setdefault("TRANSFORMERS_CACHE", _hf_cache)

from db.session import get_session
from search.retrieval import retrieve_papers_for_query
from search.embeddings import get_index

QUERIES = [
    ("S1", "making large models faster at inference"),
    ("S2", "teaching models to follow instructions"),
    ("S3", "reducing hallucinations in language models"),
    ("S4", "models that can use tools and browse the web"),
    ("S5", "understanding why neural networks make decisions"),
    ("S6", "training without labels"),
    ("S7", "models that keep learning without forgetting"),
]


def _truncate(s: str, n: int = 68) -> str:
    return s if len(s) <= n else s[:n - 1] + "…"


def run_query(term: str, session, semantic: bool) -> list[dict]:
    os.environ["SEMANTIC_SEARCH"] = "true" if semantic else "false"
    # Force re-check of env var — index is already loaded, flag is read per-call
    return retrieve_papers_for_query(term, session, limit=5)


def print_comparison(qid: str, query: str, kw_results: list[dict], hy_results: list[dict]) -> None:
    print(f"\n{'═' * 120}")
    print(f"  {qid}: \"{query}\"")
    print(f"{'═' * 120}")
    print(f"  {'KEYWORD-ONLY':^57}  │  {'HYBRID (keyword + semantic)':^57}")
    print(f"  {'─' * 57}  │  {'─' * 57}")

    rows = max(len(kw_results), len(hy_results))
    for i in range(rows):
        kw = kw_results[i] if i < len(kw_results) else None
        hy = hy_results[i] if i < len(hy_results) else None

        kw_str = f"[{i+1}] {_truncate(kw['title'], 50):50s} {kw['match_score']:5.0f}" if kw else " " * 57
        hy_str = f"[{i+1}] {_truncate(hy['title'], 50):50s} {hy['match_score']:5.0f}" if hy else " " * 57

        # Mark papers that appear only in hybrid (semantic-only candidates)
        is_new = hy and (not kw or hy["id"] != kw["id"]) and hy and "semantic" in hy.get("matched_in", [])
        marker = " ★" if is_new else "  "

        print(f"  {kw_str}  │  {hy_str}{marker}")

    # Show matched_in for hybrid results
    print(f"  {'':57}  │  matched_in:")
    for i, hy in enumerate(hy_results):
        tags = ", ".join(hy.get("matched_in", [])[:4])
        print(f"  {'':57}  │    [{i+1}] {tags}")

    # Count semantic-only papers in hybrid results
    sem_only = sum(
        1 for hy in hy_results
        if "semantic" in hy.get("matched_in", []) and not any(
            t for t in hy.get("matched_in", []) if t != "semantic"
        )
    )
    if sem_only:
        print(f"\n  ★ {sem_only} paper(s) retrieved only via semantic search (zero keyword score)")


def main() -> None:
    # Load semantic index
    print("Loading embedding index …")
    get_index().load()

    if not get_index().is_loaded():
        print(
            "\nERROR: Embedding index not found.\n"
            "Run first:  python scripts/build_embeddings.py\n"
        )
        sys.exit(1)

    print(f"Index loaded — {get_index().paper_count()} papers\n")
    print("Running benchmark: keyword-only vs hybrid for S1-S7 paraphrase queries")

    with get_session() as session:
        for qid, query in QUERIES:
            os.environ["SEMANTIC_SEARCH"] = "false"
            kw_results = retrieve_papers_for_query(query, session, limit=5)

            os.environ["SEMANTIC_SEARCH"] = "true"
            hy_results = retrieve_papers_for_query(query, session, limit=5)

            print_comparison(qid, query, kw_results, hy_results)

    print(f"\n{'═' * 120}")
    print("  Legend:  ★ = paper entered via semantic search only (not keyword-matched)")
    print(f"{'═' * 120}\n")


if __name__ == "__main__":
    main()
