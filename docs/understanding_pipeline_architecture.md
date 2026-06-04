# Research Understanding Pipeline — Architecture Design

## 1. Goal

For each paper (title + abstract), produce a structured analysis:

```
summary        → 2-3 sentence plain-English summary
categories     → research areas  (["Computer Vision", "Self-Supervised Learning"])
techniques     → named methods   (["LoRA", "FlashAttention", "RLHF"])
methodologies  → research approaches (["Supervised Learning", "Bayesian Inference"])
advantages     → claimed contributions / strengths
limitations    → stated or implied weaknesses
future_work    → directions suggested by the paper
```

---

## 2. Component Map

```
┌──────────────────────────────────────────────────────────────────────┐
│                     AnalysisPipeline  (orchestrator)                 │
│                                                                      │
│  1. Load unenriched papers from DB                                   │
│  2. Build batches  ──►  GeminiAnalyzer  ──►  PaperAnalysis (Pydantic)│
│  3. Write results  ──►  AnalysisStore   ──►  PostgreSQL / SQLite     │
└──────────────────────────────────────────────────────────────────────┘

         ┌──────────────────────────────┐
         │       GeminiAnalyzer         │
         │  - model selection           │
         │  - prompt construction       │
         │  - JSON schema enforcement   │
         │  - retry + back-off          │
         │  - token counting            │
         └──────────────────────────────┘

         ┌──────────────────────────────┐
         │       AnalysisStore          │
         │  - upsert paper_analyses     │
         │  - upsert categories         │
         │  - upsert techniques         │
         │  - upsert methodologies      │
         │  - link join tables          │
         └──────────────────────────────┘
```

---

## 3. New Database Tables

Three tables are added on top of the existing schema:

### `paper_analyses`
One row per paper. Stores the free-text fields.

```sql
CREATE TABLE paper_analyses (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    paper_id       UUID NOT NULL UNIQUE REFERENCES papers(id) ON DELETE CASCADE,

    summary        TEXT,
    advantages     TEXT,       -- newline-separated bullet points
    limitations    TEXT,
    future_work    TEXT,

    model          TEXT,       -- 'gemini-2.0-flash-lite', 'gemini-1.5-flash', …
    prompt_tokens  INT,
    output_tokens  INT,
    cost_usd       NUMERIC(10, 6),
    processing_ms  INT,

    created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

`categories`, `techniques`, `methodologies` already exist in the approved schema.
`paper_categories`, `paper_techniques`, `paper_methodologies` join tables also exist.

The `source='auto'` flag on those join tables distinguishes LLM-assigned tags from
human-curated ones. The `confidence` field on `paper_categories` stores the model's
self-reported certainty (0–1).

---

## 4. Pydantic Output Model

```python
class TechniqueItem(BaseModel):
    name:        str
    role:        Literal["introduces", "uses", "compares", "critiques"] = "uses"

class CategoryItem(BaseModel):
    name:        str
    confidence:  float = Field(ge=0.0, le=1.0)

class PaperAnalysis(BaseModel):
    summary:       str   = Field(min_length=20, max_length=600)
    categories:    list[CategoryItem]  = Field(min_length=1, max_length=6)
    techniques:    list[TechniqueItem] = Field(max_length=10)
    methodologies: list[str]           = Field(max_length=6)
    advantages:    list[str]           = Field(min_length=1, max_length=5)
    limitations:   list[str]           = Field(max_length=5)
    future_work:   list[str]           = Field(max_length=4)
```

Gemini's `response_schema` is built directly from `PaperAnalysis.model_json_schema()`,
so the API enforces structure at the model level — no regex parsing, no fallback JSON
extraction.

---

## 5. Gemini Model Selection

| Model                    | Input $/1M | Output $/1M | Speed    | Use case              |
|--------------------------|-----------|-------------|----------|-----------------------|
| `gemini-2.0-flash-lite`  | $0.075    | $0.30       | Fastest  | ✅ Default (1000+ papers) |
| `gemini-2.0-flash`       | $0.10     | $0.40       | Fast     | Higher quality needed |
| `gemini-1.5-pro`         | $1.25     | $5.00       | Slower   | Spot-check / audit    |

**Default: `gemini-2.0-flash-lite`**

Per-paper cost estimate:
```
Input:   system prompt (~350 tokens, cached) + title+abstract (~270 tokens) = ~620 tokens
Output:  structured JSON (~250 tokens)
Cost:    (620 × $0.075 + 250 × $0.30) / 1,000,000 = $0.000121 per paper
1000 papers: ~$0.12
5000 papers: ~$0.60
```

---

## 6. Prompt Strategy

### System Prompt (constant across all papers — cached)

```
You are a research paper analyst. Given a paper title and abstract,
extract structured information precisely and conservatively.
Return ONLY valid JSON matching the provided schema. No prose outside JSON.

Rules:
- summary: 2-3 sentences, plain English, no jargon inflation
- categories: use established ACM CCS or arXiv taxonomy names only
- techniques: named methods only (e.g. "LoRA", "Adam", "BERT"); no vague terms
- methodologies: broad approach (e.g. "Supervised Learning", "Variational Inference")
- advantages/limitations/future_work: extract only what is stated or clearly implied
  in the abstract; do not fabricate
- If a field has no evidence in the abstract, return an empty list
```

### User Prompt (per paper)
```
Title: {title}
Abstract: {abstract}
```

This tight separation means the system prompt (350 tokens) can be cached after the
first call in a batch, making subsequent calls charge only for the delta (~270 tokens
input + output).

---

## 7. Batch Processing Design

### Concurrency model

```
papers (N)
   │
   ├─ chunk into batches of BATCH_SIZE (default: 20)
   │
   └─ asyncio.Semaphore(MAX_CONCURRENT=5)
          │
          ├── paper_1 ──► GeminiAnalyzer ──► store
          ├── paper_2 ──► GeminiAnalyzer ──► store
          ├── paper_3 ──► GeminiAnalyzer ──► store
          ├── paper_4 ──► GeminiAnalyzer ──► store
          └── paper_5 ──► GeminiAnalyzer ──► store
```

Concurrency of 5 keeps well under Gemini Flash rate limits (1000 RPM on free tier,
no limit on paid tier) while processing 1000 papers in ~3-5 minutes.

### Rate limits

| Tier   | RPM   | TPM      | Recommended MAX_CONCURRENT |
|--------|-------|----------|---------------------------|
| Free   | 15    | 1,000,000 | 2                        |
| Pay-as-you-go | 2,000 | 4,000,000 | 10–20              |

---

## 8. Retry Strategy

```
Attempt 1 ──► success → done
           └─► failure
                  │
               HTTP 429 / RESOURCE_EXHAUSTED → wait  2^attempt × jitter, retry
               HTTP 500 / 503               → wait  2^attempt,          retry
               JSON validation failure      → retry with stricter prompt (max 2×)
               HTTP 400 (bad request)       → log + skip (not retryable)
               MAX_RETRIES = 4
```

JSON validation failures get a second attempt with an explicit error message
injected into the prompt: *"Your previous response failed validation: {error}.
Retry with exactly the required schema."*

---

## 9. Resumability

```sql
-- Papers that have NOT been analysed yet
SELECT p.id, p.title, p.abstract
FROM papers p
LEFT JOIN paper_analyses pa ON pa.paper_id = p.id
WHERE pa.id IS NULL
  AND p.abstract IS NOT NULL
ORDER BY p.citation_count DESC   -- prioritise high-impact papers
```

Running the pipeline twice is always safe. Already-analysed papers are skipped
unless `--force` is passed (useful for model upgrades).

---

## 10. File Structure

```
analysis/
├── __init__.py
├── models.py          ← Pydantic output models (PaperAnalysis, etc.)
├── gemini_client.py   ← GeminiAnalyzer: API call, retry, JSON enforcement
├── store.py           ← AnalysisStore: upsert all analysis tables
├── pipeline.py        ← AnalysisPipeline: orchestrate, batch, progress
└── run_analysis.py    ← CLI entry point

db/
├── models.py          ← add PaperAnalysisRecord ORM model
└── migrations/
    └── 002_add_analysis_tables.sql
```

---

## 11. CLI Interface

```bash
# Analyse all unenriched papers (default model, default concurrency)
python -m analysis.run_analysis

# Process only 50 papers, highest-cited first
python -m analysis.run_analysis --limit 50 --order citation_desc

# Use faster/cheaper model
python -m analysis.run_analysis --model gemini-2.0-flash-lite

# Re-analyse everything (e.g. after prompt improvement)
python -m analysis.run_analysis --force --model gemini-2.0-flash

# Dry-run: show what would be processed and estimated cost
python -m analysis.run_analysis --dry-run

# Report on current analysis coverage
python -m analysis.run_analysis --report-only
```

---

## 12. Cost & Time Estimates

| Papers | Model                 | Est. Cost | Est. Time (concurrency=5) |
|--------|-----------------------|-----------|---------------------------|
| 100    | gemini-2.0-flash-lite | ~$0.01    | ~1 min                    |
| 1,000  | gemini-2.0-flash-lite | ~$0.12    | ~8 min                    |
| 5,000  | gemini-2.0-flash-lite | ~$0.60    | ~40 min                   |
| 1,000  | gemini-2.0-flash      | ~$0.16    | ~8 min                    |

All estimates assume paid tier (2000 RPM). Free tier is ~8× slower (15 RPM).

---

## 13. Build Order

1. `db/migrations/002_add_analysis_tables.sql` — new ORM model + migration
2. `analysis/models.py` — Pydantic output schema
3. `analysis/gemini_client.py` — API wrapper with retry + JSON enforcement
4. `analysis/store.py` — idempotent upserts for all analysis tables
5. `analysis/pipeline.py` — async orchestrator + progress reporting
6. `analysis/run_analysis.py` — CLI
7. Smoke test on 5 papers → inspect DB → full run on 100
