# Research Intelligence Platform — Project Handoff

**Date:** June 2026  
**Status:** Active development — ingestion and PDF extraction complete, LLM analysis pending  
**Database:** SQLite (dev) at `research_platform.db` → PostgreSQL for production  
**Python env:** `.venv/` — activate with `source .venv/bin/activate`

---

## 1. Current Architecture

```
OpenReview API                Semantic Scholar API
      │                              │
      ▼                              ▼
ingestion/fetch_openreview.py   ingestion/enrich_citations.py
      │                              │
      └──────────────┬───────────────┘
                     ▼
              ingestion/store.py
                     │
                     ▼
          ┌──────────────────────┐
          │  SQLite / PostgreSQL │
          │  research_platform   │
          └──────────────────────┘
                     ▲
      ┌──────────────┴──────────────────┐
      │                                 │
pdf_pipeline/                    [NEXT: analysis/]
  downloader.py  → pdfs/{conf}/{year}/  gemini_client.py
  extractor.py   → paper_sections      pipeline.py
  segmenter.py   → paper_sections      store.py
  analyser.py    → paper_analyses  ◄── NOT YET RUN
  store.py
  pipeline.py
```

### Data flow

```
OpenReview ──► fetch_openreview ──► papers + authors + paper_authors
                                           │
Semantic Scholar ◄─────────────── papers.title
        │
        └──► papers.citation_count
             papers.influential_citation_count
             papers.semantic_scholar_id
                    │
           pdf_url (OpenReview) ──► downloader ──► pdfs/NeurIPS/2024/*.pdf
                                         │
                                    extractor ──► papers.pdf_word_count
                                         │
                                    segmenter ──► paper_sections.*
                                         │
                                    analyser  ──► paper_analyses.*   ← PENDING
                                                  paper_categories
                                                  paper_techniques
                                                  paper_methodologies
                                                  paper_datasets
```

---

## 2. Files Created

### Database layer (`db/`)
| File | Purpose | Lines |
|------|---------|-------|
| `db/models.py` | SQLAlchemy ORM — all 9 tables | 245 |
| `db/session.py` | Engine, `get_session()` context manager, `ping()` | 45 |
| `db/migrate.py` | Safe `ALTER TABLE ADD COLUMN` for SQLite | 35 |
| `db/schema.sql` | Reference DDL (PostgreSQL) | 180 |
| `db/seeds/conferences.sql` | 10 conference seed rows | 15 |
| `db/migrations/003_pdf_pipeline_tables.sql` | PDF pipeline tables DDL | 65 |

### Ingestion layer (`ingestion/`)
| File | Purpose | Lines |
|------|---------|-------|
| `ingestion/fetch_openreview.py` | OpenReview API client → `RawPaper` dataclass | 95 |
| `ingestion/store.py` | Upserts: conference, edition, paper, authors, paper_authors | 110 |
| `ingestion/run_ingestion.py` | CLI: fetch + store NeurIPS 2024 | 85 |
| `ingestion/enrich_citations.py` | S2 bulk search, citation enrichment, report | 310 |
| `ingestion/verify_pipeline.py` | SQLite smoke-test (no Postgres needed) | 95 |

### PDF pipeline (`pdf_pipeline/`)
| File | Purpose | Lines |
|------|---------|-------|
| `pdf_pipeline/downloader.py` | HTTP download, retry, atomic write | 120 |
| `pdf_pipeline/extractor.py` | PyMuPDF extraction, ligature fix, header strip | 80 |
| `pdf_pipeline/segmenter.py` | 3-pass section detector (v3), LLM context builder | 230 |
| `pdf_pipeline/analyser.py` | Gemini client (`google.genai`), Pydantic models, retry | 200 |
| `pdf_pipeline/store.py` | Upserts for sections, datasets, analyses, errors | 110 |
| `pdf_pipeline/pipeline.py` | 4-stage orchestrator, `PaperMeasurement`, report | 230 |
| `pdf_pipeline/run_pipeline.py` | CLI entry point | 55 |

### Utility scripts
| File | Purpose |
|------|---------|
| `validate_collection.py` | Early proof-of-concept: 20 OpenReview papers → CSV |
| `inspect_db.py` | Print DB counts + first 10 papers/authors |

### Documentation (`docs/`)
| File | Contents |
|------|---------|
| `docs/paper_collection_report.md` | API survey: S2, OpenAlex, OpenReview, DBLP, CVF, ACL |
| `docs/understanding_pipeline_architecture.md` | LLM analysis pipeline design (Gemini) |
| `docs/pdf_pipeline_architecture.md` | PDF pipeline design + 5k-paper cost estimates |
| `docs/project_handoff.md` | This document |

**Total:** ~2,700 lines of production code across 17 Python files.

---

## 3. Database Schema

### Tables (9 total)

```
conferences          ──< conference_editions ──< papers >── paper_authors >── authors
                                                   │
                    ┌──────────────────────────────┼───────────────────────────┐
                    │                              │                           │
             paper_sections                paper_analyses               pipeline_errors
             (extracted PDF)               (LLM output)                 (error log)
                                                   │
                                           paper_datasets
```

### Schema additions since initial design

**Migration 003** added these to the existing 5-table schema:

```sql
-- New columns on papers
papers.pdf_local_path     TEXT         -- path to downloaded PDF
papers.pdf_word_count     INTEGER      -- words extracted by PyMuPDF
papers.pdf_extracted_at   TIMESTAMP    -- when extraction ran

-- New tables
paper_sections    -- full_text + 10 named section fields + metadata
paper_datasets    -- datasets extracted by LLM from experiments section
paper_analyses    -- LLM-generated: summary, advantages, limitations, use_cases
pipeline_errors   -- append-only error log per paper per stage
```

### Column notes
- All PKs are `UUID` (string form) generated client-side via `uuid.uuid4()`
- `papers.last_enriched_at` — used as resumption flag for citation enrichment
- `papers.pdf_local_path` — used as resumption flag for PDF download
- `paper_sections.sections_found` — JSON array string of detected section keys
- `paper_analyses.{advantages,limitations,future_work,use_cases}` — JSON array strings

### SQLite vs PostgreSQL
The codebase runs on both. The only divergence is schema migration:
- **PostgreSQL:** `ALTER TABLE … ADD COLUMN IF NOT EXISTS` (in migration SQL files)
- **SQLite:** `db/migrate.py` uses SQLAlchemy `inspect` to check before adding

---

## 4. Current Database State

| Table | Rows |
|-------|------|
| conferences | 1 (NeurIPS) |
| conference_editions | 1 (NeurIPS 2024) |
| papers | **100** |
| authors | **444** |
| paper_authors | **450** |
| paper_sections | **10** (top 10 by citation) |
| paper_datasets | 0 (LLM not yet run) |
| paper_analyses | 0 (LLM not yet run) |
| pipeline_errors | 0 |

---

## 5. Citation Enrichment Status

**All 100 papers attempted. 97/100 matched.**

| Metric | Value |
|--------|-------|
| Papers enriched (attempted) | 100 / 100 |
| Matched via Semantic Scholar | **97** (97%) |
| Failed / no S2 match | **3** |
| Total citations across corpus | 3,583 |
| Highest cited paper | Gorilla (1,248 citations) |

**3 unmatched papers** (enriched timestamp set, S2 id is NULL):
1. `Accelerating ERM for data-driven algorithm design using output-sensitive…`
2. `The Fairness-Quality Tradeoff in Clustering`
3. `Controlling Multiple Errors Simultaneously with a PAC-Bayes Bound`

These will be re-tried when `--force` is passed, or when S2 indexes them.

### How enrichment works
- Source: `GET /graph/v1/paper/search/bulk?venue=NeurIPS&year=2024-2024&limit=5`
- Matching: fetch 5 candidates, pick best by token-overlap ratio (≥ 0.75)
- Resumable: papers with `last_enriched_at IS NULL` are the queue
- Rate limit: 2s delay between calls (unauthenticated); use `--api-key` for 100 req/s

---

## 6. PDF Pipeline Status

### Download + extraction (10 / 100 papers)
Only the **top 10 by citation count** have been processed so far.

| Stage | Completed | Notes |
|-------|-----------|-------|
| Stage 1 — Download | **10 / 10** | All from `openreview.net`; 0 errors |
| Stage 2 — Extract | **10 / 10** | PyMuPDF; avg 5,984 words/paper |
| Stage 3 — Segment | **10 / 10** | Stored as `regex-v2` (see § 7 below) |
| Stage 4 — Analyse | **0 / 10** | Awaiting `GEMINI_API_KEY` |

### PDF storage
```
pdfs/NeurIPS/2024/   10 files   71.1 MB total
                               Range: 570 KB – 31,876 KB (avg ~7 MB)
```

### Section coverage across 10 segmented papers (v3 segmenter, not yet written)
| Coverage | Count | Papers |
|----------|-------|--------|
| 100% | 1 | Gorilla |
| 80% | 5 | ALPHALLM, Refusal, VLM Limits, LACIE, Multistep Distillation, Aligning LLM Agents |
| 40% | 4 | Learning to grok, Safety Fine-tuning, KV Cache, Refusal |

Average coverage: **66%** across the 10 papers.

> ⚠️ **Note:** The 10 DB rows in `paper_sections` were written with segmenter `regex-v2`.
> The patched `regex-v3` has **not yet been written back to the database**.
> Run `--force` on the segment stage after the segmenter patch to refresh them.

---

## 7. Segmenter Fixes (v2 → v3)

Three bugs were diagnosed from inspection of real extracted text and patched in `pdf_pipeline/segmenter.py`.

### Fix 1 — Numbered headers now fully supported
**Problem:** Headers like `3 Method`, `3.1 Methodology`, `4.1 Experimental Setup` were already handled by `_NUM_PREFIX = r"(?:\d+(?:\.\d+)*\.?\s+)?"`. Confirmed working in v3.

### Fix 2 — Results merged from Experiments when absent
**Problem:** Many NeurIPS papers have no standalone "Results" header; results tables live inside the Experiments section.  
**Fix:** After pass 1, if `ps.results` is None and `ps.experiments` is populated, split the experiments block at the first table/comparison sentence past the 30% mark.  
**Result:** Gorilla gained `results_from_experiments` (1,482 words).

### Fix 3 — "background" removed from `related_work` pattern
**Problem:** Adding `background` to `related_work` caused `"2.1 Background"` (a *subsection* of `"2 Methodology"`) to steal all methodology content, leaving the methodology header with an empty body. Empty-body headers were then silently listed in `sections_found`, masking the bug.  
**Fix:** Removed `background` from `related_work`. Added guard: `sections_found` now only lists keys where `getattr(ps, key)` is non-None.  
**Result:** Refusal paper methodology restored to 3,445 words.

### Fix 4 — Conclusion trim handles inline boilerplate
**Problem:** `_CONCLUSION_STOP` used `^\s*` (line-start anchor), so `"…throughout. Acknowledgements. AA…"` (mid-paragraph) was not caught.  
**Fix:** Added `_CONCLUSION_INLINE` regex matching `. Acknowledgements` / `. Author contributions` as sentence openers. `_trim_conclusion()` now runs three independent passes and picks the shortest result with ≥ 20 words.  
**Result:** Refusal paper conclusion fallback correctly suppressed (21 words after trim — below 40-word minimum → no boilerplate reaches the LLM).

---

## 8. Outstanding Issues

### Must fix before scaling to 100 papers

| # | Issue | Severity | Location |
|---|-------|----------|----------|
| 1 | Segmenter v3 results not written to DB | Medium | Run `--force --stage segment` |
| 2 | `GEMINI_API_KEY` not configured — stage 4 never run | High | Add to `.env` |
| 3 | Only 10/100 papers have PDFs downloaded | High | Run pipeline on remaining 90 |

### Known extraction limitations

| # | Issue | Affected papers | Workaround |
|---|-------|----------------|------------|
| 4 | "Methodology" absent when paper uses custom section titles (§3 AlphaLLM, §4 Our Approach) | ~30–40% | LLM still receives abstract + experiments + results; acceptable for now |
| 5 | Two-column PDF tables produce garbled text (numbers interspersed) | All papers with tables | Tables excluded from LLM context; only prose sections sent |
| 6 | 3 papers failed S2 citation match | 3 / 100 | Retry with `--force` once S2 indexes them |
| 7 | `pdfs/` directory grows unboundedly | Future | Add per-conference subdirectory size cap; S3 migration path in architecture doc |

### Future work (not yet designed)

| # | Feature | Doc |
|---|---------|-----|
| 8 | Categories, techniques, methodologies tables not yet populated | `docs/understanding_pipeline_architecture.md` |
| 9 | Only NeurIPS 2024 ingested — need ICML, ICLR, CVPR, ACL etc. | `docs/paper_collection_report.md` |
| 10 | No search / embedding layer yet | Deferred by design |
| 11 | PostgreSQL migration (SQLite is dev only) | `db/schema.sql` + `db/migrate.py` |

---

## 9. Next Steps (priority order)

1. **Add Gemini API key** → run stage 4 on 10 papers → validate analysis quality
2. **Write segmenter v3 back to DB** → re-segment all 10 papers with the patched version
3. **Download remaining 90 PDFs** → extend pipeline to full 100-paper corpus
4. **Run full 4-stage pipeline on 100 papers** → generate analysis report
5. **Populate categories / techniques / methodologies tables** from LLM output
6. **Ingest second conference** (ICLR 2024 recommended — also on OpenReview)
7. **Migrate to PostgreSQL** when corpus exceeds ~500 papers

---

## 10. Exact Commands to Continue

```bash
# ── Environment setup ──────────────────────────────────────────────────────────
cd /Users/kausthub.gupta/research-intelligence-platfrom
source .venv/bin/activate                        # activate virtualenv
export DATABASE_URL=sqlite:///research_platform.db

# ── Inspect current DB state ───────────────────────────────────────────────────
python inspect_db.py

# ── Re-segment all 10 papers with the patched v3 segmenter ────────────────────
# (writes updated section text back to paper_sections table)
python -m pdf_pipeline.run_pipeline --stage segment --force --limit 10

# ── Add Gemini key, then run LLM analysis on 10 papers ────────────────────────
echo "GEMINI_API_KEY=your_key_here" >> .env
python -m pdf_pipeline.run_pipeline --limit 10 --force    # stages 1-4

# ── Report only (no processing) ───────────────────────────────────────────────
python -m pdf_pipeline.run_pipeline --report

# ── Download + process remaining 90 papers ────────────────────────────────────
python -m pdf_pipeline.run_pipeline --limit 100            # skips already done

# ── Citation enrichment: refresh stale counts / retry 3 failures ──────────────
python -m ingestion.enrich_citations --report-only         # check current state
python -m ingestion.enrich_citations --force --limit 3     # retry the 3 failures

# ── Ingest a second conference (ICLR 2024) ────────────────────────────────────
# Edit ingestion/run_ingestion.py: change CONFERENCE and INVITATION constants
# CONFERENCE = dict(short_name="ICLR", full_name="International Conference on
#              Learning Representations", field="ML", website="https://iclr.cc")
# EDITION    = dict(year=2024, openreview_id="ICLR.cc/2024/Conference")
# INVITATION = "ICLR.cc/2024/Conference/-/Blind_Submission"
python -m ingestion.run_ingestion --limit 100

# ── Verify pipeline logic without a running DB ────────────────────────────────
python ingestion/verify_pipeline.py                        # SQLite in-memory smoke test

# ── Switch to PostgreSQL ───────────────────────────────────────────────────────
export DATABASE_URL=postgresql://user:password@localhost:5432/research_platform
python -c "from db.migrate import run_migrations; run_migrations()"
python -m ingestion.run_ingestion --limit 100
```

---

## Appendix: Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| OpenReview as primary source for NeurIPS/ICML/ICLR | 100% coverage, includes decisions and review scores, no auth |
| Semantic Scholar bulk endpoint for citations | Standard `/paper/search` is rate-limited to ~1 req/s shared; bulk endpoint is more permissive |
| Title token-overlap matching (≥ 0.75) with 5 candidates | Bulk endpoint ranks poorly; fetching 5 and scoring all catches the correct paper in position 2–5 |
| PyMuPDF over GROBID | 200ms/paper vs 3–8s; GROBID behind `TextExtractor` interface for future swap |
| Section subset for LLM (not full text) | 4k tokens vs 18k tokens; 78% cost saving with only marginal quality loss |
| `google.genai` (not `google.generativeai`) | `google.generativeai` is deprecated as of 2025 |
| UUIDs as PKs | Parallel ingestion pipelines can merge without collision |
| `sections_found` only lists keys with non-None body | Prevents phantom sections (header detected, body empty) from inflating coverage metrics |
