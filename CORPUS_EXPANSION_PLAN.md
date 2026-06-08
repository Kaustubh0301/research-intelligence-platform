# Corpus Expansion Plan

**Created:** 2026-06-05  
**Current state:** 100 papers · 1 conference (NeurIPS 2024) · 1 year  
**Target:** Phase 1 ≥ 500 papers · Phase 2 ≥ 1000 papers · Phase 3 ≥ 2000 papers  

---

## 1. Configured Conference Inventory

### Source: OpenReview (direct API, structured metadata)

| Conference | Full name | Years configured | Status |
|---|---|---|---|
| NeurIPS | Neural Information Processing Systems | 2024, 2025 | ✅ 2024 ingested (100p) |
| ICLR | International Conference on Learning Representations | 2024, 2025, 2026 | ⬜ Not ingested |
| ICML | International Conference on Machine Learning | 2024, 2025 | ⬜ Not ingested |

### Source: Semantic Scholar (bulk search API)

| Conference | Full name | Field | Years configured | Status |
|---|---|---|---|---|
| CVPR | Conference on Computer Vision and Pattern Recognition | CV | 2024, 2025 | ⬜ Not ingested |
| ECCV | European Conference on Computer Vision | CV | 2024 | ⬜ Not ingested |
| ICCV | International Conference on Computer Vision | CV | 2025 | ⬜ Not ingested (not concluded) |
| ACL | Annual Meeting of the Association for Computational Linguistics | NLP | 2024, 2025 | ⬜ Not ingested |
| EMNLP | Empirical Methods in Natural Language Processing | NLP | 2024, 2025 | ⬜ Not ingested |
| AAAI | AAAI Conference on Artificial Intelligence | AI | 2024, 2025 | ⬜ Not ingested |
| IJCAI | International Joint Conference on Artificial Intelligence | AI | 2024, 2025 | ⬜ Not ingested (2025 not published) |

**Total configured editions:** 19 (across 10 conferences, 2024–2026)

---

## 2. Conference Acceptance Counts (publicly known)

These are the full accepted-paper counts. The `--limit` flag caps ingestion well below these.

| Conference | Year | Accepted | Submitted | Selectivity | Available now |
|---|---|---|---|---|---|
| NeurIPS | 2024 | 3,587 | 15,671 | 22.9% | ✅ Yes |
| ICLR | 2024 | 2,260 | 7,262 | 31.1% | ✅ Yes |
| ICLR | 2025 | 3,277 | 11,666 | 28.1% | ✅ Yes |
| ICML | 2024 | 2,609 | 9,473 | 27.6% | ✅ Yes |
| CVPR | 2024 | 2,719 | 11,532 | 23.6% | ✅ Yes |
| ECCV | 2024 | 2,395 | 8,585 | 27.9% | ✅ Yes |
| ACL | 2024 | 1,915 | 4,691 | 40.8% | ✅ Yes |
| EMNLP | 2024 | 1,470 | ~4,000 | ~37% | ✅ Yes |
| AAAI | 2024 | 2,342 | 12,100 | 19.4% | ✅ Yes |
| AAAI | 2025 | 3,032 | 12,957 | 23.4% | ✅ Yes |
| IJCAI | 2024 | 714 | 4,566 | 15.6% | ✅ Yes |
| ICCV | 2025 | TBD | TBD | — | ❌ Not concluded |
| NeurIPS | 2025 | TBD | TBD | — | ❌ Not concluded |
| ICML | 2025 | TBD | TBD | — | ❌ Not concluded |
| ACL | 2025 | TBD | TBD | — | ❌ Not published |

**Immediately available papers** (at full ingestion, before limits): ~24,000+ across 11 editions.  
After applying the recommended per-edition limits below, Phase 1–3 targets are easily reachable.

---

## 3. NotebookLM Cost Model

Assumes max-fill target: 45 papers/notebook, 5 synthesis queries/notebook.  
`total = creates + uploads + (ceil(papers/45) × 5)`

| Total papers | Notebooks | Creates | Uploads | Synthesis calls | **Total nlm calls** |
|---|---|---|---|---|---|
| 100 (current efficient) | 3 | 3 | 100 | 15 | **118** |
| 100 (current actual) | 23 | 23 | 100 | 115 | **238** |
| 200 | 5 | 5 | 200 | 25 | **230** |
| 300 | 7 | 7 | 300 | 35 | **342** |
| 500 | 12 | 12 | 500 | 60 | **572** |
| 750 | 17 | 17 | 750 | 85 | **852** |
| 1,000 | 23 | 23 | 1,000 | 115 | **1,138** |
| 1,500 | 34 | 34 | 1,500 | 170 | **1,704** |
| 2,000 | 45 | 45 | 2,000 | 225 | **2,270** |

> **Key ratio:** upload calls dominate (88% of total at full fill). Synthesis is cheap per
> paper at scale. The current 23-notebook state for 100 papers costs 238 calls vs the
> efficient 118 — 2× waste from sparse assignment, not from the volume model itself.

**NotebookLM cookie auth:** sessions last 2–4 weeks. At 5–10 uploads/minute (rate-limited),
500 uploads takes ~1–2 hours per session. Plan for 1–2 re-auth cycles across Phase 1.

---

## 4. Recommended Expansion Plan

### Selection criteria

Papers are selected for ingestion using `--limit N` per conference edition. The limit is a
ceiling, not a target — the ingestion pipeline fetches up to N accepted papers and stops.

**Prioritisation principles:**
1. **ML conferences first** (NeurIPS, ICLR, ICML) — highest topic overlap with existing
   100 papers, so entity normalization and graph edges benefit most immediately.
2. **2024 editions before 2025** — citation enrichment via Semantic Scholar is more
   complete for older papers; 2025 papers may have <6 months of citation accumulation.
3. **NLP conferences (ACL, EMNLP) before vision (CVPR, ECCV)** — NLP papers overlap with
   LLM techniques already in the corpus; vision papers require different topic keywords.
4. **AAAI last in Phase 1** — broad AI conference, lower average citation quality signal,
   higher noise in entity extraction.

---

### Phase 1 — Target: 500 papers

**Goal:** Reach the threshold where entity audit v2 becomes meaningful
(singleton rate drops below 80%, SHARED tier ≥ 20 techniques).

| Step | Command | Expected new papers | Cumulative total |
|---|---|---|---|
| 1a | `python -m ingestion.run_ingestion -c ICLR -y 2024 --limit 150` | ~150 | ~250 |
| 1b | `python -m ingestion.enrich_citations` | — | ~250 enriched |
| 1c | `python -m ingestion.run_ingestion -c ICML -y 2024 --limit 150` | ~150 | ~400 |
| 1d | `python -m ingestion.enrich_citations` | — | ~400 enriched |
| 1e | `python -m ingestion.run_ingestion -c ACL -y 2024 --limit 100` | ~100 | ~500 |
| 1f | `python -m ingestion.enrich_citations` | — | ~500 enriched |

**After Phase 1 ingestion — run full pipeline:**

```bash
python -m pdf_pipeline.run_pipeline --limit 500
python -m notebooklm.run_pipeline --limit 50   # batch: run repeatedly until all analysed
python normalize_entities.py
python build_graph_v2.py
python entity_audit.py
python entity_signal_audit.py
python concept_selection_audit.py
```

**Phase 1 NotebookLM cost:** ~572 total calls (12 notebooks at max fill).

---

### Phase 2 — Target: 1,000 papers

**Goal:** Reach corpus size where trend detection has temporal and cross-conference signal.

| Step | Command | Expected new papers | Cumulative total |
|---|---|---|---|
| 2a | `python -m ingestion.run_ingestion -c ICLR -y 2025 --limit 150` | ~150 | ~650 |
| 2b | `python -m ingestion.run_ingestion -c EMNLP -y 2024 --limit 150` | ~150 | ~800 |
| 2c | `python -m ingestion.run_ingestion -c CVPR -y 2024 --limit 100` | ~100 | ~900 |
| 2d | `python -m ingestion.run_ingestion -c ECCV -y 2024 --limit 100` | ~100 | ~1000 |
| 2e | `python -m ingestion.enrich_citations` | — | ~1000 enriched |

**After Phase 2 — re-run full pipeline and corpus intelligence suite:**

```bash
python -m pdf_pipeline.run_pipeline --limit 1000
python -m notebooklm.run_pipeline --limit 50
python normalize_entities.py
python build_graph_v2.py
python -m corpus_intel.run_all   # re-run all 6 intelligence scripts
```

**Phase 2 NotebookLM cost:** ~1,138 total calls (23 notebooks at max fill).

---

### Phase 3 — Target: 2,000 papers

**Goal:** Full multi-conference multi-year corpus. Enables entity_type redesign, ontology,
and Graph V3.

| Step | Command | Expected new papers | Cumulative total |
|---|---|---|---|
| 3a | `python -m ingestion.run_ingestion -c AAAI -y 2024 --limit 250` | ~250 | ~1,250 |
| 3b | `python -m ingestion.run_ingestion -c AAAI -y 2025 --limit 250` | ~250 | ~1,500 |
| 3c | `python -m ingestion.run_ingestion -c IJCAI -y 2024 --limit 200` | ~200 | ~1,700 |
| 3d | `python -m ingestion.run_ingestion -c NeurIPS -y 2024 --limit 300` | ~200 new | ~1,900 |
| 3e | `python -m ingestion.run_ingestion -c ICML -y 2024 --limit 300` | ~150 new | ~2,000 |
| 3f | `python -m ingestion.enrich_citations` | — | ~2,000 enriched |

**Phase 3 NotebookLM cost:** ~2,270 total calls (45 notebooks at max fill).

---

## 5. Pipeline Capacity Verification

### NotebookLM notebook limits

| Constraint | Value | Capacity at 2,000 papers |
|---|---|---|
| Max sources per notebook | 45 | 45 notebooks needed (within range) |
| Topic slots defined | 27 | 27 × 45 = 1,215 papers per instance round |
| Multiple instances per topic | ✅ Supported | Auto-creates instance 2, 3, etc. when full |
| NotebookLM account notebook limit | Unknown (browser-based) | **Needs verification above ~50 notebooks** |

The assigner already handles overflow via `_get_or_create_notebook()` — when a topic slot
is full, it creates a second instance with the same `topic_slug`. `llm-architectures`
already demonstrates this with 2 instances (45 + 14 papers). At 2,000 papers, most topics
will need 1–2 instances.

### Topic assignment at 1,000+ papers

At 1,000 papers the 27-topic vocabulary becomes appropriately sized:
- Current: 27 topics ÷ 100 papers = 3.7 papers/topic → severe fragmentation
- Phase 1 (500p): 27 topics ÷ 500 papers = 18.5 papers/topic → approaching adequate fill
- Phase 2 (1,000p): 27 topics ÷ 1,000 papers = 37 papers/topic → near-optimal
- Phase 3 (2,000p): 27 topics ÷ 2,000 papers = 74 papers/topic → 2 instances each

**The 27-topic configuration is appropriate at 1,000+ papers.** It is currently over-fragmented
for the 100-paper corpus, but this self-corrects as the corpus grows.

The 5 currently unused topic slugs (`3d-vision`, `dialogue-qa`, `scientific-discovery`) will
activate naturally once CVPR/ECCV and EMNLP papers enter the corpus.

### Secondary assignment threshold concern

Currently 70% of papers get a secondary notebook assignment (`_SECONDARY_THRESHOLD = 0.04`).
This doubles effective notebook count at small corpus. At 1,000+ papers, the secondary
assignments are a feature (cross-topic papers get synthesis context in both relevant notebooks)
but the threshold may still be too permissive. **Recommend reviewing after Phase 1.**

---

## 6. Known Risks and Mitigations

| Risk | Severity | Mitigation |
|---|---|---|
| NotebookLM cookie expiry mid-run | Medium | Re-auth with `nlm login`; pipeline is fully resumable at any stage |
| Semantic Scholar rate limits on bulk enrichment | Low | `enrich_citations` already handles retries; run incrementally |
| OpenReview API changes between 2024 and 2025 invitations | Low | Test with `--limit 5` before bulk run |
| CVPR/ECCV via S2 returns fewer papers than expected | Low | S2 venue matching is fuzzy; check counts after `--limit 5` smoke test |
| Entity normalization alias maps become stale | Medium | Re-run `entity_audit.py` after each phase; extend alias JSON as new variants appear |
| `finance-forecasting` and other misassigned notebooks still in DB | Low | Existing syntheses remain valid; new papers will fill correct notebooks |

---

## 7. Definition of Done for Phase 1

- [ ] ICLR 2024 ingested (≥ 150 papers)
- [ ] ICML 2024 ingested (≥ 150 papers)
- [ ] ACL 2024 ingested (≥ 100 papers)
- [ ] All papers citation-enriched
- [ ] NotebookLM pipeline run on all new papers (all `paper_analyses` rows populated)
- [ ] `normalize_entities.py` re-run
- [ ] Graph V2 rebuilt
- [ ] `entity_audit.py` re-run and singleton percentage recorded
- [ ] Singleton percentage below 80% (target; currently 96%)
- [ ] SHARED-tier techniques ≥ 20 (target; currently 2)
- [ ] Corpus intelligence scripts re-run and compared against 100-paper baseline

**Only after Phase 1 is complete and validated:** begin entity_type column design.

---

## Appendix — All Ingestion Commands

### Phase 1 (500 papers)

```bash
# Step 1a — ICLR 2024
python -m ingestion.run_ingestion -c ICLR -y 2024 --limit 150

# Step 1b — enrich
python -m ingestion.enrich_citations

# Step 1c — ICML 2024
python -m ingestion.run_ingestion -c ICML -y 2024 --limit 150

# Step 1d — enrich
python -m ingestion.enrich_citations

# Step 1e — ACL 2024
python -m ingestion.run_ingestion -c ACL -y 2024 --limit 100

# Step 1f — enrich
python -m ingestion.enrich_citations

# Pipeline
python -m pdf_pipeline.run_pipeline --limit 500
python -m notebooklm.run_pipeline --limit 50  # repeat until all papers analysed
python normalize_entities.py
python build_graph_v2.py

# Audit
python entity_audit.py
python entity_signal_audit.py
python concept_selection_audit.py
```

### Phase 2 (1,000 papers)

```bash
python -m ingestion.run_ingestion -c ICLR  -y 2025 --limit 150
python -m ingestion.run_ingestion -c EMNLP -y 2024 --limit 150
python -m ingestion.run_ingestion -c CVPR  -y 2024 --limit 100
python -m ingestion.run_ingestion -c ECCV  -y 2024 --limit 100
python -m ingestion.enrich_citations
python -m pdf_pipeline.run_pipeline --limit 1000
python -m notebooklm.run_pipeline --limit 50
python normalize_entities.py
python build_graph_v2.py
python -m corpus_intel.run_all
```

### Phase 3 (2,000 papers)

```bash
python -m ingestion.run_ingestion -c AAAI   -y 2024 --limit 250
python -m ingestion.run_ingestion -c AAAI   -y 2025 --limit 250
python -m ingestion.run_ingestion -c IJCAI  -y 2024 --limit 200
python -m ingestion.run_ingestion -c NeurIPS -y 2024 --limit 300
python -m ingestion.run_ingestion -c ICML   -y 2024 --limit 300
python -m ingestion.enrich_citations
python -m pdf_pipeline.run_pipeline --limit 2000
python -m notebooklm.run_pipeline --limit 50
python normalize_entities.py
python build_graph_v2.py
python -m corpus_intel.run_all
```

### Smoke test before any bulk run

```bash
# Always verify a new conference source with 5 papers before committing to full limit
python -m ingestion.run_ingestion -c ICLR -y 2024 --limit 5
python -m ingestion.enrich_citations --force --limit 5
```
