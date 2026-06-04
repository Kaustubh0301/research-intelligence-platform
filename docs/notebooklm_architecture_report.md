# NotebookLM Integration — Architecture Report

**Date:** June 2026  
**Status:** Pre-implementation analysis  
**Codebase reviewed:** All 17 Python source files + schema.sql + models.py + product_design.md

---

## Executive Summary

NotebookLM fits the platform as an **analysis engine** sitting downstream of the existing PDF pipeline. The database remains the source of truth for all structured data. NotebookLM operates on batches of papers grouped by topic (notebooks), producing synthesis and extraction outputs that are parsed and written back into the database. The existing ingestion, PDF, and search layers require **no structural changes**. Four new database tables are needed. The primary architectural risk is that NotebookLM has no official API — the chosen library automates a browser, which makes the integration fragile and stateful by nature.

---

## 1. What Changes Because of NotebookLM

### 1.1 The Gemini analyser is replaced entirely

`pdf_pipeline/analyser.py` was the placeholder for per-paper LLM analysis. It was already gated behind `GEMINI_API_KEY` and designed to be swapped out. NotebookLM replaces this role. The file can remain as-is (it imports lazily and won't execute without a key), but it will not be part of the production analysis path.

**Action:** Deprecate `pdf_pipeline/analyser.py`. Keep it in the repository but mark it unused. Remove stage 4 from the default pipeline run. Do not delete it — it may be useful for spot-checking individual papers.

### 1.2 The analysis pipeline changes unit of work

The current `pdf_pipeline/pipeline.py` processes one paper at a time through four stages. The analysis stage (stage 4) was the natural end of that per-paper loop.

With NotebookLM, analysis is **no longer per-paper**. It is per-notebook (per-topic-batch). This means:

- Stages 1–3 (download, extract, segment) remain per-paper, unchanged.
- Stage 4 is removed from the PDF pipeline.
- Analysis becomes a **separate, batch pipeline** that runs after all papers in a topic group have been downloaded.

The existing `pdf_pipeline/pipeline.py` should have stage 4 removed permanently. A new `notebooklm/pipeline.py` handles the analysis workflow independently.

### 1.3 The `paper_analyses` table design is partially mismatched

`paper_analyses` was designed for Gemini's per-paper synchronous output. It has columns:
- `summary`, `advantages`, `limitations`, `future_work`, `use_cases`
- `model`, `input_tokens`, `output_tokens`, `cost_usd`, `processing_ms`

The token/cost columns are Gemini-specific and meaningless for NotebookLM. The `model` field should record "notebooklm" rather than a model name. The content columns (`summary`, `limitations`, etc.) are still the right destination for extracted per-paper data.

**Action:** Keep `paper_analyses` as the destination table for per-paper analysis outputs. Drop the `input_tokens`, `output_tokens`, `cost_usd`, `processing_ms` columns (or keep them nullable and leave them null — no migration needed for nullable columns). The `model` column will store `"notebooklm/notebook:{notebook_id}"`.

### 1.4 The schema.sql / models.py misalignment must be resolved

`db/schema.sql` defines a normalized design: a `categories` table with parent hierarchy, a `techniques` table (named entities), and a `methodologies` table. `db/models.py` has simpler flat versions: `paper_categories(name, confidence, source)`, `paper_techniques(name, role, source)`, `paper_methodologies(name, source)`.

These are not the same schema. The ORM does not implement what schema.sql intended. This matters now because NotebookLM outputs will populate these tables, and the design must be resolved before we build the extraction layer.

**Decision:** Adopt the normalized schema.sql design for PostgreSQL production. For SQLite dev, keep the flat ORM tables as a temporary approximation. The resolution plan is in Section 5.

### 1.5 A topic assignment step is added before analysis

There is currently no step that groups papers into topic batches. This step must be added as a new pre-analysis stage. It runs on title + abstract text (available now for all 100 papers) and produces notebook assignments. This is a new component with no equivalent in the current codebase.

---

## 2. What Remains Unchanged

| Component | Status | Reason |
|-----------|--------|--------|
| `ingestion/` — all files | **Unchanged** | Collection and storage are independent of analysis |
| `db/models.py` — papers, authors, conferences, editions | **Unchanged** | Core entities are not affected |
| `db/models.py` — paper_sections | **Unchanged** | Extracted section text is what we upload to NotebookLM as sources |
| `db/models.py` — pipeline_errors | **Unchanged** | Reuse for NotebookLM errors |
| `pdf_pipeline/downloader.py` | **Unchanged** | PDFs must still be downloaded before NotebookLM can ingest them |
| `pdf_pipeline/extractor.py` | **Unchanged** | Text extraction feeds source preparation |
| `pdf_pipeline/segmenter.py` | **Unchanged** | Section segmentation used for source quality and text-only fallback |
| `pdf_pipeline/store.py` | **Unchanged** | Stores extracted sections; NotebookLM reads from these |
| `search/query.py` | **Unchanged** | Search operates on DB, not on NotebookLM |
| `metrics/dashboard.py` | **Unchanged** | Metrics are DB-derived |
| `db/schema.sql` (PostgreSQL reference) | **Mostly unchanged** | Need to add 4 new tables |

The key invariant: **NotebookLM is write-only from the platform's perspective**. The platform pushes sources to NotebookLM and pulls outputs back. It never queries NotebookLM for paper metadata, citations, authors, or search results.

---

## 3. Notebook Taxonomy

### 3.1 Design constraints

- **30–50 papers per notebook** (manager requirement, aligns with NotebookLM's ~50-source limit)
- **Topic-based, not venue-based** — the whole point is cross-conference synthesis
- **Two-level hierarchy** — top-level domain → specific topic. Keeps notebook count manageable.
- **Papers can appear in up to 2 notebooks** — interdisciplinary work should not be excluded from either relevant topic

### 3.2 Proposed taxonomy (25 topics)

These are the initial notebook topics. Each maps to a `notebooks` row in the database.

```
DOMAIN: LLM & Language Models
  ├── llm-architectures        "LLM Architectures & Scaling"
  ├── llm-alignment            "Instruction Tuning, RLHF & Alignment"
  ├── llm-reasoning            "LLM Reasoning, Planning & In-Context Learning"
  ├── llm-efficiency           "LLM Efficiency: Quantization, Pruning & KV Cache"
  └── llm-evaluation           "LLM Evaluation & Benchmarks"

DOMAIN: Agentic & Applied AI
  ├── agentic-ai               "Agentic AI, Tool Use & API Grounding"
  ├── retrieval-augmented      "Retrieval-Augmented Generation (RAG)"
  └── code-generation          "Code Generation & Programming AI"

DOMAIN: Safety & Trust
  ├── ai-safety                "AI Safety, Robustness & Red Teaming"
  └── fairness-ethics          "Fairness, Ethics, Bias & Privacy"

DOMAIN: Vision & Multimodal
  ├── vision-language          "Vision-Language Models & Multimodal Learning"
  ├── image-generation         "Image & Video Generation (Diffusion, GANs)"
  ├── object-detection         "Object Detection, Segmentation & Tracking"
  └── 3d-vision                "3D Vision, Point Clouds & Scene Understanding"

DOMAIN: NLP Tasks
  ├── information-extraction   "Information Extraction & Knowledge Graphs"
  ├── machine-translation      "Machine Translation & Cross-Lingual NLP"
  └── dialogue-qa              "Dialogue, Question Answering & Summarization"

DOMAIN: Core ML Methods
  ├── reinforcement-learning   "Reinforcement Learning & Decision Making"
  ├── graph-neural-networks    "Graph Neural Networks & Structured Data"
  ├── optimization-training    "Optimization, Training Dynamics & Architecture Search"
  └── theory-generalization    "Theoretical ML, Generalization & Learning Theory"

DOMAIN: Applications
  ├── biomedical-ai            "Biomedical AI, Drug Discovery & Healthcare"
  ├── scientific-discovery     "Scientific Discovery & Computational Science"
  ├── robotics                 "Robotics, Embodied AI & Physical Simulation"
  └── finance-forecasting      "Finance, Time-Series & Forecasting"
```

### 3.3 Scalability

At 30–50 papers/notebook and 3,000–8,000 total papers, we need 60–266 notebook instances. With 25 topic types, each topic will eventually need 2–10 notebook instances (e.g., "llm-architectures-1", "llm-architectures-2"). The database notebook record tracks which instance holds which papers.

**Overflow rule:** When a topic notebook reaches 45 papers, a new instance is opened. Papers in overlapping topics (e.g., a paper on RAG + alignment) go into the smaller of the two topic notebooks at the time of assignment.

---

## 4. Topic Assignment Logic

Topic assignment is the bridge between ingestion and NotebookLM. It must run before any PDF is uploaded to NotebookLM.

### 4.1 Input signals (available now, no analysis API needed)

| Signal | Weight | Notes |
|--------|--------|-------|
| Conference field (ML/CV/NLP/AI) | High | Eliminates most inter-domain ambiguity |
| Title keywords | High | Most discriminating single signal |
| Abstract keywords | Medium | Confirms or refines title signal |
| Author institution | Low | Research groups have topical tendencies |
| Citation neighbourhood | Medium | Papers citing each other share topics (future pass) |

### 4.2 Assignment algorithm (three-pass)

**Pass 1 — Hard conference rules**

Some conference + topic combinations are high-confidence:
- CVPR, ICCV, ECCV papers → Vision domain first
- ACL, EMNLP papers → NLP domain first
- NeurIPS, ICML, ICLR papers → no constraint (these are broad)

This eliminates one full domain for most CV and NLP papers before keyword matching.

**Pass 2 — Keyword scoring**

Each notebook topic has a keyword vocabulary (title and abstract terms). Score each paper against each topic vocabulary, normalizing for vocabulary size. Assign to the top-1 topic if score ≥ threshold; top-2 if score ≥ secondary threshold (multi-assignment case).

Sample keyword vocabularies (partial):

```
agentic-ai:
  primary:   [agent, tool use, API, function call, gorilla, toolbench, react,
              planning, action, environment, scaffold, autonomous]
  secondary: [LLM, language model, retrieval]

llm-efficiency:
  primary:   [quantization, pruning, KV cache, compression, distillation,
              efficient, sparse, attention, flash, low-rank, adapter]
  secondary: [transformer, inference, throughput]

ai-safety:
  primary:   [safety, alignment, refusal, jailbreak, red team, harmful,
              robustness, adversarial, backdoor, sycophancy, bias]
  secondary: [RLHF, reward, human feedback]

image-generation:
  primary:   [diffusion, GAN, generative, synthesis, denoising, latent,
              stable diffusion, DDPM, score matching, VAE, image generation]
  secondary: [vision, multimodal]
```

Each vocabulary is stored as a JSON config file in `notebooklm/topic_keywords.json` — editable without code changes.

**Pass 3 — Fallback and overflow**

- Papers with no topic score above threshold → assigned to the broadest relevant domain topic (e.g., "llm-architectures" for NeurIPS ML papers, "object-detection" for CVPR CV papers).
- Papers scoring into a notebook already at 45 sources → bump to the same-domain notebook with most remaining capacity.
- Papers with completely ambiguous signals → flagged as `assignment_confidence = "low"` in `notebook_papers.confidence`. These get human-reviewable status.

### 4.3 Assignment is revisable

Assignments are stored in `notebook_papers.confidence` and `notebook_papers.assigned_by`. After NotebookLM has run and produced category outputs, a second-pass assignment can use that richer signal to move papers between notebooks. The MCP integration tracks upload status so re-assignment is safe (un-assign from old notebook, assign to new, trigger re-upload).

---

## 5. How NotebookLM Outputs Are Stored in the Database

### 5.1 New tables required

Four new tables, none of which conflict with existing schema:

```sql
-- One row per NotebookLM notebook (one per topic instance)
notebooks (
    id                UUID PRIMARY KEY,
    topic_slug        TEXT NOT NULL,           -- 'agentic-ai', 'llm-efficiency', etc.
    topic_name        TEXT NOT NULL,           -- human-readable
    instance_number   SMALLINT NOT NULL DEFAULT 1,
    notebooklm_url    TEXT,                    -- URL of the notebook in NotebookLM UI
    source_count      SMALLINT NOT NULL DEFAULT 0,
    max_sources       SMALLINT NOT NULL DEFAULT 45,
    status            TEXT CHECK (status IN ('active','full','archived')) DEFAULT 'active',
    last_synced_at    TIMESTAMPTZ,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (topic_slug, instance_number)
)

-- Many-to-many: which papers are in which notebook
notebook_papers (
    notebook_id       UUID REFERENCES notebooks(id),
    paper_id          UUID REFERENCES papers(id),
    assigned_by       TEXT DEFAULT 'keyword',  -- 'keyword' | 'manual' | 'notebooklm'
    assignment_confidence  TEXT DEFAULT 'medium',  -- 'high' | 'medium' | 'low'
    source_status     TEXT DEFAULT 'pending'   -- 'pending' | 'uploaded' | 'error' | 'removed'
    upload_attempted_at   TIMESTAMPTZ,
    upload_completed_at   TIMESTAMPTZ,
    PRIMARY KEY (notebook_id, paper_id)
)

-- Notebook-level synthesis outputs from NotebookLM
notebook_syntheses (
    id                UUID PRIMARY KEY,
    notebook_id       UUID REFERENCES notebooks(id),
    synthesis_type    TEXT CHECK (synthesis_type IN
                          ('faq','study_guide','briefing','overview','query_response')),
    query_prompt      TEXT,                    -- the question asked (for query_response type)
    content           TEXT NOT NULL,           -- raw NotebookLM output
    word_count        INT,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (notebook_id, synthesis_type, query_prompt)
)

-- Per-paper extracts parsed out of notebook synthesis responses
-- Intermediate table; normalised into paper_analyses, paper_categories, etc.
notebook_paper_extracts (
    id                UUID PRIMARY KEY,
    notebook_id       UUID REFERENCES notebooks(id),
    paper_id          UUID REFERENCES papers(id),
    extract_type      TEXT CHECK (extract_type IN
                          ('summary','techniques','methodologies',
                           'limitations','datasets','categories','future_work')),
    content           TEXT NOT NULL,           -- raw parsed extract (prose or JSON)
    confidence        TEXT DEFAULT 'medium',
    normalized        BOOLEAN DEFAULT FALSE,   -- True once written to paper_analyses etc.
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
)
```

### 5.2 How existing tables get populated

The flow is: NotebookLM response → `notebook_syntheses` → parse → `notebook_paper_extracts` → normalize → existing tables.

```
notebook_syntheses.content
         │
         ▼ (parser)
notebook_paper_extracts (one row per paper per extract type)
         │
         ▼ (normalizer)
┌────────────────────────────────────┐
│ paper_analyses.summary             │ ← from extract_type='summary'
│ paper_analyses.limitations         │ ← from extract_type='limitations'
│ paper_analyses.advantages          │ ← parsed from extract_type='summary'
│ paper_analyses.future_work         │ ← from extract_type='future_work'
├────────────────────────────────────┤
│ paper_categories.name              │ ← from extract_type='categories'
├────────────────────────────────────┤
│ paper_techniques.name/role         │ ← from extract_type='techniques'
├────────────────────────────────────┤
│ paper_methodologies.name           │ ← from extract_type='methodologies'
├────────────────────────────────────┤
│ paper_datasets.name/task           │ ← from extract_type='datasets'
└────────────────────────────────────┘
```

### 5.3 Normalized schema alignment

The ORM (`models.py`) currently has flat per-paper tables. `schema.sql` has normalized entity tables (`categories`, `techniques`, `methodologies` as standalone entities with UUIDs, linked via join tables).

**Resolution plan:** 

- For SQLite dev: keep the flat ORM tables (`paper_categories(name)`, `paper_techniques(name, role)`, `paper_methodologies(name)`). These are sufficient for the search filter use case.
- For PostgreSQL prod: implement the normalized schema.sql design. The normalization step (extracting entity rows into `categories`, then linking) runs once as a migration job after NotebookLM populates the flat tables.
- Do not try to implement both simultaneously. The flat model works for the product launch; entity normalization is a v2 concern.

### 5.4 Querying strategy for per-paper extraction

NotebookLM is asked targeted questions designed to produce parseable per-paper output. These run as `notebook_syntheses` with `synthesis_type='query_response'`.

Example queries sent to each notebook:

```
Q1 (summaries):
"For each paper in this notebook, write a 2-sentence summary.
Format exactly as:
PAPER: [exact paper title]
SUMMARY: [2 sentences]
---
Repeat for every paper."

Q2 (techniques):
"List the key technical methods introduced or used in each paper.
Format exactly as:
PAPER: [exact paper title]
INTRODUCES: [method name] | [method name]
USES: [method name] | [method name]
---"

Q3 (limitations):
"For each paper, state its primary limitation or failure case.
Format exactly as:
PAPER: [exact paper title]
LIMITATION: [one sentence]
---"

Q4 (datasets):
"List datasets used in experiments for each paper.
Format exactly as:
PAPER: [exact paper title]
DATASETS: [dataset name] | [dataset name]
---"

Q5 (categories):
"Assign 1-3 research category tags to each paper from this list:
[LLM, Vision, Multimodal, Agentic AI, Safety, Efficiency, NLP, RL, Theory,
Graph Learning, Biomedical, Robotics, Code, Retrieval, Generative]
Format exactly as:
PAPER: [exact paper title]
CATEGORIES: [tag] | [tag]
---"
```

The parser matches paper titles from the response against the DB using fuzzy title matching (reusing the token-overlap logic already in `enrich_citations.py`).

---

## 6. Complete NotebookLM Integration Plan

### 6.1 Component map

```
┌─────────────────────────────────────────────────────────────────────┐
│  EXISTING (unchanged)                                               │
│                                                                     │
│  OpenReview/S2 → ingestion → papers + authors (DB)                 │
│  papers → pdf_pipeline stages 1-3 → paper_sections (DB)            │
│  papers → enrich_citations → citation_count (DB)                   │
│  papers → search/query → search results (API)                      │
│  papers → metrics/dashboard → charts (API)                         │
└───────────────────────────┬─────────────────────────────────────────┘
                            │ paper_sections.full_text
                            ▼
┌─────────────────────────────────────────────────────────────────────┐
│  NEW: NotebookLM Integration Layer                                  │
│                                                                     │
│  notebooklm/                                                        │
│    assigner.py     ← topic assignment (keyword scoring)             │
│    source_prep.py  ← builds uploadable source per paper             │
│    client.py       ← wraps jacob-bd MCP; notebook CRUD + queries    │
│    extractor.py    ← parses NotebookLM query responses              │
│    normalizer.py   ← writes extracts to paper_analyses, etc.        │
│    pipeline.py     ← orchestrates the 5 stages                     │
│    run_pipeline.py ← CLI entry point                                │
│  notebooklm/                                                        │
│    topic_keywords.json   ← editable keyword vocabulary              │
│    topic_taxonomy.json   ← notebook topic definitions               │
└─────────────────────────────────────────────────────────────────────┘
```

### 6.2 Five pipeline stages

**Stage A — Assign**  
Input: all papers without a `notebook_papers` assignment  
Action: run topic assignment algorithm (Section 4)  
Output: rows in `notebook_papers` with `source_status='pending'`  
Resumable: papers with existing assignment rows are skipped  

**Stage B — Provision**  
Input: `notebooks` rows for topics with pending papers  
Action: for notebooks that don't exist in NotebookLM yet, create them via MCP client; record `notebooklm_url`  
Output: all `notebooks` rows have valid `notebooklm_url`  
Idempotent: checks `notebooklm_url IS NOT NULL` before creating  

**Stage C — Upload Sources**  
Input: `notebook_papers` rows with `source_status='pending'`  
Action: for each paper, build uploadable source (see Section 6.3), upload to NotebookLM via MCP  
Output: `source_status` updated to `'uploaded'` or `'error'`  
Rate control: 1 upload per 3 seconds (browser automation is not fast)  
Resumable: only processes `source_status='pending'` rows  

**Stage D — Synthesize**  
Input: notebooks where all sources are uploaded  
Action: for each notebook, send the 5 query prompts (Section 5.4); store in `notebook_syntheses`  
Output: rows in `notebook_syntheses`  
Rate control: 1 query per 5 seconds per notebook  
Resumable: checks `notebook_syntheses` for existing rows before querying  

**Stage E — Extract & Normalize**  
Input: `notebook_syntheses` rows with `normalized=False`  
Action: parse responses → write `notebook_paper_extracts` → normalize to `paper_analyses`, `paper_categories`, `paper_techniques`, `paper_methodologies`, `paper_datasets`  
Output: per-paper analysis data in DB; `normalized` flag set to True  
Fully local: no network calls, pure DB operations  

### 6.3 Source format per paper

Each paper uploaded to NotebookLM is a single text file (not the raw PDF, which has extraction artifacts). It is assembled from `paper_sections`:

```
PAPER: {title}
AUTHORS: {author_1}, {author_2}, ...
CONFERENCE: {conference} {year}
CITATIONS: {citation_count}

ABSTRACT:
{abstract text}

INTRODUCTION:
{introduction text if available}

METHODOLOGY:
{methodology text if available}

EXPERIMENTS:
{experiments text if available}

RESULTS:
{results text if available}

CONCLUSION:
{conclusion text if available}

LIMITATIONS:
{limitations text if available}
```

**Why not upload the raw PDF?**

1. Raw PDFs have layout artifacts (column text interleaving, header/footer noise, math rendering failures).
2. The segmenter has already cleaned this text.
3. Text files upload faster.
4. We can include structured metadata (authors, citations) that is not in the PDF.
5. NotebookLM's 50-source limit is per notebook, not per MB — text files use the same "slot" as PDFs.

**Fallback for papers without PDFs:** Use abstract only. Mark `source_status='abstract_only'` so the analysis confidence is flagged as lower.

### 6.4 Refresh cycle

New papers arrive continuously. The refresh cycle is:

1. Daily ingestion run → new papers in DB
2. Citation enrichment run → citation_count updated for new and existing papers
3. PDF pipeline (stages 1–3) → new papers get sections
4. NotebookLM pipeline (stages A–E) → new papers assigned, uploaded, extracted
5. Weekly: re-run synthesis queries for active notebooks to capture any updated insights

The NotebookLM pipeline should be idempotent at every stage. A `--limit` flag on stage C controls how many uploads happen per run (browser automation sessions have finite lifetimes).

### 6.5 MCP client wrapper (`notebooklm/client.py`)

The jacob-bd/notebooklm-mcp-cli library is exposed as an MCP server. The wrapper should:

- Abstract the MCP protocol details
- Handle session management (MCP server startup, ping, shutdown)
- Implement retry with exponential backoff for all operations
- Log every operation to `pipeline_errors` on failure
- Never assume a previous operation succeeded without DB confirmation

The wrapper exposes these methods:
```python
create_notebook(name: str, description: str) -> str  # returns notebooklm_url
add_source(notebook_url: str, source_text: str, title: str) -> bool
query_notebook(notebook_url: str, prompt: str) -> str
list_notebooks() -> list[dict]
```

---

## 7. Risks, Bottlenecks, and Missing Components

### 7.1 Critical risks

**RISK 1 — No official API (HIGH severity)**  
NotebookLM has no public API. jacob-bd/notebooklm-mcp-cli automates the browser UI using Playwright. Any UI change in NotebookLM breaks the integration silently or loudly. Google has changed the UI multiple times. The library may lag behind UI changes by days or weeks.

Mitigation:
- Pin the library to a specific commit hash, not a floating version
- Build the client wrapper so the MCP calls are all in one file (`notebooklm/client.py`) — regressions are isolated
- Add a `health_check()` method that creates a test notebook and uploads a test source; run it before every batch job
- Maintain a fallback: if NotebookLM fails, the DB still has `paper_sections` data that a future analysis pass can use

**RISK 2 — 50-source limit is a hard ceiling (HIGH severity)**  
NotebookLM enforces a maximum of ~50 sources per notebook. At 30–50 papers per notebook with growing corpus, notebook instances will overflow. The multi-instance design (topic-slug-1, topic-slug-2) handles this, but cross-instance synthesis is not supported natively.

Mitigation:
- Set `max_sources = 45` (5-slot buffer) in the `notebooks` table
- The `notebooks.status = 'full'` flag triggers creation of a new instance before overflow
- Accept that cross-instance synthesis is weaker than within-instance synthesis

**RISK 3 — Output parsing is brittle (MEDIUM severity)**  
NotebookLM returns natural language. The query prompts in Section 5.4 request specific formats, but NotebookLM does not guarantee them. The parser in `extractor.py` will encounter:
- Missing sections (paper not found in notebook)
- Extra text around the structured output
- Inconsistent title matching (NotebookLM may paraphrase a paper title)

Mitigation:
- Use token-overlap fuzzy matching for paper title resolution (already implemented in `enrich_citations.py`)
- For any extract that fails to parse, write it to `notebook_paper_extracts` as raw text with `confidence='low'` rather than dropping it
- A human review queue for `confidence='low'` extracts

**RISK 4 — Browser session durability (MEDIUM severity)**  
Browser automation sessions expire after inactivity. Long upload jobs (uploading 45 PDFs at 3s/source = 135 seconds) may hit session timeouts mid-batch.

Mitigation:
- Process uploads in batches of 10, with a session health check between batches
- `notebook_papers.source_status` provides per-paper resumption — failed batch resumes from where it stopped
- Set `upload_attempted_at` immediately before the upload attempt; detect stale attempts on resume

**RISK 5 — Chicken-and-egg with category assignment (LOW-MEDIUM severity)**  
The keyword-based assignment in Phase 1 will be imperfect. Papers on novel topics (e.g., a paper on LLM-assisted drug discovery) may score into the wrong topic. Once NotebookLM assigns categories, those categories can improve reassignment — but only after the first full analysis pass.

Mitigation:
- Store `assignment_confidence` in `notebook_papers`
- After first analysis pass, run a second assignment pass using NotebookLM-derived categories as additional signals
- `assignment_confidence='low'` papers are surfaced in a review interface

### 7.2 Bottlenecks

**Upload throughput**  
At 3 seconds/source, uploading 45 papers to one notebook takes ~2.25 minutes. For 100 notebooks, that's 3.75 hours of serial uploading. If papers appear in 2 notebooks on average, double that.

Mitigate with concurrency: run 3–4 parallel browser sessions against separate notebooks. The MCP library may support this with separate server instances.

**Synthesis latency**  
Each notebook query takes 15–60 seconds for NotebookLM to generate a response. 5 queries × 100 notebooks = 500 queries × 30 seconds average = 4+ hours. This must run as a background job, not synchronously.

**Title matching failures**  
Fuzzy matching against 3,000+ paper titles becomes slow at scale. The token-overlap approach is O(n) per title lookup. For 50 papers × 5 queries × 30 words/response = 7,500 lookup operations per notebook, this is manageable but should be indexed by abstract hash.

### 7.3 Missing components

The following do not exist yet and must be built:

| Component | File | Depends on |
|-----------|------|-----------|
| Topic keyword vocabulary | `notebooklm/topic_keywords.json` | Research into corpus |
| Keyword scorer | `notebooklm/assigner.py` | topic_keywords.json |
| Source text builder | `notebooklm/source_prep.py` | paper_sections table |
| MCP client wrapper | `notebooklm/client.py` | jacob-bd library installed |
| Response parser | `notebooklm/extractor.py` | notebooklm/client.py |
| DB normalizer | `notebooklm/normalizer.py` | extractor.py |
| Pipeline orchestrator | `notebooklm/pipeline.py` | all above |
| CLI entry point | `notebooklm/run_pipeline.py` | pipeline.py |
| DB migration 005 | `db/migrations/005_notebooks.sql` | models.py additions |
| ORM models for notebooks | `db/models.py` additions | migration 005 |

The jacob-bd/notebooklm-mcp-cli library must be installed and tested for connectivity before any pipeline code is written. This is the single highest-priority prerequisite — if the library cannot reliably create notebooks and upload sources, the entire integration plan changes.

---

## 8. Summary Decision Table

| Question | Decision |
|----------|----------|
| Replace DB with NotebookLM? | No. DB is the source of truth. |
| Replace Gemini with NotebookLM? | Yes. `pdf_pipeline/analyser.py` is deprecated. |
| Per-paper notebooks? | No. Topic-based notebooks (30–50 papers each). |
| Number of topic buckets? | 25 initial topics, expandable to 60+ instances as corpus grows. |
| Papers per notebook? | 30–45 (max 45 with buffer below the 50-source limit). |
| Papers in multiple notebooks? | Yes, up to 2 notebooks per paper for cross-disciplinary work. |
| How are outputs stored? | notebooks → notebook_syntheses → notebook_paper_extracts → existing tables. |
| Upload format? | Cleaned text from paper_sections (not raw PDF). |
| Assignment method? | Keyword scoring on title + abstract; conference field as primary filter. |
| Schema changes? | 4 new tables (notebooks, notebook_papers, notebook_syntheses, notebook_paper_extracts). |
| Biggest risk? | No official NotebookLM API — browser automation fragility. |
| First thing to do? | Validate jacob-bd library can create a notebook and upload a source. |
