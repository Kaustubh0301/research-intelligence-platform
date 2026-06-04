# Research Intelligence Platform — Project State Handoff v3

**Date:** June 4, 2026  
**Purpose:** Complete context for a new Claude Code session — no additional context required  
**Status:** NotebookLM extraction pipeline built and validated end-to-end · Orchestrator not yet built

---

## 1. Current Project Goal

Build a **Research Intelligence Platform** that:

- Automatically collects research papers from 10 major AI/ML conferences (2024–2026)
- Makes all papers searchable and filterable (citation count, year, author, conference, category, title)
- Uses **NotebookLM** to produce topic-level synthesis: summaries, techniques, methodologies, datasets, limitations, use cases
- Surfaces outputs through a web interface backed by a structured database

**Not** a chatbot. All interaction is structured (filter, search, browse).  
**Not** Gemini-dependent. The Gemini stage 4 analyser is deprecated.

**Manager requirements (verbatim spec):**
- Papers collected automatically
- Searchable with filters: citation count, year, author, conference, category, title
- NotebookLM handles analysis, summarization, extraction
- No chatbot
- No Gemini API dependency

**Target conferences:** NeurIPS · ICML · ICLR · CVPR · ICCV · ECCV · ACL · EMNLP · AAAI · IJCAI  
**Target years:** 2024 · 2025 · 2026 (up to publication date)

---

## 2. Current Architecture

```
OpenReview API              Semantic Scholar API
      │                            │
      ▼                            ▼
ingestion/fetch_openreview.py  ingestion/fetch_semantic_scholar.py
      │                            │
      └──────────┬─────────────────┘
                 ▼
         ingestion/store.py
                 │
                 ▼
    ┌────────────────────────┐
    │  SQLite (dev)          │  ← research_platform.db
    │  PostgreSQL (prod)     │  ← db/schema.sql
    └────────────────────────┘
         ▲            ▲
         │            │
  pdf_pipeline/   search/         metrics/
  (stages 1–3)    query.py        dashboard.py
         │
         ▼
   paper_sections
   (regex-v3 text)
         │
         ▼  ← BUILT THIS SESSION
  notebooklm/
    assigner.py    ← keyword scoring → notebook_papers rows
    source_prep.py ← assembles uploadable text from paper_sections
    client.py      ← wraps nlm CLI (create/upload/query/delete)
    extractor.py   ← parses NotebookLM responses into typed objects
    normalizer.py  ← writes objects to paper_analyses, categories, etc.
         │
         ▼  ← NOT YET BUILT
  notebooklm/
    pipeline.py      ← 5-stage orchestrator
    run_pipeline.py  ← CLI entry point
         │
         ▼
   paper_analyses · paper_categories · paper_techniques
   paper_methodologies · paper_datasets
   (5 of 10 segmented papers already have real data from test run)
```

### Data flow (what is built and working)

```
OpenReview / S2  →  fetch_*  →  papers + authors + paper_authors (DB)
Semantic Scholar  →  citation_count enrichment
pdf_url  →  downloader  →  pdfs/NeurIPS/2024/*.pdf  (10 PDFs)
         →  extractor   →  papers.pdf_word_count
         →  segmenter   →  paper_sections.* [regex-v3, 10 rows]

paper_sections.full_text  →  source_prep  →  structured text document
papers.title + abstract   →  assigner     →  notebook_papers rows (20 rows)

[NotebookLM live API, validated]:
  create_notebook()   →  Notebook row with notebooklm_url
  add_source()        →  uploads text; --wait confirms processing
  query_notebook()    →  returns {answer, citations: {num: source_uuid}}
  delete_notebook()   →  cleanup

query responses  →  extractor  →  ExtractionResult (typed Python objects)
ExtractionResult →  normalizer →  paper_analyses, paper_techniques,
                                  paper_datasets, paper_categories,
                                  paper_methodologies, notebook_paper_extracts
```

---

## 3. Every Completed Component

### Infrastructure

| Component | File(s) | Status |
|-----------|---------|--------|
| DB ORM (16 tables) | `db/models.py` | Complete |
| SQLite migration runner | `db/migrate.py` | Complete |
| PostgreSQL reference DDL | `db/schema.sql` | Complete |
| DB session/engine | `db/session.py` | Complete |
| Migration 003 (PDF pipeline tables) | `db/migrations/003_pdf_pipeline_tables.sql` | Applied |
| Migration 004 (analysis tables) | `db/migrations/004_analysis_tables.sql` | Applied |
| Migration 005 (notebook tables) | `db/migrations/005_notebooks.sql` | Applied |

### Ingestion

| Component | File | Status |
|-----------|------|--------|
| Conference catalogue (10 conf × 19 editions) | `ingestion/conferences_config.py` | Complete |
| OpenReview fetcher | `ingestion/fetch_openreview.py` | Complete |
| Semantic Scholar bulk fetcher | `ingestion/fetch_semantic_scholar.py` | Complete |
| Idempotent store (upserts) | `ingestion/store.py` | Complete |
| Citation enrichment | `ingestion/enrich_citations.py` | Complete |
| CLI (`--conference`, `--year`, `--limit`, `--all`) | `ingestion/run_ingestion.py` | Complete |
| Smoke test | `ingestion/verify_pipeline.py` | Complete |

### PDF Pipeline

| Component | File | Status |
|-----------|------|--------|
| HTTP downloader (retry, atomic write) | `pdf_pipeline/downloader.py` | Complete |
| PyMuPDF text extractor | `pdf_pipeline/extractor.py` | Complete |
| 3-pass regex segmenter (regex-v3) | `pdf_pipeline/segmenter.py` | Complete |
| DB store for sections | `pdf_pipeline/store.py` | Complete |
| 4-stage orchestrator (`run()`) | `pdf_pipeline/pipeline.py` | Complete |
| Segment-only re-run (`run_segment_only()`) | `pdf_pipeline/pipeline.py` | **Added this session** |
| CLI (`--limit`, `--force`, `--stage segment`) | `pdf_pipeline/run_pipeline.py` | **`--stage` added this session** |
| Gemini stage 4 (deprecated) | `pdf_pipeline/analyser.py` | Deprecated, lazy import, kept for reference |

### Search

| Component | File | Status |
|-----------|------|--------|
| Multi-filter search | `search/query.py` | Complete |

### Metrics

| Component | File | Status |
|-----------|------|--------|
| Dashboard CLI | `metrics/dashboard.py` | Complete |

### NotebookLM Integration

| Component | File | Status |
|-----------|------|--------|
| nlm CLI wrapper | `notebooklm/client.py` | **Built this session** |
| Topic keyword vocabulary (25 topics) | `notebooklm/topic_keywords.json` | **Built this session** |
| Keyword-based topic assigner | `notebooklm/assigner.py` | **Built this session** |
| Source document builder | `notebooklm/source_prep.py` | **Built this session** |
| Response parser / extractor | `notebooklm/extractor.py` | **Built this session** |
| DB normalizer | `notebooklm/normalizer.py` | **Built this session** |
| Prompt format validation script | `notebooklm/validate_prompts.py` | Built this session (dev tool) |
| Saved validation responses | `notebooklm/validation_results.json` | Produced this session |
| Extraction integration test | `notebooklm/test_extraction.py` | Built this session (dev tool) |
| E2E smoke test | `notebooklm/smoke_test.py` | Built this session (dev tool) |
| **5-stage pipeline orchestrator** | `notebooklm/pipeline.py` | **NOT YET BUILT** |
| **Pipeline CLI** | `notebooklm/run_pipeline.py` | **NOT YET BUILT** |

---

## 4. Files Created or Modified This Session

### Created (new)

| File | Lines | Purpose |
|------|-------|---------|
| `db/migrations/005_notebooks.sql` | 58 | PostgreSQL DDL for 4 new NotebookLM tables |
| `notebooklm/__init__.py` | 0 | Package marker |
| `notebooklm/client.py` | 220 | nlm CLI wrapper (create/upload/query/delete) |
| `notebooklm/topic_keywords.json` | ~350 | 25-topic keyword vocabulary |
| `notebooklm/assigner.py` | 304 | 3-pass keyword scorer + DB assignment writer |
| `notebooklm/source_prep.py` | 170 | Assembles uploadable text from paper_sections |
| `notebooklm/extractor.py` | 386 | Parses NotebookLM responses into typed objects |
| `notebooklm/normalizer.py` | 372 | Writes ExtractionResult to DB tables |
| `notebooklm/validate_prompts.py` | 235 | Prompt format live validation (dev tool) |
| `notebooklm/validation_results.json` | — | Saved raw NotebookLM responses (5 queries × 5 papers) |
| `notebooklm/test_extraction.py` | 230 | Offline extraction integration test |
| `notebooklm/smoke_test.py` | 165 | Full end-to-end live smoke test |

### Modified (changed this session)

| File | What changed |
|------|-------------|
| `db/models.py` | Added 4 ORM models: `Notebook`, `NotebookPaper`, `NotebookSynthesis`, `NotebookPaperExtract` |
| `pdf_pipeline/pipeline.py` | Added `run_segment_only()` function |
| `pdf_pipeline/run_pipeline.py` | Added `--stage segment` argument routing to `run_segment_only()` |

---

## 5. Database Schema and Table Counts

### Live counts (June 4, 2026)

| Table | Rows | Notes |
|-------|------|-------|
| `conferences` | 1 | NeurIPS only |
| `conference_editions` | 1 | NeurIPS 2024 only |
| `papers` | 100 | First 100 NeurIPS 2024 by API return order |
| `authors` | 444 | De-duplicated |
| `paper_authors` | 450 | Ordered (position field) |
| `paper_sections` | 10 | Top 10 by citation; all `regex-v3` |
| `paper_datasets` | 26 | From test extraction run (5 papers) |
| `paper_analyses` | 5 | From test extraction run; model=`notebooklm/notebook:ffffffff-…` |
| `paper_categories` | 13 | From test extraction run |
| `paper_techniques` | 40 | From test extraction run |
| `paper_methodologies` | 10 | From test extraction run |
| `pipeline_errors` | 0 | No errors recorded |
| `notebooks` | 10 | 10 topic notebooks; all `source_count` reflect assignments |
| `notebook_papers` | 20 | 10 papers × 2 assignments each; all `source_status='pending'` |
| `notebook_syntheses` | 0 | Not written yet (orchestrator not built) |
| `notebook_paper_extracts` | 35 | From test extraction run (7 per paper × 5 papers) |

**Total tables: 16**

### Important column notes

- All PKs are UUID strings (`str(uuid.uuid4())`) generated client-side
- `papers.pdf_local_path` — resumption flag for PDF download (non-NULL = downloaded)
- `papers.last_enriched_at` — resumption flag for citation enrichment
- `paper_sections.segmenter_version` — all 10 rows are `"regex-v3"`
- `paper_analyses.model` — stores `"notebooklm/notebook:{notebook_id}"` (not Gemini model name)
- `notebook_papers.source_status` — `'pending'` for all 20 rows; pipeline will flip to `'uploaded'`
- `notebook_paper_extracts.normalized` — `True` for all 35 rows from test run

### Schema divergence (known, intentional)

`db/schema.sql` (PostgreSQL reference) defines a normalized design with standalone `categories`, `techniques`, `methodologies` entity tables. `db/models.py` uses simpler flat per-paper tables (`paper_categories(name, confidence)`, etc.). **These are not the same schema.** Resolution plan: flat ORM for SQLite dev; normalize to schema.sql when migrating to PostgreSQL. Do not try to reconcile them now.

---

## 6. NotebookLM Integration Status

### Library and auth

```
Package:  notebooklm-mcp-cli 0.7.0
Install:  pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org notebooklm-mcp-cli
Auth dir: ~/.notebooklm-mcp-cli/profiles/default/cookies.json  (~17KB)
Cookie lifetime: 2–4 weeks
Re-auth:  nlm login  (opens Chrome, sign in with Google)
Auth check: nlm notebook list  (NOT nlm login --check — that triggers a chmod bug)
```

### What has been validated

1. **Library connectivity**: `nlm notebook list --json` returns `[]` (empty account after cleanup)
2. **Full create/upload/query/delete cycle**: completed 3 times (validation run, smoke test, prompt format test)
3. **5-paper notebook**: created, 5 sources uploaded (21k–42k chars each), 5 queries fired, notebook deleted
4. **Format compliance**: 5/5 blocks per query, all field labels present, 100% compliance across all 5 query types
5. **Extraction pipeline**: `extractor.py → normalizer.py` on saved responses → 5/5 title matches (all 1.00 exact), 0 errors, all DB tables written correctly

### Architecture decisions confirmed

- DB is source of truth. NotebookLM is write-only analysis engine.
- Topic-based notebooks (25 topics, 30–45 papers per notebook, max 2 notebooks per paper)
- Gemini `pdf_pipeline/analyser.py` deprecated. Stage 4 replaced by NotebookLM.
- Source format: structured text (not raw PDF) assembled from `paper_sections`
- Fallback: `abstract_only` mode when no PDF is available

---

## 7. Exact NotebookLM Command Signatures Validated

```bash
# List all notebooks — confirms auth
nlm notebook list --json
# Returns: [{id, title, source_count, updated_at}, ...]

# Create notebook
nlm notebook create "Notebook Name" --json
# Returns: {notebook_id, title, url, message}

# Add source from file — does NOT support --json; parse stdout
nlm source add <notebook_id> --file <path_to_txt> --title "<title>" --wait
# Returns: plain text confirmation
# stdout contains "✓ Added source:" on success

# Query notebook
nlm notebook query <notebook_id> "<prompt>" --json
# Returns: {answer: "<prose with [1] citations>", citations: {"1": "<source-uuid>", ...}}

# Delete notebook
nlm notebook delete <notebook_id> --confirm
# Returns: plain text confirmation
# Note: use --confirm NOT --force
```

**Important gotchas:**
- `--json` flag not supported on `nlm source add` — parse plain stdout
- `nlm login --check` triggers a `chmod 700` call that fails under Claude Code sandbox — use `nlm notebook list` for auth check instead
- Source text passed via temp file (`--file`), not `--text` flag, to avoid shell quoting issues with large strings
- `~/.notebooklm-mcp-cli/` directory must exist with `chmod 700` — was created manually; verify if running on a new machine

### 5 Validated Query Prompts (full text)

```python
PROMPTS = {

    "summary": (
        "For each paper in this notebook, complete these fields.\n"
        "Use the EXACT paper title as it appears in the source.\n"
        "Format strictly as shown — no markdown, no bullets:\n\n"
        "PAPER: [exact title]\n"
        "SUMMARY: [2 sentences]\n"
        "ADVANTAGE: [key strength] | [key strength]\n"
        "LIMITATION: [key weakness] | [key weakness]\n"
        "FUTURE_WORK: [one direction] | [one direction]\n"
        "===\n\n"
        "Rules:\n"
        "- If a field has no content, write NONE.\n"
        "- Do not add any text before the first PAPER: line.\n"
        "- Do not add any text after the last ===.\n"
        "- Repeat the block for EVERY paper in the notebook."
    ),

    "techniques": (
        "For each paper in this notebook, list technical methods.\n"
        "Use the EXACT paper title as it appears in the source.\n"
        "Format strictly as shown — no markdown, no bullets:\n\n"
        "PAPER: [exact title]\n"
        "INTRODUCES: [new method or model name] | [name]\n"
        "USES: [existing method the paper builds on] | [name]\n"
        "===\n\n"
        "Rules:\n"
        "- INTRODUCES = novel contributions the paper presents.\n"
        "- USES = existing prior work methods the paper applies.\n"
        "- Use short technical names, not full sentences.\n"
        "- If none, write NONE.\n"
        "- Repeat the block for EVERY paper in the notebook."
    ),

    "datasets": (
        "For each paper in this notebook, list every dataset used in experiments.\n"
        "Use the EXACT paper title as it appears in the source.\n"
        "Format strictly as shown — one DATASET line per dataset:\n\n"
        "PAPER: [exact title]\n"
        "DATASET: [dataset name] :: [what task or metric it evaluates]\n"
        "===\n\n"
        "Rules:\n"
        "- Use the canonical dataset name (e.g. ImageNet, not 'the image benchmark').\n"
        "- If no datasets are mentioned, write: DATASET: NONE\n"
        "- Repeat the block for EVERY paper in the notebook."
    ),

    "categories": (
        "Assign research category tags and methodology labels to each paper.\n"
        "Use the EXACT paper title as it appears in the source.\n"
        "Format strictly as shown — no markdown, no bullets:\n\n"
        "PAPER: [exact title]\n"
        "CATEGORIES: [tag] | [tag]\n"
        "METHODOLOGY: [approach name] | [approach name]\n"
        "===\n\n"
        "Rules:\n"
        "- CATEGORIES must come ONLY from this list:\n"
        "  LLM | Vision | Multimodal | Agentic-AI | Safety | Efficiency |\n"
        "  NLP | RL | Theory | Graph | Biomedical | Robotics | Code |\n"
        "  Retrieval | Generative\n"
        "- METHODOLOGY = high-level methodological approach (e.g. 'Fine-tuning',\n"
        "  'Mechanistic interpretability', 'Knowledge distillation').\n"
        "- 1–3 values per field. If unsure write NONE.\n"
        "- Repeat the block for EVERY paper in the notebook."
    ),

    "use_cases": (
        "For each paper in this notebook, describe practical use cases.\n"
        "Use the EXACT paper title as it appears in the source.\n"
        "Format strictly as shown — no markdown, no bullets:\n\n"
        "PAPER: [exact title]\n"
        "USE_CASE: [concrete 1-sentence application]\n"
        "USE_CASE: [second application if applicable]\n"
        "===\n\n"
        "Rules:\n"
        "- USE_CASE lines describe real-world applications, not research contributions.\n"
        "- Write at least 1 and at most 3 USE_CASE lines per paper.\n"
        "- Do not repeat the method name — describe the downstream use.\n"
        "- Repeat the block for EVERY paper in the notebook."
    ),
}
```

---

## 8. PDF Pipeline Status

### What is built and working

- **Stage 1 — Download**: `pdf_pipeline/downloader.py` — HTTP with retry, atomic write, `pdfs/{conf}/{year}/` directory layout
- **Stage 2 — Extract**: `pdf_pipeline/extractor.py` — PyMuPDF, ligature fix, header strip
- **Stage 3 — Segment**: `pdf_pipeline/segmenter.py` — 3-pass regex-v3, section detection, results-from-experiments merge
- **Stage 4 — Analyse**: `pdf_pipeline/analyser.py` — **DEPRECATED**. Lazy import (`from google import genai` only runs if `_get_client()` is called). Without `GEMINI_API_KEY`, stage 4 auto-skips. NotebookLM replaces this role entirely.

### `--stage segment` flag (added this session)

```bash
# Re-segment papers already in DB with the current segmenter version
python -m pdf_pipeline.run_pipeline --stage segment --limit 10
python -m pdf_pipeline.run_pipeline --stage segment --force --limit 10
```

`run_segment_only()` in `pipeline.py` reads `full_text` from existing `paper_sections` rows, re-segments, writes back. Without `--force`, skips papers already at `SEGMENTER_VERSION = "regex-v3"`.

### Current state

| Stage | Completed | Notes |
|-------|-----------|-------|
| Stage 1 — Download | **10 / 100** | Top 10 by citation; 71 MB in `pdfs/NeurIPS/2024/` |
| Stage 2 — Extract | **10 / 10** | Avg 5,984 words/paper |
| Stage 3 — Segment | **10 / 10** | All `regex-v3` ✓ |
| Stage 4 — Analyse | **0 / 10** | Deprecated; NotebookLM is the path forward |

### Section coverage (10 segmented papers)

```
abstract             10/10  (100%)
introduction         10/10  (100%)
conclusion            7/10   (70%) [3 papers use conclusion_fallback]
related_work          6/10   (60%)
experiments           5/10   (50%)
results_from_expts    4/10   (40%) [v3 fix: extracted from experiments body]
methodology           3/10   (30%)
discussion            3/10   (30%)
results               2/10   (20%)
```

Avg coverage: **66%**. The papers without methodology sections use custom section names (e.g. "3 AlphaLLM", "4 Our Approach") — these are not missing, just undetected by the header regex.

### CLI commands

```bash
cd /Users/kausthub.gupta/research-intelligence-platfrom
source .venv/bin/activate
export DATABASE_URL=sqlite:///research_platform.db

# Run stages 1-3 on remaining 90 papers (stage 4 auto-skips)
python -m pdf_pipeline.run_pipeline --limit 100

# Force re-segment all 10 already-done papers
python -m pdf_pipeline.run_pipeline --stage segment --force --limit 10

# Show report only
python -m pdf_pipeline.run_pipeline --report
```

---

## 9. Search Layer Status

### What is built

`search/query.py` — all functions return plain dicts (no ORM objects leak across session boundary).

| Function | Signature |
|----------|-----------|
| `search_papers(...)` | Multi-filter; returns list of dicts |
| `get_paper(paper_id)` | Single paper with conference name |
| `top_cited(n, conference, year)` | Convenience wrapper |
| `get_paper_authors(paper_id)` | Ordered author list |

### Filter contract

```python
from search.query import search_papers

results = search_papers(
    title="transformer",        # substring, case-insensitive
    conference="NeurIPS",       # exact short_name, case-insensitive
    year=2024,
    field="ML",                 # ML | CV | NLP | AI
    min_citations=50,
    max_citations=500,
    presentation_type="oral",   # oral | spotlight | poster | other
    has_pdf=True,
    limit=100,
    offset=0,
    order_by="citation_count",  # citation_count | year | title
    descending=True,
)
```

### What is NOT built in search

- Full-text search across `paper_sections.full_text` (SQLite FTS5 / PostgreSQL `pg_trgm`)
- Author name search (currently only title substring)
- **Category/technique filters** — tables now have data for 5 papers, but `search_papers()` does not yet filter on `paper_categories.name` or `paper_techniques.name`
- REST API (no web framework; `search/query.py` is pure Python)

---

## 10. Metrics Dashboard Status

```bash
python -m metrics.dashboard                     # all metrics
python -m metrics.dashboard --metric top-cited --n 20
python -m metrics.dashboard --json
```

| Metric | Current output |
|--------|---------------|
| `per-conference` | NeurIPS = 100 |
| `per-year` | 2024 = 100 |
| `top-cited` | Gorilla 1248, Refusal 716, ALPHALLM 150 ... |
| `citations` | mean=35.8, median=9, P90=42, max=1248 |

These numbers will become meaningful once multi-conference ingestion runs.

---

## 11. Known Bugs

| # | Bug | Severity | Location | Fix |
|---|-----|----------|----------|-----|
| 1 | `notebook_papers.source_status` stays `'pending'` for all 20 rows | Medium | No upload stage run yet | Fixed when orchestrator runs Stage C |
| 2 | `notebook_syntheses` table is empty — normalizer writes `extract_type` rows with `synthesis_id` pointing to fake UUIDs from test run | Low | `test_extraction.py` used fake IDs | When real orchestrator runs, it will write real synthesis rows first |
| 3 | `object-detection` second assignment for Multistep Distillation paper is wrong (score 0.086, borderline) | Low | `notebooklm/assigner.py` | Raise `_SECONDARY_THRESHOLD` from 0.04 to 0.06, or add `image-generation` abstract keywords |
| 4 | `notebook_paper_extracts` rows from test run reference fake notebook/synthesis UUIDs | Low | `test_extraction.py` | When real pipeline runs, `test_extraction.py` rows can be deleted or ignored |
| 5 | 3 papers have `S2 id = NULL` (citation enrichment failed) | Low | Papers: *Accelerating ERM…*, *Fairness-Quality Tradeoff…*, *Controlling Multiple Errors…* | Retry: `python -m ingestion.enrich_citations --force --limit 3` |
| 6 | `search_papers()` has no filter for `paper_categories` or `paper_techniques` | Medium | `search/query.py` | Add JOIN + WHERE clause for category/technique name filter |
| 7 | `ingestion/verify_pipeline.py` smoke test may reference old column names | Low | `ingestion/verify_pipeline.py` | Run it and check; fix any AttributeError |

---

## 12. Architectural Risks

| Risk | Severity | Description | Mitigation |
|------|----------|-------------|------------|
| No official NotebookLM API | **HIGH** | `notebooklm-mcp-cli` drives the web UI via internal RPC calls. Any Google UI change can break the integration silently or loudly. | All nlm calls isolated in `notebooklm/client.py`. `health_check()` called before every batch. Cookie auth expires every 2–4 weeks. |
| ~50 queries/day rate limit (free tier) | **HIGH** | 5 queries × 25+ notebooks = 125+ queries per full analysis pass. On free tier this takes 2–3 days. | Confirm account tier before scaling. Run synthesis as a background job over multiple days. |
| 50-source hard limit per notebook | **HIGH** | At 3,000–8,000 total papers, each topic will need 2–10 notebook instances. Cross-instance synthesis is not supported natively. | Cap at 45 sources. `notebooks.status='full'` triggers new instance. Accept cross-instance synthesis is weaker. |
| Response parsing brittleness | **MEDIUM** | NotebookLM is a language model, not a structured output API. Format compliance was 100% in validation (5 papers), but may degrade with larger/noisier notebooks. | Raw responses are stored. `confidence` field tracks parse quality. Unmatched titles logged as warnings. |
| Browser session durability | **MEDIUM** | Long upload jobs (45 papers × 3s = 135s) may hit session timeouts mid-batch. | Process uploads in batches of 10 with health check between. `source_status='pending'` enables per-paper resumption. |
| ORM / schema.sql divergence | **MEDIUM** | `db/models.py` (flat tables) and `db/schema.sql` (normalized entities) are not the same schema. The flat ORM is what's in SQLite. | Keep flat for dev. Normalize when migrating to PostgreSQL. Do not try to reconcile them prematurely. |
| `pip install` SSL issue on this machine | **LOW** | `OSStatus -26276` macOS keychain issue. Every pip install must include `--trusted-host` flags. | Always use: `pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org <package>` |

---

## 13. Remaining Files to Build

### Required for first full NotebookLM analysis pass

| File | Purpose | Depends on |
|------|---------|-----------|
| `notebooklm/pipeline.py` | 5-stage orchestrator (Assign→Provision→Upload→Synthesize→Extract) | All other notebooklm/ files |
| `notebooklm/run_pipeline.py` | CLI entry point (`--stage`, `--limit`, `--notebook-id`, `--force`) | pipeline.py |

### Required for web UI

| File | Purpose |
|------|---------|
| `api/app.py` | FastAPI app (already a dependency via fastmcp) |
| `api/routes/papers.py` | GET /papers with filters |
| `api/routes/paper.py` | GET /paper/{id} |
| `api/routes/notebooks.py` | GET /notebooks, GET /notebook/{id}/synthesis |
| `api/routes/search.py` | GET /search |

### Required before production

| File | Purpose |
|------|---------|
| PostgreSQL migration script | Applies all ORM models to PostgreSQL; runs 003–005 SQL files |
| `search/query.py` extension | Add category/technique filters |

---

## 14. Recommended Build Order

### Immediate (next session priority)

**1. Build `notebooklm/pipeline.py`** — the 5-stage orchestrator:

```
Stage A — Assign:    run assign_papers() on unassigned papers; write notebook_papers rows
Stage B — Provision: for each active Notebook without notebooklm_url, call create_notebook()
Stage C — Upload:    for each notebook_papers row with source_status='pending', call add_source()
Stage D — Synthesize: for each notebook where all sources uploaded, send 5 prompts; write notebook_syntheses rows
Stage E — Extract:   for each notebook_syntheses row with normalized=False, run extractor + normalizer
```

Key design requirements:
- Each stage must be independently resumable (check DB state, skip already-done)
- `--limit` controls how many uploads per run (browser sessions have finite lifetime)
- Stage D must write `notebook_syntheses` rows BEFORE calling normalizer (normalizer needs real synthesis_ids)
- `notebook_papers.upload_attempted_at` must be set before the upload call (detect stale attempts)

**2. Build `notebooklm/run_pipeline.py`** — CLI wrapping the pipeline

**3. Run first full pass on 10 already-segmented papers:**
```bash
python -m notebooklm.run_pipeline --limit 10
```

**4. Validate that `paper_analyses`, `paper_categories`, etc. have real data with correct notebook UUIDs**

### After first pass validates

**5. Expand corpus** — ingest all 18 remaining conference editions:
```bash
python -m ingestion.run_ingestion --all --limit 500
python -m ingestion.enrich_citations
python -m pdf_pipeline.run_pipeline --limit 2000
```

**6. Add category/technique filters to `search/query.py`**

**7. Build REST API** (FastAPI — already a transitive dependency via fastmcp)

**8. Migrate to PostgreSQL** when corpus exceeds ~500 papers

---

## 15. Progress Estimate

| Layer | Status | % Done |
|-------|--------|--------|
| DB schema (all 16 tables) | Complete | 100% |
| Ingestion pipeline | Complete for NeurIPS; config for all 10 | 15% (1/19 editions ingested) |
| PDF pipeline (stages 1–3) | Complete code; 10/100 papers processed | 10% (10/100 papers) |
| Citation enrichment | 97/100 for existing corpus | ~5% of eventual corpus |
| Search layer | Complete; missing category/technique filters | 80% |
| Metrics dashboard | Complete | 100% |
| NotebookLM client | Complete and validated | 100% |
| NotebookLM assigner | Complete (10 papers assigned) | 100% |
| NotebookLM source_prep | Complete and tested | 100% |
| NotebookLM extractor | Complete and tested | 100% |
| NotebookLM normalizer | Complete and tested | 100% |
| **NotebookLM pipeline orchestrator** | **Not built** | **0%** |
| REST API / web frontend | Not started | 0% |
| PostgreSQL migration | Not executed | 0% |

**Overall platform completeness: ~45%**

The backend extraction machinery is complete and proven. The gap is the orchestrator that connects the pieces into a single runnable pipeline, and the frontend that surfaces the data.

---

## 16. Exact Next Prompt for a Fresh Claude Code Session

Paste the following as the first message in a new Claude Code session:

---

Read these documents completely before doing anything:

- `docs/project_state_handoff_v3.md`

Then do the following tasks in order. Stop and report after completing all of them.

**Task 1 — Build `notebooklm/pipeline.py`**

Implement the 5-stage orchestrator with these requirements:

- **Stage A — Assign**: call `assign_papers()` on all papers without a `notebook_papers` row. Skip papers already assigned.
- **Stage B — Provision**: for each `Notebook` row that has `notebooklm_url IS NULL`, call `client.create_notebook()` and save the URL back to the DB. Skip notebooks that already have a URL.
- **Stage C — Upload**: for each `notebook_papers` row with `source_status='pending'`, build the source doc with `source_prep.build_source()` and upload with `client.add_source()`. Set `upload_attempted_at` before the call. Set `source_status='uploaded'` on success, `'error'` on failure. Process in batches of 10 with a 3-second delay between uploads.
- **Stage D — Synthesize**: for each notebook where all its `notebook_papers` rows have `source_status='uploaded'`, send all 5 query prompts from the `PROMPTS` dict (defined in `notebooklm/validate_prompts.py`, also reproduced in handoff section §7). Write each response as a `NotebookSynthesis` row (`synthesis_type='query_response'`). Skip if the synthesis row already exists.
- **Stage E — Extract**: for each `NotebookSynthesis` row with `normalized=False`, run `extractor.extract_all()` then `normalizer.normalize()`. Mark `normalized=True` when done.

The pipeline function signature should be:
```python
def run(
    limit: int = 10,           # max upload operations per run (Stage C)
    notebook_id: str | None = None,  # restrict to one notebook if given
    force: bool = False,       # re-run even if already done
) -> PipelineStats
```

Return a `PipelineStats` dataclass with counts for each stage.

**Task 2 — Build `notebooklm/run_pipeline.py`**

CLI entry point with flags: `--limit`, `--notebook-id`, `--force`, `--stage` (choices: assign, provision, upload, synthesize, extract, all).

**Task 3 — Run the full pipeline on the 10 already-segmented papers**

```bash
python -m notebooklm.run_pipeline --limit 10
```

Verify all 5 stages complete successfully. After the run, confirm:
- All `notebook_papers.source_status` = `'uploaded'` for the 10 papers
- `notebook_syntheses` has rows for each notebook that received papers
- `paper_analyses`, `paper_techniques`, `paper_categories`, `paper_datasets`, `paper_methodologies` all have data for the 10 papers
- `paper_analyses.model` contains a real notebook UUID (not the fake test UUID)

**Do not build the web API. Do not expand the corpus. Stop after Task 3 and provide a status report.**

---

## Appendix A: Environment Setup

```bash
# Navigate to project
cd /Users/kausthub.gupta/research-intelligence-platfrom

# Activate virtualenv
source .venv/bin/activate

# Set DB URL (SQLite dev)
export DATABASE_URL=sqlite:///research_platform.db

# Verify DB state
python inspect_db.py

# Verify nlm auth
nlm notebook list

# If not authenticated:
nlm login

# Run metrics
python -m metrics.dashboard

# pip install (always use these flags due to SSL issue)
pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org <package>
```

## Appendix B: Key Commands Reference

```bash
# Ingest a conference
python -m ingestion.run_ingestion --conference ICLR --year 2024 --limit 500

# Ingest all configured editions
python -m ingestion.run_ingestion --all --limit 500

# Enrich citations
python -m ingestion.enrich_citations
python -m ingestion.enrich_citations --report-only
python -m ingestion.enrich_citations --force --limit 3  # retry 3 failed

# PDF pipeline (stages 1-3)
python -m pdf_pipeline.run_pipeline --limit 100
python -m pdf_pipeline.run_pipeline --stage segment --force --limit 10

# Search
python -c "from search.query import search_papers; print(search_papers(conference='NeurIPS', min_citations=50))"

# Metrics
python -m metrics.dashboard --metric top-cited --n 20

# NotebookLM validation (creates and deletes a test notebook)
python -m notebooklm.validate_prompts

# NotebookLM smoke test (full create/upload/query/delete cycle, 3 papers)
python -m notebooklm.smoke_test

# Extraction test (offline, uses saved validation_results.json)
python -m notebooklm.test_extraction
```

## Appendix C: pip SSL Workaround

The system Python and `.venv` both have `OSStatus -26276` (macOS keychain trust). **Every pip install must include:**

```bash
pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org <package>
```

## Appendix D: NotebookLM Auth Notes

- Cookies: `~/.notebooklm-mcp-cli/profiles/default/cookies.json`
- Lifetime: 2–4 weeks from last `nlm login`
- Re-auth: `nlm login` (opens Chrome)
- Auth check: `nlm notebook list --json` (returns `[]` if no notebooks; returns list if auth valid)
- **Do not use** `nlm login --check` — triggers `chmod 700` that fails under Claude Code sandbox
- `~/.notebooklm-mcp-cli/` was created manually with `chmod 700` on this machine; re-create if on a new machine

## Appendix E: 3 Unmatched S2 Papers

These 3 papers have `semantic_scholar_id = NULL` and `last_enriched_at` set. They appear enriched but have no citation data. Retry when S2 indexes them:

```bash
python -m ingestion.enrich_citations --force --limit 3
```

Papers:
1. *Accelerating ERM for data-driven algorithm design using output-sensitive…*
2. *The Fairness-Quality Tradeoff in Clustering*
3. *Controlling Multiple Errors Simultaneously with a PAC-Bayes Bound*
