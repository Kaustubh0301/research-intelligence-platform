# Emerging Techniques — Corpus Intelligence Report

**Generated:** 2026-06-05 06:50 UTC
**Corpus:** 100 papers
**Canonical techniques analysed:** 517

> **Corpus size caveat:** With 100 papers from a single conference-year,
> "Emerging" means introduced in one NeurIPS 2024 paper and adopted by at least one
> other.  Temporal trajectory (multi-year trends) requires corpus expansion.
> Re-run this script after ingesting all conferences for richer signal.

---

## Stage Distribution

| Stage | Count | % of techniques |
|---|---:|---:|
| Emerging | 0 | 0.0% |
| Novel | 203 | 39.3% |
| Established | 311 | 60.2% |
| Foundational | 3 | 0.6% |
| Referenced | 0 | 0.0% |
| **Total** | **517** | 100% |

---

## Stage Definitions

| Stage | Definition |
|---|---|
| **Emerging** | Introduced in ≥1 paper AND used by ≥1 *different* paper — active adoption underway |
| **Novel** | Introduced in ≥1 paper; not yet adopted by other papers in this corpus |
| **Established** | Used in ≥1 paper; nobody introduces it here — mature baseline method |
| **Foundational** | Established + GENERIC IDF tier (appears in ≥5 papers at N=100) — ubiquitous baseline |
| **Referenced** | Only appears as a comparison target or critique subject |

---

## Emerging Techniques (0)

These techniques were introduced in this corpus and are already being built upon
by other papers — the strongest signal of active adoption.

_No Emerging techniques at current corpus size._

---

## Novel Techniques — top 10 of 203 (203 total)

These techniques were introduced in this corpus but not yet adopted by other papers.
They are candidates for Emerging status as the corpus grows.

| Technique | Introduced by | IDF tier |
|---|---:|:---:|
| AID | 1 paper(s) | SPECIALIZED |
| APIBench | 1 paper(s) | SPECIALIZED |
| AST Sub-Tree Matching | 1 paper(s) | SPECIALIZED |
| Abstract Syntax Tree sub-tree matching | 1 paper(s) | SPECIALIZED |
| ActAnywhere | 1 paper(s) | SPECIALIZED |
| Adversarial CVaR evaluation | 1 paper(s) | SPECIALIZED |
| AlphaLLM | 1 paper(s) | SPECIALIZED |
| Attack-aware noise calibration | 1 paper(s) | SPECIALIZED |
| Autoregressive image diffusion model | 1 paper(s) | SPECIALIZED |
| Bayesian approach for learning causal graphs with limited interventional samples | 1 paper(s) | SPECIALIZED |

**Top 5 Novel — introducing papers:**

- **AID**
  - Introduced in: Autoregressive Image Diffusion: Generation of Image Sequence and…
- **APIBench**
  - Introduced in: Gorilla: Large Language Model Connected with Massive APIs
- **AST Sub-Tree Matching**
  - Introduced in: Gorilla: Large Language Model Connected with Massive APIs
- **Abstract Syntax Tree sub-tree matching**
  - Introduced in: Gorilla: Large Language Model Connected with Massive APIs
- **ActAnywhere**
  - Introduced in: ActAnywhere: Subject-Aware Video Background Generation

---

## Foundational Techniques (3)

Ubiquitous baselines that appear in many papers but are never introduced here.
GENERIC IDF tier: idf < 3.00, corresponding to paper\_count ≥ 5 at N=100.

| Technique | Papers using it | IDF score |
|---|---:|---:|
| Large Language Models | 9 | 2.408 |
| Transformers | 7 | 2.659 |
| Diffusion Models | 5 | 2.996 |

---

## Summary

| Stage | Count | Interpretation |
|---|---:|---|
| Emerging | 0 | Techniques with active adoption signal |
| Novel | 203 | Introduced but awaiting adoption |
| Established | 311 | Mature methods, in active use |
| Foundational | 3 | Ubiquitous baselines (GENERIC tier) |
| Referenced | 0 | Mentioned as comparisons only |

The high Novel count reflects the 100-paper single-conference corpus: most
introduced techniques appear in only one paper, leaving no other NeurIPS 2024 paper
to adopt them.  This ratio will improve substantially after multi-conference ingestion.
