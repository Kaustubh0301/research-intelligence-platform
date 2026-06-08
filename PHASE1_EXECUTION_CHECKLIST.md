# Phase 1 Execution Checklist

**Date produced:** 2026-06-05  
**Target:** 100 → 400 papers (ICLR 2024 + ICML 2024)  
**Strategy:** Scenario B from PHASE1_EXPANSION_RUNBOOK.md — Model B (full re-synthesis of all touched notebooks)  
**Sessions:** 3 sessions across 2 days (Session 1: ingestion + PDF; Session 2: NLM upload; Session 3: synthesis + extract + audit)

---

## Verified Baseline (2026-06-05)

| Metric | Runbook Says | Actual | Δ |
|---|---|---|---|
| Papers | 100 | **100** | — |
| paper_analyses | 100 | **100** | — |
| Notebooks | 23 | **23** | — |
| paper_techniques rows | 1,115 | **1,369** | +254 (extra extraction rows exist) |
| Distinct canonical_name | 1,115 | **1,115** | — |
| Missing canonical_name | 0 | **0** | — |
| paper_relationships | 2,916 | **2,916** | — |
| notebook_papers | ~170 | **170** | — |
| uploaded status | ~168 | **166** | — |
| abstract_only status | 2 | **4** | +2 |

**Baseline verdict:** READY TO PROCEED. Paper count and analysis coverage are correct. The 1,369 technique rows vs 1,115 documented is a known discrepancy — the distinct canonical count (1,115) matches. The 4 abstract_only entries (vs 2 documented) are benign.

**Pre-ingestion normalization (Steps 0A–0E) not yet applied.** Confirmed by `distinct canonical_name = 1,115` — after merges those will drop below 1,100. These steps MUST run before any new paper extraction.

---

## How to Use This Checklist

- Work top-to-bottom.
- Run each validation query immediately after its step; paste the output into a scratch file or terminal log for audit trail.
- **STOP** markers are hard stops — do not skip them.
- All steps are idempotent unless marked otherwise. On interruption, re-run the same command.
- Recovery procedures are at the bottom of each step that has failure risk.

---

## PRE-SESSION: Apply Normalization Fixes

These steps have no NLM calls, take ~15 minutes total, and must complete before any new paper extraction. Run them in the working directory with `.venv` active.

```bash
source .venv/bin/activate
export DATABASE_URL=sqlite:///research_platform.db
```

### Step 0A — Fix parenthetical acronym regex

**File:** `normalize/rules.py`, line 37

Change:
```python
_PAREN_ACRONYM_RE = re.compile(r"\s*\([A-Z][A-Z0-9\-]+\)\s*$")
```
To:
```python
_PAREN_ACRONYM_RE = re.compile(r"\s*\([A-Z][A-Za-z0-9\-]+\)\s*$")
```

Fixes "Large Language Models" / "Large language models (LLMs)" remaining as separate canonicals, and all future mixed-case acronym parentheticals (ViTs, GNNs, MLPs).

**Checkpoint (no query needed):** Confirm the file diff shows the change before proceeding.

---

### Step 0B — Add missing alias entries

**File:** `normalize/technique_aliases.json`

Minimum required additions before Phase 1 (from NORMALIZATION_V2_AUDIT.md Rank 4 + Rank 5):

| Key to add | Maps to |
|---|---|
| `"sgd"` | `"Stochastic gradient descent"` |
| `"ppo"` | `"Proximal Policy Optimization"` |
| `"low-rank adaptation"` | `"LoRA"` |
| `"low rank adaptation"` | `"LoRA"` |
| `"resnets"` | `"ResNet"` |
| `"residual network"` | `"ResNet"` |
| `"direct preference optimization (dpo)"` | `"Direct Preference Optimization"` |
| `"direct preference optimization"` (lowercase) | `"Direct Preference Optimization"` |
| `"chain-of-thought (cot)"` | `"Chain-of-Thought"` |
| `"chain-of-thought prompting"` | `"Chain-of-Thought"` |
| `"chain-of-thought (cot) prompting"` | `"Chain-of-Thought"` |
| `"graph convolutional networks"` | `"Graph convolutional network"` |

**Checkpoint:** Confirm file is valid JSON after edits:
```bash
python3 -c "import json; json.load(open('normalize/technique_aliases.json')); print('JSON valid')"
# Expected: JSON valid
```

---

### Step 0C — Extend Pass 2 paren-strip in rules.py

**File:** `normalize/rules.py`, `case_fold_canonical()` function.

Change the group key from:
```python
name.lower()
```
To:
```python
_PAREN_ACRONYM_RE.sub("", name).strip().lower()
```

Collapses 50+ singleton pairs of the form `"Foo (BAR)"` / `"Foo"` without requiring individual alias entries.

---

### Step 0D — Re-run normalization (force)

```bash
python normalize_entities.py --force
```

**Runtime:** < 1 minute  
**Expected:** Re-processes all 1,369 technique rows. Merges the ~30 case-fold drift pairs and applies new alias entries from Step 0B.

**Validation query:**
```bash
python3 -c "
import sqlite3; c=sqlite3.connect('research_platform.db').cursor()
c.execute('SELECT COUNT(*) FROM paper_techniques WHERE canonical_name IS NULL')
print('Missing canonical:', c.fetchone()[0])
c.execute('SELECT COUNT(DISTINCT canonical_name) FROM paper_techniques')
print('Distinct canonicals:', c.fetchone()[0])
"
# Required: Missing canonical = 0
# Required: Distinct canonicals < 1,115 (merges applied — expect 1,050–1,100)
```

**STOP if missing canonical > 0.** Investigate normalize_entities.py before proceeding.

---

### Step 0E — Rebuild baseline graph snapshot

```bash
python build_graph_v2.py
```

**Runtime:** < 1 minute  
**Purpose:** Captures the post-normalization baseline graph so Phase 1 improvement can be measured against it.

**Validation query:**
```bash
python entity_signal_audit.py
# Expected: singleton rate lower than 95.1%; Shared+Core count higher than 55
# Record the output — this is the pre-Phase-1 baseline
```

---

## SESSION 1: Ingestion + PDF Pipeline (~1–1.5 hours, no NLM calls)

### Step 1 — Verify prerequisites

```bash
source .venv/bin/activate
export DATABASE_URL=sqlite:///research_platform.db

# Confirm auth
nlm notebook list --json | python3 -c "
import sys, json; d=json.load(sys.stdin)
print(f'Auth OK — {len(d)} notebooks')
"
# Required: Auth OK — 23 notebooks
# If auth expired: nlm login

# Confirm DB baseline
python3 -c "
import sqlite3; c=sqlite3.connect('research_platform.db').cursor()
c.execute('SELECT COUNT(*) FROM papers'); print('Papers:', c.fetchone()[0])
c.execute('SELECT COUNT(*) FROM paper_analyses'); print('Analyses:', c.fetchone()[0])
c.execute('SELECT COUNT(*) FROM notebooks'); print('Notebooks:', c.fetchone()[0])
c.execute('SELECT COUNT(*) FROM paper_techniques WHERE canonical_name IS NULL'); print('Missing canonical:', c.fetchone()[0])
"
# Required: Papers=100, Analyses=100, Notebooks=23, Missing canonical=0

# Confirm pre-ingestion normalization applied
python3 -c "
import sqlite3; c=sqlite3.connect('research_platform.db').cursor()
c.execute('SELECT COUNT(DISTINCT canonical_name) FROM paper_techniques')
print('Distinct canonicals:', c.fetchone()[0])
"
# Required: < 1,115 — if still 1,115 the normalization steps 0A–0E have not been applied
```

**STOP if auth fails, paper count ≠ 100, or distinct canonicals = 1,115.**

---

### Step 2 — ICLR 2024 smoke test

```bash
python -m ingestion.run_ingestion -c ICLR -y 2024 --limit 5
```

**Runtime:** ~1 minute  
**Expected log:** `Papers inserted: 5`

**Validation query:**
```bash
python3 -c "
import sqlite3; c=sqlite3.connect('research_platform.db').cursor()
c.execute(\"SELECT co.short_name, ce.year, COUNT(*) FROM papers p JOIN conference_editions ce ON p.conference_edition_id=ce.id JOIN conferences co ON ce.conference_id=co.id GROUP BY co.short_name, ce.year ORDER BY co.short_name\")
print(c.fetchall())
"
# Expected: [('ICLR', 2024, 5), ('NeurIPS', 2024, 100)]
```

**STOP if ICLR rows = 0.** The OpenReview API may be rate-limiting or the ICLR 2024 venue key may have changed. Wait 5 minutes, then retry. If still 0, check `ingestion/conferences_config.py` for the ICLR 2024 venue string.

---

### Step 3 — ICLR 2024 full ingestion

```bash
python -m ingestion.run_ingestion -c ICLR -y 2024 --limit 150
```

**Runtime:** ~3–5 minutes  
**Expected log:** `Papers inserted: ~145` (5 from smoke test already exist — updated as no-op)

**Expected row counts after:**

| Table | Before | After |
|---|---|---|
| papers | 100 | **250** |
| paper_analyses | 100 | 100 (unchanged — analysis runs later) |

**Validation query:**
```bash
python3 -c "
import sqlite3; c=sqlite3.connect('research_platform.db').cursor()
c.execute(\"SELECT co.short_name, ce.year, COUNT(*) FROM papers p JOIN conference_editions ce ON p.conference_edition_id=ce.id JOIN conferences co ON ce.conference_id=co.id GROUP BY co.short_name, ce.year ORDER BY co.short_name\")
print(c.fetchall())
c.execute('SELECT COUNT(*) FROM papers'); print('Total papers:', c.fetchone()[0])
"
# Expected: [('ICLR', 2024, 150), ('NeurIPS', 2024, 100)], Total papers: 250
```

**Recovery:** Command is fully idempotent. If interrupted, re-run the same command — already-inserted papers are upserted as no-ops.

---

### Step 4 — Citation enrichment (ICLR batch)

```bash
python -m ingestion.enrich_citations
```

**Runtime:** ~5–10 minutes (150 new papers × ~1 req/s without S2_API_KEY)  
**Expected log:** `Enriched X papers, Y failed` where Y is near 0.

**Validation query:**
```bash
python3 -c "
import sqlite3; c=sqlite3.connect('research_platform.db').cursor()
c.execute('SELECT COUNT(*) FROM papers WHERE semantic_scholar_id IS NULL AND conference_edition_id IN (SELECT id FROM conference_editions WHERE year=2024 AND conference_id IN (SELECT id FROM conferences WHERE short_name=\"ICLR\"))')
print('ICLR papers missing S2 ID:', c.fetchone()[0])
"
# Expected: near 0 (some papers not in S2 index — up to 10% failure is acceptable)
```

**Recovery:** Fully resumable. `enrich_citations` skips already-enriched papers. For persistent failures: `python -m ingestion.enrich_citations --force --limit 10`.

---

### Step 5 — ICML 2024 smoke test

```bash
python -m ingestion.run_ingestion -c ICML -y 2024 --limit 5
```

**Runtime:** ~1 minute  
**Expected log:** `Papers inserted: 5`

**Validation query:**
```bash
python3 -c "
import sqlite3; c=sqlite3.connect('research_platform.db').cursor()
c.execute(\"SELECT co.short_name, ce.year, COUNT(*) FROM papers p JOIN conference_editions ce ON p.conference_edition_id=ce.id JOIN conferences co ON ce.conference_id=co.id GROUP BY co.short_name, ce.year ORDER BY co.short_name\")
print(c.fetchall())
"
# Expected: [('ICLR', 2024, 150), ('ICML', 2024, 5), ('NeurIPS', 2024, 100)]
```

**STOP if ICML rows = 0.** ICML 2024 is OpenReview-hosted — verify `conferences_config.py` venue key. Do not proceed to full ICML ingestion.

---

### Step 6 — ICML 2024 full ingestion

```bash
python -m ingestion.run_ingestion -c ICML -y 2024 --limit 150
```

**Runtime:** ~3–5 minutes  
**Expected log:** `Papers inserted: ~145`

**Expected row counts after:**

| Table | Before | After |
|---|---|---|
| papers | 250 | **400** |
| conference breakdown | ICLR:150, NeurIPS:100 | ICLR:150, ICML:150, NeurIPS:100 |

**Validation query:**
```bash
python3 -c "
import sqlite3; c=sqlite3.connect('research_platform.db').cursor()
c.execute(\"SELECT co.short_name, ce.year, COUNT(*) FROM papers p JOIN conference_editions ce ON p.conference_edition_id=ce.id JOIN conferences co ON ce.conference_id=co.id GROUP BY co.short_name, ce.year ORDER BY co.short_name\")
print(c.fetchall())
c.execute('SELECT COUNT(*) FROM papers'); print('Total papers:', c.fetchone()[0])
"
# Expected: [('ICLR', 2024, 150), ('ICML', 2024, 150), ('NeurIPS', 2024, 100)], Total: 400
```

**Recovery:** Idempotent upsert. Re-run if interrupted.

---

### Step 7 — Citation enrichment (ICML batch)

```bash
python -m ingestion.enrich_citations
```

**Runtime:** ~5–8 minutes  
**Purpose:** Enriches the ~150 new ICML papers with `semantic_scholar_id` and `citation_count`.

**Validation query:**
```bash
python3 -c "
import sqlite3; c=sqlite3.connect('research_platform.db').cursor()
c.execute('SELECT COUNT(*) FROM papers WHERE citation_count IS NULL')
print('Papers missing citation_count:', c.fetchone()[0])
c.execute('SELECT COUNT(*) FROM papers WHERE semantic_scholar_id IS NULL')
print('Papers missing S2 ID:', c.fetchone()[0])
"
# Expected: both near 0 (up to ~30–40 unmatched papers is acceptable)
```

---

### Step 8 — PDF pipeline

**MUST complete before NotebookLM upload.** Full-text quality depends on PDFs being available for the upload stage.

```bash
python -m pdf_pipeline.run_pipeline --limit 400
```

**Runtime:** ~20–40 minutes (network-dependent, 300 new downloads × ~3–5s each)  
**Expected behavior:**
- Downloads PDFs for all 300 new papers (ICLR + ICML)
- Retries the 2 existing NeurIPS papers that had no PDF
- Extracts text via PyMuPDF
- Segments into: abstract, intro, methodology, experiments, results, conclusion

**Expected row counts after:**

| Metric | Before | After | Notes |
|---|---|---|---|
| papers with pdf_local_path | ~98 | **250–380** | 10–20% PDF failure rate expected |
| papers with paper_sections rows | ~98 | **200–360** | Segmentation success subset of downloads |

**Validation query:**
```bash
python3 -c "
import sqlite3; c=sqlite3.connect('research_platform.db').cursor()
c.execute('SELECT COUNT(*) FROM papers WHERE pdf_local_path IS NOT NULL')
print('Papers with PDFs:', c.fetchone()[0])
c.execute('SELECT COUNT(DISTINCT paper_id) FROM paper_sections')
print('Papers with segmented text:', c.fetchone()[0])
c.execute('SELECT COUNT(*) FROM papers WHERE pdf_local_path IS NULL')
print('Papers without PDFs (abstract fallback):', c.fetchone()[0])
"
# Expected: PDFs: 250–380; with sections: 200–360; without PDFs: 20–150
# Accept if: PDFs < 240 (>37% failure rate) — note it but proceed; abstract fallback covers remainder
```

**Recovery:** Fully resumable. PDF pipeline skips already-downloaded/segmented papers. Re-run same command if interrupted.

**Checkpoint:** Session 1 complete. All 400 papers are in the DB and PDFs are processed. NLM upload can begin any time — no auth expiry concern between sessions.

---

## SESSION 2: NotebookLM Upload (6 batches × 50 papers, ~2–2.5 hours)

**Begin by confirming auth is live:**
```bash
nlm notebook list --json | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'Auth OK — {len(d)} notebooks')"
# Required: Auth OK — 23 notebooks
# If expired: nlm login
```

### Step 9 — NotebookLM pipeline upload (Stages A + B + C)

Run in 6 batches of 50. Each batch takes ~20–30 minutes.

```bash
# Batch 1 — papers 1–50
python -m notebooklm.run_pipeline --limit 50

# After Batch 1, validate:
python3 -c "
import sqlite3; c=sqlite3.connect('research_platform.db').cursor()
c.execute('SELECT source_status, COUNT(*) FROM notebook_papers GROUP BY source_status')
print('After Batch 1:', dict(c.fetchall()))
c.execute('SELECT COUNT(*) FROM notebooks'); print('Notebooks:', c.fetchone()[0])
"
# Expected after Batch 1: uploaded grows by ~85 (50 papers × 1.7 avg assignments)

# Batch 2 — papers 51–100
python -m notebooklm.run_pipeline --limit 50

# Batch 3 — papers 101–150
python -m notebooklm.run_pipeline --limit 50

# Batch 4 — papers 151–200
python -m notebooklm.run_pipeline --limit 50

# Batch 5 — papers 201–250
python -m notebooklm.run_pipeline --limit 50

# Batch 6 — papers 251–300 (remaining)
python -m notebooklm.run_pipeline --limit 50
```

**Between-batch checkpoint (run after every batch):**
```bash
python3 -c "
import sqlite3; c=sqlite3.connect('research_platform.db').cursor()
c.execute('SELECT source_status, COUNT(*) FROM notebook_papers GROUP BY source_status')
print('Upload status:', dict(c.fetchall()))
c.execute('SELECT COUNT(*) FROM notebooks'); print('Total notebooks:', c.fetchone()[0])
c.execute('SELECT COUNT(*) FROM paper_analyses'); print('paper_analyses:', c.fetchone()[0])
"
```

**Expected row counts after all 6 batches:**

| Table/Metric | Before Session 2 | After All Batches |
|---|---|---|
| notebook_papers total | 170 | **~680** (170 old + ~510 new) |
| source_status = uploaded | 166 | **~570–600** |
| source_status = abstract_only | 4 | **~80–120** |
| source_status = pending | 0 | **0 (required)** |
| source_status = error | 0 | **0 (investigate if > 0)** |
| notebooks total | 23 | **~28–30** (~7 new notebooks auto-created by Stage B) |
| paper_analyses | 100 | 100 (unchanged — Stage D only runs on new notebooks in default mode) |

**Final upload validation query (run after Batch 6):**
```bash
python3 -c "
import sqlite3; c=sqlite3.connect('research_platform.db').cursor()
c.execute('SELECT source_status, COUNT(*) FROM notebook_papers GROUP BY source_status')
statuses = dict(c.fetchall())
print('pending:', statuses.get('pending', 0), '  ← MUST BE 0')
print('uploaded:', statuses.get('uploaded', 0), '  ← expect 570–600')
print('abstract_only:', statuses.get('abstract_only', 0), '  ← expect 80–120')
print('error:', statuses.get('error', 0), '  ← INVESTIGATE if > 0')
c.execute('SELECT COUNT(*) FROM notebooks'); print('Total notebooks:', c.fetchone()[0], '  ← expect 28–30')
"
# STOP if pending > 0 — re-run --limit 50 until drained
# STOP if error > 5 — investigate NLM CLI logs before proceeding
```

**Auth expiry recovery:**
```bash
nlm login
# Then re-run the same batch:
python -m notebooklm.run_pipeline --limit 50
# Already-uploaded sources are skipped automatically.
```

**Notebook creation failure recovery:**
```bash
# If Stage B errors on notebook creation:
nlm notebook list  # confirm count < 100 (any reasonable limit)
python -m notebooklm.run_pipeline --stage provision
# Then re-run the upload batch.
```

---

## SESSION 3: Re-synthesis + Extraction + Normalization + Graph + Audit (~2–2.5 hours)

**Begin by confirming auth:**
```bash
nlm notebook list --json | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'Auth OK — {len(d)} notebooks')"
# Required: Auth OK — 28–30 notebooks (confirm count increased from 23)
```

### Step 10 — Re-synthesize all notebooks (Model B — CRITICAL)

This step re-queries ALL notebooks (existing 23 + ~7 new) so that papers uploaded to existing notebooks get extraction coverage. **Without this step, all ICLR/ICML papers that landed in NeurIPS-era notebooks will have zero analysis data.**

```bash
python -m notebooklm.run_pipeline --stage synthesize --force
```

**Runtime:** ~75 minutes (~150 synthesis queries × ~30s each)  
**Expected behavior:**
- Overwrites existing `notebook_syntheses` rows for the 23 existing notebooks
- Creates new `notebook_syntheses` rows for the ~7 new notebooks
- Total queries: ~30 notebooks × 5 prompts = **~150 synthesis calls**

**Expected row counts after:**

| Table | Before | After |
|---|---|---|
| notebook_syntheses total | ~115 (23 × 5) | **~150** (30 × 5) |
| notebook_syntheses where normalized=0 | ~0 | **~150** (all freshly written) |

**Validation query:**
```bash
python3 -c "
import sqlite3; c=sqlite3.connect('research_platform.db').cursor()
c.execute('SELECT COUNT(*) FROM notebook_syntheses'); total = c.fetchone()[0]
c.execute('SELECT COUNT(*) FROM notebooks WHERE notebooklm_id IS NOT NULL'); nb = c.fetchone()[0]
c.execute('SELECT COUNT(*) FROM notebook_syntheses WHERE normalized=0'); unnorm = c.fetchone()[0]
expected_min = int(nb * 5 * 0.9)
print(f'Synthesis rows: {total} (expected ≥ {expected_min})')
print(f'Notebooks with NLM ID: {nb}')
print(f'Ready for extraction (normalized=False): {unnorm}  ← MUST BE > 0')
"
# Required: total ≥ (notebooks × 5) × 0.9  (allow 10% partial failures)
# Required: unnorm > 0 (otherwise Stage E has nothing to process)
```

**Recovery if synthesis incomplete:** Re-run the same command. It is idempotent — skips notebooks that already have 5 `normalized=False` rows, retries those that don't.

---

### Step 11 — Extraction (Stage E)

```bash
python -m notebooklm.run_pipeline --stage extract
```

**Runtime:** ~15–30 minutes  
**Expected behavior:**
- Processes all `notebook_syntheses` rows where `normalized=False`
- Upserts into `paper_analyses`, `paper_techniques`, `paper_datasets`, `paper_categories`, `paper_methodologies`
- Sets `normalized=True` on all processed rows

**Expected row counts after:**

| Table | Before | After |
|---|---|---|
| paper_analyses | 100 | **~400** |
| paper_techniques | ~1,369 | **~3,500–4,500** |
| paper_datasets | ~unknown | **~200–400** |
| notebook_syntheses where normalized=0 | ~150 | **0 (required)** |

**Validation query:**
```bash
python3 -c "
import sqlite3; c=sqlite3.connect('research_platform.db').cursor()
c.execute('SELECT COUNT(*) FROM paper_analyses'); print('paper_analyses:', c.fetchone()[0])
c.execute('SELECT COUNT(*) FROM papers'); total = c.fetchone()[0]
c.execute('SELECT COUNT(*) FROM paper_analyses'); analyses = c.fetchone()[0]
print(f'Coverage: {analyses/total*100:.0f}%  ← must be 100%')
c.execute('SELECT COUNT(*) FROM paper_techniques'); print('paper_techniques:', c.fetchone()[0])
c.execute('SELECT COUNT(*) FROM paper_datasets'); print('paper_datasets:', c.fetchone()[0])
c.execute('SELECT COUNT(*) FROM notebook_syntheses WHERE normalized=0'); print('un-normalized remaining:', c.fetchone()[0], '  ← MUST BE 0')
"
# Required: paper_analyses = ~400 (must equal total papers count)
# Required: coverage = 100%
# Required: un-normalized = 0
# Expected: paper_techniques: 3,500–4,500
# Expected: paper_datasets: 200–400
```

**Recovery if unnorm > 0 after run:** Re-run `python -m notebooklm.run_pipeline --stage extract` — it processes any remaining `normalized=False` rows.

---

### Step 12 — Entity normalization (post-extraction)

```bash
python normalize_entities.py --force
```

**Runtime:** < 1 minute  
**Purpose:** Applies alias map from Step 0B to all ~3,500–4,500 newly extracted technique rows. Running with `--force` because the alias map was updated in pre-ingestion steps.

**Validation query:**
```bash
python3 -c "
import sqlite3; c=sqlite3.connect('research_platform.db').cursor()
c.execute('SELECT COUNT(*) FROM paper_techniques WHERE canonical_name IS NULL')
print('Missing canonical_name:', c.fetchone()[0], '  ← MUST BE 0')
c.execute('SELECT COUNT(DISTINCT canonical_name) FROM paper_techniques')
print('Distinct canonical techniques:', c.fetchone()[0])
c.execute('SELECT COUNT(*) FROM paper_techniques'); print('Total technique rows:', c.fetchone()[0])
"
# Required: missing canonical_name = 0
# Expected: distinct canonicals significantly less than total rows (merges working)
```

---

### Step 13 — Graph rebuild

```bash
python build_graph_v2.py
```

**Runtime:** ~30–60 seconds  
**Expected behavior:**
- Recomputes IDF weights on N=400 corpus
- Rebuilds `paper_relationships` and `entity_relationships` tables
- Writes `outputs/graph_v2_report.md`

**Expected row counts and stats after:**

| Metric | Before Phase 1 | Expected After | Target |
|---|---|---|---|
| paper_relationships edges | 2,916 | **~12,000–18,000** | > 10,000 |
| Average edge weight | 1.625 | **~1.8–2.1** | > 1.8 |
| Max edge weight | 15.0 | **~25–35** | — |
| Graph clusters | 3 | **5–8** | — |

**Validation query:**
```bash
python build_graph.py --stats
# Verify: edge count >> 2,916; avg weight > 1.625
# Then check generated report:
cat outputs/graph_v2_report.md
```

**Recovery if graph builder crashes:** Most likely cause is `NULL canonical_name` values — run Step 12 first, then retry.

---

### Step 14 — Entity audit V2 (Phase 1 pass/fail gate)

```bash
python entity_audit.py
python entity_signal_audit.py
python concept_selection_audit.py
```

**Runtime:** < 2 minutes total

**Pass criteria (Phase 1 definition of done):**

| Metric | Pre-Phase-1 | Target | Action if not met |
|---|---|---|---|
| Singleton rate | 95.1% | **< 80%** | Add ACL 2024 or ICLR 2025 and re-audit |
| SHARED+Core techniques | 55 | **≥ 100** | Same — extend corpus |
| Total techniques | 1,369 rows / 1,115 canonicals | ~3,500–4,500 rows | Investigate extraction |
| paper_analyses coverage | 100% | **100%** | Re-run Stage E if any gap |
| ICLR/ICML papers in top-20 centrality | — | **Yes** | Informational only |

**Record all three audit outputs.** These become the Phase 1 baseline for Phase 2 planning.

---

## Checkpoint Locations (for crash recovery between sessions)

| Checkpoint | Location | How to verify |
|---|---|---|
| ICLR ingested | DB: papers table | `SELECT COUNT(*) FROM papers` ≈ 250 |
| ICML ingested | DB: papers table | `SELECT COUNT(*) FROM papers` ≈ 400 |
| Citations enriched | DB: papers.semantic_scholar_id | `SELECT COUNT(*) FROM papers WHERE semantic_scholar_id IS NULL` ≈ 0 |
| PDFs downloaded | DB: papers.pdf_local_path | `SELECT COUNT(*) FROM papers WHERE pdf_local_path IS NOT NULL` |
| PDFs segmented | DB: paper_sections | `SELECT COUNT(DISTINCT paper_id) FROM paper_sections` |
| NLM upload complete | DB: notebook_papers | `SELECT source_status, COUNT(*) FROM notebook_papers GROUP BY source_status` — pending = 0 |
| New notebooks created | DB: notebooks | `SELECT COUNT(*) FROM notebooks` ≈ 28–30 |
| Synthesis complete | DB: notebook_syntheses | `SELECT COUNT(*) FROM notebook_syntheses WHERE normalized=0` > 0 |
| Extraction complete | DB: paper_analyses + notebook_syntheses | analyses ≈ 400; normalized=0 count = 0 |
| Normalization applied | DB: paper_techniques | `canonical_name IS NULL` = 0 |
| Graph rebuilt | outputs/graph_v2_report.md | edge count > 2,916 |

---

## Consolidated Command Sequence

```bash
# === PRE-SESSION (no NLM calls, ~15 min) ===
# Step 0A: Edit normalize/rules.py line 37 — fix _PAREN_ACRONYM_RE (allow mixed-case)
# Step 0B: Edit normalize/technique_aliases.json — add 12 alias entries
# Step 0C: Edit normalize/rules.py case_fold_canonical() — change group key to strip parens
python normalize_entities.py --force                    # Step 0D
python build_graph_v2.py                                # Step 0E (baseline snapshot)
python entity_signal_audit.py                           # record pre-Phase-1 baseline

# === SESSION 1 (no NLM calls, ~1–1.5 hr) ===
source .venv/bin/activate
export DATABASE_URL=sqlite:///research_platform.db
nlm notebook list --json | python3 -c "import sys,json; d=json.load(sys.stdin); print(len(d), 'notebooks')"  # Step 1
python -m ingestion.run_ingestion -c ICLR -y 2024 --limit 5    # Step 2: smoke test
python -m ingestion.run_ingestion -c ICLR -y 2024 --limit 150  # Step 3: full ICLR
python -m ingestion.enrich_citations                             # Step 4
python -m ingestion.run_ingestion -c ICML -y 2024 --limit 5    # Step 5: smoke test
python -m ingestion.run_ingestion -c ICML -y 2024 --limit 150  # Step 6: full ICML
python -m ingestion.enrich_citations                             # Step 7
python -m pdf_pipeline.run_pipeline --limit 400                  # Step 8

# === SESSION 2 (NLM upload, ~2–2.5 hr) ===
# Confirm auth: nlm notebook list --json | python3 -c "import sys,json; d=json.load(sys.stdin); print(len(d))"
python -m notebooklm.run_pipeline --limit 50   # Step 9 Batch 1  [checkpoint]
python -m notebooklm.run_pipeline --limit 50   # Step 9 Batch 2  [checkpoint]
python -m notebooklm.run_pipeline --limit 50   # Step 9 Batch 3  [checkpoint]
python -m notebooklm.run_pipeline --limit 50   # Step 9 Batch 4  [checkpoint]
python -m notebooklm.run_pipeline --limit 50   # Step 9 Batch 5  [checkpoint]
python -m notebooklm.run_pipeline --limit 50   # Step 9 Batch 6  [checkpoint]
# Verify: pending=0, error=0 before ending session

# === SESSION 3 (synthesis + extract + audit, ~2–2.5 hr) ===
# Confirm auth
python -m notebooklm.run_pipeline --stage synthesize --force  # Step 10 (~75 min)
python -m notebooklm.run_pipeline --stage extract              # Step 11
python normalize_entities.py --force                           # Step 12
python build_graph_v2.py                                       # Step 13
python entity_audit.py                                         # Step 14
python entity_signal_audit.py                                  # Step 14
python concept_selection_audit.py                              # Step 14
```

---

## Recovery Procedures

| Failure | Detection | Recovery |
|---|---|---|
| OpenReview returns 0 papers | Log: `Received 0 papers` | Wait 5 min, retry same command; API may rate-limit |
| ICML not on OpenReview | Step 5 smoke test = 0 | Check `conferences_config.py` ICML 2024 venue key |
| Ingestion interrupted | Paper count below expected | Re-run same command — upsert is idempotent |
| S2 rate limit (HTTP 429) | Script logs 429 | Wait 60s; script has built-in retry; re-run |
| PDF failure > 40% | Step 8 checkpoint: PDFs < 240 | Note it, proceed — abstract fallback used |
| NLM auth expired mid-upload | `nlm` CLI returns auth error | `nlm login`, then re-run `--limit 50`; already-uploaded skip |
| Synthesis timeout for a notebook | Step 10 checkpoint: unnorm < expected | Re-run `--stage synthesize --force`; skips notebooks already at 5 unnorm rows |
| Stage E unnorm > 0 after run | Step 11 validation query | Re-run `--stage extract`; processes remaining `normalized=False` rows |
| Graph builder crashes NULL canonical | Stack trace | Run Step 12 first, then retry Step 13 |
| DB locked | `sqlite3.OperationalError: database is locked` | Kill all Python processes; retry |
| Notebook count hits NLM account limit | Stage B error on create | Investigate NLM account limit; must consolidate or get limit increase before continuing |

---

## Phase 1b Decision Gate (After Step 14)

**If singleton rate < 80% AND shared+core techniques ≥ 100:**
- Phase 1 targets met.
- Proceed to: entity_type column design, or optionally add ACL 2024 as Phase 1b.

**If singleton rate ≥ 80% OR shared+core < 100:**
- Phase 1 targets not yet met.
- Option A: Add ACL 2024 (+100 papers) — re-run Steps 1–14 with `-c ACL -y 2024 --limit 100`.
- Option B: Add ICLR 2025 (+150 papers) — same process.
- **Do not begin entity_type column design, ontology work, or Graph V3 until this gate passes.**

**Phase 2 (ICLR 2025 + EMNLP 2024 + CVPR 2024 + ECCV 2024) must not begin until Phase 1 audits are complete and the decision gate above is evaluated.**
