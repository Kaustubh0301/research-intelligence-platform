# Upgrade Path Audit — Abstract-Only → Full-Text

**Date:** 2026-06-05  
**Question:** Can the 90 papers currently uploaded as `abstract_only` be re-uploaded with full-text sources after `paper_sections` become available?

---

## 1. Exact Code Path — Stage C (Upload)

**File:** `notebooklm/pipeline.py`, function `run_upload()`, lines 250–261.

```python
q = (
    select(NotebookPaper)
    .join(Notebook, Notebook.id == NotebookPaper.notebook_id)
    .where(
        Notebook.notebooklm_id != None,
    )
)
if not force:
    q = q.where(NotebookPaper.source_status == "pending")
```

**Finding 1: Without `--force`, Stage C only processes rows where `source_status = 'pending'`.**  

The 90 `abstract_only` rows and 20 `uploaded` rows are both terminal states as far as Stage C is concerned. Running `python -m notebooklm.run_pipeline --stage upload` on the current DB produces exactly 0 uploads — the log would say `Stage C: no pending uploads`.

**Finding 2: `abstract_only` is a permanent terminal state under normal operation.**  

Once a paper is uploaded (even with abstract-only content), the row is never re-queued automatically. There is no quality-check path that would detect "this row was `abstract_only` but now `paper_sections` exists — re-upload it."

---

## 2. What `--force` Actually Does

With `force=True`, Stage C changes its query to select ALL `NotebookPaper` rows (not just `pending`), then calls `client.add_source()` for each one.

**Critical finding: `add_source` is additive, not replacive.**

```python
# client.py — add_source(), lines 179–192
stdout, _ = _run(["source", "add", notebook_id,
                  "--file", tmp_path,
                  "--title", title,
                  "--wait"])
```

The `nlm source add` command adds a new source to the notebook. There is no `nlm source remove` or `nlm source replace` command anywhere in `client.py`. Running Stage C with `--force` on the current DB would:

1. Re-upload all 170 `notebook_papers` rows
2. Each abstract-only paper would get a **second source** added to its notebook — the new full-text version sitting alongside the old abstract-only version
3. Each already-uploaded (full-text) paper would also get a duplicate added

The notebook would then contain two sources per paper: an old abstract-only one and a new full-text one. NotebookLM would synthesize from both, producing confused and potentially contradictory extraction output.

**`--force` is not a safe upgrade path.**

---

## 3. Stage D (Synthesize) Behaviour

**File:** `notebooklm/pipeline.py`, function `run_synthesize()`, lines 373–403.

Without `--force`, Stage D skips notebooks that already have `notebook_syntheses` rows:

```python
existing = session.scalar(
    select(NotebookSynthesis).where(...)
)
if existing and not force:
    log.debug("Stage D: synthesis %s/%s already exists, skipping")
    continue
```

With `--force`, Stage D deletes the existing synthesis rows and replaces them:

```python
if existing and force:
    session.delete(existing)
    session.flush()
```

The new synthesis rows are written with `normalized=False`, which triggers Stage E to re-extract on the next run. This part of the pipeline is cleanly re-runnable — Stage D `--force` is the correct way to refresh synthesis quality after sources change.

**Stage D is not the blocker. Stage C + the NotebookLM source accumulation is the blocker.**

---

## 4. Stage E (Extract) Behaviour

**File:** `notebooklm/pipeline.py`, function `run_extract()`, lines 412–515.

Stage E activates whenever a `notebook_syntheses` row exists with `normalized=False`:

```python
q = (
    select(Notebook)
    .join(NotebookSynthesis, NotebookSynthesis.notebook_id == Notebook.id)
    .where(NotebookSynthesis.normalized == False)
    .distinct()
)
```

Stage E has no `force` switch on its trigger query — it just processes whatever has `normalized=False`. After Stage D `--force` rewrites synthesis rows with `normalized=False`, Stage E runs naturally and calls `normalizer.normalize()`.

The normalizer writes to `paper_analyses`, `paper_techniques`, `paper_categories`, `paper_datasets`, `paper_methodologies` in upsert-style. Existing rows for the same `(paper_id, name)` are updated. So Stage E is re-runnable and upgrades existing extraction rows.

**Stage E is not the blocker.**

---

## 5. DB Tables Involved in Upgrade

| Table | Relevant column | Role in upgrade |
|---|---|---|
| `notebook_papers` | `source_status` | **Blocker.** Must be reset from `abstract_only` → `pending` to allow Stage C re-upload. |
| `notebook_papers` | `upload_attempted_at`, `upload_completed_at` | Should be cleared (NULL) when resetting to `pending`. |
| `notebooks` | `notebooklm_id` | Must be set to NULL if the notebook is deleted and re-created. |
| `notebooks` | `source_count` | Must be reset to 0 if notebook is deleted. |
| `notebook_syntheses` | `normalized` | Must be set to `False` (or row deleted) to trigger Stage E re-extraction. Stage D `--force` handles this automatically. |
| `paper_sections` | all section columns | **Prerequisite.** Must exist before upgrade. Created by `pdf_pipeline`. |
| `paper_analyses` | all columns | Overwritten by Stage E re-extraction (upsert). |
| `paper_techniques` | `name`, `role`, `canonical_name` | Overwritten by Stage E. |
| `paper_categories` | `name` | Overwritten by Stage E. |
| `paper_datasets` | `name` | Overwritten by Stage E. |
| `paper_methodologies` | `name` | Overwritten by Stage E. |

---

## 6. Is Re-Upload Automatic After `paper_sections` Appear?

**No.** There is no trigger, watcher, or quality-gate in the pipeline that detects when a `paper_sections` row is created for a paper whose `notebook_papers.source_status` is `abstract_only`. The pipeline is linear and stateless between stages — it only acts on `source_status = 'pending'`. Once that column leaves `pending`, the paper is invisible to Stage C forever (unless manually reset or `--force` is used).

---

## 7. Is a Manual Reset Required?

**Yes, for a clean upgrade.** The safe procedure requires manual DB updates to reset `source_status` before re-running Stage C.

Additionally, because `add_source` is additive and there is no source removal command, the notebooks in NotebookLM must be deleted and re-created before re-uploading. Otherwise each paper would appear twice in its notebook.

---

## 8. Safest Upgrade Procedure

This is a two-part procedure: clean the NotebookLM side, then reset the DB side and re-run the pipeline.

### Prerequisites (must be done first)

```bash
# 1. Run the PDF pipeline to get paper_sections for the remaining 90 papers
python -m pdf_pipeline.run_pipeline --limit 100
```

Verify before continuing:
```bash
python3 -c "
import sqlite3; c=sqlite3.connect('research_platform.db').cursor()
c.execute('SELECT COUNT(DISTINCT paper_id) FROM paper_sections')
print('Papers segmented:', c.fetchone()[0])
"
# Target: 85–100 (some PDFs may be unavailable; expect ~5–15% failure)
```

### Part 1 — Delete existing NotebookLM notebooks

All 23 current notebooks contain at least some abstract-only sources. The cleanest path is to delete all notebooks and start fresh, rather than trying to identify which notebooks are affected.

```bash
# List current notebooks and their notebooklm_ids
python3 -c "
import sqlite3; c=sqlite3.connect('research_platform.db').cursor()
c.execute('SELECT topic_slug, instance_number, notebooklm_id, source_count FROM notebooks ORDER BY topic_slug, instance_number')
for r in c.fetchall(): print(r)
"

# Then delete each notebook via the nlm CLI:
# nlm notebook delete <notebooklm_id> --confirm
# (Repeat for all 23 notebooks — get IDs from query above)
```

### Part 2 — Reset the database

After all notebooks are deleted from NotebookLM, reset the DB state:

```sql
-- Reset all notebooks so Stage B re-provisions them
UPDATE notebooks
SET notebooklm_id = NULL,
    notebooklm_url = NULL,
    source_count = 0,
    status = 'active',
    last_synced_at = NULL;

-- Reset all notebook_papers so Stage C re-uploads them
UPDATE notebook_papers
SET source_status = 'pending',
    upload_attempted_at = NULL,
    upload_completed_at = NULL;

-- Delete all synthesis rows so Stage D re-synthesizes
-- (Stage D --force would also work, but deleting is cleaner
--  and avoids any risk of operating on stale notebook IDs)
DELETE FROM notebook_syntheses;
```

Run as a Python one-liner:
```bash
python3 -c "
import sqlite3
conn = sqlite3.connect('research_platform.db')
c = conn.cursor()
c.execute(\"UPDATE notebooks SET notebooklm_id=NULL, notebooklm_url=NULL, source_count=0, status='active', last_synced_at=NULL\")
c.execute(\"UPDATE notebook_papers SET source_status='pending', upload_attempted_at=NULL, upload_completed_at=NULL\")
c.execute('DELETE FROM notebook_syntheses')
conn.commit()
print('Reset:', c.rowcount, 'synthesis rows deleted')
c.execute('SELECT source_status, COUNT(*) FROM notebook_papers GROUP BY source_status')
print('notebook_papers status:', c.fetchall())
c.execute('SELECT COUNT(*) FROM notebooks WHERE notebooklm_id IS NULL')
print('Notebooks needing provision:', c.fetchone()[0])
conn.close()
"
```

### Part 3 — Re-run the pipeline

```bash
# Stage B: re-provision notebooks
python -m notebooklm.run_pipeline --stage provision

# Stage C: upload all papers (now full-text where paper_sections exist)
python -m notebooklm.run_pipeline --stage upload --limit 50
# Repeat until all 170 rows are uploaded (100 papers × ~1.7 avg assignments)

# Stage D: synthesize
python -m notebooklm.run_pipeline --stage synthesize

# Stage E: extract
python -m notebooklm.run_pipeline --stage extract
```

### Part 4 — Re-normalize and rebuild graph

```bash
python normalize_entities.py
python build_graph_v2.py
```

---

## 9. Expected NotebookLM Call Count for Clean Upgrade

Assumes ~90 papers successfully get `paper_sections` (~10 PDFs may be unavailable).

| Operation | Count | Notes |
|---|---|---|
| Notebook deletes | 23 | Not an `add_source` call; no rate-limit impact |
| Notebook creates (Stage B) | ~15–18 | Fewer notebooks needed at higher fill (90 papers / 45 max = 2 full notebooks + ~13 partial) |
| Source uploads (Stage C) | ~170 | 100 papers × avg 1.7 assignments; full-text for ~90, abstract for ~10 |
| Synthesis queries (Stage D) | ~75–90 | ~15–18 notebooks × 5 prompts |
| **Total new NLM calls** | **~260–280** | |
| **Running total (added to existing 308)** | **~568–588** | |

**Comparison to just running new papers without upgrading:**  
Phase 1 ingestion alone costs ~342 NLM calls. The upgrade costs ~260–280 calls. Since the upgrade should happen before Phase 1 expansion anyway, it is reasonable to absorb this cost upfront.

---

## 10. Summary

| Question | Answer |
|---|---|
| Does Stage C skip `abstract_only` rows normally? | **Yes** — only `source_status = 'pending'` is processed |
| Does Stage C detect source quality upgrades? | **No** — no quality-gate exists in the pipeline |
| Does Stage C replace existing sources with `--force`? | **No** — `add_source` is additive; `--force` creates duplicates |
| Is a `remove_source` command available? | **No** — `client.py` has no such function |
| Is re-upload automatic after `paper_sections` appear? | **No** — manual DB reset is required |
| What DB rows need resetting? | `notebook_papers.source_status` → `pending`; `notebooks.notebooklm_id` → NULL; `notebook_syntheses` → delete |
| Is Stage D re-runnable cleanly? | **Yes** — `--force` deletes and rewrites synthesis rows |
| Is Stage E re-runnable cleanly? | **Yes** — triggered automatically by `normalized=False` rows |
| Safest upgrade procedure | Delete notebooks → reset DB → re-provision → re-upload → re-synthesize → re-extract |
| Expected NLM calls for upgrade | ~260–280 incremental (~568 cumulative) |
