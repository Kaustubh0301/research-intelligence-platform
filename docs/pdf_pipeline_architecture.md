# PDF Processing Pipeline — Architecture Design

## Empirical Baseline (measured on real papers)

| Metric | Min | Avg | Max |
|--------|-----|-----|-----|
| PDF size | 500 KB | 1.5 MB | 5 MB |
| Pages | 10 | 18 | 35 |
| Words | 6,000 | 12,000 | 20,000 |
| Raw tokens (chars÷4) | 8,000 | 18,000 | 30,000 |
| Download time | 0.6s | 2.5s | 8s |
| PyMuPDF extraction | 50ms | 200ms | 400ms |
| Sections detected by regex | 6 | 9 | 14 |

**Critical constraint:** full-paper input to Gemini = 18,000 tokens avg.
Sending full text for 5,000 papers at $0.075/1M tokens = **$6.75 input cost alone** —
3× more expensive than abstract-only.

**Strategy:** extract sections, then send only the high-signal subset
(Methodology + Experiments + Results + Conclusion + Limitations) to the LLM.
That subset averages ~4,000 tokens per paper — comparable to abstract-only cost
while delivering 10× richer analysis.

---

## 1. Pipeline Stages

```
┌──────────────────────────────────────────────────────────────────────────┐
│                     PDF Processing Pipeline                              │
│                                                                          │
│  Stage 1          Stage 2           Stage 3          Stage 4            │
│  DOWNLOAD    ──►  EXTRACT      ──►  SEGMENT     ──►  ANALYSE            │
│                                                                          │
│  async HTTP       PyMuPDF           SectionParser     Gemini Flash Lite  │
│  resume/retry     raw text          + Cleaner         structured JSON    │
│  local cache      + metadata        named sections    Pydantic output    │
│                                                                          │
│  └─► pdfs/        └─► paper_        └─► paper_        └─► paper_        │
│       {id}.pdf         raw_texts         sections          analyses      │
│      (filesystem)      (DB)              (DB)              (DB)          │
└──────────────────────────────────────────────────────────────────────────┘
```

Each stage is **independently resumable** and **independently re-runnable**.
Stages are decoupled via DB state flags — running stage 3 twice is safe.

---

## 2. PDF Source Strategy

All 100 current papers come from OpenReview (`pdf_url` = `https://openreview.net/pdf?id=…`).
For future conferences, the fallback priority is:

```
1. openreview_id  →  https://openreview.net/pdf?id={id}        (NeurIPS, ICLR, ICML)
2. arxiv_id       →  https://arxiv.org/pdf/{arxiv_id}           (all conferences)
3. openalex_id    →  openAccessPdf URL from OpenAlex API        (CVPR, ECCV, ACL, …)
4. doi            →  Unpaywall API  →  open-access PDF URL      (last resort)
5. semantic_scholar openAccessPdf field                         (S2 enrichment pass)
```

Current corpus: 100% OpenReview → single download pattern, no auth required.

---

## 3. Stage 1 — Download

### Design

```python
class PDFDownloader:
    storage_dir:   Path          # pdfs/{conference}/{year}/{paper_id}.pdf
    max_concurrent: int = 8      # asyncio.Semaphore
    timeout:        int = 30     # seconds per request
    max_retries:    int = 4      # exponential back-off
    retry_statuses: set = {429, 500, 502, 503, 504}

    async def download_paper(paper: Paper) -> Path | None
    async def download_all(papers: list[Paper]) -> DownloadResult
```

### Resume / Skip Logic

```sql
-- Papers that still need a PDF download
SELECT id, title, pdf_url
FROM papers
WHERE pdf_local_path IS NULL    -- new column on papers table
  AND pdf_url IS NOT NULL
```

`pdf_local_path` is set atomically after a successful write. A partial download
(crash mid-write) leaves the file incomplete — detected by comparing
`Content-Length` header to actual file size on disk.

### Storage Layout

```
pdfs/
└── NeurIPS/
    └── 2024/
        ├── iEeiZlTbts.pdf      (paper.openreview_id)
        ├── jIh4W7r0rn.pdf
        └── …
```

All paths are relative to `PDF_STORAGE_ROOT` (env var). On a laptop this is a
local directory; on a server it can be an NFS mount or replaced by S3 with a
one-line change to the storage adapter.

### Error Taxonomy

| Error | Action |
|-------|--------|
| HTTP 404 | Mark `pdf_url` as invalid; try fallback sources |
| HTTP 429 | Back-off + retry (up to 4×) |
| Content-Type ≠ application/pdf | Log warning; skip |
| File < 10 KB after download | Treat as stub/redirect; mark failed |
| Timeout | Retry with longer timeout (2×) |

---

## 4. Stage 2 — Extract

### Tool Selection

| Tool | Speed | Academic PDF quality | Two-column | Notes |
|------|-------|---------------------|------------|-------|
| **PyMuPDF (fitz)** | ⚡ 200ms | ★★★★☆ | ✅ Good | **Default** |
| pdfplumber | 800ms | ★★★★☆ | ✅ Good | Better table extraction |
| pdfminer.six | 1.2s | ★★★☆☆ | ⚠ Mediocre | Pure Python fallback |
| GROBID | 3–8s | ★★★★★ | ✅ Excellent | Java service; best headers |
| Adobe Extract API | 8–15s | ★★★★★ | ✅ Excellent | $0.05/page; expensive |

**Decision: PyMuPDF as primary.** GROBID is architecturally isolated behind
a `TextExtractor` interface — it can be swapped in for a quality improvement
pass without touching the rest of the pipeline.

### What is Extracted

```python
@dataclass
class RawExtraction:
    paper_id:       str
    full_text:      str          # concatenated pages, cleaned
    page_count:     int
    word_count:     int
    char_count:     int
    has_equations:  bool         # heuristic: unicode math chars > threshold
    has_figures:    bool         # heuristic: page contains image blocks
    extractor_name: str          # 'pymupdf_1.27'
    extraction_ms:  int
```

### Cleaning Steps (applied before section parsing)

```
1. Remove page headers/footers  (lines matching "^\d+$" or conference name)
2. Collapse ligature artefacts   (ﬁ → fi, ﬀ → ff, ﬂ → fl)
3. Strip reference list          (everything after "References\n")
4. Remove figure/table captions  (lines starting "Figure \d" / "Table \d")
5. Normalise whitespace          (3+ newlines → 2)
6. Detect encoding issues        (replacement char ratio > 5% → log warning)
```

### DB Column Added

```sql
ALTER TABLE papers ADD COLUMN pdf_local_path   TEXT;
ALTER TABLE papers ADD COLUMN pdf_extracted_at TIMESTAMPTZ;
ALTER TABLE papers ADD COLUMN pdf_word_count   INT;
```

---

## 5. Stage 3 — Segment

### Section Detection Strategy

Two-pass approach: regex primary, position-based fallback.

**Pass 1 — Explicit header regex**

```python
CANONICAL_SECTIONS = {
    'abstract':     r'abstract',
    'introduction': r'(?:\d+\.?\s+)?introduction',
    'related_work': r'(?:\d+\.?\s+)?related\s+work',
    'methodology':  r'(?:\d+\.?\s+)?(?:method(?:ology|s)?|approach|model|framework)',
    'experiments':  r'(?:\d+\.?\s+)?(?:experiments?|experimental\s+setup|evaluation)',
    'results':      r'(?:\d+\.?\s+)?results?',
    'discussion':   r'(?:\d+\.?\s+)?discussion',
    'conclusion':   r'(?:\d+\.?\s+)?conclusions?',
    'limitations':  r'(?:\d+\.?\s+)?limitations?',
    'future_work':  r'(?:\d+\.?\s+)?future\s+work',
}
```

Lines are candidates if they are ≤ 60 chars, standalone (blank lines before/after),
and match a canonical pattern. This correctly handles both "3 Methodology" and
"Methodology" styles.

**Pass 2 — Fallback for missed sections**

If `methodology` is not found, look for the longest text block between
`introduction` and `experiments` and label it `methodology`.
If `conclusion` is not found, take the last 800 words of body text.

**Known hard cases (handled explicitly):**

| Issue | Mitigation |
|-------|------------|
| Two-column layout mixes lines | PyMuPDF sort_order flag; join short lines |
| Appendix re-uses section names | Strip text after "References" first |
| NeurIPS uses unnumbered sections | Regex handles both numbered and bare headers |
| Some papers have "Experimental Results" | Merged into `experiments` canonical key |

### Output Schema

```python
@dataclass
class PaperSections:
    paper_id:       str
    abstract:       str | None
    introduction:   str | None
    related_work:   str | None
    methodology:    str | None    # ← highest LLM value
    experiments:    str | None    # ← highest LLM value
    results:        str | None    # ← highest LLM value
    discussion:     str | None
    conclusion:     str | None    # ← highest LLM value
    limitations:    str | None    # ← highest LLM value
    future_work:    str | None    # ← highest LLM value
    full_text:      str           # stored but not sent to LLM
    sections_found: list[str]     # which keys were detected
    segmenter_version: str
```

### New DB Table: `paper_sections`

```sql
CREATE TABLE paper_sections (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    paper_id          UUID NOT NULL UNIQUE REFERENCES papers(id) ON DELETE CASCADE,

    -- Named sections (nullable — not all papers have all sections)
    abstract          TEXT,
    introduction      TEXT,
    related_work      TEXT,
    methodology       TEXT,
    experiments       TEXT,
    results           TEXT,
    discussion        TEXT,
    conclusion        TEXT,
    limitations       TEXT,
    future_work       TEXT,

    -- Full clean text (for future search / embeddings)
    full_text         TEXT,

    -- Quality metadata
    sections_found    TEXT,       -- JSON array: ["abstract","methodology","conclusion"]
    word_count        INT,
    segmenter_version TEXT,
    segmented_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

---

## 6. Stage 4 — Analyse (LLM)

### Input Construction

Rather than sending the full paper (avg 18,000 tokens), send only the
**high-signal section subset**:

```python
HIGH_SIGNAL_SECTIONS = [
    'abstract',       # ~200 words   — always present
    'methodology',    # ~1,200 words — core contribution
    'experiments',    # ~800 words   — validation
    'results',        # ~1,500 words — findings
    'conclusion',     # ~400 words   — summary + future work
    'limitations',    # ~300 words   — often the most honest part
]
```

Average token budget: **4,000 tokens input** (vs 18,000 for full text).

If a section is missing, it is simply omitted. If total tokens exceed 6,000,
`methodology` is truncated to its first 2,000 words.

### Extended Output Schema (PDF → richer than abstract-only)

```python
class DatasetRef(BaseModel):
    name:        str
    description: str = ""
    task:        str = ""          # "image classification", "QA", …

class PaperAnalysis(BaseModel):
    summary:       str                    = Field(min_length=20, max_length=800)
    categories:    list[CategoryItem]     = Field(min_length=1, max_length=6)
    techniques:    list[TechniqueItem]    = Field(max_length=12)
    methodologies: list[str]              = Field(max_length=6)
    datasets:      list[DatasetRef]       = Field(max_length=8)   # NEW — from experiments
    advantages:    list[str]              = Field(min_length=1, max_length=6)
    limitations:   list[str]              = Field(max_length=6)
    future_work:   list[str]              = Field(max_length=5)
    use_cases:     list[str]              = Field(max_length=5)   # NEW — practical applications
```

The `datasets` and `use_cases` fields are only possible with full-paper context.

### New DB Table: `paper_datasets`

```sql
CREATE TABLE paper_datasets (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    paper_id    UUID NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
    name        TEXT NOT NULL,
    description TEXT,
    task        TEXT,
    source      TEXT DEFAULT 'auto'
);
```

---

## 7. Complete Data Flow

```
papers.pdf_url
      │
      ▼ Stage 1: Download
papers.pdf_local_path  ──►  pdfs/NeurIPS/2024/{id}.pdf

      │
      ▼ Stage 2: Extract
paper_sections.full_text  +  papers.pdf_word_count

      │
      ▼ Stage 3: Segment
paper_sections.{abstract, methodology, experiments, results, …}

      │
      ▼ Stage 4: Analyse
paper_analyses.{summary, advantages, limitations, future_work}
paper_categories   (join)  ──►  categories
paper_techniques   (join)  ──►  techniques
paper_methodologies(join)  ──►  methodologies
paper_datasets             ──►  datasets
```

---

## 8. Processing Requirements — 5,000 Papers

### Storage

| Asset | Size per paper | 5,000 papers |
|-------|---------------|--------------|
| PDF files | 1.5 MB avg | **7.5 GB** |
| Extracted full text (DB) | 60 KB | **300 MB** |
| Section text (DB) | 20 KB | **100 MB** |
| Analysis JSON (DB) | 3 KB | **15 MB** |
| **Total** | | **~8 GB** |

Recommendation: store PDFs on filesystem (or S3), text/analysis in PostgreSQL.

### Time

| Stage | Per paper | Workers | 5,000 papers |
|-------|-----------|---------|-------------|
| Download | 2.5s | 8 async | **26 min** |
| Extract | 200ms | 4 threads | **4 min** |
| Segment | 50ms | 4 threads | **1 min** |
| Analyse (LLM) | 3s* | 5 async | **50 min** |
| **Total** | | | **~80 min** |

*At paid-tier Gemini rate limits (2,000 RPM). Free tier (15 RPM): ~10 hours.

### Cost

| Component | Rate | 5,000 papers |
|-----------|------|-------------|
| Gemini 2.0 Flash Lite input | $0.075/1M tokens × 4,000 tokens | $1.50 |
| Gemini 2.0 Flash Lite output | $0.30/1M tokens × 400 tokens | $0.60 |
| Egress (downloads, cloud) | ~free on-premises | — |
| **Total LLM cost** | | **~$2.10** |

Abstract-only was ~$0.60. PDF adds $1.50 for 3× richer analysis.
**Cost per paper: $0.00042** — essentially free at this scale.

### Bottleneck Analysis

```
Download    ████████████████████████████  26 min  ← primary bottleneck
LLM         ████████████████████████████  50 min  ← if free tier
Extract     ████                           4 min
Segment     █                              1 min
```

On **paid Gemini tier**: LLM drops to 50 min but download stays at 26 min.
True throughput limit is the download stage — constrained by source server
rate limits, not our infrastructure.

**Mitigation:** stagger downloads from different sources (OpenReview, arXiv,
CVF), use separate async queues per domain, respect per-domain rate limits.

---

## 9. Failure Modes and Recovery

| Failure | Rate (expected) | Recovery |
|---------|----------------|----------|
| PDF download 404 | ~2% | Try arXiv fallback → log as unresolvable |
| PDF download timeout | ~3% | Retry ×4 with back-off |
| PDF is scanned (no text layer) | ~1% | Log; skip LLM stage (OCR is out of scope) |
| Section detection finds < 3 sections | ~5% | Fall back to abstract-only for LLM input |
| LLM JSON validation failure | ~2% | Retry with stricter prompt (max 2×) |
| LLM rate limit | variable | Exponential back-off; resume from last checkpoint |

All failures write a `pipeline_errors` log table row rather than crashing.

### New Table: `pipeline_errors`

```sql
CREATE TABLE pipeline_errors (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    paper_id    UUID REFERENCES papers(id),
    stage       TEXT NOT NULL,   -- 'download', 'extract', 'segment', 'analyse'
    error_type  TEXT NOT NULL,   -- 'http_404', 'timeout', 'json_invalid', …
    error_msg   TEXT,
    retryable   BOOLEAN DEFAULT TRUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

---

## 10. File Structure

```
pdf_pipeline/
├── __init__.py
├── downloader.py       ← Stage 1: async HTTP, resume, per-domain rate limits
├── extractor.py        ← Stage 2: PyMuPDF wrapper, cleaning, RawExtraction
├── segmenter.py        ← Stage 3: SectionParser, two-pass detection
├── analyser.py         ← Stage 4: Gemini client, section subset selection
├── store.py            ← DB upserts for all new tables
├── pipeline.py         ← Orchestrator: runs all 4 stages, progress tracking
└── run_pipeline.py     ← CLI entry point

db/
└── migrations/
    └── 003_pdf_pipeline_tables.sql   ← paper_sections, paper_datasets, pipeline_errors
                                         + new columns on papers
```

---

## 11. CLI Interface

```bash
# Run full pipeline: download → extract → segment → analyse
python -m pdf_pipeline.run_pipeline

# Run individual stages (useful for debugging / re-processing)
python -m pdf_pipeline.run_pipeline --stage download
python -m pdf_pipeline.run_pipeline --stage extract
python -m pdf_pipeline.run_pipeline --stage segment
python -m pdf_pipeline.run_pipeline --stage analyse

# Limit scope
python -m pdf_pipeline.run_pipeline --limit 50 --conference NeurIPS --year 2024

# Re-run a specific stage (skip papers already done unless --force)
python -m pdf_pipeline.run_pipeline --stage segment --force

# Dry-run: show what would be processed + storage/cost estimate
python -m pdf_pipeline.run_pipeline --dry-run

# Report: current stage completion for all papers
python -m pdf_pipeline.run_pipeline --report
```

---

## 12. Build Order

| Step | Deliverable | Validates |
|------|-------------|-----------|
| 1 | `003_pdf_pipeline_tables.sql` migration | Schema correct |
| 2 | `pdf_pipeline/downloader.py` | Download 5 real PDFs, check local_path set |
| 3 | `pdf_pipeline/extractor.py` | Extract text, verify word counts |
| 4 | `pdf_pipeline/segmenter.py` | Detect sections on 10 papers, inspect output |
| 5 | `pdf_pipeline/analyser.py` | Analyse 3 papers with Gemini, check JSON |
| 6 | `pdf_pipeline/store.py` + `pipeline.py` | End-to-end on 10 papers |
| 7 | Full run on 100 papers → inspect DB | Pipeline ready |
