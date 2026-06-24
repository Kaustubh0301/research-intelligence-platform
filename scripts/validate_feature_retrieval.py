"""
scripts/validate_feature_retrieval.py
--------------------------------------
Standalone validation script for feature-to-paper retrieval and
LLM extraction before implementing the full API.

Tests:
  1. Normalization: does entities_fts resolve technical terms to corpus vocabulary?
  2. Retrieval: do the three signals (dense, technique, category) return sensible papers?
  3. RRF fusion: does the combined ranking look reasonable?
  4. Token limit: does 1024 max_tokens truncate feature extraction output?

Run:
    cd /path/to/research-intelligence-platfrom
    source .venv/bin/activate
    python scripts/validate_feature_retrieval.py

Output: printed results for each feature. No DB writes, no side effects.
"""

from __future__ import annotations

import json
import os
import re
import sys
import time

os.environ["OMP_NUM_THREADS"] = "1"
os.environ["OPENBLAS_NUM_THREADS"] = "1"

# ── Bootstrap path and env ────────────────────────────────────────────────────

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from dotenv import load_dotenv
load_dotenv(dotenv_path=os.path.join(PROJECT_ROOT, ".env"), override=True)

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from db.models import PaperCategory, PaperTechnique
from db.session import get_session
from search.embeddings import get_index
from search.fts import query_entities_fts
from search.metadata import fetch_paper_metadata_batch

# ── Constants ─────────────────────────────────────────────────────────────────

RRF_K = 60
WEIGHT_DENSE = 1.0
WEIGHT_TECHNIQUE = 1.4
WEIGHT_CATEGORY = 0.7
TOP_K = 5

# ── 10 Test features across NLP, CV, LLM domains ─────────────────────────────
# Each entry: (domain, feature_name, description, raw_terms, expected_category_hint)

TEST_FEATURES = [
    # ── LLM domain ────────────────────────────────────────────────────────────
    (
        "LLM",
        "Chain-of-thought prompting for multi-step reasoning",
        "The system uses chain-of-thought prompting to guide large language models through "
        "intermediate reasoning steps before producing a final answer. Each reasoning step "
        "is generated autoregressively and conditions subsequent steps.",
        ["Chain-of-Thought prompting", "Large Language Models", "reasoning"],
        "LLM",
    ),
    (
        "LLM",
        "LoRA parameter-efficient fine-tuning",
        "We apply Low-Rank Adaptation (LoRA) to fine-tune large language models without "
        "updating all parameters. Low-rank matrices are injected into attention layers. "
        "Reduces GPU memory requirements by 3-4x compared to full fine-tuning.",
        ["LoRA", "parameter-efficient fine-tuning", "Transformers"],
        "LLM",
    ),
    (
        "LLM",
        "RLHF reward model training",
        "A reward model is trained on human preference comparisons between model outputs. "
        "The reward model then guides PPO-based reinforcement learning to align the "
        "language model with human preferences.",
        ["Reinforcement Learning from Human Feedback", "PPO", "reward model"],
        "Reinforcement learning",
    ),
    (
        "LLM",
        "Grouped-query attention for inference efficiency",
        "We replace standard multi-head attention with grouped-query attention (GQA) to "
        "reduce the KV cache memory footprint during autoregressive generation. Each group "
        "of query heads shares a single key and value head.",
        ["Grouped-Query Attention", "Multi-Query Attention", "KV cache"],
        "LLM",
    ),
    # ── NLP / Retrieval domain ────────────────────────────────────────────────
    (
        "NLP/Retrieval",
        "BM25 sparse retrieval with inverted index",
        "Sparse retrieval using BM25 scoring over an inverted index built with Pyserini. "
        "Queries are tokenized and matched against the index using TF-IDF-based term "
        "weighting with document length normalization.",
        ["BM25", "inverted index", "sparse retrieval", "TF-IDF"],
        "Retrieval",
    ),
    (
        "NLP/Retrieval",
        "Dense bi-encoder retrieval with FAISS",
        "Documents and queries are independently encoded using a bi-encoder (E5-large). "
        "Document embeddings are indexed in FAISS IVF256 for approximate nearest-neighbor "
        "search. Retrieval latency is sub-10ms for a 1M document corpus.",
        ["DPR", "FAISS", "bi-encoder", "dense retrieval", "approximate nearest neighbor"],
        "Retrieval",
    ),
    (
        "NLP/Retrieval",
        "Reciprocal rank fusion for hybrid retrieval",
        "BM25 and dense retrieval scores are fused using Reciprocal Rank Fusion (RRF) "
        "with k=60. RRF is parameter-free and robust to score distribution differences "
        "between sparse and dense signals.",
        ["Reciprocal Rank Fusion", "hybrid retrieval", "BM25"],
        "Retrieval",
    ),
    # ── CV domain ─────────────────────────────────────────────────────────────
    (
        "CV",
        "Vision transformer for image classification",
        "We use a Vision Transformer (ViT) backbone pretrained on ImageNet-21k for image "
        "classification. Patches of 16x16 pixels are linearly projected and processed by "
        "transformer encoder blocks with self-attention.",
        ["Vision Transformer", "ViT", "self-attention", "image classification"],
        "Vision",
    ),
    (
        "CV",
        "Contrastive learning for visual representation",
        "Visual representations are learned via contrastive learning using SimCLR. "
        "Positive pairs are augmented views of the same image. The InfoNCE loss pushes "
        "positive pairs together and negatives apart in the embedding space.",
        ["contrastive learning", "SimCLR", "InfoNCE loss", "representation learning"],
        "Vision",
    ),
    # ── Agentic / LLM Agents domain ──────────────────────────────────────────
    (
        "LLM-Agents",
        "Tool-use via function calling in LLM agents",
        "The agent framework uses LLM function calling to invoke external tools (web "
        "search, code execution, API calls). Tool schemas are passed in the system prompt "
        "and the LLM emits structured JSON tool calls.",
        ["function calling", "Large Language Models", "tool use", "agentic"],
        "Agentic-AI",
    ),
]

# ── Retrieval helpers ─────────────────────────────────────────────────────────

def normalize_terms(raw_terms: list[str], session: Session) -> tuple[list[str], list[str], list[str]]:
    """
    Resolve raw_terms against entities_fts (techniques and categories).
    Returns (matched_techniques, matched_categories, unrecognized).
    Uses FTS5 MATCH so it handles partial/tokenized matches.
    """
    matched_techniques: list[str] = []
    matched_categories: list[str] = []
    unrecognized: list[str] = []

    for term in raw_terms:
        hits = query_entities_fts(session, term, limit=10)
        techs = [h[2] for h in hits if h[1] == "technique"]
        cats  = [h[2] for h in hits if h[1] == "category"]

        if techs:
            # Take the first (most-relevant) match; deduplicate across terms
            for t in techs[:2]:
                if t not in matched_techniques:
                    matched_techniques.append(t)
        if cats:
            for c in cats[:2]:
                if c not in matched_categories:
                    matched_categories.append(c)
        if not techs and not cats:
            unrecognized.append(term)

    return matched_techniques, matched_categories, unrecognized


def retrieve_technique_scores(
    matched_techniques: list[str],
    session: Session,
) -> dict[str, float]:
    """paper_id → normalized technique match score [0,1]"""
    if not matched_techniques:
        return {}
    rows = session.execute(
        select(
            PaperTechnique.paper_id,
            func.count(PaperTechnique.id).label("cnt"),
        )
        .where(func.lower(PaperTechnique.name).in_([t.lower() for t in matched_techniques]))
        .group_by(PaperTechnique.paper_id)
    ).all()
    denom = len(matched_techniques)
    return {row.paper_id: row.cnt / denom for row in rows}


def retrieve_category_scores(
    matched_categories: list[str],
    session: Session,
) -> dict[str, float]:
    """paper_id → normalized category match score [0,1]"""
    if not matched_categories:
        return {}
    rows = session.execute(
        select(
            PaperCategory.paper_id,
            func.count(PaperCategory.id).label("cnt"),
        )
        .where(func.lower(PaperCategory.name).in_([c.lower() for c in matched_categories]))
        .group_by(PaperCategory.paper_id)
    ).all()
    denom = len(matched_categories)
    return {row.paper_id: row.cnt / denom for row in rows}


def rrf_fuse(
    dense: dict[str, float],
    technique: dict[str, float],
    category: dict[str, float],
) -> dict[str, float]:
    """Weighted Reciprocal Rank Fusion across three signals."""
    dense_ranked = sorted(dense, key=lambda p: dense[p], reverse=True)
    tech_ranked  = sorted(technique, key=lambda p: technique[p], reverse=True)
    cat_ranked   = sorted(category, key=lambda p: category[p], reverse=True)

    all_ids = set(dense) | set(technique) | set(category)
    fused: dict[str, float] = {}
    for pid in all_ids:
        score = 0.0
        if pid in dense_ranked:
            score += WEIGHT_DENSE     / (RRF_K + dense_ranked.index(pid))
        if pid in tech_ranked:
            score += WEIGHT_TECHNIQUE / (RRF_K + tech_ranked.index(pid))
        if pid in cat_ranked:
            score += WEIGHT_CATEGORY  / (RRF_K + cat_ranked.index(pid))
        fused[pid] = score
    return fused


def coverage_score(
    dense: dict,
    technique: dict,
    category: dict,
    top_fused: list[float],
) -> tuple[float, str]:
    signals = sum([
        1 if len(dense) >= 3 else 0,
        1 if len(technique) >= 2 else 0,
        1 if len(category) >= 2 else 0,
    ])
    breadth = signals / 3
    max_possible = WEIGHT_DENSE / (RRF_K + 0) + WEIGHT_TECHNIQUE / (RRF_K + 0) + WEIGHT_CATEGORY / (RRF_K + 0)
    quality = (sum(top_fused[:5]) / max(1, len(top_fused[:5]))) / max_possible if top_fused else 0.0
    quality = min(1.0, quality)
    score = round(0.6 * breadth + 0.4 * quality, 3)
    if score > 0.65:   tier = "strong"
    elif score > 0.40: tier = "moderate"
    elif score > 0.15: tier = "weak"
    else:              tier = "novel"
    return score, tier


def retrieve_feature(
    domain: str,
    feature_name: str,
    description: str,
    raw_terms: list[str],
    session: Session,
    index,
) -> dict:
    """Full retrieval pipeline for one feature. Returns a result dict."""
    # 1. Normalize
    t0 = time.monotonic()
    matched_tech, matched_cat, unrecognized = normalize_terms(raw_terms, session)

    # 2. Dense retrieval
    query_text = f"{feature_name}. {description}. {' '.join(matched_tech)}"
    dense_scores = index.search(query_text, k=50)

    # 3. Technique + category retrieval
    tech_scores = retrieve_technique_scores(matched_tech, session)
    cat_scores  = retrieve_category_scores(matched_cat, session)

    # 4. Fuse
    fused = rrf_fuse(dense_scores, tech_scores, cat_scores)

    # 5. Top-K
    ranked_ids = sorted(fused, key=lambda p: fused[p], reverse=True)[:TOP_K]
    metadata   = fetch_paper_metadata_batch(session, ranked_ids)

    # 6. Coverage
    top_scores = [fused[p] for p in ranked_ids]
    cov_score, cov_tier = coverage_score(dense_scores, tech_scores, cat_scores, top_scores)

    elapsed_ms = int((time.monotonic() - t0) * 1000)

    papers = []
    for rank, pid in enumerate(ranked_ids, 1):
        m = metadata.get(pid)
        if not m:
            continue
        papers.append({
            "rank":       rank,
            "title":      m["title"],
            "year":       m["year"],
            "venue":      m.get("conference") or "?",
            "rrf_score":  round(fused[pid], 6),
            "sem_score":  round(dense_scores.get(pid, 0.0), 4),
            "tech_score": round(tech_scores.get(pid, 0.0), 4),
            "cat_score":  round(cat_scores.get(pid, 0.0), 4),
            "techniques": m.get("top_techniques", []),
            "categories": m.get("categories", []),
            "signals_fired": sum([
                pid in dense_scores,
                pid in tech_scores,
                pid in cat_scores,
            ]),
        })

    return {
        "domain":          domain,
        "feature":         feature_name,
        "matched_tech":    matched_tech,
        "matched_cat":     matched_cat,
        "unrecognized":    unrecognized,
        "dense_count":     len(dense_scores),
        "tech_count":      len(tech_scores),
        "cat_count":       len(cat_scores),
        "coverage_score":  cov_score,
        "coverage_tier":   cov_tier,
        "elapsed_ms":      elapsed_ms,
        "papers":          papers,
    }


# ── Token limit test ──────────────────────────────────────────────────────────

def test_token_limits() -> None:
    print("\n" + "=" * 70)
    print("TOKEN LIMIT VALIDATION")
    print("=" * 70)

    from llm.providers import AnthropicProvider

    api_key  = os.getenv("ANTHROPIC_API_KEY", "")
    base_url = os.getenv("ANTHROPIC_BASE_URL", "") or None
    p = AnthropicProvider(api_key=api_key, base_url=base_url)
    client = p._client()

    json_format = (
        '[{"name":"...","description":"2-3 sentences","source_section":"heading or null",'
        '"source_text":"exact quote","feature_type":"algorithm|architecture|training|'
        'evaluation|data|infrastructure|other","raw_terms":["term1","term2"]}]'
    )

    # Build a prompt with 10 sections (worst-case)
    sections = "\n\n".join([
        f"## {name}\n{desc}"
        for _, name, desc, _, _ in TEST_FEATURES
    ])
    prompt = (
        "Identify 3-10 discrete technical features in this project document. "
        "Return a JSON array ONLY, no other text. Each feature must be grounded "
        "in text that actually appears in the document.\n\n"
        + sections
        + f"\n\nReturn format: {json_format}"
    )

    for max_tokens in [1024, 2048]:
        resp = client.messages.create(
            model=AnthropicProvider.MODEL,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        out = resp.content[0].text
        stop = resp.stop_reason
        out_tokens = resp.usage.output_tokens

        # Try to parse
        parsed_count = 0
        parse_ok = False
        try:
            m = re.search(r"\[.*\]", out, re.DOTALL)
            if m:
                parsed = json.loads(m.group())
                parsed_count = len(parsed)
                parse_ok = True
        except (json.JSONDecodeError, AttributeError):
            pass

        status = "OK" if (stop == "end_turn" and parse_ok) else "TRUNCATED" if stop == "max_tokens" else "PARSE_FAIL"
        print(f"\n  max_tokens={max_tokens:5d} | used={out_tokens:4d} | stop={stop:10s} | "
              f"parse={'OK' if parse_ok else 'FAIL'} | features={parsed_count} | STATUS={status}")

        if not parse_ok and stop == "max_tokens":
            print(f"  Last 80 chars: ...{repr(out[-80:])}")


# ── Print helpers ─────────────────────────────────────────────────────────────

TIER_COLORS = {"strong": "✅", "moderate": "🟡", "weak": "🟠", "novel": "🔴"}

def print_result(r: dict) -> None:
    tier_icon = TIER_COLORS.get(r["coverage_tier"], "?")
    print(f"\n{'─'*70}")
    print(f"  [{r['domain']}]  {r['feature']}")
    print(f"  Coverage: {tier_icon} {r['coverage_tier'].upper()}  (score={r['coverage_score']})  "
          f"[{r['elapsed_ms']}ms]")
    print(f"  Signals: dense={r['dense_count']} tech={r['tech_count']} cat={r['cat_count']}")
    print(f"  Matched techniques : {r['matched_tech'] or '(none)'}")
    print(f"  Matched categories : {r['matched_cat'] or '(none)'}")
    if r["unrecognized"]:
        print(f"  Unrecognized terms : {r['unrecognized']}")

    if not r["papers"]:
        print("  ⚠️  NO PAPERS RETURNED")
        return

    print(f"  Top-{len(r['papers'])} papers:")
    for p in r["papers"]:
        sig_bar = "".join([
            "D" if p["sem_score"] > 0 else ".",
            "T" if p["tech_score"] > 0 else ".",
            "C" if p["cat_score"] > 0 else ".",
        ])
        print(
            f"    #{p['rank']} [{sig_bar}] rrf={p['rrf_score']:.5f}  "
            f"{p['year']} {p['venue']:8s}  {p['title'][:65]}"
        )
        if p["techniques"]:
            print(f"         techniques: {', '.join(p['techniques'])}")


def print_summary(results: list[dict]) -> None:
    print(f"\n{'='*70}")
    print("SUMMARY")
    print(f"{'='*70}")
    tiers = {"strong": 0, "moderate": 0, "weak": 0, "novel": 0}
    for r in results:
        tiers[r["coverage_tier"]] += 1
    print(f"  Total features tested: {len(results)}")
    for tier, count in tiers.items():
        icon = TIER_COLORS[tier]
        print(f"  {icon} {tier:10s}: {count}")
    avg_ms = int(sum(r["elapsed_ms"] for r in results) / len(results)) if results else 0
    print(f"  Avg retrieval latency: {avg_ms}ms per feature")
    print()

    zero_papers = [r for r in results if not r["papers"]]
    if zero_papers:
        print(f"  ⚠️  Features with NO papers returned ({len(zero_papers)}):")
        for r in zero_papers:
            print(f"     - [{r['domain']}] {r['feature']}")

    no_norm = [r for r in results if not r["matched_tech"] and not r["matched_cat"]]
    if no_norm:
        print(f"  ⚠️  Features with NO normalization matches ({len(no_norm)}):")
        for r in no_norm:
            print(f"     - [{r['domain']}] {r['feature']}")
            print(f"       raw_terms were: {TEST_FEATURES[results.index(r)][3]}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    print("Loading embedding index...")
    index = get_index()
    index.load()
    if not index.is_loaded():
        print("WARNING: Embedding index not loaded — dense retrieval will return empty results.")
    else:
        print(f"Index loaded: {index.paper_count()} papers")

    print("\n" + "=" * 70)
    print("RETRIEVAL VALIDATION — 10 features across NLP, CV, LLM domains")
    print("=" * 70)

    results = []
    with get_session() as session:
        for domain, name, desc, raw_terms, _expected_cat in TEST_FEATURES:
            r = retrieve_feature(domain, name, desc, raw_terms, session, index)
            print_result(r)
            results.append(r)

    print_summary(results)

    # Token limit test — separate from retrieval
    test_token_limits()

    print("\nValidation complete.\n")


if __name__ == "__main__":
    main()
