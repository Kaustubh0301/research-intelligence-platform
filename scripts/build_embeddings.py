"""
scripts/build_embeddings.py
────────────────────────────
One-time offline job: embed all papers and write the FAISS index.

Each paper produces up to 5 chunks (one per field), so the index holds
~10k vectors instead of ~2k. At query time, chunk scores are aggregated
back to paper level via max-pooling in search/embeddings.py.

Chunks (in priority order):
    methodology          — implementation detail, highest signal
    techniques_text      — joined technique canonical names
    experimental_findings — benchmark results and comparisons
    summary              — NotebookLM-generated summary
    abstract             — fallback when analyses are missing

Output (project root):
    embeddings.index      — FAISS FlatIP index
    embeddings_ids.json   — list of {"paper_id": ..., "field": ...} dicts

Usage:
    cd ~/research-intelligence-platfrom
    python scripts/build_embeddings.py

Options:
    --batch-size N    encode batch size (default 64)
    --dry-run         print chunk count and samples, do not write files
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(override=True)

import os as _os
_hf_cache = str(ROOT / ".hf_cache")
_os.makedirs(_hf_cache, exist_ok=True)
_os.environ.setdefault("HF_HOME", _hf_cache)
_os.environ.setdefault("TRANSFORMERS_CACHE", _hf_cache)
_os.environ.setdefault("HF_HUB_OFFLINE", "1")

from sqlalchemy import text
from db.session import get_session

INDEX_PATH = ROOT / "embeddings.index"
IDS_PATH   = ROOT / "embeddings_ids.json"
MODEL_NAME = "all-MiniLM-L6-v2"

# Max chars per field before truncation (512 tokens ≈ 380 words ≈ 2000 chars)
_MAX_CHARS = 2000

# Fields emitted per paper, in priority order.
# Only emitted when non-empty after stripping.
_FIELDS = [
    "methodology",
    "techniques_text",
    "experimental_findings",
    "summary",
    "abstract",
]


def _join_list_field(value) -> str:
    """JSON-stored list fields (e.g. experimental_findings) → single string."""
    if not value:
        return ""
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            if isinstance(parsed, list):
                return " ".join(str(x) for x in parsed if x)
        except (json.JSONDecodeError, TypeError):
            return value.strip()
    if isinstance(value, list):
        return " ".join(str(x) for x in value if x)
    return str(value).strip()


def fetch_chunks(session) -> list[tuple[str, str, str]]:
    """
    Return list of (paper_id, field_name, text_to_embed).

    Joins papers → paper_analyses → paper_techniques so we can build a
    techniques_text chunk from canonical technique names.
    """
    rows = session.execute(text("""
        SELECT
            p.id,
            p.title,
            p.abstract,
            pa.methodology,
            pa.summary,
            pa.experimental_findings
        FROM papers p
        LEFT JOIN paper_analyses pa ON p.id = pa.paper_id
        ORDER BY p.created_at
    """)).fetchall()

    # Fetch per-paper technique names in one query
    tech_rows = session.execute(text("""
        SELECT paper_id, GROUP_CONCAT(canonical_name, ', ')
        FROM paper_techniques
        WHERE canonical_name IS NOT NULL
        GROUP BY paper_id
    """)).fetchall()
    tech_map = {r[0]: r[1] for r in tech_rows if r[1]}

    chunks: list[tuple[str, str, str]] = []

    for paper_id, title, abstract, methodology, summary, experimental_findings in rows:
        title = (title or "").strip()
        prefix = f"{title}. " if title else ""

        field_texts = {
            "methodology":            (methodology or "").strip(),
            "techniques_text":        tech_map.get(paper_id, ""),
            "experimental_findings":  _join_list_field(experimental_findings),
            "summary":                (summary or "").strip(),
            "abstract":               (abstract or "").strip(),
        }

        emitted = 0
        for field in _FIELDS:
            body = field_texts[field]
            if not body:
                continue
            text_to_embed = (prefix + body)[: _MAX_CHARS]
            chunks.append((paper_id, field, text_to_embed))
            emitted += 1

        # Always emit at least one chunk (title only) so every paper is reachable
        if emitted == 0:
            chunks.append((paper_id, "title", title or paper_id))

    return chunks


def build(batch_size: int = 64, dry_run: bool = False) -> None:
    import numpy as np

    print(f"Loading model {MODEL_NAME} …")
    t0 = time.time()
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer(MODEL_NAME)
    print(f"Model loaded in {time.time() - t0:.1f}s")

    print("Fetching chunks from database …")
    with get_session() as session:
        chunks = fetch_chunks(session)

    paper_ids  = [c[0] for c in chunks]
    field_names = [c[1] for c in chunks]
    texts      = [c[2] for c in chunks]

    unique_papers = len(set(paper_ids))
    print(f"Found {len(chunks)} chunks across {unique_papers} papers")

    field_counts = {}
    for f in field_names:
        field_counts[f] = field_counts.get(f, 0) + 1
    for f in _FIELDS + ["title"]:
        if f in field_counts:
            print(f"  {f:25s} {field_counts[f]} chunks")

    if dry_run:
        print("\n── Sample chunks (first 5) ──")
        for pid, field, t in list(zip(paper_ids, field_names, texts))[:5]:
            print(f"  [{pid[:8]}] [{field}] {t[:120]}")
        print("\nDry run — no files written.")
        return

    print(f"\nEncoding {len(texts)} chunks (batch_size={batch_size}) …")
    t1 = time.time()
    vectors = model.encode(
        texts,
        batch_size=batch_size,
        normalize_embeddings=True,
        show_progress_bar=True,
        convert_to_numpy=True,
    ).astype("float32")
    elapsed = time.time() - t1
    print(f"Encoded in {elapsed:.1f}s ({len(texts)/elapsed:.0f} chunks/sec)")

    import faiss
    dim = vectors.shape[1]
    print(f"\nBuilding FAISS FlatIP index (dim={dim}) …")
    index = faiss.IndexFlatIP(dim)
    index.add(vectors)
    print(f"Index contains {index.ntotal} vectors")

    print(f"\nWriting {INDEX_PATH} …")
    faiss.write_index(index, str(INDEX_PATH))

    print(f"Writing {IDS_PATH} …")
    # Each entry is {paper_id, field} so search/embeddings.py can aggregate by paper
    entries = [{"paper_id": pid, "field": field} for pid, field in zip(paper_ids, field_names)]
    with open(IDS_PATH, "w") as f:
        json.dump(entries, f)

    index_mb = INDEX_PATH.stat().st_size / 1_048_576
    ids_kb   = IDS_PATH.stat().st_size / 1_024
    print(f"\nDone.")
    print(f"  embeddings.index    {index_mb:.1f} MB")
    print(f"  embeddings_ids.json {ids_kb:.0f} KB")
    print(f"  Total time          {time.time() - t0:.1f}s")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build FAISS embedding index for papers")
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    build(batch_size=args.batch_size, dry_run=args.dry_run)
