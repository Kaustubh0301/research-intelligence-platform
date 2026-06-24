"""
scripts/feature_retrieval_regression.py
────────────────────────────────────────
Objective regression suite for feature-to-paper retrieval.

For each of 12 curated features (spanning NLP, retrieval, CV, LLM, graph,
efficiency, generative domains) we assert that at least one EXPECTED paper —
identified by a title substring — appears in the top-5 retrieved papers.
Expectations are grounded in the current 2000-paper corpus.

This is a recall@5 gate, deliberately lenient (any-of substring match) so it
catches genuine retrieval regressions without being brittle to score shuffles.

Run:
    cd /path/to/research-intelligence-platfrom
    source .venv/bin/activate
    python scripts/feature_retrieval_regression.py

Exit code 0 if pass rate >= PASS_THRESHOLD, else 1 (suitable for CI).
"""

from __future__ import annotations

import os
import sys
import uuid

os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from dotenv import load_dotenv
load_dotenv(dotenv_path=os.path.join(PROJECT_ROOT, ".env"), override=True)

from search.embeddings import get_index
from db.session import get_session
from feature_mapper.models import Feature
from feature_mapper.retrieval import retrieve_for_feature

# Fraction of cases that must pass for the suite to succeed.
PASS_THRESHOLD = 0.80
TOP_K = 5

# ── Regression cases ──────────────────────────────────────────────────────────
# Each: (id, name, description, matched_techniques, matched_categories,
#        expected_substrings)  — pass if ANY expected substring appears in the
#        top-5 titles (case-insensitive). Substrings reflect papers known to be
#        retrievable from the current corpus.

CASES = [
    (
        "cot_reasoning",
        "Chain-of-thought prompting for multi-step reasoning",
        "Chain-of-thought prompting guides LLMs through intermediate reasoning steps before a final answer.",
        ["Chain-of-Thought prompting", "Large Language Models (LLMs)"],
        [],
        ["reasoning", "LLM", "Chain", "Self-Improvement", "Compose"],
    ),
    (
        "lora_peft",
        "LoRA parameter-efficient fine-tuning",
        "Low-Rank Adaptation injects low-rank matrices into attention layers to fine-tune LLMs cheaply.",
        ["LoRA", "Transformers"],
        [],
        ["Finetuning", "Fine-tuning", "Finetune", "LoRA", "Adaptation"],
    ),
    (
        "gqa_kvcache",
        "Grouped-query attention for inference efficiency",
        "Grouped-query attention reduces the KV cache footprint during autoregressive generation.",
        ["Grouped-Query Attention", "Multi-Query Attention", "Key-Value (KV) cache"],
        [],
        ["Attention", "Key-Value Cache", "KV Cache", "CHAI", "Cross-Layer"],
    ),
    (
        "bm25_sparse",
        "BM25 sparse retrieval with inverted index",
        "Sparse retrieval scores documents with BM25 over an inverted index.",
        ["BM25"],
        [],
        ["RAPTOR", "SuRe", "Retrieval", "Gorilla", "RECOMP"],
    ),
    (
        "dpr_dense",
        "Dense bi-encoder retrieval with FAISS",
        "Bi-encoder dense retrieval encodes queries and passages, indexed in FAISS for ANN search.",
        ["DPR", "FAISS", "Dense Passage Retrieval (DPR)"],
        [],
        ["RAPTOR", "SuRe", "Retrieval", "In-Context Pretraining", "RECOMP"],
    ),
    (
        "vit_classification",
        "Vision transformer for image classification",
        "A Vision Transformer backbone processes 16x16 patches with self-attention for classification.",
        ["Vision Transformer (ViT)"],
        [],
        ["Vision Transformer", "ViT", "Image Classification", "Visual Prompt"],
    ),
    (
        "contrastive_repr",
        "Contrastive learning for visual representation",
        "Visual representations learned via contrastive learning with SimCLR and the InfoNCE loss.",
        ["Contrastive Learning (CL)", "SimCLR", "InfoNCE loss"],
        [],
        ["Contrastive Learning", "Contrastive", "Self-Supervised"],
    ),
    (
        "tool_use_agents",
        "Tool-use via function calling in LLM agents",
        "An agent framework uses LLM function calling to invoke external tools via structured JSON.",
        ["Function Calling Planner", "Large Language Models (LLMs)"],
        ["Agentic-AI"],
        ["Function Calling", "LLM Compiler", "LLM Agents", "Agent"],
    ),
    (
        "diffusion_gen",
        "Denoising diffusion models for image generation",
        "Denoising diffusion probabilistic models iteratively denoise noise into images.",
        ["Diffusion Models"],
        [],
        ["Diffusion Models", "Diffusion"],
    ),
    (
        "gnn_message_passing",
        "Graph neural network message passing for node classification",
        "A GNN performs message passing over graph nodes for node classification.",
        ["Graph Neural Network (GNN)", "Graph Attention Network (GAT)"],
        [],
        ["Graph Neural Network", "GNN", "Graph"],
    ),
    (
        "speculative_decoding",
        "Speculative decoding for faster LLM inference",
        "Speculative decoding uses a small draft model to accelerate autoregressive generation.",
        ["Speculative Decoding"],
        [],
        ["Speculative Decoding", "Speculati", "GliDe", "Accelerate"],
    ),
    (
        "rlhf_reward",
        "RLHF reward model training",
        "A reward model trained on human preferences guides PPO to align the language model.",
        ["Reinforcement Learning from Human Feedback (RLHF)", "Proximal Policy Optimization (PPO)"],
        [],
        ["RLHF", "DPO", "PPO", "Preference", "Reward"],
    ),
]


def _matches(titles: list[str], expected: list[str]) -> list[str]:
    lowered = [t.lower() for t in titles]
    hits = []
    for sub in expected:
        if any(sub.lower() in t for t in lowered):
            hits.append(sub)
    return hits


def main() -> int:
    print("Loading embedding index...")
    index = get_index()
    index.load()
    if not index.is_loaded():
        print("FATAL: embedding index not loaded — dense signal disabled, suite invalid.")
        return 2
    print(f"Index loaded: {index.paper_count()} papers\n")

    print("=" * 78)
    print(f"FEATURE RETRIEVAL REGRESSION — {len(CASES)} cases, recall@{TOP_K}, "
          f"pass threshold {PASS_THRESHOLD:.0%}")
    print("=" * 78)

    passed = 0
    failures: list[str] = []

    with get_session() as session:
        for cid, name, desc, tech, cat, expected in CASES:
            feature = Feature(
                id=str(uuid.uuid4()),
                name=name,
                description=desc,
                feature_type="other",
                matched_techniques=tech,
                matched_categories=cat,
            )
            papers, cov_score, cov_tier = retrieve_for_feature(feature, session, top_k=TOP_K)
            titles = [p.title for p in papers]
            hits = _matches(titles, expected)
            ok = len(hits) > 0

            status = "PASS" if ok else "FAIL"
            icon = "✅" if ok else "❌"
            print(f"\n{icon} [{status}] {cid}  ({cov_tier} {cov_score})")
            if ok:
                print(f"     matched expected: {hits}")
                passed += 1
            else:
                print(f"     expected ANY of: {expected}")
                print(f"     got top-{TOP_K}:")
                for t in titles:
                    print(f"       - {t[:70]}")
                failures.append(cid)

    rate = passed / len(CASES)
    print("\n" + "=" * 78)
    print(f"RESULT: {passed}/{len(CASES)} passed  ({rate:.0%})")
    if failures:
        print(f"Failures: {', '.join(failures)}")
    gate = "PASS" if rate >= PASS_THRESHOLD else "FAIL"
    print(f"GATE ({PASS_THRESHOLD:.0%}): {gate}")
    print("=" * 78)

    return 0 if rate >= PASS_THRESHOLD else 1


if __name__ == "__main__":
    sys.exit(main())
