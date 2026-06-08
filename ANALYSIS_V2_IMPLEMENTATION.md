# Analysis V2 Implementation Log

**Date:** 2026-06-08  
**Branch:** `notebooklm-pipeline`  
**Status:** Schema + pipeline changes complete. Smoke test pending.

---

## What Changed and Why

Analysis V2 replaces the thin 5-field, 2-sentence-summary schema with 7 structured
analysis fields per paper (500–900 words total). The core problem was that the old
`PROMPTS["summary"]` hard-capped output at 2 sentences and the DB had no columns for
methodology, experimental findings, or analyst-generated future research directions.

---

## Files Modified

### 1. `notebooklm/assigner.py`

**Change:** `_get_or_create_notebook()` default `max_sources` changed from `45` → `20`.

**Why:** The `llm-architectures` notebook with 45 papers caused silent NLM truncation —
NLM returned 106 words covering only 9 of 45 papers with no error signal. Capping at 20
stays well within NLM's practical synthesis limit.

---

### 2. `db/models.py`

**Change 1:** Added 5 new columns to `PaperAnalysisRecord` (after `use_cases`):

| Column | Type | Content |
|---|---|---|
| `methodology` | Text | Multi-paragraph prose, 150-250 words |
| `experimental_findings` | Text | JSON array of `"benchmark :: metric :: score"` strings |
| `strengths` | Text | JSON array of 1-2 sentence mechanism explanations |
| `practical_applications` | Text | JSON array of 2-3 sentence deployment scenarios |
| `future_research_directions` | Text | JSON array of analyst-generated research directions |

Legacy columns `advantages`, `future_work`, `use_cases` are kept for backward
compatibility. `limitations` is now populated by the dedicated `limitations` prompt.

**Change 2:** Expanded the `notebook_paper_extracts.extract_type` CHECK constraint
to include the 5 new V2 type names (model-level; the existing SQLite table retains
the old constraint until a full migration is run — V2 extracts are not written to
this table for now, raw content is preserved in `notebook_syntheses`).

---

### 3. `db/migrate.py`

**Change:** Added 5 `_add_column_if_missing()` calls in `run_migrations()`:

```python
_add_column_if_missing("paper_analyses", "methodology",                "TEXT")
_add_column_if_missing("paper_analyses", "experimental_findings",      "TEXT")
_add_column_if_missing("paper_analyses", "strengths",                  "TEXT")
_add_column_if_missing("paper_analyses", "practical_applications",     "TEXT")
_add_column_if_missing("paper_analyses", "future_research_directions", "TEXT")
```

**Migration executed:** 2026-06-08 — all 5 columns confirmed present in
`research_platform.db` via `PRAGMA table_info(paper_analyses)`.

---

### 4. `notebooklm/pipeline.py`

**Change 1: PROMPTS dict** — expanded from 5 to 10 keys:

| Key | Type | Description |
|---|---|---|
| `summary` | V2 analysis | 3-5 paragraph detailed summary, 300-500 words |
| `methodology` | V2 analysis | 2-3 paragraph mechanism explanation, 150-250 words |
| `experimental_findings` | V2 analysis | `FINDING: benchmark :: metric :: score` triples |
| `strengths` | V2 analysis | Repeated `STRENGTH:` lines, mechanism-explaining |
| `limitations` | V2 analysis | Repeated `LIMITATION:` lines, constraint + reason |
| `practical_applications` | V2 analysis | Repeated `APPLICATION:` lines, deployment context |
| `future_research_directions` | V2 analysis | Repeated `DIRECTION:` lines, analyst-synthesized |
| `techniques` | metadata | Unchanged from V1 |
| `datasets` | metadata | Unchanged from V1 |
| `categories` | metadata | Unchanged from V1 |

The old `summary` prompt hard-coded `SUMMARY: [2 sentences]` and included
`ADVANTAGE:`, `LIMITATION:`, and `FUTURE_WORK:` in the same block. All three
are now separate prompts. `FUTURE_WORK:` (which stored the paper's own stated
future work) is replaced by `future_research_directions` (analyst-generated
open questions).

**Change 2: Coverage validation** — added to `run_synthesize()`:

- `_count_paper_blocks(text)` — counts `PAPER:` lines in a response
- `_check_coverage(nb_slug, prompt_key, answer, expected_count)` — raises
  `RuntimeError` if coverage < 80% for analysis prompts; logs warning for
  metadata prompts (techniques/datasets/categories)
- `notebook_failed` flag — if any analysis prompt fails coverage for a notebook,
  all remaining prompts for that notebook are skipped (not silently continued)

**Coverage threshold:** 80% (`_COVERAGE_THRESHOLD = 0.80`)

---

### 5. `notebooklm/extractor.py`

**New label constants:**
```python
LABEL_STRENGTH    = "STRENGTH:"
LABEL_FINDING     = "FINDING:"
LABEL_APPLICATION = "APPLICATION:"
LABEL_DIRECTION   = "DIRECTION:"
```

**New dataclasses:**
- `ParsedMethodology` — `.methodology` (str, multi-paragraph prose)
- `ParsedFinding` — `.benchmark`, `.metric`, `.scores`
- `ParsedExperimentalFindings` — `.findings` (list[ParsedFinding])
- `ParsedStrengths` — `.strengths` (list[str])
- `ParsedLimitations` — `.limitations` (list[str])
- `ParsedPracticalApplications` — `.applications` (list[str])
- `ParsedFutureResearchDirections` — `.directions` (list[str])

**New parse functions:**
- `parse_methodology()` — multi-line prose collector (same pattern as summary)
- `parse_experimental_findings()` — `FINDING: name :: metric :: score` triples
- `parse_strengths()` — repeated `STRENGTH:` lines via `_get_all_fields()`
- `parse_limitations_v2()` — repeated `LIMITATION:` lines
- `parse_practical_applications()` — repeated `APPLICATION:` lines
- `parse_future_research_directions()` — repeated `DIRECTION:` lines

**`ExtractionResult` extended:** 6 new fields added alongside existing V1 fields.

**`extract_all()` updated:** routes the 6 new response keys to new parsers.

---

### 6. `notebooklm/normalizer.py`

**`_upsert_analysis()` signature** — changed from:
```python
def _upsert_analysis(session, paper_id, notebook_id, summary, use_cases)
```
to accept all 7 optional analysis parsed objects. Each field is only written
if its parsed object is not `None` — partial re-synthesis is safe and won't
null out previously written columns.

**`normalize()` function** — 6 new lookup maps built from `ExtractionResult`;
`all_paper_ids` union expanded to include all new maps; `_upsert_analysis` called
with all available parsed objects per paper.

**Audit extracts** — V2 fields are not written to `notebook_paper_extracts`
because the existing table has a CHECK constraint on `extract_type` that predates
V2. The raw synthesis content is preserved in `notebook_syntheses.content`.

---

## Migration Verification

```
$ python3 -c "from db.migrate import run_migrations; run_migrations(); ..."

paper_analyses columns:
  id, paper_id, summary, advantages, limitations, future_work, use_cases,
  model, input_tokens, output_tokens, cost_usd, processing_ms,
  created_at, updated_at,
  methodology, experimental_findings, strengths,
  practical_applications, future_research_directions   ✓
```

---

## Parser Unit Test Results (2026-06-08)

All 6 new parsers verified against 2-paper mock corpus:

| Parser | Papers parsed | Unmatched | Status |
|---|---|---|---|
| `parse_methodology` | 2/2 | 0 | ✓ |
| `parse_experimental_findings` | 2/2 | 0 | ✓ — triples parse correctly |
| `parse_strengths` | 2/2 | 0 | ✓ |
| `parse_limitations_v2` | 2/2 | 0 | ✓ |
| `parse_practical_applications` | 2/2 | 0 | ✓ |
| `parse_future_research_directions` | 2/2 | 0 | ✓ |

Coverage validation tests:
- 5/5 papers → no exception ✓
- 1/5 papers (20%) → `RuntimeError` for analysis prompt ✓
- 1/5 papers (20%) → warning only for metadata prompt ✓
- 4/5 papers (80%) → exactly at threshold, no exception ✓

DB write test (normalizer): all 7 columns written correctly, 0 errors ✓

---

## What Is NOT Yet Done

| Task | Status |
|---|---|
| `api/models.py` — extend `AnalysisOut` with V2 fields | Not done |
| `api/helpers.py` — read V2 columns in `build_paper_detail()` | Not done |
| Frontend `types.ts` + `AnalysisPanel.tsx` | Not done — Step 13 |
| Smoke test on `ai-safety` notebook (NLM call) | Pending approval |
| Full 161-call re-synthesis | **Requires explicit approval after smoke test** |

---

## Next Steps (in order)

1. **Approve smoke test** — run `--stage synthesize --force --notebook-id <ai-safety-uuid>` then `--stage extract`
2. Review smoke test output (summary length, methodology quality, findings populated)
3. Approve full re-synthesis (161 NLM calls, ~80 min)
4. Update `api/models.py` + `api/helpers.py`
5. Update frontend types and `AnalysisPanel.tsx`
6. ICLR pipeline (Phase 1A) — Step 11 in corpus expansion plan
