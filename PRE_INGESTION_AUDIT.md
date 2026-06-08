# Pre-Ingestion Audit

**Date:** 2026-06-05  
**Branch:** `notebooklm-pipeline`  
**Purpose:** Validate operational readiness before Phase 1 corpus expansion.  
**Auditor:** Pre-ingestion automated audit pass

---

## 1. Current Corpus State

| Metric | Value |
|---|---|
| Total papers | **100** |
| Conferences ingested | **NeurIPS 2024 only** |
| Conferences in DB registry | **1** (NeurIPS) |
| Conference editions in DB | **1** (NeurIPS 2024) |
| Papers with analysis | **100 / 100** (100%) |
| Papers without analysis | **0** |
| Pipeline errors | **0** |

---

## 2. Current Notebook State

| Metric | Value |
|---|---|
| Total notebooks | **23** |
| Active notebooks | **23** |
| Average notebook fill | **7.4 sources / 45 max** (16%) |
| Fullest notebook | `llm-architectures` instance 1: 45/45 (full) |
| Second instance | `llm-architectures` instance 2: 14/45 |
| Emptiest notebooks | `vision-language`, `code-generation`, `machine-translation`, `retrieval-augmented`, `finance-forecasting`: 1/45 each |
| Total notebook_papers rows | **170** |
| Papers uploaded (full text) | **20** (12%) |
| Papers uploaded (abstract only) | **150** (88%) |
| Total syntheses | **115** (5 per notebook × 23) |

### Notebook fill by topic

| Topic slug | Sources | Capacity | Fill % |
|---|---|---|---|
| llm-architectures (inst 1) | 45 | 45 | 100% FULL |
| reinforcement-learning | 16 | 45 | 36% |
| information-extraction | 14 | 45 | 31% |
| optimization-training | 14 | 45 | 31% |
| llm-architectures (inst 2) | 14 | 45 | 31% |
| llm-evaluation | 9 | 45 | 20% |
| theory-generalization | 7 | 45 | 16% |
| image-generation | 6 | 45 | 13% |
| llm-alignment | 6 | 45 | 13% |
| agentic-ai | 5 | 45 | 11% |
| ai-safety | 5 | 45 | 11% |
| llm-efficiency | 5 | 45 | 11% |
| graph-neural-networks | 5 | 45 | 11% |
| fairness-ethics | 4 | 45 | 9% |
| llm-reasoning | 3 | 45 | 7% |
| object-detection | 3 | 45 | 7% |
| biomedical-ai | 2 | 45 | 4% |
| robotics | 2 | 45 | 4% |
| vision-language | 1 | 45 | 2% |
| code-generation | 1 | 45 | 2% |
| machine-translation | 1 | 45 | 2% |
| retrieval-augmented | 1 | 45 | 2% |
| finance-forecasting | 1 | 45 | 2% (known misassignment) |

**Key observation:** 23 notebooks for 100 papers is ~2× inefficient vs optimal fill. Optimal at 100 papers is 3 notebooks (ceil(100/45)). New papers will primarily fill existing sparse notebooks before creating new ones.

---

## 3. NotebookLM Call Accounting (Calls Used So Far)

| Call type | Count |
|---|---|
| Notebook creates | 23 |
| Source uploads | 170 |
| Synthesis queries | 115 |
| **Total calls used** | **308** |

**Note:** The optimal efficient baseline at 100 papers is 118 calls (3 notebooks × create + 100 uploads + 15 synths). Current 308 calls reflects sparse assignment from NeurIPS-only corpus. The waste does not affect correctness — all 100 papers are analyzed.

---

## 4. NotebookLM Call Estimates — Incremental

These estimates use the formula from `CORPUS_EXPANSION_PLAN.md`:  
`incremental_calls = new_notebooks + new_uploads + (new_notebooks × 5)`

At max-fill target (45 papers/notebook), `new_notebooks = ceil(new_papers / 45)`.

| Target expansion | New papers | New notebooks | New creates | New uploads | New synths | **Incremental calls** | Cumulative total |
|---|---|---|---|---|---|---|---|
| +100 papers | 100 | 3 | 3 | 100 | 15 | **118** | 426 |
| +300 papers | 300 | 7 | 7 | 300 | 35 | **342** | 650 |
| +500 papers | 500 | 12 | 12 | 500 | 60 | **572** | 880 |
| +900 papers (→1000 total) | 900 | 20 | 20 | 900 | 100 | **1,020** | 1,328 |

**Phase 1 target (+300 papers, ICLR 2024 + ICML 2024):** ~342 incremental calls.

---

## 5. Conference Configuration Readiness

### OpenReview conferences (ICLR, ICML, NeurIPS)

| Conference | Year | Config status | OpenReview ID | Notes |
|---|---|---|---|---|
| ICLR | 2024 | ✅ Configured | `ICLR.cc/2024/Conference` | Phase 1 target |
| ICLR | 2025 | ✅ Configured | `ICLR.cc/2025/Conference` | Phase 2 |
| ICLR | 2026 | ✅ Configured | `ICLR.cc/2026/Conference` | Future |
| ICML | 2024 | ✅ Configured | `ICML.cc/2024/Conference` | Phase 1 target |
| ICML | 2025 | ✅ Configured | `ICML.cc/2025/Conference` | Phase 2 |
| NeurIPS | 2024 | ✅ In DB | `NeurIPS.cc/2024/Conference` | Already ingested |
| NeurIPS | 2025 | ✅ Configured | `NeurIPS.cc/2025/Conference` | Not concluded |

**Finding:** ICLR and ICML are not yet registered in the `conferences` or `conference_editions` DB tables. They exist only in `conferences_config.py`. The ingestion script creates them on first run — this is expected behavior (`upsert_conference` / `upsert_conference_edition`). No pre-work needed.

### Semantic Scholar conferences (Phase 2+)

| Conference | Year | Config status | S2 venue key |
|---|---|---|---|
| CVPR | 2024 | ✅ Configured | `CVPR` |
| ECCV | 2024 | ✅ Configured | `ECCV` |
| ACL | 2024 | ✅ Configured | `ACL` |
| EMNLP | 2024 | ✅ Configured | `EMNLP` |
| AAAI | 2024 | ✅ Configured | `AAAI` |
| AAAI | 2025 | ✅ Configured | `AAAI` |
| IJCAI | 2024 | ✅ Configured | `IJCAI` |
| ICCV | 2025 | ✅ Configured | `ICCV` |

**Finding:** S2 venue matching is fuzzy — CVPR, ECCV, ACL, EMNLP, AAAI have never been tested against this codebase. Require smoke test (`--limit 5`) before bulk run.

---

## 6. Ingestion Script Readiness

| Script | Status | Notes |
|---|---|---|
| `ingestion/run_ingestion.py` | ✅ Ready | Handles `--conference`, `--year`, `--limit`, `--all`, `--list` |
| `ingestion/fetch_openreview.py` | ✅ Ready | Tested against NeurIPS 2024; ICLR/ICML use same OpenReview API |
| `ingestion/fetch_semantic_scholar.py` | ⚠️ Untested at scale | Never run for Phase 1 conferences; smoke test required |
| `ingestion/enrich_citations.py` | ✅ Ready | Tested; handles retries; idempotent |
| `ingestion/store.py` | ✅ Ready | Idempotent upsert; safe to re-run |

---

## 7. NotebookLM Pipeline Readiness

| Component | Status | Notes |
|---|---|---|
| `nlm` CLI auth | ✅ VALID | `nlm notebook list` returns 23 notebooks — auth cookie is live |
| `notebooklm/assigner.py` | ✅ Ready | 25 topic keywords configured; overflow handling tested (`llm-architectures` has 2 instances) |
| `notebooklm/client.py` | ✅ Ready | All 5 commands validated in prior runs |
| `notebooklm/pipeline.py` | ✅ Ready | 5-stage orchestrator (A→B→C→D→E); fully resumable per stage |
| `notebooklm/run_pipeline.py` | ✅ Ready | `--limit` flag for batching; `--stage` flag for partial runs |
| Source text quality | ⚠️ Degraded | 150/170 assignments used abstract_only (88%). PDFs required for full-text upload. |
| `pdf_pipeline` | ⚠️ Partially ready | 10/100 papers have segmented PDFs. Must run before NotebookLM for quality. |

**Critical finding:** The overwhelming majority of current analyses (88%) are from abstract-only sources, not full-text PDFs. Running the PDF pipeline before NotebookLM on new papers is strongly recommended.

---

## 8. Database Capacity Readiness

| Check | Status | Notes |
|---|---|---|
| SQLite file | ✅ OK | `research_platform.db` — no size issues at current scale |
| Schema completeness | ✅ All migrations applied | Migrations 003–009 all present |
| Max migrations | `009_graph_v2.sql` | No pending migrations |
| Idempotency | ✅ Safe | All ingestion, normalization, and graph scripts are re-runnable |
| Foreign key integrity | ✅ OK | 0 pipeline errors; all 100 analyses present |

At 500 papers, SQLite remains fully adequate. PostgreSQL migration is deferred until ~500+ (see Architecture Decision 2).

---

## 9. Known Anomalies

| Anomaly | Severity | Action |
|---|---|---|
| `finance-forecasting` notebook: 1 mis-assigned paper | Low | Do not delete; leave in place — re-assignment is not needed for expansion |
| 3 papers with `semantic_scholar_id = NULL` | Low | Will be retried during `enrich_citations` run |
| 150/170 notebook_papers use abstract_only | Medium | Run `pdf_pipeline` before NotebookLM for new papers |
| 23 notebooks sparse (avg 7.4 fill) | Expected | Will self-fill as corpus grows; no action needed |
| Only NeurIPS 2024 in `conferences`/`conference_editions` tables | Expected | ICLR and ICML rows auto-created on first ingestion run |

---

## 10. Readiness Verdict

| Component | Ready? |
|---|---|
| Conference configs | ✅ YES — all Phase 1 targets configured |
| Ingestion scripts | ✅ YES — OpenReview path well-tested |
| NotebookLM auth | ✅ YES — 23 live notebooks, cookie valid |
| NotebookLM pipeline | ✅ YES — all stages functional |
| Database capacity | ✅ YES — SQLite adequate through 500 papers |
| PDF pipeline | ⚠️ RUN FIRST — needed for full-text quality on new papers |
| S2 conferences | ⚠️ SMOKE TEST FIRST — not Phase 1, but flag for Phase 2 |

**Conclusion: Phase 1 is operationally ready to execute.** The only pre-condition is running the PDF pipeline on existing papers before the NotebookLM run (for quality), which is already in the execution plan.
