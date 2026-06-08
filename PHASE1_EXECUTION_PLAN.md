# Phase 1 Execution Plan

**Date:** 2026-06-05  
**Target:** +300 papers (ICLR 2024 + ICML 2024) → ~400 papers total  
**Status:** AWAITING REVIEW — do not execute until approved  

---

## 0. Prerequisites (Verify Before Starting)

```bash
# 1. Activate virtualenv
source .venv/bin/activate

# 2. Set DB path
export DATABASE_URL=sqlite:///research_platform.db

# 3. Confirm NotebookLM auth is live
nlm notebook list --json | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'Auth OK — {len(d)} notebooks')"
# Expected: "Auth OK — 23 notebooks"
# If auth expired: nlm login

# 4. Confirm DB baseline
python3 -c "
import sqlite3; c=sqlite3.connect('research_platform.db').cursor()
c.execute('SELECT COUNT(*) FROM papers'); print('Papers:', c.fetchone()[0])
c.execute('SELECT COUNT(*) FROM paper_analyses'); print('Analyses:', c.fetchone()[0])
"
# Expected: Papers: 100, Analyses: 100
```

---

## Step 1 — ICLR 2024 Smoke Test

**Goal:** Verify OpenReview API returns ICLR 2024 papers before committing to bulk run.

```bash
python -m ingestion.run_ingestion -c ICLR -y 2024 --limit 5
```

**Expected output:**
- Log line: `Received 5 papers — writing to database…`
- `Papers inserted: 5, Papers updated: 0`
- No errors

**Checkpoint validation:**
```bash
python3 -c "
import sqlite3; c=sqlite3.connect('research_platform.db').cursor()
c.execute(\"SELECT co.short_name, ce.year, COUNT(*) FROM papers p JOIN conference_editions ce ON p.conference_edition_id=ce.id JOIN conferences co ON ce.conference_id=co.id GROUP BY co.short_name, ce.year\")
print(c.fetchall())
"
# Expected: [('ICLR', 2024, 5), ('NeurIPS', 2024, 100)]
```

**If smoke test fails:** STOP. Do not proceed. Investigate OpenReview API availability for ICLR 2024.

---

## Step 2 — ICLR 2024 Full Ingestion

```bash
python -m ingestion.run_ingestion -c ICLR -y 2024 --limit 150
```

**Expected output:**
- `Received ~150 papers — writing to database…`
- `Papers inserted: ~145–150` (smoke test already inserted 5, so expect ~145 new + 5 updated)
- Runtime: ~3–5 minutes (OpenReview API rate-limited at ~1 req/s, batching helps)

**Expected paper count after:** ~250 total

**Checkpoint validation:**
```bash
python3 -c "
import sqlite3; c=sqlite3.connect('research_platform.db').cursor()
c.execute(\"SELECT co.short_name, ce.year, COUNT(*) FROM papers p JOIN conference_editions ce ON p.conference_edition_id=ce.id JOIN conferences co ON ce.conference_id=co.id GROUP BY co.short_name, ce.year ORDER BY co.short_name\")
print(c.fetchall())
"
# Expected: [('ICLR', 2024, 150), ('NeurIPS', 2024, 100)]
```

**Failure recovery:** The upsert store is idempotent. If the run is interrupted mid-way, simply re-run the same command — already-inserted papers will be updated (no-op), and remaining papers will be inserted. No data loss possible.

---

## Step 3 — Citation Enrichment Pass 1

```bash
python -m ingestion.enrich_citations
```

**Expected output:**
- Enriches all papers missing `semantic_scholar_id` or `citation_count`
- Logs: `Enriched X papers, Y failed`
- Runtime: ~5–10 minutes for 250 papers (Semantic Scholar bulk API, 1 req/s without S2_API_KEY)

**Checkpoint validation:**
```bash
python3 -c "
import sqlite3; c=sqlite3.connect('research_platform.db').cursor()
c.execute('SELECT COUNT(*) FROM papers WHERE semantic_scholar_id IS NULL')
print('Papers missing S2 ID:', c.fetchone()[0])
c.execute('SELECT COUNT(*) FROM papers WHERE citation_count IS NULL')
print('Papers missing citation count:', c.fetchone()[0])
"
# Expected: both counts near 0 (some may fail if paper not in S2 index — acceptable)
```

**Failure recovery:** Fully resumable. `enrich_citations` skips papers already enriched. For persistently failing papers: `python -m ingestion.enrich_citations --force --limit 10`.

---

## Step 4 — ICML 2024 Smoke Test

```bash
python -m ingestion.run_ingestion -c ICML -y 2024 --limit 5
```

**Expected output:** Same as ICLR smoke test — 5 papers inserted.

**Checkpoint validation:**
```bash
python3 -c "
import sqlite3; c=sqlite3.connect('research_platform.db').cursor()
c.execute(\"SELECT co.short_name, ce.year, COUNT(*) FROM papers p JOIN conference_editions ce ON p.conference_edition_id=ce.id JOIN conferences co ON ce.conference_id=co.id GROUP BY co.short_name, ce.year ORDER BY co.short_name\")
print(c.fetchall())
"
# Expected: [('ICLR', 2024, 150), ('ICML', 2024, 5), ('NeurIPS', 2024, 100)]
```

**If smoke test fails:** STOP. Do not proceed to full ICML ingestion.

---

## Step 5 — ICML 2024 Full Ingestion

```bash
python -m ingestion.run_ingestion -c ICML -y 2024 --limit 150
```

**Expected output:**
- `Papers inserted: ~145–150`
- Runtime: ~3–5 minutes

**Expected paper count after:** ~400 total

**Checkpoint validation:**
```bash
python3 -c "
import sqlite3; c=sqlite3.connect('research_platform.db').cursor()
c.execute(\"SELECT co.short_name, ce.year, COUNT(*) FROM papers p JOIN conference_editions ce ON p.conference_edition_id=ce.id JOIN conferences co ON ce.conference_id=co.id GROUP BY co.short_name, ce.year ORDER BY co.short_name\")
print(c.fetchall())
c.execute('SELECT COUNT(*) FROM papers'); print('Total:', c.fetchone()[0])
"
# Expected: [('ICLR', 2024, 150), ('ICML', 2024, 150), ('NeurIPS', 2024, 100)], Total: 400
```

---

## Step 6 — Citation Enrichment Pass 2

```bash
python -m ingestion.enrich_citations
```

Enriches the ~150 new ICML papers. Same behavior as Step 3.

**Runtime:** ~5–8 minutes for the 150 new papers.

---

## Step 7 — PDF Pipeline

Download and segment PDFs for all new papers. This is required before NotebookLM for full-text quality.

```bash
python -m pdf_pipeline.run_pipeline --limit 400
```

**Expected behavior:**
- Stage 1 (download): ~300 new PDFs + retries for the 90 existing papers that failed
- Stage 2 (extract): PyMuPDF text extraction
- Stage 3 (segment): 3-pass regex segmenter

**Expected counts after:**
- Target: 300–380 papers with segmented PDFs
- Some PDFs will be unavailable (404, paywalled, wrong URL) — expect ~10–20% failure rate

**Runtime:** 300 new papers × ~3–5s download = ~15–25 minutes (network dependent). Segmentation adds ~2 minutes.

**Checkpoint validation:**
```bash
python3 -c "
import sqlite3; c=sqlite3.connect('research_platform.db').cursor()
c.execute('SELECT COUNT(*) FROM papers WHERE pdf_local_path IS NOT NULL')
print('Papers with PDFs:', c.fetchone()[0])
c.execute('SELECT COUNT(DISTINCT paper_id) FROM paper_sections')
print('Papers with segmented text:', c.fetchone()[0])
"
# Expected: 250–380 papers with PDFs; 200–350 with sections
```

**Failure recovery:** Fully resumable. PDF pipeline skips papers already downloaded/extracted/segmented. Re-run the same command if interrupted.

---

## Step 8 — NotebookLM Pipeline

Run the 5-stage analysis pipeline on all un-analyzed papers.

**Run in batches of 50 to manage session length and allow checkpoint after each batch:**

```bash
# Batch 1 (first 50 new papers)
python -m notebooklm.run_pipeline --limit 50

# Batch 2
python -m notebooklm.run_pipeline --limit 50

# Batch 3
python -m notebooklm.run_pipeline --limit 50

# Batch 4
python -m notebooklm.run_pipeline --limit 50

# Batch 5
python -m notebooklm.run_pipeline --limit 50

# Batch 6 (remaining ~50)
python -m notebooklm.run_pipeline --limit 50
```

Or run continuously (monitor for auth expiry):

```bash
python -m notebooklm.run_pipeline --limit 300
```

**Expected behavior:**
- Stage A (Assign): ~300 papers assigned to topic notebooks (fills sparse existing notebooks first)
- Stage B (Provision): Creates ~7 new notebooks where topics overflow
- Stage C (Upload): ~300 source uploads (full text where PDFs exist, abstract fallback otherwise)
- Stage D (Synthesize): ~7 new notebooks × 5 prompts = 35 new synthesis queries
- Stage E (Extract): Parses responses → populates `paper_analyses`, `paper_techniques`, `paper_datasets`, `paper_categories`, `paper_methodologies`

**Expected NotebookLM call counts (incremental for Phase 1):**

| Call type | Count |
|---|---|
| Notebook creates | ~7 |
| Source uploads | ~300 |
| Synthesis queries | ~35 |
| **Total incremental** | **~342** |
| Running total | **~650** |

**Runtime:** ~60–90 minutes (300 uploads × ~10–15s each + synthesis queries)

**Auth expiry risk:** Cookie sessions last 2–4 weeks. If auth fails mid-run:
```bash
nlm login
# Then resume from where it stopped:
python -m notebooklm.run_pipeline --limit 300
# Pipeline resumes — already-uploaded sources are skipped
```

**Checkpoint validation:**
```bash
python3 -c "
import sqlite3; c=sqlite3.connect('research_platform.db').cursor()
c.execute('SELECT COUNT(*) FROM paper_analyses'); print('Analyses:', c.fetchone()[0])
c.execute('SELECT COUNT(*) FROM papers'); total = c.fetchone()[0]; print('Total papers:', total)
print('Coverage:', f'{c.execute(\"SELECT COUNT(*) FROM paper_analyses\").fetchone()[0]/total*100:.0f}%')
c.execute('SELECT COUNT(*) FROM notebooks'); print('Notebooks:', c.fetchone()[0])
"
# Expected: Analyses: ~400, Coverage: ~100%, Notebooks: ~30
```

---

## Step 9 — Entity Normalization

```bash
python normalize_entities.py
```

**Expected behavior:**
- Re-runs alias map normalization on all `paper_techniques` and `paper_datasets` rows
- Writes/updates `canonical_name` for new technique rows
- Fast: < 1 minute

**Checkpoint validation:**
```bash
python3 -c "
import sqlite3; c=sqlite3.connect('research_platform.db').cursor()
c.execute('SELECT COUNT(*) FROM paper_techniques'); print('Techniques total:', c.fetchone()[0])
c.execute('SELECT COUNT(*) FROM paper_techniques WHERE canonical_name IS NULL'); print('Techniques missing canonical_name:', c.fetchone()[0])
"
# Expected: 0 techniques missing canonical_name
```

---

## Step 10 — Graph Rebuild

```bash
python build_graph_v2.py
```

**Expected behavior:**
- Recomputes IDF weights on expanded corpus (N≈400)
- Rebuilds `paper_relationships` and `entity_relationships`
- Generates `outputs/graph_v2_report.md`
- Runtime: ~30–60 seconds

**Expected graph stats after:**

| Metric | NeurIPS 100 (current) | Phase 1 ~400 (estimate) |
|---|---|---|
| Papers | 100 | ~400 |
| Paper edges | 2,517 | ~10,000–15,000 |
| Entity edges | 2,042 | ~5,000–10,000 |
| Clusters | 3 | 5–8 |
| Singletons | 96% | target <80% |
| SHARED-tier techniques | 2 | target ≥20 |

**Checkpoint validation:**
```bash
python build_graph.py --stats
# Check: edge count has increased, clusters may have grown
```

---

## Step 11 — Entity Audit V2

```bash
python entity_audit.py
python entity_signal_audit.py
python concept_selection_audit.py
```

**Purpose:** Validate that expansion targets were met.

**Pass criteria:**
- Singleton percentage < 80% (currently 96%)
- SHARED-tier techniques ≥ 20 (currently 2)
- New top-cited papers from ICLR/ICML appear in top centrality rankings

---

## Summary: Expected Counts After Phase 1

| Metric | Before Phase 1 | After Phase 1 |
|---|---|---|
| Total papers | 100 | ~400 |
| Conferences | NeurIPS 2024 | NeurIPS 2024, ICLR 2024, ICML 2024 |
| Total notebooks | 23 | ~30 |
| Total paper_analyses | 100 | ~400 |
| Total paper_techniques | 655 | ~2,500–2,800 |
| Total paper_relationships | 2,517 | ~10,000–15,000 |
| Total entity_relationships | 2,042 | ~5,000–10,000 |
| NLM calls (cumulative) | 308 | ~650 |

---

## Full Command Sequence (Consolidated)

```bash
# 0. Setup
source .venv/bin/activate
export DATABASE_URL=sqlite:///research_platform.db

# 1. Smoke test ICLR
python -m ingestion.run_ingestion -c ICLR -y 2024 --limit 5

# 2. Full ICLR 2024 ingestion
python -m ingestion.run_ingestion -c ICLR -y 2024 --limit 150

# 3. Citation enrichment
python -m ingestion.enrich_citations

# 4. Smoke test ICML
python -m ingestion.run_ingestion -c ICML -y 2024 --limit 5

# 5. Full ICML 2024 ingestion
python -m ingestion.run_ingestion -c ICML -y 2024 --limit 150

# 6. Citation enrichment again
python -m ingestion.enrich_citations

# 7. PDF pipeline
python -m pdf_pipeline.run_pipeline --limit 400

# 8. NotebookLM analysis (run in batches; re-auth with `nlm login` if needed)
python -m notebooklm.run_pipeline --limit 50  # × 6 batches

# 9. Entity normalization
python normalize_entities.py

# 10. Graph rebuild
python build_graph_v2.py

# 11. Audit V2
python entity_audit.py
python entity_signal_audit.py
python concept_selection_audit.py
```

---

## Estimated Total Runtime

| Step | Estimated time |
|---|---|
| Smoke tests (×2) | 2 min |
| ICLR 2024 ingestion | 3–5 min |
| ICML 2024 ingestion | 3–5 min |
| Citation enrichment (×2) | 10–15 min total |
| PDF pipeline (300 new PDFs) | 20–40 min |
| NotebookLM pipeline (300 papers) | 60–90 min |
| Entity normalization | <1 min |
| Graph rebuild | <1 min |
| Entity audits | <2 min |
| **Total** | **~2.5–3 hours** |

---

## Failure Recovery Plan

| Failure mode | Detection | Recovery |
|---|---|---|
| OpenReview API timeout during ingestion | Script logs `Received 0 papers` | Wait 5 min, retry same command |
| Ingestion interrupted mid-run | Paper count lower than expected | Re-run same command — upsert is idempotent |
| S2 citation enrichment rate-limited | Script logs HTTP 429 | Wait 60s; script has built-in retry; re-run if needed |
| PDF download failures (404, timeout) | `pdf_local_path IS NULL` for some papers | Acceptable; abstract fallback used in NotebookLM |
| NotebookLM auth expired mid-run | `nlm` CLI returns auth error | `nlm login`, then re-run `notebooklm.run_pipeline --limit 50`; already-uploaded sources skipped |
| NotebookLM notebook creation fails | Pipeline stage B logs error | Check `nlm notebook list`; if < 100 notebooks exist, retry stage B only: `python -m notebooklm.run_pipeline --stage provision` |
| NotebookLM synthesis timeout | Synthesis count lower than expected | Re-run `python -m notebooklm.run_pipeline --stage synthesize` |
| Graph builder crashes | Stack trace in terminal | Check that normalization ran first; check for NULL `canonical_name` values |
| DB file locked | `sqlite3.OperationalError: database is locked` | Ensure no other process has the DB open; kill any dangling Python processes |

---

## STOP: Do Not Proceed Past This Point Without Review

Before executing any commands from this plan:

1. Review `PRE_INGESTION_AUDIT.md` — confirm all readiness checks passed
2. Confirm NotebookLM auth is live (`nlm notebook list --json | wc -l`)
3. Confirm this plan has been reviewed and approved

**Phase 2 (EMNLP, CVPR, ECCV) must NOT begin until Phase 1 is fully complete, audited, and the entity audit targets are validated.**
