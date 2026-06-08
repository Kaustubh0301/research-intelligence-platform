# Expected Rebuild Impact — Full-Text Re-Upload

**Date:** 2026-06-05  
**Basis:** Direct DB measurement from 100 NeurIPS 2024 papers  
**Method:** Split current extraction data by upload quality (full-text vs abstract-only), then project the upgrade gain

---

## Reconciled State of the Database

The PDF pipeline has been run on 98 of 100 papers since the original NotebookLM pipeline ran:

| Metric | Count |
|---|---|
| Papers with `pdf_local_path` and `pdf_extracted_at` | **98** |
| Papers with `paper_sections` row | **98** |
| Papers truly without sections (no PDF) | **2** |
| Papers uploaded to NotebookLM as **full text** | **10** |
| Papers uploaded to NotebookLM as **abstract-only** | **90** |

**The critical gap:** 88 papers have full-text `paper_sections` that were never used. Their NotebookLM synthesis — and therefore all their extracted techniques, datasets, categories, and methodologies — was generated from abstracts only. The sections exist in the DB but the synthesis has never seen them.

---

## 1. Context Size: Before vs After

Measured from actual DB content.

| Source type | Words | Characters | Source |
|---|---|---|---|
| Abstract-only (header + abstract) | ~244 words | ~1,220 chars | avg abstract = 194 words + ~50 header |
| Full-text (header + all sections) | ~6,062 words | ~30,311 chars | measured from 98 `paper_sections.word_count` values |
| **Ratio** | **24.8×** | **24.8×** | |

Section word counts range from 4,331 to 7,248 (avg 6,012). All papers have methodology, experiments, results, and conclusion sections available.

NotebookLM receives 24.8× more content per paper after the upgrade. The methodology, experiments, and results sections — where dataset names, specific technique parameters, baselines, and ablation studies appear — are entirely absent from the current synthesis.

---

## 2. Extraction Quality: Full-Text vs Abstract-Only

Measured by splitting current `paper_techniques`, `paper_datasets`, `paper_categories` data by upload quality.

**Group A — Full-text uploaded (n=10):** papers where `notebook_papers.source_status = 'uploaded'`  
**Group B — Abstract-only uploaded (n=90):** papers where all `notebook_papers` rows have `source_status = 'abstract_only'`

| Metric | Full-text (n=10) | Abstract-only (n=90) | Ratio |
|---|---|---|---|
| Techniques per paper | **13.10** | **5.82** | **2.25×** |
| `introduces` per paper | **4.70** | **2.07** | **2.27×** |
| `uses` per paper | **8.40** | **3.76** | **2.23×** |
| Datasets per paper | **3.00** | **0.21** | **14.21×** |
| Categories per paper | **2.70** | **2.14** | **1.26×** |

**The dataset gap is the most severe finding.** The experiments and results sections are where dataset names appear in full. Abstracts rarely name more than 1–2 benchmarks. The current 90 abstract-only papers have produced only 19 total datasets — an average of 0.21 per paper. The 10 full-text papers produced 30 datasets (3.0 per paper). After upgrade, dataset extraction will increase roughly 14× per upgraded paper.

Categories are relatively stable across both groups (2.14 vs 2.70 per paper, 1.26×) because research categories are often stated in the abstract. Techniques and especially datasets require the methodology and experiments sections.

---

## 3. Projected Totals After Upgrading 88 Papers

**Assumption:** The 88 upgradeable papers achieve the same extraction quality as the 10 full-text papers (same prompt set, similar paper length, same NotebookLM model). This is the expected outcome — the per-paper signal difference is driven purely by source context depth.

The remaining 2 papers (no `paper_sections`) stay at abstract-only quality.

| Metric | Current | After upgrade (+88 papers at FT quality) | Change |
|---|---|---|---|
| Total techniques | 655 | **~1,295** | +640 (+98%) |
| Total `introduces` rows | 233 | **~464** | +231 (+99%) |
| Total `uses` rows | 422 | **~844** | +422 (+100%) |
| Total datasets | 49 | **~294** | +245 (+500%) |
| Total categories | 220 | **~270** | +50 (+23%) |

### Calculation method

For each metric, the gain per paper is `(FT avg − AO avg) × 88 upgradeable papers`:

| Metric | FT avg | AO avg | Gain/paper | × 88 papers |
|---|---|---|---|---|
| Techniques | 13.10 | 5.82 | 7.28 | +640 |
| Introduces | 4.70 | 2.07 | 2.63 | +231 |
| Datasets | 3.00 | 0.21 | 2.79 | +245 |

---

## 4. Expected Impact on Canonical Techniques and Singletons

Current technique distribution:

| Appears in N papers | Technique count |
|---|---|
| 1 paper (singleton) | 498 |
| 2 papers | 14 |
| 3 papers | 2 |
| 5 papers | 1 |
| 7 papers | 1 |
| 9 papers | 1 |
| **Total canonical** | **517** |
| **Singleton rate** | **96.3%** |

After upgrading 88 papers to full-text, technique counts will roughly double (+640 new rows). Normalization will map many new variants to existing canonical names, increasing the paper_count of existing techniques. New techniques introduced in methodology sections will appear as new rows.

**Expected singleton rate after upgrade:**  
The 10 full-text papers already produce 13.10 techniques/paper with richer, more specific technique names. As 88 more papers produce similar output, many techniques currently appearing in only 1 paper will be found in a second paper (from similar methodology descriptions). The singleton rate is expected to drop from 96% toward **70–80%**, meaning roughly 100–150 additional shared techniques.

**Expected shared techniques (contributes to graph edges):** 19 → **~100–150**

This directly scales the number of technique-weighted graph edges.

---

## 5. Expected Impact on `introduces` Relationships

`introduces` is the most structurally important role in the graph. It is extracted when NotebookLM identifies a paper as presenting a novel method — information that lives in the methodology section, not the abstract.

Current state:
- 10 full-text papers: **47 introduces rows** (4.70/paper)
- 90 abstract-only papers: **186 introduces rows** (2.07/paper)

The abstract-only rate of 2.07/paper partly reflects what authors explicitly claim in their abstracts. Full-text synthesis yields 2.27× more introduces because NotebookLM can read the methodology section directly and identify specific sub-contributions not highlighted in the abstract.

**After upgrade: +231 introduces rows → ~464 total (+99%)**

This has downstream consequences for:
- `corpus_intel/technique_evolution.py` — directed influence graph depends on introduces relationships
- `corpus_intel/emerging.py` — Emerging classification requires introduces in one paper + uses in another
- `graph/explainer.py` — the "differences" section of relationship explanations is derived from introduces-role techniques

With 2.27× more introduces, the technique evolution directed graph gains ~2.27× more directed edges. Papers currently classified as "Novel" (introduces only) will have a higher chance of being reclassified as "Emerging" (introduces + adopted by another paper using the same technique), because the richer technique vocabulary increases pairwise overlap.

---

## 6. Expected Impact on Graph Edges

Current graph:

| Metric | Value |
|---|---|
| Paper edges | 2,517 |
| Edges with technique_score > 0 | **85** (3.4% of all edges) |
| Edges with technique_score = 0 / NULL | **2,432** (96.6%) |
| Average weight | 1.339 |
| Maximum weight | 9.0 |
| Shared techniques per edge (non-empty) | 1.0 avg |

**The current graph is almost entirely category-driven.** 96.6% of edges derive their weight purely from shared categories and methodologies. Techniques contribute to only 85 of 2,517 edges, and where they do, the shared_techniques count is 1 per edge on average.

### Why techniques contribute so little now

- 498/517 techniques (96.3%) are singletons — they cannot appear in two papers → zero technique-based edges
- The 19 shared techniques produce 85 technique-scored edges among the 10 full-text papers and their cross-paper overlaps
- The 90 abstract-only papers produce few specific technique mentions → minimal cross-paper co-occurrence

### Projected change after upgrade

After upgrading 88 papers:
- Shared (non-singleton) techniques: 19 → ~100–150
- Each new shared technique creates new technique-score contributions for all pairs of papers sharing it
- At 100 papers, a technique shared by 2 papers creates 1 new pair; shared by 3 papers creates 3 pairs, etc.

**Estimated technique-weighted edges after upgrade: 85 → ~400–600**

This is a 5–7× increase in technique-meaningful connections. The total edge count (currently 2,517) will not increase proportionally — most new technique connections are between paper pairs that already have a category-based edge. The primary effect is:

1. **Edge weight increase** for existing category-based edges that also gain technique overlap
2. **New high-weight edges** (weight > 3.0) where two papers share multiple specialized techniques
3. **Better cluster separation** — technique-weighted edges are more semantically specific than category edges; clusters defined by technique overlap will be more distinct

The IDF weighting amplifies the impact of new specialized techniques. SPECIALIZED-tier techniques (IDF ≥ 3.69) score 2× vs a flat weight. With more techniques per paper, more pairs will share at least one SPECIALIZED technique — currently the highest-weight pair is 9.0 from sharing a SPECIALIZED technique; more such pairs will emerge.

**Expected edge count change:** 2,517 → ~2,800–3,200 (11–27% more total edges from newly technique-linked paper pairs that don't currently share a category)

**Expected average weight change:** 1.339 → ~1.8–2.2 (increase driven by technique contribution activating across the graph)

---

## 7. Summary Table

| Metric | Current | After Upgrade | Change |
|---|---|---|---|
| Context per paper | ~244 words | ~6,062 words | **24.8×** |
| Total techniques | 655 | ~1,295 | **+98%** |
| Total `introduces` | 233 | ~464 | **+99%** |
| Total datasets | 49 | ~294 | **+500%** |
| Shared (non-singleton) techniques | 19 | ~100–150 | **5–8×** |
| Singleton technique rate | 96.3% | ~70–80% | **−16–26 pp** |
| Technique-weighted edges | 85 | ~400–600 | **5–7×** |
| Total graph edges | 2,517 | ~2,800–3,200 | **+11–27%** |
| Average edge weight | 1.339 | ~1.8–2.2 | **+35–64%** |

---

## 8. What the Upgrade Does NOT Change

- **Categories per paper**: ~1.26× improvement — modest, because category labels appear in abstracts
- **Paper count**: stays at 100 (no new ingestion)
- **Graph topology (clusters)**: number of clusters may shift slightly but community structure won't fundamentally change at 100 papers
- **Corpus intelligence scripts**: outputs will improve in quality but not in kind — the upgrade makes existing signals richer, not new

---

## 9. Significance for Phase 1 Ingestion

Phase 1 will add ~300 new papers (ICLR 2024 + ICML 2024). Those new papers will be ingested and processed end-to-end — PDF pipeline first, then NotebookLM. They will arrive at full-text quality by default if PDFs are available.

**Without the upgrade**, the 90 abstract-only NeurIPS papers create a permanent quality asymmetry in the graph: 10 papers at ~13 techniques each, 90 at ~6 techniques each. As the corpus grows, the 90 weaker papers will still have fewer shared techniques with the 300 new papers, weakening the graph signal for those pairs.

**With the upgrade**, all 100 NeurIPS papers enter Phase 1 at comparable extraction depth. The singleton rate drops before expansion begins. The graph built on 400 papers will have a more uniform foundation.

The upgrade should be executed before Phase 1 ingestion.
