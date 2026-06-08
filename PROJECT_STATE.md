# Research Intelligence Platform — Project State

**Last updated:** June 5, 2026  
**Branch:** `notebooklm-pipeline`  
**Status:** Knowledge audit complete · Graph V2 live · Relationship explanations live · Ontology redesign not yet started

---

## 1. Project Vision

Build a **Research Intelligence Platform** that automatically collects AI/ML research papers, extracts structured knowledge from them, organizes that knowledge into a queryable graph, and surfaces research relationships through a structured API.

**This is NOT:**
- A chatbot or conversational AI
- A generic RAG pipeline
- A Gemini-dependent system (stage 4 Gemini analyser was deprecated)

**This IS:**
- A structured research database with knowledge extraction
- A searchable, filterable corpus of papers and their entities
- A knowledge graph that connects papers through shared techniques, datasets, categories, and methodologies
- A platform for research discovery — finding what relates papers and why

**Manager requirements (verbatim):**
- Papers collected automatically
- Searchable with filters: citation count, year, author, conference, category, title
- NotebookLM handles analysis, summarization, extraction
- No chatbot
- No Gemini API dependency

**Target conferences:** NeurIPS · ICML · ICLR · CVPR · ICCV · ECCV · ACL · EMNLP · AAAI · IJCAI  
**Target years:** 2024 · 2025 · 2026

---

## 2. Current Architecture

```
OpenReview API          Semantic Scholar API
      │                        │
      ▼                        ▼
ingestion/fetch_openreview.py  ingestion/fetch_semantic_scholar.py
      │                        │
      └──────────┬─────────────┘
                 ▼
         ingestion/store.py  (upserts, idempotent)
                 │
                 ▼
    ┌────────────────────────────┐
    │  SQLite (dev)              │  ← research_platform.db
    │  PostgreSQL (prod schema)  │  ← db/schema.sql
    └────────────────────────────┘
         │
         ├── pdf_pipeline/          Stages 1–3: Download → Extract → Segment
         │       downloader.py      HTTP download with retry + atomic write
         │       extractor.py       PyMuPDF text extraction
         │       segmenter.py       3-pass regex-v3 section detector
         │       pipeline.py        Orchestrator
         │
         ├── notebooklm/            Stage 4: Topic assignment → Upload → Query → Extract
         │       assigner.py        Keyword-scored topic assignment
         │       source_prep.py     Assembles uploadable text from paper_sections
         │       client.py          nlm CLI wrapper (create/upload/query/delete)
         │       extractor.py       Parses NotebookLM responses into typed objects
         │       normalizer.py      Writes objects to DB tables
         │       pipeline.py        5-stage orchestrator (A→B→C→D→E)
         │       run_pipeline.py    CLI entry point
         │
         ├── normalize/             Entity normalization
         │       rules.py           2-pass normalizer (alias map + case-fold)
         │       technique_aliases.json
         │       dataset_aliases.json
         │   normalize_entities.py  Runner script
         │
         ├── graph/                 Knowledge graph
         │       builder.py         IDF-weighted edge builder (Graph V2)
         │       analytics.py       Centrality, clustering, technique metrics
         │       explainer.py       Relationship explanation engine
         │   build_graph.py         Original build runner (v1 compatible)
         │   build_graph_v2.py      V2 rebuild + diagnostic report runner
         │
         ├── api/
         │       search.py          FastAPI app — all endpoints
         │
         ├── search/
         │       query.py           Pure Python search functions (pre-API)
         │
         └── metrics/
                 dashboard.py       CLI metrics dashboard
```

---

## 3. Database Schema

**20 tables total** in `research_platform.db` (SQLite dev) / `db/schema.sql` (PostgreSQL reference).

### Core tables

| Table | Rows | Purpose |
|---|---|---|
| `conferences` | 1 | Conference registry (NeurIPS, ICML, …) |
| `conference_editions` | 1 | Per-year conference instance |
| `papers` | 100 | Paper metadata, abstracts, PDF state |
| `authors` | 444 | De-duplicated author records |
| `paper_authors` | 450 | Paper ↔ Author join (with position) |

### PDF pipeline tables

| Table | Rows | Purpose |
|---|---|---|
| `paper_sections` | 10 | Segmented paper text (abstract, intro, methodology, …) |

### Knowledge extraction tables

| Table | Rows | Purpose |
|---|---|---|
| `paper_analyses` | 100 | Summaries, advantages, limitations, use cases, future work |
| `paper_techniques` | 655 | Extracted techniques with `canonical_name` and `role` |
| `paper_datasets` | 49 | Extracted datasets with `canonical_name` |
| `paper_categories` | 220 | Research area categories (15 canonical values) |
| `paper_methodologies` | 256 | Methodological approaches (flat strings) |

### NotebookLM tables

| Table | Rows | Purpose |
|---|---|---|
| `notebooks` | 23 | One row per topic notebook (topic_slug, notebooklm_id, url) |
| `notebook_papers` | 170 | Paper ↔ Notebook assignment with `source_status` |
| `notebook_syntheses` | 115 | Raw query responses from NotebookLM (5 per notebook) |
| `notebook_paper_extracts` | — | Per-paper parsed data from synthesis responses |
| `pipeline_errors` | 0 | Append-only error log |

### Knowledge graph tables

| Table | Rows | Purpose |
|---|---|---|
| `paper_relationships` | 2517 | Weighted edges between paper pairs |
| `entity_relationships` | 2042 | Co-occurrence edges between entities |
| `paper_graph_metrics` | 100 | Per-paper centrality, cluster, neighbor counts |
| `technique_graph_metrics` | 517 | Per-canonical-technique usage and co-occurrence stats |

### Key column notes

- **`paper_techniques.canonical_name`** — normalized form; used by graph builder. `name` is the raw extracted value and is never modified.
- **`paper_techniques.role`** — `introduces | uses | compares | critiques`. Distinction is important for relationship explanations.
- **`paper_relationships.technique_score`** — IDF-weighted technique contribution to edge weight (Graph V2, nullable on pre-migration rows).
- **`paper_relationships.dataset_score`**, **`category_score`** — flat-weighted component scores stored per edge.
- **All PKs** are UUID strings generated client-side with `str(uuid.uuid4())`.
- **`papers.pdf_local_path`** — non-NULL means PDF downloaded.
- **`papers.last_enriched_at`** — non-NULL means citation enrichment attempted.

### Known schema divergence

`db/schema.sql` (PostgreSQL reference) has a normalized entity design with standalone `categories`, `techniques`, `methodologies` tables. `db/models.py` uses flat per-paper tables. **These are intentionally different.** Do not attempt to reconcile them. Flat ORM is used for SQLite dev; normalize to schema.sql when migrating to PostgreSQL.

---

## 4. Pipeline Stages

### Stage 1 — Paper ingestion

```bash
python -m ingestion.run_ingestion --conference NeurIPS --year 2024 --limit 500
python -m ingestion.run_ingestion --all --limit 500   # all 10 conferences
python -m ingestion.enrich_citations                  # add citation counts via S2
```

Sources: OpenReview (oral/spotlight/poster papers), Semantic Scholar (citation enrichment).  
**Current state:** 100 NeurIPS 2024 papers. 9 other conferences configured but not yet ingested.

### Stage 2 — PDF pipeline (stages 1–3)

```bash
python -m pdf_pipeline.run_pipeline --limit 100
python -m pdf_pipeline.run_pipeline --stage segment --force --limit 10
```

Stage 1 downloads PDFs, Stage 2 extracts text with PyMuPDF, Stage 3 segments into sections.  
**Current state:** 10/100 papers have PDFs downloaded and segmented. Stage 4 (Gemini) is deprecated.

### Stage 3 — NotebookLM analysis pipeline

```bash
python -m notebooklm.run_pipeline --limit 10
python -m notebooklm.run_pipeline --stage synthesize
python -m notebooklm.run_pipeline --stage extract
```

Five internal stages: A (Assign topics) → B (Provision notebooks) → C (Upload sources) → D (Synthesize with 5 prompts) → E (Extract structured data).  
**Current state:** 100 papers analysed, 115 synthesis responses, all extraction tables populated.

### Stage 4 — Entity normalization

```bash
python normalize_entities.py
```

Two-pass normalization: explicit alias map (JSON files in `normalize/`) then case-fold grouping.  
**Current state:** 655 technique rows → 517 canonical names. 49 dataset rows → 44 canonical names.

### Stage 5 — Graph build

```bash
python build_graph_v2.py          # rebuild with IDF weighting + generate report
python build_graph.py --stats     # print current graph stats
python build_graph.py             # rebuild (uses same IDF builder)
```

**Current state:** 2517 paper edges, 2042 entity edges, 3 clusters, 0 isolated papers.

---

## 5. Implemented Features

### Ingestion
- Multi-conference config (`ingestion/conferences_config.py`) — 10 conferences × 19 editions configured
- Idempotent upsert store — safe to re-run ingestion
- Citation enrichment via Semantic Scholar bulk API
- Smoke test: `python -m ingestion.verify_pipeline`

### PDF Pipeline
- HTTP downloader with retry and atomic write
- PyMuPDF text extraction with ligature fix and header stripping
- 3-pass regex segmenter (regex-v3) detecting: abstract, introduction, related_work, methodology, experiments, results, discussion, conclusion, limitations, future_work
- `--stage segment` flag for re-segmenting without re-downloading

### NotebookLM Integration
- `notebooklm/client.py` — nlm CLI wrapper. All 5 commands validated: `create_notebook`, `add_source`, `query_notebook`, `delete_notebook`, `health_check`
- `notebooklm/assigner.py` — 3-pass keyword scorer assigns papers to topic notebooks (25 topics)
- `notebooklm/source_prep.py` — builds uploadable text from `paper_sections`; falls back to abstract-only
- `notebooklm/extractor.py` — regex parser for 5 structured query responses
- `notebooklm/normalizer.py` — writes `ExtractionResult` to DB tables
- 5 validated query prompts: `summary`, `techniques`, `datasets`, `categories`, `use_cases`
- Cookie auth, 2–4 week lifetime, re-auth: `nlm login`

### Entity Normalization
- Alias maps for techniques (`normalize/technique_aliases.json`) and datasets (`normalize/dataset_aliases.json`)
- Case-fold grouping with deterministic canonical selection
- `canonical_name` column written to `paper_techniques` and `paper_datasets`
- `paper_categories` uses a 15-value controlled vocabulary (no alias map needed)

### Knowledge Graph (V2)
- IDF-weighted technique edges: `idf(t) = ln(N / paper_count(t))`
- Three-tier classification: GENERIC (idf < 3.0, ×0.25) · SHARED (idf < 3.69, ×1.0) · SPECIALIZED (idf ≥ 3.69, ×2.0)
- Per-edge score diagnostics stored: `technique_score`, `dataset_score`, `category_score`
- Datasets/categories/methodologies use flat weights (unchanged from V1)
- Community detection via greedy modularity — 3 clusters
- Betweenness and degree centrality computed per paper
- Co-occurrence edges between entities of the same type

### Relationship Explanation (`graph/explainer.py`)
- `explain(session, paper_id_a, paper_id_b) → RelationshipExplanation`
- Shared Concepts: sorted SPECIALIZED first, each annotated with IDF tier and per-paper role
- Differences: derived from `introduces`-role techniques per paper, unique methodologies, or summary first sentence
- Research Connection: 15 category-combination templates + methodology qualifier
- No LLM calls. All derived from existing DB data.

### Search API (`api/search.py` — FastAPI)
All endpoints are live and tested. See section 8 for full list.

### Audit Scripts (read-only)
- `entity_audit.py` — frequency, variant counts, candidate entity type classification per canonical technique
- `entity_signal_audit.py` — paper_count, graph degree contribution, tier (Core/Shared/Singleton)
- `concept_selection_audit.py` — IDF scores, GENERIC/SHARED/SPECIALIZED classification, proposed weight multipliers

---

## 6. Completed Audits

All audit outputs are in `outputs/`.

### Entity audit (`outputs/entity_audit.csv`, `outputs/entity_summary.md`)
- 517 canonical techniques across 100 papers
- 498 singletons (96%) — appear in only 1 paper; cannot contribute to graph edges
- 405 "Unknown" type — genuine research terms too granular for classification rules
- 8 Models, 25 Architectures, 33 Techniques, 11 Algorithms, 8 Optimizers, 18 Tools, 5 Metrics classified
- 39 suspected duplicate pairs detected
- 2 normalization issues: `Transformers` (7 raw variants), `Large Language Models` (4 raw variants)

### Signal audit (`outputs/entity_signal_audit.csv`, `outputs/entity_signal_summary.md`)
- 3 Core entities (paper_count ≥ 5): LLMs (9), Transformers (7), Diffusion Models (5)
- 16 Shared entities (paper_count 2–4)
- 498 Singletons contribute 0 graph edges
- Core entities drive 77% of graph edge contributions under V1 weighting

### Concept selection audit (`outputs/concept_selection.csv`)
- IDF scores computed for all 517 canonical techniques
- Weight multipliers proposed and validated: GENERIC ×0.25, SHARED ×1.0, SPECIALIZED ×2.0
- At N=100: GENERIC = paper_count ≥ 5; SHARED = 3–4; SPECIALIZED ≤ 2
- Thresholds scale automatically with corpus size — no code changes needed at N=1000

### Graph V2 report (`outputs/graph_v2_report.md`)
- V1 vs V2 comparison: edge count unchanged (2517), avg weight 1.383 → 1.339
- High-weight edges (4–8): 87 → 23 (−64) — GENERIC entities correctly down-weighted
- New max weight: 9.0 (V1: 8.0) — SPECIALIZED co-occurrence now scores higher
- Top pair: "AI Feedback for Alignment" ↔ "Safety Fine-tuning" via Direct Preference Optimization (SPECIALIZED)

---

## 7. Graph V2 Design

### Edge weight formula

```
For each shared technique t:
    idf(t)         = ln(total_papers / paper_count(t))
    tier(t)        = GENERIC     if idf < 3.00
                   = SHARED      if idf < 3.69
                   = SPECIALIZED if idf ≥ 3.69
    multiplier(t)  = 0.25 (GENERIC) | 1.00 (SHARED) | 2.00 (SPECIALIZED)
    contribution(t)= WEIGHT_TECHNIQUE(3) × multiplier(t)

technique_score    = Σ contribution(t) for t in shared_techniques
dataset_score      = 2 × |shared_datasets|
category_score     = 1 × |shared_categories|
methodology_score  = 1 × |shared_methodologies|
final_weight       = technique_score + dataset_score + category_score + methodology_score
```

Thresholds are corpus-size-independent. At N=1000, GENERIC = paper_count ≥ 50.

### Stored diagnostics

`paper_relationships` columns added in migration 009:
- `technique_score REAL` — IDF-weighted technique component
- `dataset_score REAL` — flat dataset component
- `category_score REAL` — flat category component
- `weight REAL` — final combined weight (unchanged column)

### Current graph stats (Graph V2)
- 2517 paper edges · avg weight 1.339 · max weight 9.0
- 3 clusters · 0 isolated papers
- Most central paper: "Incentivizing Quality Text Generation via Statistical Contracts" (BC 0.0259)

---

## 8. API Endpoints

**Run:** `uvicorn api.search:app --reload --port 8000`  
**Docs:** `http://localhost:8000/docs`

| Method | Path | Description |
|---|---|---|
| GET | `/papers` | List/filter papers (title, conference, year, min/max citations, presentation_type, has_pdf, has_analysis) |
| GET | `/papers/{id}` | Full paper detail with authors, techniques, datasets, categories, methodologies, analysis |
| GET | `/techniques` | Technique frequency list (filterable by role, searchable) |
| GET | `/datasets` | Dataset frequency list |
| GET | `/categories` | Category frequency list |
| GET | `/methodologies` | Methodology frequency list |
| GET | `/search` | Cross-field search (title +40/+20, category +15, technique +12, dataset +10, citation boost) |
| GET | `/papers/{id}/related` | Related papers via graph edges (sorted by weight) |
| GET | `/papers/{id}/explain/{other_id}` | Structured relationship explanation (WHY are these related) |
| GET | `/techniques/{name}/related` | Papers using a technique + co-occurring techniques |
| GET | `/graph/stats` | Overall graph statistics |
| GET | `/graph/top-clusters` | Research clusters with dominant topics and representative papers |

### Relationship explanation response shape

```json
{
  "relationship_score": 9.0,
  "technique_score": 6.0,
  "dataset_score": 0.0,
  "category_score": 2.0,
  "shared_concepts": [
    {"name": "Direct preference optimization", "signal_tier": "SPECIALIZED",
     "idf_score": 3.912, "paper_a_role": "uses", "paper_b_role": "uses"}
  ],
  "shared_categories": ["LLM", "Safety"],
  "shared_methodologies": ["Fine-tuning"],
  "differences": [
    "**Paper A** — Introduces Mechanistic explanation for SFT vs LAIF",
    "**Paper B** — Introduces Synthetic data generation framework, JB-CO-Task"
  ],
  "research_connection": "Both investigate post-training alignment and safety of large language models."
}
```

---

## 9. Known Problems

| # | Problem | Severity | Location | Fix |
|---|---|---|---|---|
| 1 | Entity taxonomy missing — `paper_techniques` mixes Models, Frameworks, Optimizers, Metrics into one flat table | High | `paper_techniques` | Add `entity_type` column after ontology design is approved (deliberately postponed — see §11) |
| 2 | Methodology hierarchy is flat strings — "Adam", "AdamW", "SGD" have no parent relationship | Medium | `paper_methodologies` | Add ontology layer after entity_type is implemented |
| 3 | 498 singleton techniques (96%) cannot contribute to graph edges at current corpus size | Medium | `paper_techniques` | Will self-resolve as corpus grows; some may be pruned after entity_type redesign |
| 4 | `Transformers` and `Large Language Models` classified as GENERIC and down-weighted — but they still appear as shared concepts in some pairs | Low | `graph/builder.py` | Correct behavior; IDF weighting is working as designed |
| 5 | Only 10/100 papers have PDF text segmented | Medium | `pdf_pipeline/` | Run `python -m pdf_pipeline.run_pipeline --limit 100` |
| 6 | Only NeurIPS 2024 ingested (100 papers) out of 10 conferences × multiple years | Medium | `ingestion/` | Run `python -m ingestion.run_ingestion --all --limit 500` |
| 7 | 3 papers have `semantic_scholar_id = NULL` (citation enrichment failed) | Low | Papers: *Accelerating ERM…*, *Fairness-Quality Tradeoff…*, *Controlling Multiple Errors…* | Retry: `python -m ingestion.enrich_citations --force --limit 3` |
| 8 | `search_papers()` in `search/query.py` has no filter for `paper_categories` or `paper_techniques` | Low | `search/query.py` | Add JOIN + WHERE (low priority, API /search covers this) |
| 9 | `db/schema.sql` (PostgreSQL) and `db/models.py` (SQLite ORM) are intentionally diverged | Low | Both files | Resolve when migrating to PostgreSQL |
| 10 | `concept_selection_audit.py` SHARED bucket has only 2 techniques at N=100 — tier split is extreme | Low | Audit scripts | Self-resolves as corpus grows |

---

## 10. Current Priorities

In order:

1. **Expand corpus** — ingest all remaining conferences and years before designing the ontology. The ontology design depends on seeing the full entity distribution, not just 100 papers.

   ```bash
   python -m ingestion.run_ingestion --all --limit 500
   python -m ingestion.enrich_citations
   python -m pdf_pipeline.run_pipeline --limit 2000
   python -m notebooklm.run_pipeline --limit 50
   python normalize_entities.py
   python build_graph_v2.py
   ```

2. **Re-run entity audit on larger corpus** — re-run `entity_audit.py`, `entity_signal_audit.py`, `concept_selection_audit.py` after corpus expansion to see which singletons graduate to Shared/Core and what the real entity type distribution looks like.

3. **Entity type redesign** — add `entity_type` column to `paper_techniques` and classify entities using rules derived from the expanded audit. Only after step 2.

4. **Ontology / hierarchy layer** — define parent-child relationships for Optimizers, Architectures, etc. Only after entity_type is stable.

5. **Graph V3** — incorporate entity_type into base weights and hierarchy into edge traversal. Only after ontology is stable.

---

## 11. Things Explicitly NOT to Build Yet

These are deliberate holds, not oversights. See `ARCHITECTURE_DECISIONS.md` for full reasoning.

| Thing | Reason for hold |
|---|---|
| **Entity type column (`entity_type`)** | Audit showed 78% of entities are "Unknown" — classification rules need the full corpus to be meaningful |
| **Ontology / entity hierarchy** | Requires stable entity_type first; hierarchy built on partial data will need to be rebuilt |
| **Graph V3 with entity-type weights** | Requires ontology to be stable |
| **Vector embeddings** | No embedding model, no storage layer, and the corpus is too small to make similarity search meaningful |
| **Vector / semantic search** | Same — wait until corpus is ≥ 1,000 papers |
| **RAG / question answering** | Explicitly out of scope per manager requirements — no chatbot |
| **Recommendation engine** | Out of scope for current phase |
| **Research copilot / agent** | Out of scope for current phase |
| **More API endpoints** | No new endpoints until ontology and entity_type are finalized |
| **PostgreSQL migration** | Wait until corpus exceeds ~500 papers |
| **Frontend / UI** | Not started; no design spec yet |

---

## 12. Corpus Intelligence Layer

Scripts live in `corpus_intel/`. All are read-only — no DB writes, no schema changes.
Outputs in `outputs/corpus_intel/`.

| Script | Goal | Status |
|---|---|---|
| `emerging.py` | Classify techniques by adoption stage (Emerging / Novel / Established / Foundational / Referenced) | ✅ Complete |
| `trends.py` | Category-level snapshot + technique momentum scores | ✅ Complete |
| `communities.py` | Cluster profiles, cohesion scores, bridge papers | ✅ Complete |
| `technique_evolution.py` | Directed influence graph: in-degree (foundational) + out-degree (cutting-edge) | ✅ Complete |
| `convergence.py` | Cross-domain convergence zones, bridge techniques, bridge papers | ⬜ Not started |
| `influential.py` | Composite influence score per paper | ⬜ Not started |

**Technique Evolution findings (preliminary):**
The directed influence graph is structurally valid but currently dominated by singleton
techniques and normalization granularity. Cutting-edge rankings are inflated by variant
technique names (e.g. CLA2/CLA3/CLA4) introduced within a single paper — these share
identical foundation sets, producing identical out-degree through the cross-product
construction. This is a normalization granularity issue, not an analytics logic error.
Results should be considered preliminary until corpus expansion (≥ 500 papers) and
normalization audit v2. The `normalized_out_degree` column in the CSV (out_degree ÷
introduced_by_count) is the correct ranking signal but has no corrective power when
introduced_by_count = 1 (which is 96% of techniques at current corpus size).

---

## 13. Next Milestone

**Milestone: Corpus Expansion + Entity Audit V2**

Definition of done:
- [ ] All 10 conferences ingested for 2024 (≥ 300 papers per major conference)
- [ ] All papers enriched with citation counts
- [ ] PDFs downloaded and segmented for top-cited papers
- [ ] NotebookLM analysis pipeline run on all segmented papers
- [ ] Entity normalization re-run on expanded corpus
- [ ] Graph V2 rebuilt on expanded corpus
- [ ] `entity_audit.py` re-run and results reviewed
- [ ] Singleton percentage below 80% (currently 96%)
- [ ] SHARED tier has ≥ 20 techniques (currently 2)
- [ ] Entity type classification rules written and validated against expanded corpus

**Only after this milestone:** begin entity_type column, ontology design, and Graph V3.

---

## Appendix A — Environment Setup

```bash
cd /Users/kausthub.gupta/research-intelligence-platfrom
source .venv/bin/activate
export DATABASE_URL=sqlite:///research_platform.db

# Verify DB state
python inspect_db.py

# Verify NotebookLM auth
nlm notebook list

# If not authenticated
nlm login

# pip install (SSL issue on this machine — always use these flags)
pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org <package>
```

## Appendix B — Key Commands

```bash
# Ingestion
python -m ingestion.run_ingestion --conference ICLR --year 2024 --limit 500
python -m ingestion.run_ingestion --all --limit 500
python -m ingestion.enrich_citations
python -m ingestion.enrich_citations --force --limit 3   # retry failed

# PDF pipeline
python -m pdf_pipeline.run_pipeline --limit 100
python -m pdf_pipeline.run_pipeline --stage segment --force --limit 10

# NotebookLM pipeline
python -m notebooklm.run_pipeline --limit 10
python -m notebooklm.run_pipeline --stage synthesize
python -m notebooklm.run_pipeline --stage extract
python -m notebooklm.smoke_test              # full create/upload/query/delete cycle

# Normalization
python normalize_entities.py

# Graph
python build_graph_v2.py                     # rebuild + generate report
python build_graph.py --stats                # print current stats without rebuilding

# Audits (read-only)
python entity_audit.py
python entity_signal_audit.py
python concept_selection_audit.py

# API
uvicorn api.search:app --reload --port 8000

# Metrics
python -m metrics.dashboard
python -m metrics.dashboard --metric top-cited --n 20
```

## Appendix C — NotebookLM Auth Notes

- Cookies: `~/.notebooklm-mcp-cli/profiles/default/cookies.json`
- Lifetime: 2–4 weeks from last `nlm login`
- Auth check: `nlm notebook list --json` — returns `[]` if no notebooks; non-empty if auth valid
- **Do not use** `nlm login --check` — triggers `chmod 700` that fails under Claude Code sandbox
- `--json` flag not supported on `nlm source add` — parse plain stdout instead
- Source text passed via temp file (`--file`), not `--text`, to avoid shell quoting issues with large strings

## Appendix D — pip SSL Workaround

```bash
# Every pip install must include these flags (macOS keychain OSStatus -26276):
pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org <package>
```
