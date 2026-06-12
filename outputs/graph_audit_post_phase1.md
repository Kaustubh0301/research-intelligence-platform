# Graph Audit: Post Phase 1 Corpus Expansion
**Date:** 2026-06-11  
**Corpus:** 1,500 papers (up from 250)  
**Graph pipeline last run at:** 250 papers

---

## Current State

| Metric | 250-paper baseline | Post Phase 1 (1,500 papers) |
|--------|:------------------:|:---------------------------:|
| Total papers | 250 | 1,500 |
| Papers with entities | 250 | 250 |
| Paper relationships | 15,978 | 15,978 (unchanged) |
| Entity relationships | 18,142 | 18,142 (unchanged) |
| Isolated papers | 0 | **1,250** |
| Connected papers | 250 | 250 |

**Critical finding: The graph has not grown.** The 1,250 new papers (NeurIPS 2024 new 400 + ICLR 2024 new 350 + ICML 2024 all 500) are fully isolated because they have no entity data (techniques or categories). The normalizer pipeline has not yet been run on them.

**Root cause:** `paper_relationships` is built from shared techniques, categories, and datasets. Papers without entity rows have nothing to link on. The graph builder produces 0 edges for any paper with no entities.

---

## Connected Paper Breakdown

| Conference | Connected | Total | Coverage |
|-----------|:---------:|:-----:|:--------:|
| NeurIPS | 100 | 500 | 20% |
| ICLR | 150 | 500 | 30% |
| ICML | 0 | 500 | 0% |
| **Total** | **250** | **1,500** | **17%** |

The 250 connected papers are exactly the original pre-expansion corpus. The graph accurately reflects entity coverage, not paper count.

---

## Edge Weight Distribution (current, 250-paper graph)

| Weight | Count | Pct |
|-------:|------:|----:|
| 1 | 11,704 | 73.3% |
| 2 | 2,769 | 17.3% |
| 3 | 626 | 3.9% |
| 4 | 226 | 1.4% |
| 5 | 131 | 0.8% |
| 6 | 69 | 0.4% |
| 7 | 178 | 1.1% |
| 8 | 146 | 0.9% |
| 9–10 | 70 | 0.4% |
| 11–15 | 55 | 0.3% |
| 16–26 | 7 | <0.1% |

**73.3% of edges have weight=1** — a single shared entity. This is expected for a 250-paper graph where most entities are fairly specialized.

---

## Degree Distribution (250 connected papers)

| Degree bucket | Papers |
|--------------:|-------:|
| 21–50 | 10 |
| 50+ | 240 |

- Min degree: 25 | Max degree: 231 | Avg degree: 127.8
- 240/250 connected papers have > 50 neighbors
- The graph is very dense within the entity-covered subgraph: effective density = **15,978 / (250×249/2) = 51.3%**

This is the key tension: the 250-paper subgraph is **highly over-connected** (51% density), but the full 1,500-paper corpus has only 250/1,500 = 16.7% coverage with the remaining 83.3% isolated.

---

## Top-K Pruning Analysis

| Threshold | Edges kept | Reduction | Use case |
|-----------|:----------:|:---------:|----------|
| weight ≥ 1 | 15,978 | 0% | Current (no pruning) |
| weight ≥ 2 | 4,274 | 73.3% | Remove single-entity matches |
| weight ≥ 3 | 1,505 | 90.6% | Strong signal only |
| weight ≥ 5 | 653 | 95.9% | Very strong signal |
| weight ≥ 7 | 453 | 97.2% | Near-duplicate detection |
| weight ≥ 10 | 80 | 99.5% | Only the tightest clusters |

**Recommendation:** At current 250-paper scale (51% density), pruning to `weight ≥ 2` is appropriate for graph visualization — removes 73% of noise edges and retains papers with at least 2 shared signals.

After normalizer runs on 1,250 new papers, revisit. At 1,500 papers with full entity coverage, weight ≥ 2 may still be the right threshold, but the avg degree will drop significantly (fewer shared entities per paper pair as vocabulary grows).

---

## Top 10 Most Connected Papers

| Degree | Paper |
|-------:|-------|
| 231 | Group and Shuffle: Efficient Structured Orthogonal Parametrization |
| 229 | Communication Efficient Distributed Training with Distributed Lion |
| 210 | On the Inductive Bias of Stacking Towards Improving Reasoning |
| 209 | Normalization Layer Per-Example Gradients are Sufficient to Predict Gradient Norms |
| 204 | Attack-Aware Noise Calibration for Differential Privacy |
| 201 | Constrained Diffusion Models via Dual Training |
| 200 | Incentivizing Quality Text Generation via Statistical Contracts |
| 196 | In-Context Learning through the Bayesian Prism |
| 195 | Realistic Evaluation of Semi-supervised Learning Algorithms in Open Environments |
| 193 | The Consensus Game: Language Model Generation via Equilibrium Search |

High-degree papers share generic techniques (attention, optimization, gradient methods) that appear in many papers. These are "hub" papers, not necessarily the most important — IDF weighting in V2 helps but doesn't fully suppress generic technique overlap.

---

## Projections After Normalizer Runs

Assuming similar entity density for new papers as existing (~10.7 techniques/categories per paper):

| Metric | Estimated post-normalizer |
|--------|:------------------------:|
| Papers with entities | 1,500 |
| Estimated entity rows | ~16,050 techniques + categories |
| Estimated paper pairs | ~1.12M |
| Expected new edges (at current sparsity) | ~25,000–60,000 |
| Expected density | 2–5% (IDF weighting will keep it sparse) |
| Expected avg degree | 35–80 (vs 127.8 now) |

As vocab grows with 6× more papers, IDF weights will suppress generic techniques more aggressively, leading to sparser edges per paper pair. The graph should become more meaningful (edges = stronger signal) at full scale.

---

## Required Actions

### Immediate (blocking graph correctness)
1. **Run normalizer** on all 1,250 new papers. Until this is done, the graph reflects only 16.7% of the corpus.
2. **Rebuild FTS entities** (`python rebuild_fts.py`) after normalizer completes.
3. **Re-run `build_edges.py`** to regenerate paper_relationships and entity_relationships.

### After rebuild
4. **Re-audit**: check new density, new degree distribution, re-evaluate top-K threshold.
5. **Consider weight ≥ 2 as default threshold** for the UI graph view (pruning 73% of weight=1 noise edges).
6. **IDF recalibration**: with 6× more entity rows, IDF denominators change — high-frequency techniques (transformers, attention, gradient) get further suppressed, which is correct behavior.

### Phase 2 graph improvements (deferred)
- Add `paper_datasets` to entity score (currently `dataset_score` is always 0)
- Consider author co-occurrence as an additional edge signal
- Top-K per-paper limit to cap hub-paper degree explosions at very large corpus sizes

---

## Summary

The graph pipeline is correct but operating on stale entity data. The Phase 1 corpus expansion added 1,250 papers that are all isolated until the normalizer runs. **No graph changes are needed before running the normalizer** — `build_edges.py` will naturally incorporate all papers once entity rows exist for them. The critical path is:

```
run normalizer (1250 papers) → rebuild_fts.py → build_edges.py → re-audit
```
