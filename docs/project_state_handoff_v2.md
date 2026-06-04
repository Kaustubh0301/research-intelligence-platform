# Research Intelligence Platform — Project State Handoff v2

**Date:** June 4, 2026  
**Purpose:** Full project context for a new Claude Code session to continue work without context loss  
**Status:** Backend infrastructure complete · NotebookLM validated · Integration not yet built

---

## 1. Current Project Goal

Build a **Research Intelligence Platform** that:

- Automatically collects research papers from the 10 major AI/ML conferences (2024–2026)
- Makes all papers searchable and filterable by citation count, year, author, conference, category, and title
- Uses **NotebookLM** to synthesize topic-level analysis: summaries, techniques, methodologies, datasets, limitations, and research gaps
- Surfaces analysis outputs through a web interface backed by a structured database

The platform is for researchers who need to navigate a large, multi-conference corpus efficiently. It is **not** a chatbot — all interaction is structured (filter, search, browse).

---

## 2. Manager Requirements

Provided verbatim as the authoritative spec:

- Research papers should be automatically collected
- Research papers should be searchable
- Search should support filters: citation count, year, author, conference, category, title
- Platform should help users discover techniques, methodologies, limitations, and research gaps
- **NotebookLM should handle analysis, summarization, and extraction** (this decision was made after investigation — see §9–11)
- Do NOT implement a chatbot
- Do NOT depend on the Gemini API

**Target conferences:** NeurIPS · ICML · ICLR · CVPR · ICCV · ECCV · ACL · EMNLP · AAAI · IJCAI  
**Target years:** 2024 · 2025 · 2026 (up to May)

---

## 3. Current Architecture

```
OpenReview API          Semantic Scholar API
      │                        │
      ▼                        ▼
ingestion/fetch_openreview.py  ingestion/fetch_semantic_scholar.py
      │                        │
      └──────────┬─────────────┘
                 ▼
         ingestion/store.py
                 │
                 ▼
    ┌────────────────────────┐
    │  SQLite (dev)          │   ← research_platform.db
    │  PostgreSQL (prod)     │   ← db/schema.sql
    └────────────────────────┘
           ▲          ▲
           │          │
pdf_pipeline/     search/          metrics/
(stages 1–3)      query.py         dashboard.py
           │
           ▼
    paper_sections
    (extracted text)
           │
           ▼  ← NOT YET BUILT
    notebooklm/              ← topic assignment + upload + query + extraction
           │
           ▼
    paper_analyses
    paper_categories
    paper_techniques
    paper_methodologies
    paper_datasets
```

### Data flow (what is built)

```
OpenReview / S2  ──►  fetch_*  ──►  papers + authors + paper_authors (DB)
                                          │
Semantic Scholar  ◄──────────── papers.title
        │
        └──►  papers.citation_count
              papers.influential_citation_count
              papers.semantic_scholar_id
                     │
      pdf_url  ──►  downloader  ──►  pdfs/{conf}/{year}/*.pdf
                         │
                    extractor  ──►  papers.pdf_word_count
                         │
                    segmenter  ──►  paper_sections.*     [stored as regex-v2]
                         │
                    [analyser]  ──►  PENDING (was Gemini; now NotebookLM)
```

### Data flow (what is planned — NotebookLM layer)

```
paper_sections.full_text (or assembled sections)
        │
        ▼
notebooklm/assigner.py      ← keyword scoring → notebook_papers rows
        │
        ▼
notebooklm/client.py        ← wraps jacob-bd/notebooklm-mcp-cli CLI
        │
        ├──►  notebook create     (one per topic × instance)
        ├──►  source add          (one per paper per notebook)
        └──►  notebook query      (5 structured prompts per notebook)
                    │
                    ▼
        notebooklm/extractor.py  ← parse prose → structured extracts
                    │
                    ▼
        notebooklm/normalizer.py ← write to paper_analyses, paper_categories, etc.
```

---

## 4. Database Schema Summary

### ORM models in use (`db/models.py`) — 12 tables

| Table | Rows (live) | Purpose |
|-------|-------------|---------|
| `conferences` | 1 | Venue master: NeurIPS, ICML, etc. |
| `conference_editions` | 1 | Year-specific instances (NeurIPS 2024) |
| `papers` | 100 | Core entity — one row per paper |
| `authors` | 444 | De-duplicated author entities |
| `paper_authors` | 450 | Ordered author↔paper links (position, affiliation) |
| `paper_sections` | 10 | Extracted section text (abstract, intro, methodology, etc.) |
| `paper_datasets` | 0 | Datasets extracted by analysis — empty, pending |
| `paper_analyses` | 0 | Per-paper LLM summary — empty, pending |
| `paper_categories` | 0 | Topic tags per paper — empty, pending |
| `paper_techniques` | 0 | Technique tags per paper — empty, pending |
| `paper_methodologies` | 0 | Methodology tags per paper — empty, pending |
| `pipeline_errors` | 0 | Append-only error log |

**Four additional tables are needed** before the NotebookLM pipeline can run:
`notebooks`, `notebook_papers`, `notebook_syntheses`, `notebook_paper_extracts` — defined in `docs/notebooklm_architecture_report.md` §5. Migration 005 has not been created yet.

### Key column notes

- All PKs are UUID strings generated client-side (`uuid.uuid4()`)
- `papers.last_enriched_at` — resumption flag for citation enrichment
- `papers.pdf_local_path` — resumption flag for PDF download
- `paper_sections.segmenter_version` — currently `"regex-v2"` for all 10 rows; regex-v3 is the current code version but has **not** been written back to DB
- `paper_analyses.model` — was intended for Gemini model name; will now store `"notebooklm/notebook:{notebook_id}"`

### Schema divergence

`db/schema.sql` (PostgreSQL reference DDL) defines a normalized design with standalone `categories`, `techniques`, `methodologies` entity tables and proper join tables. `db/models.py` (the actual ORM) uses simpler flat tables (`paper_categories(name, confidence)`, etc.). **These are not the same schema.** Resolution plan: flat ORM for SQLite dev; normalize to schema.sql when migrating to PostgreSQL.

### Migrations

| File | Status | Purpose |
|------|--------|---------|
| `db/migrations/003_pdf_pipeline_tables.sql` | Applied | Added `pdf_local_path`, `pdf_word_count`, `pdf_extracted_at` to papers; created `paper_sections`, `paper_datasets`, `paper_analyses`, `pipeline_errors` |
| `db/migrations/004_analysis_tables.sql` | Applied | Created `paper_categories`, `paper_techniques`, `paper_methodologies` |
| Migration 005 (not yet created) | Pending | Will create `notebooks`, `notebook_papers`, `notebook_syntheses`, `notebook_paper_extracts` |

### SQLite vs PostgreSQL

`db/migrate.py` handles column additions for SQLite using SQLAlchemy `inspect()`. Called automatically at startup by `run_migrations()`. PostgreSQL uses `IF NOT EXISTS` in migration SQL files.

---

## 5. Ingestion Pipeline Status

### What is built

| File | Purpose |
|------|---------|
| `ingestion/conferences_config.py` | Master catalogue: 10 conferences × 19 editions (2024–2026) |
| `ingestion/fetch_openreview.py` | OpenReview API fetcher → `RawPaper` dataclass |
| `ingestion/fetch_semantic_scholar.py` | S2 bulk endpoint fetcher (for non-OpenReview conferences) |
| `ingestion/store.py` | Idempotent upserts: conference, edition, paper, authors, paper_authors |
| `ingestion/enrich_citations.py` | S2 citation enrichment with resumption flag and retry |
| `ingestion/run_ingestion.py` | CLI: `--conference NeurIPS --year 2024 --limit 500` or `--all` |
| `ingestion/verify_pipeline.py` | In-memory SQLite smoke test (no DB needed) |

### Current ingestion state

- **Conferences in DB:** NeurIPS only (1 of 10)
- **Editions in DB:** NeurIPS 2024 only (1 of 19 configured)
- **Papers in DB:** 100 (first 100 by API return order from OpenReview)
- **Authors in DB:** 444
- **Paper-author links:** 450

### Citation enrichment state

- 100/100 papers attempted
- **97/100 matched** via Semantic Scholar (97%)
- **3 unmatched** (S2 id is NULL, `last_enriched_at` is set so they appear done):
  1. *Accelerating ERM for data-driven algorithm design using output-sensitive…*
  2. *The Fairness-Quality Tradeoff in Clustering*
  3. *Controlling Multiple Errors Simultaneously with a PAC-Bayes Bound*
- Total citations across corpus: 3,583 · Highest: Gorilla (1,248)
- Re-retry with: `python -m ingestion.enrich_citations --force --limit 3`

### How to run ingestion

```bash
cd /Users/kausthub.gupta/research-intelligence-platfrom
source .venv/bin/activate
export DATABASE_URL=sqlite:///research_platform.db

# List all configured editions
python -m ingestion.run_ingestion --list

# Ingest one conference+year
python -m ingestion.run_ingestion --conference ICLR --year 2024 --limit 500

# Ingest all configured editions
python -m ingestion.run_ingestion --all --limit 500

# Enrich citations for new papers
python -m ingestion.enrich_citations --report-only
python -m ingestion.enrich_citations
```

### Conference configuration

19 editions across 10 conferences are configured in `ingestion/conferences_config.py`:

| Conference | Field | Source | Years configured |
|------------|-------|--------|-----------------|
| NeurIPS | ML | OpenReview | 2024, 2025 |
| ICLR | ML | OpenReview | 2024, 2025, 2026 |
| ICML | ML | OpenReview | 2024, 2025 |
| CVPR | CV | Semantic Scholar | 2024, 2025 |
| ICCV | CV | Semantic Scholar | 2025 |
| ECCV | CV | Semantic Scholar | 2024 |
| ACL | NLP | Semantic Scholar | 2024, 2025 |
| EMNLP | NLP | Semantic Scholar | 2024, 2025 |
| AAAI | AI | Semantic Scholar | 2024, 2025 |
| IJCAI | AI | Semantic Scholar | 2024, 2025 |

OpenReview requires an `invitation` string; Semantic Scholar uses `venue` name + year filter on the bulk endpoint.

---

## 6. PDF Pipeline Status

### What is built

| File | Purpose |
|------|---------|
| `pdf_pipeline/downloader.py` | HTTP download with retry, atomic write to `pdfs/{conf}/{year}/` |
| `pdf_pipeline/extractor.py` | PyMuPDF text extraction, ligature fix, header strip |
| `pdf_pipeline/segmenter.py` | 3-pass regex section detector (regex-v3 in code) |
| `pdf_pipeline/store.py` | Upserts for sections, datasets, analyses, errors |
| `pdf_pipeline/pipeline.py` | 4-stage orchestrator (stage 4 auto-skips without Gemini key) |
| `pdf_pipeline/run_pipeline.py` | CLI entry point |
| `pdf_pipeline/analyser.py` | Gemini stage 4 — **deprecated**, google.genai import is now lazy |

### Current PDF state

- **PDFs downloaded:** 10 / 100 papers (top 10 by citation count)
- **Storage:** `pdfs/NeurIPS/2024/` — 10 files, 71 MB total, range 570 KB–31 MB
- **Text extracted:** 10 / 10 (avg 5,984 words/paper)
- **Sections segmented:** 10 / 10 — stored as `regex-v2` in DB
- **Analysis run:** 0 / 10 (Gemini key never provided; now replaced by NotebookLM)

### Critical note on segmenter version

The 10 rows in `paper_sections` were written with the old `regex-v2` segmenter. The current `pdf_pipeline/segmenter.py` is `regex-v3` and includes four bug fixes. **The DB has not been updated.** Run:

```bash
python -m pdf_pipeline.run_pipeline --stage segment --force --limit 10
```

This is blocked in the current `run_pipeline.py` CLI (it processes all 4 stages, not individual ones). The `--stage` flag is not implemented — it would need to be added, or the `run()` function in `pipeline.py` called directly with stage control.

### How to run the PDF pipeline

```bash
# Run stages 1-3 on remaining 90 papers (stage 4 auto-skips — no Gemini key)
python -m pdf_pipeline.run_pipeline --limit 100

# Force reprocess already-downloaded papers
python -m pdf_pipeline.run_pipeline --limit 10 --force

# Show report only (no processing)
python -m pdf_pipeline.run_pipeline --report
```

### Stage 4 (analysis) status

`pdf_pipeline/analyser.py` uses the Gemini API. The `from google import genai` import is now lazy (only executes when `_get_client()` is called). When `GEMINI_API_KEY` is absent, `run_pipeline.py` sets `skip_llm=True` automatically and prints a note. **This file is deprecated** — stage 4 analysis is now handled by NotebookLM, not Gemini.

### Conference name in pipeline

`pdf_pipeline/pipeline.py` previously hardcoded `conference="NeurIPS"` in the downloader call. This was fixed — it now derives the conference short_name from the DB via the paper's `conference_edition_id` → `conference_editions` → `conferences` join.

---

## 7. Search/Filter Layer Status

### What is built

`search/query.py` — all functions return plain dicts (no ORM dependency after session closes).

| Function | Purpose |
|----------|---------|
| `search_papers(...)` | Multi-filter search: conference, year, field, citation range, presentation_type, has_pdf, title substring. Paginated, sortable. |
| `get_paper(paper_id)` | Single paper by ID with joined conference name |
| `top_cited(n, conference, year)` | Convenience wrapper around search_papers |
| `get_paper_authors(paper_id)` | Ordered author list for a paper |

### Filter contract

```python
from search.query import search_papers

results = search_papers(
    title="transformer",       # substring, case-insensitive
    conference="NeurIPS",      # exact short_name, case-insensitive
    year=2024,
    field="ML",                # ML | CV | NLP | AI
    min_citations=50,
    max_citations=500,
    presentation_type="oral",  # oral | spotlight | poster | other
    has_pdf=True,
    limit=100,
    offset=0,
    order_by="citation_count", # citation_count | year | title
    descending=True,
)
```

### What is not built yet

- Full-text search across `paper_sections.full_text` (SQLite FTS5 / PostgreSQL `pg_trgm`)
- Author name search (currently only via title substring)
- Category/technique filters (tables are empty until NotebookLM runs)
- REST API layer (no web framework yet — `search/query.py` is pure Python)

---

## 8. Metrics/Dashboard Status

### What is built

`metrics/dashboard.py` — CLI tool with four metrics, text output with bar charts, or `--json` for programmatic use.

```bash
python -m metrics.dashboard                    # all four metrics
python -m metrics.dashboard --metric per-conference
python -m metrics.dashboard --metric per-year
python -m metrics.dashboard --metric top-cited --n 20
python -m metrics.dashboard --metric citations
python -m metrics.dashboard --json
```

### Available metrics

| Metric | Description |
|--------|-------------|
| `per-conference` | Paper count per venue, sorted descending, bar chart |
| `per-year` | Paper count per year, sorted ascending |
| `top-cited` | Top-N papers by citation count (default N=20) |
| `citations` | Histogram: mean, median, P75/P90/P99, log-scale buckets |

### Current output (live)

```
Papers per Conference: NeurIPS = 100
Papers per Year:       2024 = 100
Citation stats:        mean=35.8  median=9  P90=42  max=1248
```

These numbers will become meaningful once multi-conference ingestion runs.

---

## 9. NotebookLM Investigation Findings

### Background

The manager decided that NotebookLM will handle analysis, summarization, and extraction. Two repositories were evaluated:

1. **PleasePrompto/notebooklm-mcp** — older, limited automation
2. **jacob-bd/notebooklm-mcp-cli** — unified CLI + MCP server, chosen

### Why jacob-bd was selected

- Automatic notebook creation
- Source ingestion (URL, text, file, Drive, YouTube)
- `--wait` flag for source processing confirmation
- Batch operations and cross-notebook queries
- Tagging and pipeline support
- Better automation support overall

### Key findings from investigation

- **No official API.** The library automates the NotebookLM web UI via internal RPC calls and browser-based cookie authentication. Google may change the UI or internal API without notice.
- **50-source limit per notebook** — hard constraint. The architecture uses 30–45 papers/notebook as the target to stay safely under the limit.
- **Rate limit:** ~50 queries/day on free tier. Google AI Ultra / Pro accounts have higher limits.
- **Cookie auth** persists 2–4 weeks, then requires `nlm login` again.
- **Query response format:** JSON with `answer` (prose, citation-tagged) and `citations` (array of `{source_id, citation_number, cited_text}`). The citations field enables mapping claims back to exact source sentences — higher fidelity than expected.

Full architecture analysis: `docs/notebooklm_architecture_report.md`

---

## 10. Repository Selection Decision

**Selected: jacob-bd/notebooklm-mcp-cli**  
**PyPI package:** `notebooklm-mcp-cli`  
**Version in use:** 0.7.0 (released June 3, 2026)  
**Installed in:** project `.venv/`

### NotebookLM architecture decision

| Principle | Decision |
|-----------|----------|
| Is NotebookLM the DB? | No. DB is source of truth for all metadata, citations, search. |
| What does NotebookLM do? | Analysis only: summaries, technique/methodology/dataset/limitation extraction |
| Notebooks per paper? | No. Topic-based notebooks: 30–45 papers per notebook. |
| Number of topics? | 25 initial topics across 7 domains (see architecture report) |
| Multi-topic papers? | Yes, up to 2 notebooks per paper for cross-disciplinary work |
| Output storage? | 4 new tables → then normalized into existing analysis tables |

---

## 11. NotebookLM Validation Results

### Environment setup

```
Package:  notebooklm-mcp-cli 0.7.0
Install:  pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org notebooklm-mcp-cli
          pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org "httpx[socks]"
Auth dir: ~/.notebooklm-mcp-cli/profiles/default/cookies.json  (17KB, valid)
```

**Important:** The system pip has an SSL certificate issue (`OSStatus -26276`) with pypi.org. Always use the `--trusted-host` flags shown above for any pip install. The issue affects the system Python at `/Library/Frameworks/Python.framework/Versions/3.14/` — the project `.venv/` pip has the same issue.

**Also important:** `~/.notebooklm-mcp-cli/` must be created manually with `chmod 700` before the first `nlm` command. The Claude Code sandbox cannot create directories in `$HOME` without `dangerouslyDisableSandbox=true`. This was done; the directory and subdirectories exist and are owned by `kausthub.gupta`.

### Validated commands and exact signatures

```bash
# List notebooks — confirms auth; supports --json
nlm notebook list --json
# → [{id, title, source_count, updated_at}, ...]

# Create notebook — supports --json
nlm notebook create "Topic Name" --json
# → {notebook_id, title, url, message}

# Add source — does NOT support --json; parse stdout
nlm source add <notebook_id> --text "<content>" --title "<title>" --wait
# → plain text: confirmation message

# Query notebook — supports --json
nlm notebook query <notebook_id> "<prompt>" --json
# → {answer: "<prose with [1] citations>", citations: [{source_id, citation_number, cited_text}...]}

# Delete notebook — use --confirm, NOT --force
nlm notebook delete <notebook_id> --confirm
# → plain text: confirmation
```

### End-to-end test result

**Test script:** `/tmp/nlm_validate.py` (not in project codebase)

**Paper used:** Gorilla: Large Language Model Connected with Massive APIs (1,248 citations, 4/6 sections present, 41,905-char source text)

| Step | Result |
|------|--------|
| Auth check (via `notebook list`) | ✅ 1 notebook visible |
| Notebook create | ✅ ID returned in JSON |
| Source add (41,905-char text, `--wait`) | ✅ Processed |
| Notebook query (5-part structured prompt) | ✅ Full structured response returned |
| Notebook delete (`--confirm`) | ✅ Deleted |

**Query prompt used:**
```
"Summarize this paper and list: (1) techniques introduced or used, (2) methodologies, (3) datasets mentioned, (4) stated limitations, (5) future work directions."
```

**Response quality:** Excellent. NotebookLM returned all 5 sections correctly structured, with inline citation numbers (`[1]`, `[2]`, etc.) and a `citations` array containing the exact source sentences. Output was precise enough that no prompt engineering iteration was needed.

### Known account state

There is one notebook left in the NotebookLM account from a partial earlier validation run:
- **Title:** `NLM_Validation_Test`  
- **ID:** `3914c5ce-b056-445c-96cc-5adef58e2a76`  
- **Source count:** 0  

This should be deleted before integration work begins:
```bash
source .venv/bin/activate
nlm notebook delete 3914c5ce-b056-445c-96cc-5adef58e2a76 --confirm
```

---

## 12. Risks and Open Questions

### Active risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| No official NotebookLM API — library automates browser UI | High | Isolate all MCP calls in `notebooklm/client.py`; run `health_check()` before every batch job; pin library to commit hash |
| 50-source hard limit per notebook | High | Cap notebooks at 45 papers; use multi-instance naming (`llm-efficiency-1`, `llm-efficiency-2`) |
| Query response parsing is fragile (prose output, not structured) | Medium | Request specific `PAPER: / SECTION:` formats; use existing fuzzy title-matching from `enrich_citations.py`; store all raw extracts even if unparseable |
| Browser session expires mid-batch | Medium | Process uploads in batches of 10 with health check between; resumption via `notebook_papers.source_status` |
| `pip install` SSL issue on this machine | Low | Always use `--trusted-host pypi.org --trusted-host files.pythonhosted.org` |
| `~/.notebooklm-mcp-cli` permissions need manual setup | Low | Directory already created and configured; recheck if new user or machine |
| Segmenter DB state is regex-v2, code is regex-v3 | Low | Run `--force` re-segment on the 10 papers before NotebookLM upload |
| 3 papers unmatched in S2 enrichment | Low | Retry with `--force` after S2 indexes them |

### Open questions for the manager

1. **Google account type:** Is the account used for NotebookLM a free tier, Pro, or Google AI Ultra? This determines the ~50 queries/day vs higher limits for the synthesis step.
2. **Web UI framework:** No frontend has been chosen or started. The product design doc (`docs/product_design.md`) specifies routes and components but no implementation language or framework.
3. **PostgreSQL:** When should the migration from SQLite to PostgreSQL happen? The architecture report suggests at ~500 papers, but this is a guess.
4. **Corpus scope:** Should we prioritize getting all 10 conferences × 3 years ingested first, or get the NotebookLM pipeline running on the existing 100-paper corpus first?
5. **`notebooklm/` module ownership:** The architecture report defines 8 new files. Should these be built before or after expanding ingestion to all conferences?

---

## 13. Next Recommended Steps

In priority order, based on current state:

### Immediate (before any new features)

**1. Clean up leftover test notebook**
```bash
source .venv/bin/activate
nlm notebook delete 3914c5ce-b056-445c-96cc-5adef58e2a76 --confirm
```

**2. Re-segment 10 papers with regex-v3**
The 10 rows in `paper_sections` were written by the old regex-v2 segmenter. Run a force re-segment to get clean v3 data before uploading to NotebookLM.
```bash
# Note: --stage flag not yet implemented in run_pipeline.py
# Workaround: call pipeline.run(force=True, skip_llm=True, limit=10)
# then manually call the segmenter store for those papers
```
This requires a small code addition to `run_pipeline.py` to support `--stage segment`.

### Phase 1: Corpus expansion

**3. Ingest remaining 18 conference editions**
```bash
python -m ingestion.run_ingestion --all --limit 500
# Then enrich citations for all new papers:
python -m ingestion.enrich_citations
```
Expected result: ~3,000–8,000 papers across all 10 conferences and 19 editions.

**4. Run PDF pipeline on remaining papers**
```bash
python -m pdf_pipeline.run_pipeline --limit 1000
```
Stages 1–3 only (download, extract, segment). Stage 4 auto-skips.

### Phase 2: NotebookLM integration

**5. Create DB migration 005**
Add `notebooks`, `notebook_papers`, `notebook_syntheses`, `notebook_paper_extracts` tables. Schema defined in `docs/notebooklm_architecture_report.md` §5.1.

**6. Build `notebooklm/` module** (8 files)
In this order:
- `notebooklm/topic_keywords.json` — keyword vocabulary for 25 topics
- `notebooklm/assigner.py` — topic assignment via keyword scoring
- `notebooklm/source_prep.py` — assemble uploadable text from `paper_sections`
- `notebooklm/client.py` — wrapper around `nlm` CLI commands
- `notebooklm/extractor.py` — parse NotebookLM query responses
- `notebooklm/normalizer.py` — write extracts to `paper_analyses`, etc.
- `notebooklm/pipeline.py` — 5-stage orchestrator (Assign → Provision → Upload → Synthesize → Extract)
- `notebooklm/run_pipeline.py` — CLI entry point

**7. Run first analysis pass**
Start with the 10 papers already segmented. Create notebooks, upload, query, extract. Validate output quality before scaling to the full corpus.

### Phase 3: Web UI

**8. Choose and implement web framework**
The product design (`docs/product_design.md`) defines 4 routes, all components, and the full API contract. The backend data is ready. A REST API layer needs to be built (FastAPI recommended — already pulls in as a dependency of `notebooklm-mcp-cli` via `fastmcp`).

---

## Appendix A: Key File Reference

```
/Users/kausthub.gupta/research-intelligence-platfrom/
│
├── research_platform.db           ← SQLite dev database
├── pdfs/NeurIPS/2024/             ← 10 PDFs, 71 MB
├── requirements.txt
│
├── db/
│   ├── models.py                  ← 12-table SQLAlchemy ORM
│   ├── session.py                 ← engine, get_session(), ping()
│   ├── migrate.py                 ← run_migrations() — called at startup
│   ├── schema.sql                 ← PostgreSQL reference DDL (normalized)
│   ├── seeds/conferences.sql      ← 10 conference seed rows
│   └── migrations/
│       ├── 003_pdf_pipeline_tables.sql
│       └── 004_analysis_tables.sql
│
├── ingestion/
│   ├── conferences_config.py      ← 10 conf × 19 editions catalogue
│   ├── fetch_openreview.py        ← OpenReview fetcher → RawPaper
│   ├── fetch_semantic_scholar.py  ← S2 bulk fetcher → RawPaper
│   ├── store.py                   ← idempotent upserts
│   ├── enrich_citations.py        ← S2 citation enrichment
│   ├── run_ingestion.py           ← CLI: --conference --year --limit --all
│   └── verify_pipeline.py         ← smoke test
│
├── pdf_pipeline/
│   ├── downloader.py              ← HTTP download, retry, atomic write
│   ├── extractor.py               ← PyMuPDF extraction
│   ├── segmenter.py               ← regex-v3 section segmenter
│   ├── store.py                   ← upserts for sections/analyses/errors
│   ├── pipeline.py                ← 4-stage orchestrator (stage 4 skippable)
│   ├── run_pipeline.py            ← CLI: --limit --skip-llm --force
│   └── analyser.py                ← [DEPRECATED] Gemini stage 4
│
├── search/
│   └── query.py                   ← search_papers(), top_cited(), etc.
│
├── metrics/
│   └── dashboard.py               ← CLI: --metric per-conference|per-year|top-cited|citations
│
└── docs/
    ├── project_handoff.md                   ← original handoff (v1)
    ├── project_state_handoff_v2.md          ← THIS DOCUMENT
    ├── product_design.md                    ← UX/product design spec
    ├── notebooklm_architecture_report.md    ← NotebookLM integration design
    ├── paper_collection_report.md           ← API survey: S2, OpenAlex, etc.
    ├── pdf_pipeline_architecture.md         ← PDF pipeline design
    └── understanding_pipeline_architecture.md ← LLM pipeline design (pre-NotebookLM)
```

## Appendix B: Environment Setup for a New Session

```bash
# 1. Navigate to project
cd /Users/kausthub.gupta/research-intelligence-platfrom

# 2. Activate virtualenv
source .venv/bin/activate

# 3. Set database URL
export DATABASE_URL=sqlite:///research_platform.db

# 4. Verify DB state
python inspect_db.py

# 5. Verify nlm CLI is authenticated
nlm notebook list

# 6. If nlm is not authenticated (no cookies):
nlm login
# → Chrome opens, sign in with Google, cookies are saved automatically

# 7. Run metrics to see current corpus state
python -m metrics.dashboard

# 8. If pip install is needed:
pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org <package>
```

## Appendix C: pip SSL Workaround

The system Python and the project `.venv` both have an SSL certificate issue with pypi.org on this machine (`OSStatus -26276`, macOS keychain trust issue). **Every `pip install` command must include:**

```bash
pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org <package>
```

This is not a security risk in a local dev context — it bypasses certificate verification for PyPI only.

## Appendix D: NotebookLM Auth Notes

- **Cookies file:** `~/.notebooklm-mcp-cli/profiles/default/cookies.json`
- **Cookie lifetime:** 2–4 weeks from last `nlm login`
- **Re-auth:** Run `nlm login` (opens Chrome, user signs in, cookies saved)
- **Auth check** (without triggering the chmod bug): `nlm notebook list --json`
  - `login --check` triggers a `chmod 700` on the profile directory that fails under sandbox execution; `notebook list` makes the same API call without the post-check save
- **`~/.notebooklm-mcp-cli/` permissions:** Created with `chmod 700` (must be done with `dangerouslyDisableSandbox=true` from Claude Code, or manually in a terminal). Subdirectory structure: `profiles/`, `profiles/default/`, `cache/`, `chrome-profiles/`.
