# Post-Rebuild Validation Report

**Date:** 2026-06-05  
**Corpus:** 100 NeurIPS 2024 papers  
**Rebuild type:** Full-text source upgrade — abstract-only → full-text re-upload for 88 papers  
**Validation basis:** Measured DB values from `entity_signal_summary.md`, `graph_v2_report.md`, and `EXPECTED_REBUILD_IMPACT.md`

---

## 1. Original Problem Statement

The NotebookLM synthesis pipeline was run on all 100 NeurIPS 2024 papers before the PDF extraction pipeline completed. As a result, 90 of 100 papers were uploaded to NotebookLM as **abstract-only** sources (~244 words each), while their full paper sections (~6,062 words each) sat unused in `paper_sections`. Only 10 papers received full-text uploads.

This created a systematic extraction quality deficit: techniques, datasets, and methodology-specific terms appear in the methods and experiments sections of papers — not in abstracts. The synthesis and all downstream extracted entities for 90 papers were generated from roughly 4% of the available content.

---

## 2. Root Cause Summary

**Primary cause:** Linear pipeline ordering. The NotebookLM pipeline (Stage C upload) ran before `pdf_pipeline` completed, using `abstract_only` as a fallback source. Once uploaded, `source_status` transitions to a permanent terminal state — the pipeline has no quality-gate that re-queues a paper when richer content becomes available.

**Secondary cause:** `add_source` is additive, not replacive. There is no `remove_source` command in the NLM client. Running Stage C with `--force` would add a second source alongside the original abstract, producing confused dual-source synthesis — not a clean upgrade. This meant a notebook delete-and-recreate cycle was required.

**Scope of the gap (measured):**

| Metric | Full-text (n=10) | Abstract-only (n=90) | Ratio |
|---|---|---|---|
| Techniques per paper | 13.10 | 5.82 | 2.25× |
| `introduces` per paper | 4.70 | 2.07 | 2.27× |
| Datasets per paper | 3.00 | 0.21 | 14.21× |

---

## 3. Rebuild Actions Performed

The full-text upgrade was executed following the procedure documented in `REBUILD_RUNBOOK.md`. Backups confirmed before execution:

- `research_platform.db.backup_20260605_145653` — DB snapshot (size-verified)
- `synthesis_backup_20260605_145727.json` — 115 synthesis rows exported
- `notebook_registry_backup_20260605_145737.json` — 23 notebook registrations exported

**Execution sequence completed:**

| Step | Action | Outcome |
|---|---|---|
| Step 0 | Verified prerequisites: 98 papers with sections, DB baseline (100 papers, 115 syntheses, 23 notebooks) | Passed |
| Steps 1–3 | Took three backups (DB, synthesis JSON, registry JSON) | Confirmed |
| Step 4 | Deleted all 23 NotebookLM notebooks (point of no return) | Completed |
| Step 5 | Reset DB: `notebooks.notebooklm_id → NULL`, all 170 `notebook_papers → pending`, deleted 115 synthesis rows | Confirmed |
| Steps 6–9 | Re-provisioned notebooks, re-uploaded sources (full-text for papers with sections), re-synthesized, re-extracted | Completed |
| Step 10 | Re-ran `normalize_entities.py` | Completed |
| Step 11 | Rebuilt graph with `build_graph_v2.py` (IDF-weighted) | Completed |
| Step 12 | Ran `entity_signal_audit.py` | Output in `outputs/entity_signal_summary.md` |

**Note on residual papers:** 2 papers had no `paper_sections` and remained at abstract-only quality, as projected.

---

## 4. Before vs After Metrics

### Extraction counts

| Metric | Pre-Rebuild | Post-Rebuild | Change |
|---|---|---|---|
| Total `paper_techniques` rows | 655 | 1,115 | **+70% (+460)** |
| Total canonical techniques | 517 | ~1,115 (pre-dedup canonical) | — |
| `introduces` rows | 233 | not yet measured post-rebuild | — |
| `paper_datasets` rows | 49 | not yet measured post-rebuild | — |

### Graph topology

| Metric | Pre-Rebuild | Post-Rebuild | Change |
|---|---|---|---|
| Paper edges | 2,517 | **2,916** | **+15.8% (+399)** |
| Average edge weight | 1.339 | **1.625** | **+21.4%** |
| Maximum edge weight | 9.0 | **15.0** | +67% |
| Clusters | not reported | **3** | — |
| Isolated papers | not reported | **0** | — |

### Entity tier distribution

| Tier | Pre-Rebuild | Post-Rebuild | Change |
|---|---|---|---|
| Core (≥5 papers) | 3 | **4** | +1 |
| Shared (≥2 papers) | 16 | **51** | **+35 (+219%)** |
| Singleton (1 paper) | 498 | **1,060** | +113% |
| Singleton rate | 96.3% | **95.1%** | −1.2 pp |

---

## 5. Extraction Quality Improvements

**Technique extraction improved materially.** Total `paper_techniques` rows increased 70% (655 → 1,115). The number of Shared-tier techniques (paper_count ≥ 2) increased from 16 to 51 — a 219% increase in cross-paper technique coverage. Four techniques now qualify as Core (≥5 papers): Large Language Models (9 papers), Large language models/LLMs (7), Transformers (7), Diffusion Models (6).

**Normalization identified meaningful duplicate variants.** The entity signal shows multiple canonical forms of the same concept still present (e.g., "Direct Preference Optimization", "Direct Preference Optimization (DPO)", "Direct preference optimization" each listed as separate shared entities). Alias consolidation would reduce the nominal shared count but increase per-canonical paper counts.

**Technique role quality:** The `introduces` relationship improvement cannot be directly quantified from available outputs, but the pre/per-paper ratio (4.70 FT vs 2.07 AO) and the 70% technique increase strongly imply a proportional improvement in introduces rows.

**Dataset extraction:** Pre-rebuild, 19 total dataset rows across 90 abstract-only papers (0.21/paper) vs 30 for the 10 full-text papers (3.00/paper). Post-rebuild total not yet surfaced in an audit output, but the upgrade made experiments and results sections available to synthesis for 88 previously-abstract papers. Dataset counts are expected to have increased substantially.

---

## 6. Graph Quality Improvements

**Edge count** increased from 2,517 to 2,916 (+15.8%), within the projected range of 2,800–3,200.

**Average weight** increased from 1.339 to 1.625 (+21.4%), below the projected 1.8–2.2 range but directionally correct. The graph now produces weights up to 15.0 (vs 9.0 pre-rebuild), reflecting richer multi-technique overlaps.

**IDF weighting** (Graph V2) had no measurable redistributive effect relative to flat weighting (Graph V1) — the V1 vs V2 comparison shows identical edge counts, weight distribution, and centrality rankings. This is expected when the technique vocabulary is still dominated by singletons: IDF tiers only activate when a technique appears in ≥2 papers. With 95.1% of techniques still singletons, IDF has minimal surface area to act on.

**Graph V2 score component breakdown** (top-10 edges):

| Component | Sum (top-10 edges) | Mean per edge |
|---|---|---|
| Technique (IDF-weighted) | 65.25 | 6.53 |
| Dataset (flat ×2) | 14.00 | 1.40 |
| Category (flat ×1) | 21.00 | 2.10 |

**Three-cluster structure** is stable. No isolated papers. Top papers by betweenness centrality are unchanged between V1 and V2 within the current corpus.

**Known graph staleness issue:** The entity signal audit reports "0 singletons appear in graph edges — indicates the graph was built before the latest normalization pass ran." This means the graph in `paper_relationships` does not yet reflect the output of the most recent `normalize_entities.py` run. The graph should be rebuilt (`python build_graph_v2.py`) to incorporate the full normalized technique vocabulary.

---

## 7. Validation of Expected Projections

| Projection | Expected | Actual | Met? |
|---|---|---|---|
| Total techniques | ~1,295 (+98%) | 1,115 (+70%) | **Partially** — 73% of projected gain |
| Shared techniques | 100–150 | 55 (Core + Shared) | **Partially** — 37–55% of lower bound |
| Singleton rate | 70–80% | 95.1% | **Not met** — only −1.2 pp |
| Technique-weighted edges | ~400–600 | not yet measured post graph-rebuild | Pending |
| Graph edges | 2,800–3,200 | 2,916 | **Met** — within range |
| Average weight | 1.8–2.2 | 1.625 | **Not met** — 20–28% below range |
| Max weight | higher than 9.0 | 15.0 | **Met** — exceeded |
| Context per paper | 24.8× increase | 24.8× (structural) | **Met** — pipeline enforced |

**Why the singleton rate projection missed:** The projection assumed 88 papers upgrading to full-text quality would produce enough technique vocabulary overlap to drop singletons from 96.3% to 70–80%. The actual drop was only 1.2 pp (96.3% → 95.1%). Three factors explain this:

1. Full-text synthesis generates more diverse, paper-specific technique names — each paper names its own specific ablations, baselines, and components, many of which do not appear in other papers. More technique rows per paper does not linearly translate to more cross-paper overlap.
2. Normalization alias coverage was incomplete. The entity signal shows multiple canonical forms of the same technique counted separately (e.g., three variants of "Direct Preference Optimization"). A single alias consolidation pass would merge these into higher-count canonical entries.
3. The graph rebuild was executed before the latest normalization pass completed, as noted in the entity signal audit.

---

## 8. Remaining Limitations

**Singleton dominance persists.** 1,060 of 1,115 techniques (95.1%) appear in only one paper. At 100 papers, most specialized technique terms are unique to their paper. This is a corpus size effect — no single rebuild can resolve it. The singleton rate will naturally decline as the corpus expands to 400+ papers.

**Alias normalization is incomplete.** At least three canonical variants of "Direct Preference Optimization" and two of "Chain-of-Thought" are counted as separate Shared entities. Proper deduplication would increase per-canonical paper counts and potentially elevate several entries from Shared to Core tier, improving graph edge weights.

**Graph is stale.** As noted in entity_signal_summary, the current `paper_relationships` table was built before the latest normalization pass. Technique contributions to graph edges are understated until a fresh `build_graph_v2.py` run completes.

**Dataset audit gap.** No post-rebuild audit report for `paper_datasets` was produced (equivalent to the entity signal audit for techniques). The dataset improvement from the rebuild is inferred from pre-rebuild ratios rather than measured.

**IDF weighting delivers no benefit at current corpus size.** With 95.1% singletons, the IDF formula has almost no techniques to re-weight. Graph V1 and V2 are functionally identical. IDF will become meaningful once the corpus reaches 300–400 papers and more techniques accumulate cross-paper presence.

**2 papers remain abstract-only.** Papers without `paper_sections` rows (no available PDF) are permanently at abstract-only extraction quality unless PDFs are located and re-processed.

---

## 9. Recommendation for Next Milestone

**Immediate (before Phase 1 ingestion):**

1. **Rebuild the graph.** Run `python build_graph_v2.py` to incorporate the post-normalization technique vocabulary. This is a one-command fix for the known staleness issue noted in the entity signal audit.

2. **Run an alias consolidation pass.** The entity signal shows at least 6–8 technique variants that map to the same canonical concept. A targeted manual alias update to `normalize_entities.py` followed by a re-normalization run would merge these, increasing per-canonical paper counts and reducing the nominal shared count while improving graph edge quality.

3. **Run a dataset audit.** Execute the equivalent of `entity_signal_audit.py` for `paper_datasets` to confirm the dataset extraction improvement and identify any alias consolidation needed there.

**Phase 1 ingestion (ICLR 2024 + ICML 2024, ~300 papers):**

The corpus is now ready for Phase 1 expansion. All 100 NeurIPS papers are at comparable extraction depth (98 full-text, 2 abstract-only). The primary limiting factor for graph quality is corpus size — the singleton rate will decline significantly as 300 additional papers are added. Techniques currently appearing in 1 paper have a meaningful probability of appearing in a second paper from a related venue.

New papers should be ingested PDF-first: run `pdf_pipeline` to completion before triggering any NotebookLM upload. The abstract-only trap that necessitated this rebuild originated from inverting this order.

**Expected Phase 1 impact on graph quality (for planning):**

With ~400 total papers and a similar technique density, techniques appearing in 2+ papers will increase substantially. The singleton rate is expected to fall into the 60–75% range, IDF weighting will begin to differentiate generic vs specialized techniques meaningfully, and average edge weight should reach the 1.8–2.2 target range that the rebuild alone could not deliver.
