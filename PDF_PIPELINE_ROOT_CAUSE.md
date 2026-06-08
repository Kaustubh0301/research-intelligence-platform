# PDF Pipeline Root Cause Report

**Date:** 2026-06-05  
**Question:** Why are only 20 of 170 notebook_papers rows marked `uploaded` (full text)?

---

## 1. Stage-by-Stage Counts

| Stage | Count | Notes |
|---|---|---|
| Total papers | 100 | All NeurIPS 2024 |
| PDFs downloaded (`pdf_local_path IS NOT NULL`) | **10** | |
| PDFs text-extracted (`pdf_extracted_at IS NOT NULL`) | **10** | Matches download count exactly |
| PDFs segmented (rows in `paper_sections`) | **10** | Same 10 papers |
| Papers with `full_text` in `paper_sections` | **10** | All 10 have full text |
| **Distinct papers uploaded as full text** | **10** | |
| **Distinct papers uploaded as abstract-only** | **90** | |
| NotebookLM rows marked `uploaded` | 20 | 10 papers × avg 2 notebook assignments |
| NotebookLM rows marked `abstract_only` | 150 | 90 papers × avg 1.7 assignments |

The 20/150 row split is **not** 20 unique papers — it is 10 PDF-backed papers assigned to an average of 2 notebooks each (primary + secondary assignment), producing 20 `uploaded` rows. The actual upload gap is **10 papers with full text vs 90 abstract-only**.

---

## 2. Root Cause

**The PDF pipeline was run with a limit of ~10 papers and was not re-run.**

The chain of causation:

```
pdf_pipeline.run_pipeline --limit 10
        ↓
Only 10 PDFs downloaded + extracted + segmented
        ↓
90 papers have no paper_sections row
        ↓
source_prep.build_source() finds no PaperSection → falls back to abstract_only
        ↓
NotebookLM uploaded header + abstract only (no methodology, experiments, results, etc.)
        ↓
source_status = 'abstract_only' written to notebook_papers
```

The fallback logic in `notebooklm/source_prep.py` is correct and working as designed (line 104):  
> *"Returns a SourceDocument with mode='abstract_only' if no paper_sections row."*

The upload logic in the NotebookLM pipeline correctly uploaded all 100 papers — but 90 of them had only abstract-level content to upload because the PDF pipeline had not been run on them.

---

## 3. Ruling Out the Other Hypotheses

| Hypothesis | Verdict | Evidence |
|---|---|---|
| 1. PDFs were never downloaded | **YES — this is the primary cause** | `pdf_local_path IS NOT NULL` = 10 only |
| 2. PDF extraction failed | **No** | All 10 downloaded PDFs extracted successfully; no partial extraction state |
| 3. NotebookLM upload used abstract instead of PDF | **No** | `source_prep.py` uses full text when `paper_sections` row exists; 0 cases where PDF exists but abstract was used |
| 4. PDF pipeline was run only partially | **Yes — consequence of hypothesis 1** | `--limit 10` (or equivalent) was used; 90 papers never entered the PDF pipeline |
| 5. Source assignment skipped PDF-backed sources | **No** | All 10 PDF-backed papers were correctly uploaded as full text |

The cross-check that closes the case: **zero papers have a PDF but were uploaded as abstract-only**. The source_prep fallback is only triggered by a missing `paper_sections` row, which is only possible when the PDF pipeline didn't run. The NotebookLM pipeline itself has no bug.

---

## 4. Supporting Data

All 100 papers have `pdf_url` set and `is_open_access = True`. There is no structural barrier preventing the remaining 90 PDFs from being downloaded. The failure is purely operational — the PDF pipeline was not run at sufficient scale before the NotebookLM pipeline was executed.

The 10 papers that were fully processed have word counts of 5,111–6,853 words (avg 5,984), confirming the segmenter produces high-quality structured text when the PDF is available. The 90 abstract-only sources average ~150–300 words.

---

## 5. Fastest Path to Full-Text Quality on Existing Papers

The existing NotebookLM analyses for the 90 abstract-only papers are not wrong — they are just lower quality. NotebookLM synthesized from abstracts, which means the extracted techniques, datasets, and categories were derived from abstract-level language only, missing methodology details, experiment results, and limitations.

**To upgrade existing papers to full-text quality:**

### Step 1 — Download and segment the remaining 90 PDFs

```bash
python -m pdf_pipeline.run_pipeline --limit 100
```

This is idempotent. The pipeline skips the 10 already-downloaded papers and processes the remaining 90. Expected runtime: ~10–20 minutes (90 PDFs × ~3–5s download + segmentation).

Expected result: 90–100 papers with segmented `paper_sections` rows (some PDFs may be unavailable ~5–10%).

### Step 2 — Re-upload and re-synthesize upgraded sources

The NotebookLM pipeline needs to re-upload papers that are currently `abstract_only` but now have `paper_sections`. There is no `--force-reupload` flag in the current CLI, so this requires running the pipeline in a way that re-processes already-assigned papers.

```bash
python -m notebooklm.run_pipeline --stage upload
python -m notebooklm.run_pipeline --stage synthesize
python -m notebooklm.run_pipeline --stage extract
```

**Important:** Check whether `run_pipeline --stage upload` re-uploads papers where `source_status = 'abstract_only'`. If the pipeline skips already-uploaded papers regardless of status, a one-time DB update to reset `abstract_only` rows to `pending` may be needed before re-running — but **do not modify code or data without review**.

### Step 3 — Re-run normalization and graph

```bash
python normalize_entities.py
python build_graph_v2.py
```

### Cost estimate for upgrading existing 90 papers

| Call type | Count |
|---|---|
| Re-uploads (90 papers × avg 1.7 assignments) | ~153 |
| Re-synthesis (only notebooks whose sources changed) | ~100–115 |
| **Total additional NLM calls** | **~253–268** |

Runtime: ~45–60 minutes.

---

## 6. Decision Point

Before executing the upgrade, one question needs an answer:

**Does `notebooklm.run_pipeline --stage upload` re-upload papers with `source_status = 'abstract_only'`?**

If yes → run Steps 1–3 above in sequence.  
If no → the `abstract_only` rows need to be reset before re-uploading, which requires either a direct DB update or a code change. Either path is straightforward but should be confirmed before execution.

Check `notebooklm/pipeline.py` stage C (upload) to see whether it filters on `source_status`.

---

## 7. Recommendation

**Run the PDF pipeline on the existing 100 papers before ingesting any new papers.** The cost is low (~10–20 minutes of downloads + ~253 NLM calls) and the benefit is high: the existing 100 analyses will use full-text methodology + experiments sections instead of abstracts, which directly improves entity extraction quality (techniques, datasets, categories) and will produce better graph edges on the existing corpus before expansion begins.

This should be done as Step 0 of Phase 1, before any new ingestion.
