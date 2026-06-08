# Phase 1 Expansion Runbook

**Date:** 2026-06-05  
**Current corpus:** 100 papers · 1 conference (NeurIPS 2024) · 23 notebooks (post-rebuild)  
**Target:** 400 papers (ICLR 2024 + ICML 2024) in this runbook, with optional extension to 500 (+ ACL 2024)  
**Status:** AWAITING APPROVAL — do not execute without review  
**Prerequisites:** Rebuild complete, all 23 notebooks live, 98 papers at full-text quality

---

## 1. Current Corpus Composition

| Metric | Value | Source |
|---|---|---|
| Total papers | 100 | NeurIPS 2024 |
| Full-text papers | 98 | PDF + sections in DB |
| Abstract-only papers | 2 | No PDF available |
| paper_analyses rows | 100 | 100% coverage |
| paper_techniques rows | 1,115 | Post-rebuild extraction |
| Shared/Core techniques | 55 | entity_signal_audit |
| Singleton rate | 95.1% | entity_signal_audit |
| paper_relationships edges | 2,916 | build_graph_v2.py |
| Average edge weight | 1.625 | graph_v2_report.md |
| Clusters | 3 | graph_v2_report.md |
| Active notebooks | 23 | Post-rebuild |
| notebook_papers rows | ~170 | 100 papers × ~1.7 avg assignments |
| NLM calls to date | ~588 | 308 original + ~280 rebuild |

---

## 2. Notebook Capacity Analysis

### Current fill state

| Metric | Value |
|---|---|
| Active notebooks | 23 |
| Max papers per notebook | 45 |
| Raw capacity | 23 × 45 = **1,035 slots** |
| Slots currently used | ~170 (100 papers × 1.7 avg assignments) |
| Slots remaining | **~865** |
| Average fill per notebook | 7.4 / 45 = **16.4%** |

The corpus was rebuilt from scratch for 100 papers across 27 topic slots. Most notebooks are very sparse — on average 7.4 papers against a 45-paper capacity. This spare capacity is the primary resource for Phase 1 expansion.

### Assignment model

The assigner produces a primary and (70% of the time) a secondary notebook assignment per paper. At the current secondary threshold (`_SECONDARY_THRESHOLD = 0.04`), roughly 1.7 notebook_papers rows are created per paper ingested. This is the multiplier used throughout this document.

**At +300 papers (to 400 total):**
- New notebook_papers needed: 300 × 1.7 = **~510 new slots**
- Available slots: 865
- Verdict: **existing notebooks absorb all assignments** — no new notebooks required on aggregate

However, topic-level distribution is not uniform. Existing notebooks hold NeurIPS papers that skew toward LLM, theory, and optimization topics. ICLR/ICML papers will reinforce the same topics. Some notebooks (particularly `llm-architectures`, `efficient-inference`, `optimization-theory`) will fill faster than others.

**Estimated new notebooks needed by phase:**

| Phase | New papers | New slots needed | Overflow → new notebooks |
|---|---|---|---|
| +100 (to 200) | 100 | ~170 | 0–1 (borderline LLM overflow) |
| +300 (to 400) | 300 | ~510 | **5–8** (LLM, optimization, generative) |
| +400 (to 500, with ACL) | 400 | ~680 | **6–10** (adds NLP topics) |
| +900 (to 1,000) | 900 | ~1,530 | **~15** new; total ~38 notebooks |

Stage B (`--stage provision`) handles overflow automatically: when a topic's current notebook reaches 45 sources, it creates a second instance with the same `topic_slug`. No manual intervention needed.

### Upper-bound concern: NLM account notebook limit

NotebookLM has an unverified per-account notebook limit (noted as "Unknown" in CORPUS_EXPANSION_PLAN). At 23 notebooks now, Phase 1 to 400 papers adds 5–8 more → ~31 total. This is well within any reasonable limit. At 1,000 papers the total reaches ~38. Verify the limit before Phase 2 begins if concerns arise.

---

## 3. Maximum Safe Batch Size

**Recommended batch size: 50 papers per pipeline run.**

Rationale:

| Factor | Constraint | Derived limit |
|---|---|---|
| Cookie auth session | 2–4 weeks, not a rate concern | Not the binding constraint |
| Source upload rate | ~5–10 uploads/min (rate-limited by NLM client) | 50 uploads = 5–10 min |
| Synthesis duration | ~30s/query × 5 queries × notebooks touched | 50 papers → ~5 notebooks → ~12 min |
| Total per-batch time | Upload + synthesis | ~20–25 min per batch of 50 |
| Auth failure surface area | Longer run = higher risk of mid-run expiry | 50 keeps single-run exposure low |

**For a single continuous run with auth pre-confirmed,** batches of 100 are safe. Do not exceed 150 papers per run without an explicit auth check between stages — synthesis stage takes significantly longer and sessions can expire mid-query.

**Between-batch checkpoints** (verify after each batch of 50):
```bash
python3 -c "
import sqlite3; c=sqlite3.connect('research_platform.db').cursor()
c.execute('SELECT source_status, COUNT(*) FROM notebook_papers GROUP BY source_status')
print(dict(c.fetchall()))
c.execute('SELECT COUNT(*) FROM paper_analyses')
print('Analyses:', c.fetchone()[0])
"
```

---

## 4. Existing Notebook Absorption Capacity

**Yes — existing notebooks can absorb all Phase 1 papers without requiring new notebooks on aggregate.** The 865 remaining slots exceed the 510 needed for +300 papers.

However, for full extraction quality, **existing notebooks must be re-synthesized after new papers are uploaded.** This is the most important design decision in this runbook.

### The synthesis coverage gap

Stage D without `--force` skips notebooks that already have `notebook_syntheses` rows. All 23 current notebooks have synthesis rows from the rebuild. When new papers are uploaded to these notebooks (Stage C), those notebooks will NOT be re-synthesized by default. Result: new papers in existing notebooks have no extraction data.

Two models exist:

**Model A — Minimal (new notebooks only)**  
Stage D runs without `--force`, synthesizing only newly created notebooks.  
New papers in existing notebooks: uploaded but NOT synthesized → NOT extracted.  
Coverage: 100% for papers landing in new notebooks, 0% for papers in existing notebooks.

**Model B — Full coverage (re-synthesize all touched notebooks)**  
After Stage C uploads, run Stage D `--force` on all notebooks that received new papers.  
Coverage: 100% for all papers in all notebooks.

**Recommendation: use Model B for all expansion phases.** Model A produces systematic extraction gaps: the most-populated topic notebooks (LLM, optimization) will contain many new papers with zero analysis data, exactly where cross-paper signal is highest.

The additional synthesis cost of Model B over Model A:

| Phase | Model A synthesis | Model B synthesis | Δ calls |
|---|---|---|---|
| +100 papers | ~5 (1 new notebook) | ~95 (~19 notebooks touched) | +90 |
| +300 papers | ~35 (7 new notebooks) | ~150 (~30 notebooks touched) | +115 |
| +900 papers | ~75 (~15 new notebooks) | ~190 (38 total notebooks) | +115 |

The re-synthesis overhead is modest: ~90–115 additional calls per phase. At NLM's synthesis rate (~30s/query), this adds ~45–75 minutes per phase. This is the correct tradeoff for full extraction coverage.

---

## 5. New Notebook Partitions Required

### Phase 1 (+300 papers to 400 total)

**Expected new notebooks: 5–8.** Stage B creates them automatically when topic notebooks overflow. No pre-provisioning is needed.

Topics most likely to need a second notebook instance:
- `llm-architectures` — already had 2 instances at 100 papers; will likely need a third
- `efficient-inference` — high ICLR/ICML presence
- `optimization-theory` — perennial ML conference topic
- Possibly `generative-models`, `reinforcement-learning`

Topics likely to receive their first notebook (new topic activation):
- `3d-vision` — will activate with CVPR/ECCV papers in Phase 2, not Phase 1
- `dialogue-qa` — may activate with ACL 2024 (if ACL is included)
- `scientific-discovery` — unlikely from ICLR/ICML

### Phase 2 (+400–500 more papers to 1,000 total)

**Expected new notebooks: ~12–15.** EMNLP/CVPR/ECCV activate new topics. Total notebook count reaches ~35–38. This is still well below any known NotebookLM limit.

---

## 6. NLM Call Volume Estimates

All estimates use **Model B (full coverage, re-synthesize touched notebooks)**.  
Minimal (Model A) estimates shown in parentheses for reference.

### Definitions

| Term | Meaning |
|---|---|
| `uploads` | Stage C: one `nlm source add` call per notebook_paper assignment |
| `creates` | Stage B: one `nlm notebook create` call per new notebook |
| `synthesis` | Stage D: 5 `nlm query` calls per notebook (re-synthesized under Model B) |
| `incremental` | Cost of this phase only, not cumulative |
| `cumulative` | Total NLM calls from project start |

### Scenario A: +100 papers → 200 total

**Target configuration:** ICLR 2024, `--limit 100`

| Call type | Count | Notes |
|---|---|---|
| Source uploads | ~170 | 100 papers × 1.7 avg assignments |
| Notebook creates | 0–1 | 1 only if LLM notebooks fully overflow |
| Synthesis (Model B) | ~95 | ~19 notebooks touched × 5 prompts |
| Synthesis (Model A) | ~5 | 1 new notebook only |
| **Total (Model B)** | **~266** | |
| **Total (Model A)** | **~176** | |
| **Cumulative (Model B)** | **~854** | Current ~588 + ~266 |

**Runtime estimate:** ~2–3 hours (upload: ~30 min, synthesis: ~48 min, extraction: ~15 min)

---

### Scenario B: +300 papers → 400 total ← RECOMMENDED Phase 1

**Target configuration:** ICLR 2024 (`--limit 150`) + ICML 2024 (`--limit 150`)

| Call type | Count | Notes |
|---|---|---|
| Source uploads | ~510 | 300 papers × 1.7 avg assignments |
| Notebook creates | ~7 | Stage B auto-provisions on overflow |
| Synthesis (Model B) | ~150 | ~23 existing touched × 5 + 7 new × 5 |
| Synthesis (Model A) | ~35 | 7 new notebooks only |
| **Total (Model B)** | **~667** | |
| **Total (Model A)** | **~552** | |
| **Cumulative (Model B)** | **~1,255** | Current ~588 + ~667 |

**Runtime estimate:** ~4–6 hours (upload: ~85 min, synthesis: ~75 min, extraction: ~30 min)  
**Batching:** 6 batches of 50 papers. Run one batch per sitting with checkpoint verification.

---

### Scenario C: +400 papers → 500 total (Phase 1 extended with ACL 2024)

**Target configuration:** ICLR 2024 (150) + ICML 2024 (150) + ACL 2024 (100)

| Call type | Count | Notes |
|---|---|---|
| Source uploads | ~680 | 400 papers × 1.7 avg assignments |
| Notebook creates | ~9 | More NLP topic notebooks needed |
| Synthesis (Model B) | ~160 | ~23 existing + 9 new × 5 |
| Synthesis (Model A) | ~45 | 9 new notebooks only |
| **Total (Model B)** | **~849** | |
| **Total (Model A)** | **~734** | |
| **Cumulative (Model B)** | **~1,437** | Current ~588 + ~849 |

**Runtime estimate:** ~5–7 hours total

---

### Scenario D: +900 papers → 1,000 total (Phase 2)

**Target configuration:** Phase 1 (500 total) + ICLR 2025 (150) + EMNLP 2024 (150) + CVPR 2024 (100) + ECCV 2024 (100)

| Call type | Count | Notes |
|---|---|---|
| Source uploads (Phase 1 only) | ~680 | Already counted in Scenario C |
| Source uploads (Phase 2 only) | ~850 | 500 new × 1.7 |
| Notebook creates (Phase 2 only) | ~12 | Adds CV/NLP topics; total ~44 notebooks |
| Synthesis Phase 1 (Model B) | ~160 | From Scenario C |
| Synthesis Phase 2 (Model B) | ~220 | ~44 total notebooks × 5 |
| **Phase 1 total (Model B)** | **~849** | |
| **Phase 2 incremental (Model B)** | **~1,082** | 850 + 12 + 220 |
| **Full +900 papers total (Model B)** | **~1,931** | Phased |
| **Cumulative at 1,000 papers** | **~2,519** | |

**Runtime for +900 papers (phased):** ~12–16 hours total across Phase 1 + Phase 2 sessions

---

### Summary table

| Scenario | New papers | Total papers | New notebooks | Incremental NLM calls | Cumulative NLM calls |
|---|---|---|---|---|---|
| +100 | 100 | 200 | 0–1 | ~266 | ~854 |
| **+300 (recommended)** | **300** | **400** | **~7** | **~667** | **~1,255** |
| +400 (Phase 1 + ACL) | 400 | 500 | ~9 | ~849 | ~1,437 |
| +900 (to 1,000, phased) | 900 | 1,000 | ~27 total | ~1,931 phased | ~2,519 |

---

## 7. Recommended Target Corpus Size

**Recommended next wave: 400 papers total (ICLR 2024 + ICML 2024 only).**

Rationale:

| Factor | Evidence | Verdict for 400 |
|---|---|---|
| Singleton rate target | Needs <80%; NORMALIZATION_V2 audit shows ~87–88% achievable floor with perfect normalization at 100 papers | 400 papers expected to reach 75–85% singleton rate, meeting target |
| Shared-tier techniques | Target ≥20; currently 55 at 100 papers with rebuild | 400 papers should produce 100–180 shared techniques |
| Graph edge quality | Average weight 1.625 vs 1.8–2.2 target; IDF needs more shared techniques | 400 papers expected to reach 1.8–2.1 |
| NLM call budget | ~667 incremental calls; manageable in 3–4 sessions | Acceptable |
| Conference alignment | ICLR + ICML maximize topic overlap with NeurIPS; entity normalization benefits most | High signal-per-call |
| ACL 2024 inclusion | ACL adds NLP papers that activate new topic slots; singleton benefit delayed until cross-conference overlap builds | Defer ACL to Phase 1b after entity audit at 400 |

**Why not +100 (200 papers)?**  
Insufficient to move the singleton rate meaningfully. NORMALIZATION_V2 audit shows the singleton rate floor at 100 papers is ~87–88% even with perfect normalization. Adding only 100 more papers from a related conference (ICLR) will move the rate modestly but won't reach the 80% milestone target. The 400-paper mark is the minimum threshold where entity audit v2 becomes meaningful.

**Why not +900 (1,000 papers) now?**  
Phase 2 (EMNLP, CVPR, ECCV) introduces conference types not currently represented in the corpus. Topic vocabulary, entity normalization, and alias maps all need extension before those conferences are ingested. The entity audit at 400 papers will reveal which normalization gaps are highest priority and which alias categories need adding before NLP/CV paper extraction.

**The normalization improvements from NORMALIZATION_V2_AUDIT must be applied before Phase 1 begins.** New paper extraction will produce the same alias variants that currently inflate the singleton count. Fixing normalization first means Phase 1 papers contribute to the correct canonical counts from the start.

---

## 8. Pre-Ingestion Steps (Apply Before Any New Paper Ingestion)

These are required to fix the current normalization gaps identified in NORMALIZATION_V2_AUDIT.md. They take ~15 minutes and have no irreversible operations.

### Step 0A — Fix the parenthetical acronym regex

**File:** `normalize/rules.py`, line 37.

Change:
```python
_PAREN_ACRONYM_RE = re.compile(r"\s*\([A-Z][A-Z0-9\-]+\)\s*$")
```
to:
```python
_PAREN_ACRONYM_RE = re.compile(r"\s*\([A-Z][A-Za-z0-9\-]+\)\s*$")
```

This fixes the bug causing "Large Language Models" and "Large language models (LLMs)" to remain as two separate Core-tier canonicals. It also fixes ViTs, GNNs, MLPs, and all future mixed-case acronym parentheticals.

### Step 0B — Add missing alias entries

Add to `normalize/technique_aliases.json` before running normalization:

Key additions (minimum required before Phase 1):
- `"sgd"` → `"Stochastic gradient descent"` (raises to 6 papers, Core tier)
- `"ppo"` → `"Proximal Policy Optimization"` (raises to 5 papers, Core tier)
- `"low-rank adaptation"` / `"low rank adaptation"` → `"LoRA"` (raises to ~5 papers, Core tier)
- `"resnets"` / `"residual network"` → `"ResNet"` (raises to ~5 papers, Core tier)
- `"direct preference optimization (dpo)"` / `"direct preference optimization"` (lowercase) → `"Direct Preference Optimization"` (merges 3 shared entries)
- `"chain-of-thought (cot)"` / `"chain-of-thought prompting"` / `"chain-of-thought (cot) prompting"` → `"Chain-of-Thought"` (merges 3 shared entries)
- `"graph convolutional networks"` → `"Graph convolutional network"` (merges 2 shared entries, raises to ~6 papers, Core tier)

Full alias additions are specified in NORMALIZATION_V2_AUDIT.md, Rank 4 and Rank 5 recommendations.

### Step 0C — Extend Pass 2 paren-strip in rules.py

**File:** `normalize/rules.py`, `case_fold_canonical()`.

Change the group key from `name.lower()` to `_PAREN_ACRONYM_RE.sub("", name).strip().lower()`.

This collapses 50+ singleton pairs of the form `"Foo (BAR)"` / `"Foo"` without requiring individual alias entries.

### Step 0D — Run `normalize_entities.py --force`

```bash
python normalize_entities.py --force
```

Re-processes all 1,115 technique rows simultaneously. Fixes the ~30 case-fold drift pairs where the same concept was assigned different canonicals in separate incremental runs.

**Checkpoint:**
```bash
python3 -c "
import sqlite3; c=sqlite3.connect('research_platform.db').cursor()
c.execute('SELECT COUNT(*) FROM paper_techniques WHERE canonical_name IS NULL')
print('Missing canonical:', c.fetchone()[0])
c.execute('SELECT COUNT(DISTINCT canonical_name) FROM paper_techniques')
print('Distinct canonicals:', c.fetchone()[0])
"
# Expected: 0 missing; distinct canonicals lower than 1,115 (merges collapsed)
```

### Step 0E — Rebuild graph

```bash
python build_graph_v2.py
```

Incorporates the post-normalization technique vocabulary. Fixes the known staleness noted in entity_signal_summary ("0 singletons appear in graph edges — indicates the graph was built before the latest normalization pass ran").

**Checkpoint — verify improvement:**
```bash
python entity_signal_audit.py
# Expected: singleton rate lower than 95.1%; Core/Shared count higher than 55
```

**Estimated singleton rate after Steps 0A–0E:** ~87–90% (down from 95.1%).  
**Estimated new Core-tier techniques:** +4–6 (SGD, PPO, LoRA, ResNet, DPO, CoT merges).

---

## 9. Execution Order — Phase 1 (+300 papers to 400 total)

### Session structure

Due to the ~667 NLM call volume and ~4–6 hour runtime, Phase 1 is designed for **two sessions of ~3 hours each:**

- **Session 1:** Ingestion + PDF pipeline (Steps 1–7)
- **Session 2:** NotebookLM pipeline + normalization + graph + audit (Steps 8–14)

Sessions can be split across days. All steps are resumable.

---

### Step 1 — Verify prerequisites

```bash
source .venv/bin/activate
export DATABASE_URL=sqlite:///research_platform.db

# Confirm auth
nlm notebook list --json | python3 -c "
import sys, json; d=json.load(sys.stdin)
print(f'Auth OK — {len(d)} notebooks in NLM')
"
# Required: 23 notebooks

# Confirm DB baseline
python3 -c "
import sqlite3; c=sqlite3.connect('research_platform.db').cursor()
c.execute('SELECT COUNT(*) FROM papers'); print('Papers:', c.fetchone()[0])
c.execute('SELECT COUNT(*) FROM paper_analyses'); print('Analyses:', c.fetchone()[0])
c.execute('SELECT COUNT(*) FROM notebooks'); print('Notebooks:', c.fetchone()[0])
"
# Required: Papers=100, Analyses=100, Notebooks=23

# Confirm Pre-Ingestion Steps 0A–0E have been applied
python3 -c "
import sqlite3; c=sqlite3.connect('research_platform.db').cursor()
c.execute('SELECT COUNT(DISTINCT canonical_name) FROM paper_techniques')
print('Distinct canonicals:', c.fetchone()[0])
"
# Expected: < 1,115 (merges applied); ideally < 1,050
```

**STOP if auth fails or paper count ≠ 100.** Do not proceed until all checks pass.

---

### Step 2 — ICLR 2024 smoke test

```bash
python -m ingestion.run_ingestion -c ICLR -y 2024 --limit 5
```

**Expected:** 5 papers inserted, no errors.

**Checkpoint:**
```bash
python3 -c "
import sqlite3; c=sqlite3.connect('research_platform.db').cursor()
c.execute(\"SELECT co.short_name, ce.year, COUNT(*) FROM papers p JOIN conference_editions ce ON p.conference_edition_id=ce.id JOIN conferences co ON ce.conference_id=co.id GROUP BY co.short_name, ce.year\")
print(c.fetchall())
"
# Expected: [('ICLR', 2024, 5), ('NeurIPS', 2024, 100)]
```

**STOP if smoke test fails.** Investigate OpenReview API availability before proceeding.

---

### Step 3 — ICLR 2024 full ingestion

```bash
python -m ingestion.run_ingestion -c ICLR -y 2024 --limit 150
```

**Expected:** ~145 new papers inserted (5 from smoke test already exist → updated as no-op).  
**Runtime:** ~3–5 minutes.

**Checkpoint:**
```bash
python3 -c "
import sqlite3; c=sqlite3.connect('research_platform.db').cursor()
c.execute(\"SELECT co.short_name, ce.year, COUNT(*) FROM papers p JOIN conference_editions ce ON p.conference_edition_id=ce.id JOIN conferences co ON ce.conference_id=co.id GROUP BY co.short_name, ce.year\")
print(c.fetchall()); c.execute('SELECT COUNT(*) FROM papers'); print('Total:', c.fetchone()[0])
"
# Expected: [('ICLR', 2024, 150), ('NeurIPS', 2024, 100)], Total: 250
```

---

### Step 4 — Citation enrichment (ICLR batch)

```bash
python -m ingestion.enrich_citations
```

**Expected:** ~150 new papers enriched with `semantic_scholar_id` and `citation_count`.  
**Runtime:** ~5–8 minutes.

---

### Step 5 — ICML 2024 smoke test

```bash
python -m ingestion.run_ingestion -c ICML -y 2024 --limit 5
```

**Expected:** 5 papers inserted, no errors.

**STOP if smoke test fails.**

---

### Step 6 — ICML 2024 full ingestion

```bash
python -m ingestion.run_ingestion -c ICML -y 2024 --limit 150
```

**Expected:** ~145–150 new papers inserted.  
**Runtime:** ~3–5 minutes.

**Checkpoint:**
```bash
python3 -c "
import sqlite3; c=sqlite3.connect('research_platform.db').cursor()
c.execute(\"SELECT co.short_name, ce.year, COUNT(*) FROM papers p JOIN conference_editions ce ON p.conference_edition_id=ce.id JOIN conferences co ON ce.conference_id=co.id GROUP BY co.short_name, ce.year\")
print(c.fetchall()); c.execute('SELECT COUNT(*) FROM papers'); print('Total:', c.fetchone()[0])
"
# Expected: [('ICLR', 2024, 150), ('ICML', 2024, 150), ('NeurIPS', 2024, 100)], Total: 400
```

---

### Step 7 — Citation enrichment (ICML batch)

```bash
python -m ingestion.enrich_citations
```

---

### Step 8 — PDF pipeline

Download and segment PDFs for all new papers. **This must complete before NotebookLM upload** to ensure full-text quality.

```bash
python -m pdf_pipeline.run_pipeline --limit 400
```

**Expected behavior:**
- Downloads ~300 new PDFs (some unavailable — expect 10–20% failure rate)
- Extracts text via PyMuPDF
- Segments into sections: abstract, intro, methodology, experiments, results, conclusion

**Expected after:**
- 250–350 new papers with `paper_sections` rows
- 50–150 new papers at abstract-only fallback (no PDF available)

**Runtime:** ~25–40 minutes (network-dependent).

**Checkpoint:**
```bash
python3 -c "
import sqlite3; c=sqlite3.connect('research_platform.db').cursor()
c.execute('SELECT COUNT(DISTINCT paper_id) FROM paper_sections')
print('Papers with sections:', c.fetchone()[0])
c.execute('SELECT COUNT(*) FROM papers WHERE pdf_local_path IS NOT NULL')
print('Papers with PDFs:', c.fetchone()[0])
"
# Expected: 250–380 papers with PDFs; 200–360 with segmented sections
```

---

### Step 9 — NotebookLM pipeline (6 batches)

This is the longest step. Run in batches of 50. Each batch takes ~20–30 minutes.

**Before starting, confirm auth is live:**
```bash
nlm notebook list --json | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'Auth OK — {len(d)} notebooks')"
```

**Run 6 batches:**
```bash
# Batch 1
python -m notebooklm.run_pipeline --limit 50

# Batch 2
python -m notebooklm.run_pipeline --limit 50

# Batch 3
python -m notebooklm.run_pipeline --limit 50

# Batch 4
python -m notebooklm.run_pipeline --limit 50

# Batch 5
python -m notebooklm.run_pipeline --limit 50

# Batch 6
python -m notebooklm.run_pipeline --limit 50
```

After each batch, run the checkpoint:
```bash
python3 -c "
import sqlite3; c=sqlite3.connect('research_platform.db').cursor()
c.execute('SELECT source_status, COUNT(*) FROM notebook_papers GROUP BY source_status')
print('Upload status:', dict(c.fetchall()))
"
```

If auth expires mid-batch: `nlm login`, then re-run the same `--limit 50` command.  
Already-uploaded sources are skipped automatically.

**Stage coverage after all batches:**
- Stage A (Assign): 300 new papers assigned to existing and new notebooks
- Stage B (Provision): ~7 new notebooks created for overflow topics
- Stage C (Upload): ~510 new source uploads (full-text for papers with sections)

**Checkpoint after all uploads:**
```bash
python3 -c "
import sqlite3; c=sqlite3.connect('research_platform.db').cursor()
c.execute('SELECT source_status, COUNT(*) FROM notebook_papers GROUP BY source_status')
statuses = dict(c.fetchall())
print('pending:', statuses.get('pending', 0), '← must be 0')
print('uploaded:', statuses.get('uploaded', 0))
print('abstract_only:', statuses.get('abstract_only', 0))
print('error:', statuses.get('error', 0), '← investigate if > 0')
"
# Required: pending = 0
# Expected: uploaded = ~570-600 (170 old + ~430 new full-text)
# Expected: abstract_only = ~80-120 (2 old + ~80-100 new without PDFs)
```

---

### Step 10 — Re-synthesize all notebooks that received new papers (Model B)

This is the critical step that produces full extraction coverage. It re-queries all notebooks (existing + new) to incorporate newly added sources in the synthesis responses.

```bash
# Re-synthesize all notebooks — force overwrites existing synthesis rows
python -m notebooklm.run_pipeline --stage synthesize --force
```

**Expected behavior:**
- Overwrites existing `notebook_syntheses` rows for the 23 existing notebooks
- Creates new `notebook_syntheses` rows for the ~7 new notebooks
- Total synthesis queries: ~150 (30 notebooks × 5 prompts)
- Runtime: ~75 minutes (~150 queries × ~30s each)

**Checkpoint:**
```bash
python3 -c "
import sqlite3; c=sqlite3.connect('research_platform.db').cursor()
c.execute('SELECT COUNT(*) FROM notebook_syntheses'); total = c.fetchone()[0]
c.execute('SELECT COUNT(*) FROM notebooks WHERE notebooklm_id IS NOT NULL'); nb = c.fetchone()[0]
c.execute('SELECT COUNT(*) FROM notebook_syntheses WHERE normalized=0'); unnorm = c.fetchone()[0]
print(f'Synthesis rows: {total} (expected ~{nb*5})')
print(f'Notebooks with syntheses: {nb}')
print(f'Ready for extraction (normalized=False): {unnorm}')
"
# Required: total ≥ (notebooks × 5) × 0.9
# Required: unnorm > 0 (needed for Stage E)
```

If synthesis is incomplete, re-run `--stage synthesize --force` — it skips notebooks already at 5 normalized=False rows.

---

### Step 11 — Extraction (Stage E)

```bash
python -m notebooklm.run_pipeline --stage extract
```

**Expected behavior:**
- Processes all notebooks with `normalized=False` synthesis rows
- Upserts into `paper_analyses`, `paper_techniques`, `paper_datasets`, `paper_categories`, `paper_methodologies`
- Sets `normalized=True` on processed synthesis rows
- Runtime: ~15–30 minutes

**Checkpoint:**
```bash
python3 -c "
import sqlite3; c=sqlite3.connect('research_platform.db').cursor()
c.execute('SELECT COUNT(*) FROM paper_analyses'); print('paper_analyses:', c.fetchone()[0])
c.execute('SELECT COUNT(*) FROM paper_techniques'); print('paper_techniques:', c.fetchone()[0])
c.execute('SELECT COUNT(*) FROM paper_datasets'); print('paper_datasets:', c.fetchone()[0])
c.execute('SELECT COUNT(*) FROM notebook_syntheses WHERE normalized=0'); print('un-normalized remaining:', c.fetchone()[0])
"
# Expected: paper_analyses: ~400 (all papers)
# Expected: paper_techniques: ~3,500–4,500 (400 papers × ~9–11 techniques/paper avg)
# Expected: paper_datasets: ~200–400 (full-text papers with dataset mentions)
# Required: un-normalized = 0
```

---

### Step 12 — Entity normalization

```bash
python normalize_entities.py --force
```

Running with `--force` because new extractions have been added and the alias map was updated in Step 0B. Forces a full re-pass over all rows.

**Checkpoint:**
```bash
python3 -c "
import sqlite3; c=sqlite3.connect('research_platform.db').cursor()
c.execute('SELECT COUNT(*) FROM paper_techniques WHERE canonical_name IS NULL')
print('Missing canonical_name:', c.fetchone()[0])
c.execute('SELECT COUNT(DISTINCT canonical_name) FROM paper_techniques')
print('Distinct canonical techniques:', c.fetchone()[0])
"
# Required: 0 missing canonical_name
```

---

### Step 13 — Graph rebuild

```bash
python build_graph_v2.py
```

**Expected graph stats after Phase 1:**

| Metric | NeurIPS 100 (current) | Phase 1 ~400 (estimate) |
|---|---|---|
| Paper edges | 2,916 | ~12,000–18,000 |
| Average edge weight | 1.625 | ~1.8–2.1 |
| Max edge weight | 15.0 | ~25–35 |
| Clusters | 3 | 5–8 |
| Singleton rate | 95.1% | ~75–85% |
| Shared+Core techniques | 55 | ~150–250 |

Edge count scales as O(N²) with connected papers: C(400, 2) = 79,800 possible pairs. Not all are connected — the graph is sparse, with edges only where papers share at least one category. Expected connected pairs: ~12,000–18,000 based on the current density.

**Checkpoint:**
```bash
python build_graph.py --stats
# Verify: edge count >> 2,916; avg weight > 1.625; isolated papers = 0
```

---

### Step 14 — Entity audit V2

```bash
python entity_audit.py
python entity_signal_audit.py
python concept_selection_audit.py
```

**Pass criteria (Phase 1 definition of done):**

| Metric | Before Phase 1 | Target | Verdict |
|---|---|---|---|
| Singleton percentage | 95.1% | < 80% | Evaluate from audit output |
| SHARED-tier techniques | 55 | ≥ 100 | Evaluate from audit output |
| Total techniques | 1,115 | ~3,500–4,500 | Evaluate from audit output |
| paper_analyses coverage | 100% | 100% | Verify in Step 11 |
| New top-cited papers in centrality | — | ICLR/ICML papers appear in top-20 | Verify from graph report |

---

## 10. Expected Cost

| Phase | NLM calls | Sessions | Runtime |
|---|---|---|---|
| Pre-ingestion normalization (Steps 0A–0E) | ~0 NLM | 1 short session | ~15 min |
| Phase 1 ingestion + PDF (Steps 1–8) | ~0 NLM | 1 session | ~1 hr |
| Phase 1 NLM pipeline (Steps 9–11) | **~667** | 2–3 sessions | ~3.5–5 hr |
| Normalization + graph + audit (Steps 12–14) | ~0 NLM | <30 min | ~30 min |
| **Phase 1 total** | **~667 NLM calls** | **~3–4 sessions** | **~5–7 hr** |
| **Cumulative at 400 papers** | **~1,255 NLM calls** | — | — |

**NotebookLM call budget context:**
The pre-rebuild total was ~308 calls. The rebuild consumed ~280 more (cumulative ~588). Phase 1 adds ~667, reaching ~1,255 cumulative. The full Phase 2 (to 1,000 papers) adds approximately another ~1,082, reaching ~2,337. The CORPUS_EXPANSION_PLAN's full-corpus cost model at 2,000 papers is ~2,270 total — this runbook's phased Model B is slightly higher per-phase due to re-synthesis, but produces complete extraction coverage.

---

## 11. Expected Graph Impact

### Technique signal

At 400 papers (4× the current corpus), technique co-occurrence grows roughly as N²/4 relative to 100 papers. Techniques shared by 2 papers at 100 papers will appear in proportionally more pairs at 400, lifting many SPECIALIZED-tier techniques (currently contributing 0) into SHARED.

| Metric | Current (100 papers) | Estimated (400 papers) |
|---|---|---|
| Total techniques | 1,115 | ~3,500–4,500 |
| Singleton rate | 95.1% | ~75–85% |
| Shared+Core count | 55 | ~150–250 |
| Shared techniques driving edges | 55 | ~150–250 |
| Technique-weighted edges | — (stale) | ~2,500–5,000 |
| Average edge weight | 1.625 | ~1.8–2.1 |

### IDF tier shifts at N=400

The IDF formula `ln(N/paper_count)` shifts tier boundaries with corpus size:
- GENERIC (idf < 3.00) at N=400: `paper_count > e^(3.0) × 400/400` ≈ paper_count ≥ 20
- SHARED at N=400: paper_count 8–20
- SPECIALIZED at N=400: paper_count ≤ 7

At 100 papers, "Large Language Models" (9 papers) is GENERIC. At 400 papers, if LLMs appear in 20 papers, it remains at the GENERIC/SHARED boundary. Techniques currently in SHARED tier (2–4 papers) will become SPECIALIZED at 400 papers if their paper count stays the same — getting the 2× weight multiplier. This is the primary mechanism by which graph quality improves with corpus size.

### Cluster structure

At 100 papers the graph has 3 clusters, likely dominated by topic-level category assignments. At 400 papers with ICLR/ICML overlap, expect:
- 5–8 clusters (finer subdivision by technique-based community structure)
- LLM cluster splitting into LLM-alignment, LLM-efficiency, LLM-theory sub-clusters
- Optimization theory likely to form a distinct cluster driven by technique overlap
- Cross-conference bridge papers visible in betweenness centrality

---

## 12. Failure Recovery Plan

| Failure mode | Detection | Recovery action |
|---|---|---|
| OpenReview API returns 0 papers | Log output | Wait 5 min, retry; API may be rate-limiting |
| ICML papers not on OpenReview | Step 5 smoke test fails | Check CORPUS_EXPANSION_PLAN — ICML is OpenReview-hosted for 2024; verify `conferences_config.py` |
| PDF download >40% failure rate | Step 8 checkpoint shows <240 papers with PDFs | Acceptable; abstract fallback used; proceed |
| NotebookLM auth expires mid-upload | NLM CLI returns auth error | `nlm login`, re-run `--limit 50`; already-uploaded skip |
| Synthesis timeout for a notebook | Checkpoint 10 shows missing synthesis rows | Re-run `--stage synthesize --force`; idempotent, skips complete notebooks |
| Stage E extraction has un-normalized rows after run | Checkpoint 11 shows unnorm > 0 | Re-run `--stage extract`; triggered by normalized=False |
| Graph builder crashes (NULL canonical_name) | Stack trace | Run Step 12 (normalization) first, then retry graph build |
| DB locked error | `sqlite3.OperationalError` | Kill all Python processes; retry |
| Notebook count exceeds NLM limit | Stage B errors on create | Investigate NLM limit; if hit, must consolidate notebooks or obtain limit increase |

---

## 13. Execution Order — Quick Reference

```
Pre-ingestion (no NLM calls):
  Step 0A  Fix paren regex in normalize/rules.py
  Step 0B  Add missing aliases to technique_aliases.json
  Step 0C  Extend Pass 2 paren-strip in rules.py
  Step 0D  python normalize_entities.py --force
  Step 0E  python build_graph_v2.py  [baseline snapshot]

Session 1 — Ingestion + PDF (no NLM calls):
  Step 1   Verify prerequisites
  Step 2   python -m ingestion.run_ingestion -c ICLR -y 2024 --limit 5   [smoke test]
  Step 3   python -m ingestion.run_ingestion -c ICLR -y 2024 --limit 150
  Step 4   python -m ingestion.enrich_citations
  Step 5   python -m ingestion.run_ingestion -c ICML -y 2024 --limit 5   [smoke test]
  Step 6   python -m ingestion.run_ingestion -c ICML -y 2024 --limit 150
  Step 7   python -m ingestion.enrich_citations
  Step 8   python -m pdf_pipeline.run_pipeline --limit 400

Session 2 — NLM upload (6 × 50-paper batches, ~2 hr):
  Step 9   python -m notebooklm.run_pipeline --limit 50   [× 6]
           [checkpoint after each batch]

Session 3 — Re-synthesis + extraction (~2 hr):
  Step 10  python -m notebooklm.run_pipeline --stage synthesize --force
  Step 11  python -m notebooklm.run_pipeline --stage extract

Final (no NLM calls, <30 min):
  Step 12  python normalize_entities.py --force
  Step 13  python build_graph_v2.py
  Step 14  python entity_audit.py
           python entity_signal_audit.py
           python concept_selection_audit.py
```

---

## 14. Phase 1b Decision Gate (After Entity Audit at 400 Papers)

After Step 14, evaluate against pass criteria:

**If singleton rate < 80% AND shared techniques ≥ 100:**  
Phase 1 targets met. Proceed to:
1. Entity type column design (add `entity_type` to `paper_techniques`)
2. Optionally add ACL 2024 (+100 papers) as Phase 1b before entity type work

**If singleton rate still ≥ 80% or shared techniques < 100:**  
Phase 1 targets not yet met. Options:
1. Add ACL 2024 (+100 papers) to this phase → re-run audit
2. Add ICLR 2025 (+150 papers) → re-run audit
3. Accept partial targets and proceed — singleton rate may be corpus-size-limited even at 400

In either case, **do not start entity_type column design, ontology work, or Graph V3 until this gate passes.**

**Phase 2 (to 1,000 papers: ICLR 2025 + EMNLP 2024 + CVPR 2024 + ECCV 2024) must not begin until Phase 1 audits are complete and reviewed.**
