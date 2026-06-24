"""
search/embeddings.py
────────────────────
EmbeddingIndex singleton for semantic search over per-field paper chunks.

Each FAISS row corresponds to one (paper_id, field) chunk. After nearest-
neighbour search, chunk scores are aggregated back to paper level by
max-pooling: a paper's final score is its best-scoring chunk's score.

Index files (project root):
    embeddings.index      — FAISS FlatIP index (384-dim, L2-normalised)
    embeddings_ids.json   — list of {"paper_id": ..., "field": ...} dicts
                            (legacy: plain list of paper_id strings also supported)

Environment:
    SEMANTIC_SEARCH=false — disables semantic path entirely

Build the index with:
    python scripts/build_embeddings.py
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

log = logging.getLogger(__name__)

MODEL_NAME      = "all-MiniLM-L6-v2"
TOP_K_SEMANTIC  = 50
SEM_MIN_COSINE  = 0.30

# How many chunks to pull from FAISS before aggregating to paper level.
# More chunks = more recall at the cost of slightly slower aggregation.
_CHUNK_FETCH_K = 200

_PROJECT_ROOT = Path(__file__).parent.parent
INDEX_PATH    = Path(os.environ.get("EMBEDDINGS_INDEX_PATH", str(_PROJECT_ROOT / "embeddings.index")))
IDS_PATH      = Path(os.environ.get("EMBEDDINGS_IDS_PATH",   str(_PROJECT_ROOT / "embeddings_ids.json")))

_hf_cache = str(_PROJECT_ROOT / ".hf_cache")
os.makedirs(_hf_cache, exist_ok=True)
os.environ.setdefault("HF_HOME", _hf_cache)
os.environ.setdefault("TRANSFORMERS_CACHE", _hf_cache)
os.environ.setdefault("HF_HUB_OFFLINE", "1")


class EmbeddingIndex:
    def __init__(self) -> None:
        self._model  = None
        self._index  = None
        # Each entry is either a str (legacy) or {"paper_id": ..., "field": ...}
        self._entries: list = []
        self._loaded = False

    def load(self) -> None:
        if os.getenv("SEMANTIC_SEARCH", "true").strip().lower() == "false":
            log.info("SEMANTIC_SEARCH=false — semantic index not loaded")
            return

        if not INDEX_PATH.exists() or not IDS_PATH.exists():
            log.warning(
                "Embedding index files not found (%s, %s). "
                "Run scripts/build_embeddings.py to enable semantic search. "
                "Server will run in keyword-only mode.",
                INDEX_PATH, IDS_PATH,
            )
            return

        try:
            import faiss
            from sentence_transformers import SentenceTransformer

            log.info("Loading sentence-transformers model %s …", MODEL_NAME)
            self._model = SentenceTransformer(MODEL_NAME)

            log.info("Loading FAISS index from %s …", INDEX_PATH)
            self._index = faiss.read_index(str(INDEX_PATH))

            with open(IDS_PATH) as f:
                self._entries = json.load(f)

            self._loaded = True
            n_chunks = len(self._entries)
            n_papers = len({self._paper_id(e) for e in self._entries})
            log.info("Semantic index ready — %d chunks across %d papers", n_chunks, n_papers)

        except Exception as exc:
            log.error("Failed to load embedding index: %s — running keyword-only", exc)
            self._loaded = False

    def _paper_id(self, entry) -> str:
        if isinstance(entry, dict):
            return entry["paper_id"]
        return entry  # legacy plain string

    def is_loaded(self) -> bool:
        return self._loaded

    def search(self, query: str, k: int = TOP_K_SEMANTIC) -> dict[str, float]:
        """
        Return {paper_id: score} for the top-k papers.

        Fetches _CHUNK_FETCH_K chunks from FAISS, filters by SEM_MIN_COSINE,
        then aggregates to paper level via max-pooling before returning top-k.
        """
        if not self._loaded:
            return {}

        import numpy as np

        vec = self._model.encode(
            [query],
            normalize_embeddings=True,
            show_progress_bar=False,
        ).astype("float32")

        fetch_k = min(_CHUNK_FETCH_K, len(self._entries))
        distances, indices = self._index.search(vec, fetch_k)

        # Aggregate chunk scores → paper scores via max-pooling
        paper_scores: dict[str, float] = {}
        for dist, idx in zip(distances[0], indices[0]):
            if idx == -1:
                continue
            score = float(dist)  # inner product of L2-normalised = cosine similarity
            if score < SEM_MIN_COSINE:
                continue
            pid = self._paper_id(self._entries[idx])
            if pid not in paper_scores or score > paper_scores[pid]:
                paper_scores[pid] = score

        # Return top-k papers by score
        top_k_papers = dict(
            sorted(paper_scores.items(), key=lambda x: x[1], reverse=True)[:k]
        )
        return top_k_papers

    def paper_count(self) -> int:
        return len({self._paper_id(e) for e in self._entries})


_index = EmbeddingIndex()


def get_index() -> EmbeddingIndex:
    return _index
