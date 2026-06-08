# Technique Evolution — Corpus Intelligence Report

**Generated:** 2026-06-05 07:33 UTC
**Corpus:** 100 papers
**Canonical techniques:** 517
**Directed influence edges:** 790 (unique A→B pairs)
**Techniques in at least one edge:** 492

> **How to read this report.** An edge A → B means: a paper introduced A
> while using B — implying A was built on B.  In-degree measures how many
> novel techniques depend on a given foundation.  Out-degree measures how
> many foundations a technique synthesized when it was introduced.
>
> **Corpus size caveat:** At 100 papers from a single conference-year,
> chains are short and edge weights are mostly 1.  The structure is correct;
> density and chain depth improve automatically as the corpus grows.

---

## Classification

| Classification | Count | Description |
|---|---:|---|
| **Foundational** | 106 (20.5%) | Many introduced techniques were built on top of this one |
| **Cutting-edge** | 60 (11.6%) | Introduced + built on many foundations (high synthesis) |
| **Isolated** | 5 (1.0%) | Introduced but built on no visible prior technique here |
| **Versatile** | 188 (36.4%) | Never introduced; frequently used as a foundation by others |
| **Pure-user** | 158 (30.6%) | Only used; neither introduced nor relied upon as a foundation |

**Percentile thresholds used:**
- Foundational: in\_degree ≥ 75% percentile of techniques with in\_degree > 0
- Cutting-edge: normalized\_out\_degree ≥ 75% percentile of introduced techniques with out\_degree > 0

---

## Foundational Techniques (106)

These techniques have the highest in-degree in the influence graph — the most
novel contributions in this corpus were built on top of them.

| Technique | In-degree | Foundation use (papers) | IDF tier |
|---|---:|---:|:---:|
| Large Language Models | 33 | 9 | GENERIC |
| Transformers | 16 | 7 | GENERIC |
| Diffusion Models | 12 | 5 | GENERIC |
| Chain-of-Thought | 12 | 2 | SPECIALIZED |
| Markov Decision Process | 11 | 2 | SPECIALIZED |
| In-context learning | 10 | 3 | SHARED |
| Monte Carlo Tree Search | 10 | 2 | SPECIALIZED |
| AdamW optimizer | 9 | 3 | SHARED |
| Chain-of-Thought prompting | 9 | 1 | SPECIALIZED |
| Process Reward Model | 9 | 1 | SPECIALIZED |

---

## Cutting-Edge Techniques (60)

These techniques were introduced in this corpus AND built on many prior
foundations — the highest-synthesis new contributions.

Ranked by **normalized out-degree** = raw out-degree ÷ introduced\_by\_count.
This corrects for cross-product inflation: when one paper introduces several
variant techniques (e.g. CLA2, CLA3, CLA4) while using the same foundation set,
raw out-degree is identical for each variant.  Normalized out-degree divides by
the number of papers that introduced the technique, yielding a per-paper average
foundations-relied-upon score.

> ⚠ **Variant inflation note:** Cutting-edge rankings may still be inflated by
> variant techniques introduced within a single paper (e.g. CLA2/CLA3/CLA4 all
> have introduced\_by\_count = 1, so normalization does not fully de-duplicate
> them).  Future corpus expansion and normalization audits are expected to reduce
> this effect as variant names are merged into canonical forms.

| Technique | Norm out-degree | Raw out-degree | Introduced by (papers) | IDF tier |
|---|---:|---:|---:|:---:|
| Input pre-processing technique | 15.00 | 15 | 1 | SPECIALIZED |
| Scene description benchmark | 15.00 | 15 | 1 | SPECIALIZED |
| APIBench | 8.00 | 8 | 1 | SPECIALIZED |
| AST Sub-Tree Matching | 8.00 | 8 | 1 | SPECIALIZED |
| Abstract Syntax Tree sub-tree matching | 8.00 | 8 | 1 | SPECIALIZED |
| CLA2 | 8.00 | 8 | 1 | SPECIALIZED |
| CLA3 | 8.00 | 8 | 1 | SPECIALIZED |
| CLA4 | 8.00 | 8 | 1 | SPECIALIZED |
| Cross-Layer Attention | 8.00 | 8 | 1 | SPECIALIZED |
| Gorilla | 8.00 | 8 | 1 | SPECIALIZED |
| Retriever-Aware Training | 8.00 | 8 | 1 | SPECIALIZED |
| AlphaLLM | 7.00 | 7 | 1 | SPECIALIZED |
| CIPHER | 7.00 | 7 | 1 | SPECIALIZED |
| Imagination-searching-criticizing framework | 7.00 | 7 | 1 | SPECIALIZED |
| Latent Preference Induction | 7.00 | 7 | 1 | SPECIALIZED |
| Moment Matching Distillation | 7.00 | 7 | 1 | SPECIALIZED |
| PRELUDE | 7.00 | 7 | 1 | SPECIALIZED |
| Sinkhorn Value Iteration | 7.00 | 7 | 1 | SPECIALIZED |
| Tool-augmented Outcome Reward Model | 7.00 | 7 | 1 | SPECIALIZED |
| adaptive branching | 7.00 | 7 | 1 | SPECIALIZED |

---

## Isolated Techniques (5) — top 10

Introduced in this corpus but built on no other technique visible here.
Either genuinely novel from scratch, or the foundations were not extracted.

| Technique | Introduced by (papers) | IDF tier |
|---|---:|:---:|
| MPR optimization algorithms | 1 | SPECIALIZED |
| Multi-Group Proportional Representation | 1 | SPECIALIZED |
| cross-view contrastive knowledge distillation | 1 | SPECIALIZED |
| graph-based learning framework | 1 | SPECIALIZED |
| view decoupling | 1 | SPECIALIZED |

---

## Evolution Chains

Sample chains showing what cutting-edge techniques were built on.
Format: **introduced technique** built on: foundation1 → foundation2 → …
Edge weight (×N) shown where the same A→B relationship appears in multiple papers.

- **Input pre-processing technique** built on: Blender → Claude Sonnet 3.5 → DALL-E 3 → GPT-4o → GPT-4v → Gemini Ultra 1.5
- **Scene description benchmark** built on: Blender → Claude Sonnet 3.5 → DALL-E 3 → GPT-4o → GPT-4v → Gemini Ultra 1.5
- **APIBench** built on: Abstract Syntax Tree → BM25 → Document retriever → GPT-Index → LLaMA → LLaMA-7B
- **AST Sub-Tree Matching** built on: Abstract Syntax Tree → BM25 → Document retriever → GPT-Index → LLaMA → LLaMA-7B
- **Abstract Syntax Tree sub-tree matching** built on: Abstract Syntax Tree → BM25 → Document retriever → GPT-Index → LLaMA → LLaMA-7B

---

## Notes for Re-run After Corpus Expansion

- Edge count will grow quadratically as more papers introduce techniques on shared foundations.
- Chain depth will increase: currently most chains are length 1 (A built on B only).
- Foundational threshold will shift — techniques currently at the 75th percentile may
  drop to Versatile when the distribution widens with more papers.
- Isolated count will decrease as cross-paper adoption becomes visible.
