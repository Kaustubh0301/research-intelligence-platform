# NotebookLM Synthesis Integration — Backend Design

**Status:** design (not yet implemented)
**Depends on:** Feature Mapper (Phases 1–3, complete) and the existing `notebooklm/` pipeline.
**Goal:** summarize the papers retrieved for a project into cross-paper synthesis —
methodology trends, common architectures, datasets, evaluation metrics, strengths,
limitations, and research directions.

---

## 1. Key insight that drives the design

The retrieved papers are **already analyzed**. The existing `notebooklm/` pipeline
runs topic-based notebooks and extracts per-paper structured analysis into
`paper_analyses` (`methodology`, `experimental_findings`, `strengths`,
`limitations`, `practical_applications`, `future_research_directions`), plus
`paper_techniques`, `paper_datasets`, `paper_categories`.

Measured coverage on a live project: **11/11 retrieved papers already had
`paper_analyses.methodology` populated.** So the synthesis problem is primarily an
**aggregation problem over cached per-paper analysis**, not a fresh NotebookLM run.

This yields a two-tier design: a fast cached path that works today, and an optional
live NotebookLM path for depth or for papers lacking cached analysis.

---

## 2. Two synthesis tiers

### Tier A — Cached aggregation (default, fast, synchronous)

Aggregate the already-extracted per-paper analysis of a project's retrieved papers,
then one LLM call synthesizes the cross-paper trends.

```
project's retrieved paper_ids
  → batch-load paper_analyses + paper_techniques + paper_datasets + paper_categories
  → deterministic aggregation:
       methodologies   ← paper_analyses.methodology (prose) + paper_methodologies
       architectures   ← paper_techniques (architecture-tier names) frequency
       datasets        ← paper_datasets.canonical_name frequency
       eval metrics    ← parsed paper_analyses.experimental_findings ("bench :: metric :: score")
       strengths       ← paper_analyses.strengths (union, frequency)
       limitations     ← paper_analyses.limitations (union, frequency)
       directions      ← paper_analyses.future_research_directions (union)
  → 1 LLM call: synthesize ranked trends + narrative per dimension
  → persist to fm_syntheses
```

- **Latency:** seconds (one LLM call; everything else is SQL).
- **Coverage:** as good as the corpus's existing analysis (high — these are corpus papers).
- **No browser automation, no rate limits.**

This is the recommended default and what the API returns synchronously.

### Tier B — Live NotebookLM synthesis (optional, slow, async)

For deeper grounded multi-document synthesis, or when retrieved papers lack cached
analysis, create an ephemeral NotebookLM notebook scoped to the project's papers and
query it directly.

```
project's retrieved papers (PDFs / source text)
  → notebooklm.client.create_notebook("fm-synth-<project_id>")
  → for each paper: client.add_source(...)         [reuses source_prep.py]
  → client.query_notebook(prompt) for each synthesis dimension
       (methodology trends, common architectures, datasets, metrics,
        strengths, limitations, research directions)
  → notebooklm.extractor parses answers into structured fields
  → persist to fm_syntheses (source='notebooklm')
  → client.delete_notebook(...)   (ephemeral; do not pollute the topic notebooks)
```

- **Latency:** minutes (browser automation, upload + multiple queries).
- **Constraints:** NotebookLM has no API — `notebooklm/client.py` wraps a CLI doing
  browser automation; it is rate-limited and auth-cookie dependent (2–4 week lifetime).
- **Therefore must be async** (background job), never inline in a request.

**Reuse, don't rebuild:** Tier B is wiring of existing `notebooklm/` primitives
(`client.create_notebook/add_source/query_notebook/delete_notebook`,
`source_prep.py`, `extractor.parse_*`). No new NotebookLM mechanics.

---

## 3. Data model

One new table. Synthesis is scoped to a project (project-level) and optionally to a
feature (feature-level), so the same machinery serves both.

```sql
CREATE TABLE fm_syntheses (
    id              UUID PRIMARY KEY,
    project_id      UUID NOT NULL REFERENCES fm_projects(id) ON DELETE CASCADE,
    feature_id      UUID REFERENCES fm_features(id) ON DELETE CASCADE,  -- NULL = project-level
    scope           TEXT NOT NULL,        -- 'project' | 'feature'
    source          TEXT NOT NULL,        -- 'cached' | 'notebooklm'
    status          TEXT NOT NULL,        -- 'pending'|'running'|'complete'|'failed' (Tier B)

    -- Structured synthesis dimensions (JSON-encoded TEXT, SQLite convention)
    methodology_trends      TEXT,   -- JSON: [{name, paper_count, note}]
    common_architectures    TEXT,   -- JSON: [{name, paper_count}]
    datasets                TEXT,   -- JSON: [{name, paper_count}]
    evaluation_metrics      TEXT,   -- JSON: [{name, paper_count}]
    strengths               TEXT,   -- JSON: [string]
    limitations             TEXT,   -- JSON: [string]
    research_directions     TEXT,   -- JSON: [string]
    narrative               TEXT,   -- LLM prose tying the dimensions together

    paper_ids               TEXT,   -- JSON: the papers this synthesis covers
    llm_model               TEXT,
    notebook_id             TEXT,   -- Tier B ephemeral notebook (for audit/cleanup)
    generation_ms           INTEGER,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (project_id, feature_id, source)
);
```

`status` is only meaningful for Tier B (async); Tier A writes `complete` directly.

---

## 4. Module structure

```
feature_mapper/
└── synthesis/
    ├── __init__.py
    ├── aggregator.py     # Tier A: load + aggregate cached paper_analyses → structured dims
    ├── synthesizer.py    # 1 LLM call → trends + narrative (grounded in aggregates)
    ├── notebook_job.py   # Tier B: async orchestration over notebooklm/ primitives
    └── models.py         # SynthesisResult / SynthesisDimensions pydantic
```

`notebook_job.py` is the only file that imports `notebooklm/`; Tier A has zero
NotebookLM dependency. This keeps the fast path runnable even when NotebookLM auth is
down (the recurring environmental risk noted in project memory).

---

## 5. API

```
POST /api/v1/feature-map/projects/{id}/synthesis
     ?source=cached        → Tier A, synchronous, returns SynthesisResult (default)
     ?source=notebooklm    → Tier B, enqueues async job, returns {status:'pending'}

GET  /api/v1/feature-map/projects/{id}/synthesis
     → latest synthesis (cached preferred; includes status for in-flight Tier B)

GET  /api/v1/feature-map/features/{id}/synthesis   (feature-scoped, Tier A)
```

The report generator (`feature_mapper/report.py`) gains an **optional** dependency:
when a synthesis exists, its trends feed Sections 2 (Key Research Areas), 8 (Research
Gaps), and a new optional "Methodology & Architecture Trends" subsection. The report
must still work with no synthesis present (graceful degradation).

---

## 6. End-to-end data flow

```
                    ┌─────────────────────────────────────────────┐
   analyze (done) → │ fm_features · fm_paper_matches · fm_recs     │
                    └───────────────────┬─────────────────────────┘
                                        │ retrieved paper_ids
              ┌─────────────────────────┴──────────────────────────┐
              │                                                     │
        TIER A (default)                                     TIER B (optional, async)
              │                                                     │
   load paper_analyses / techniques /                    create ephemeral notebook
   datasets / categories  (SQL, batched)                 add_source(retrieved papers)
              │                                           query_notebook(×7 dimensions)
   deterministic aggregation per dimension               extractor.parse_* → dims
              │                                                     │
   1 LLM call → trends + narrative                       1 LLM call (optional polish)
              │                                                     │
              └──────────────► fm_syntheses ◄──────────────────────┘
                                    │
                       feeds report.py sections 2 / 8 / trends
```

---

## 7. Synthesis dimensions → source fields

| Dimension | Tier A source (cached) | Tier B source (live) |
|---|---|---|
| Methodology trends | `paper_analyses.methodology`, `paper_methodologies` | "Summarize the common methodologies across these papers" |
| Common architectures | `paper_techniques` (architecture-tier) frequency | "What model architectures recur across these papers?" |
| Datasets | `paper_datasets.canonical_name` frequency | "What datasets are used to evaluate this work?" |
| Evaluation metrics | parsed `experimental_findings` (`metric` token) | "What evaluation metrics are reported?" |
| Strengths | `paper_analyses.strengths` (union) | "What are the common strengths?" |
| Limitations | `paper_analyses.limitations` (union) | "What limitations recur?" |
| Research directions | `paper_analyses.future_research_directions` | "What future directions do these papers propose?" |

The architecture-tier technique filter (transformers, CNNs, SSMs, GNNs, diffusion,
encoder/decoder variants) is a small curated allowlist in `aggregator.py`.

---

## 8. Phasing

- **Phase 3.1 (next, small):** `fm_syntheses` table + `synthesis/aggregator.py` +
  `synthesis/synthesizer.py` (Tier A) + the two synchronous endpoints. Wire trends
  into the report. Fully functional with zero NotebookLM dependency.
- **Phase 3.2 (later, when needed):** `synthesis/notebook_job.py` (Tier B async) +
  job status plumbing. Only worth building if Tier A's cached coverage proves
  insufficient for some domains (it was 11/11 in testing).

## 9. Risks & mitigations

| Risk | Mitigation |
|---|---|
| NotebookLM auth/cookie expiry, rate limits (Tier B) | Tier A is default and independent; Tier B is opt-in + async + fail-soft |
| Retrieved papers lacking cached analysis | aggregator reports coverage; falls back to abstract-only dims; Tier B can backfill |
| Ephemeral notebooks polluting the topic-notebook set | dedicated `fm-synth-*` naming + guaranteed `delete_notebook` in a finally block |
| LLM proxy outages (observed intermittently) | Tier A synthesizer fail-soft to deterministic dimension lists (no narrative) |
| Latency creep in `analyze` | synthesis is a **separate endpoint**, never inline in analyze (same pattern as the report) |

---

## 10. Why this shape

- **Decoupled from analyze:** synthesis, like the report, runs on persisted data via
  its own endpoint — analyze stays at its current latency.
- **Cached-first:** the corpus already paid the NotebookLM extraction cost; we
  aggregate it instead of re-paying per project. Fast, reliable, no browser automation.
- **NotebookLM as enrichment, not dependency:** the heavy, fragile path is isolated,
  async, and optional — so the feature works even when NotebookLM is unavailable.
- **One synthesis machine, two scopes:** the same aggregator serves project-level and
  feature-level synthesis by varying the paper-id set.
