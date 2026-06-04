# Next Session Plan — Research Intelligence Platform

**Full context:** `docs/project_state_handoff_v3.md`  
**Date written:** June 4, 2026

---

## 1. Current Status

The NotebookLM extraction machinery is **fully built and tested**. Every component from "paper in DB" to "structured data in analysis tables" works. The missing piece is the **orchestrator** that runs them in sequence as a single pipeline. Without it, each stage must be called manually.

---

## 2. What Is Completed

| Component | Location | Verified |
|-----------|----------|---------|
| DB schema (16 tables) | `db/models.py`, migrations 003–005 | ✓ Live in SQLite |
| Ingestion (NeurIPS 2024, 100 papers) | `ingestion/` | ✓ 97/100 citation-enriched |
| PDF pipeline stages 1–3 | `pdf_pipeline/` | ✓ 10 papers, all regex-v3 |
| `--stage segment` CLI flag | `pdf_pipeline/run_pipeline.py` | ✓ |
| Search layer | `search/query.py` | ✓ |
| Metrics dashboard | `metrics/dashboard.py` | ✓ |
| `notebooklm/client.py` | nlm CLI wrapper | ✓ Live-tested |
| `notebooklm/assigner.py` | Keyword topic scorer | ✓ 20 assignments written |
| `notebooklm/source_prep.py` | Text doc builder | ✓ |
| `notebooklm/extractor.py` | Response parser | ✓ 5/5 titles matched |
| `notebooklm/normalizer.py` | DB writer | ✓ 0 errors, all tables written |
| 5 validated query prompts | `notebooklm/validate_prompts.py` §PROMPTS | ✓ 100% format compliance |

---

## 3. Partially Completed

- **Corpus**: only NeurIPS 2024 (100 papers). Config for all 10 conferences × 19 editions exists in `ingestion/conferences_config.py` but ingestion hasn't run.
- **PDFs**: 10 of 100 NeurIPS papers downloaded and segmented. Remaining 90 not processed.
- **Analysis data**: 5 of 10 segmented papers have `paper_analyses` / `paper_techniques` / etc. rows — from the offline extraction test, using a fake notebook UUID. These rows need to be overwritten by the real pipeline run.
- **`notebook_papers`**: 20 rows exist, all `source_status='pending'`. No notebook has been uploaded to NotebookLM permanently.

---

## 4. What Remains

**Required for first real analysis pass:**
1. `notebooklm/pipeline.py` — 5-stage orchestrator
2. `notebooklm/run_pipeline.py` — CLI entry point

**Required before production:**
3. `search/query.py` — add category/technique name filters
4. REST API (`api/` with FastAPI — already a transitive dependency)
5. Web frontend (spec in `docs/product_design.md`)
6. PostgreSQL migration (currently SQLite dev only)
7. Corpus expansion: 18 remaining conference editions

---

## 5. Immediate Next Task

**Build `notebooklm/pipeline.py` with 5 stages:**

```
Stage A — Assign:     assign_papers() on unassigned papers → notebook_papers rows
Stage B — Provision:  create_notebook() for notebooks with notebooklm_url=NULL → save URL
Stage C — Upload:     add_source() for source_status='pending' → set 'uploaded' or 'error'
Stage D — Synthesize: query_notebook() × 5 prompts per ready notebook → notebook_syntheses rows
Stage E — Extract:    extractor.extract_all() + normalizer.normalize() per synthesis row
```

Required function signature:
```python
def run(
    limit: int = 10,              # max Stage C uploads per invocation
    notebook_id: str | None = None,  # restrict to one notebook if given
    force: bool = False,
) -> PipelineStats
```

Then build `notebooklm/run_pipeline.py` with `--stage`, `--limit`, `--notebook-id`, `--force` flags.

---

## 6. Expected Implementation Order

```
1. notebooklm/pipeline.py        (core logic, ~250 lines)
2. notebooklm/run_pipeline.py    (CLI wrapper, ~60 lines)
3. python -m notebooklm.run_pipeline --limit 10   (first real run)
4. Verify DB state (see §7)
5. python -m ingestion.run_ingestion --all --limit 500
6. python -m pdf_pipeline.run_pipeline --limit 2000
7. python -m notebooklm.run_pipeline --limit 500
8. Add category/technique filters to search/query.py
9. Build FastAPI REST layer
```

---

## 7. Commands to Verify Success After Pipeline Run

```bash
source .venv/bin/activate && export DATABASE_URL=sqlite:///research_platform.db

# 1. All uploads complete
python -c "
from db.session import get_session
from db.models import NotebookPaper
from sqlalchemy import select, func
with get_session() as s:
    for status in ['pending','uploaded','error']:
        n = s.execute(select(func.count()).select_from(NotebookPaper).where(NotebookPaper.source_status==status)).scalar()
        print(status, n)
"

# 2. Syntheses written
python -c "
from db.session import get_session
from db.models import NotebookSynthesis
from sqlalchemy import select, func
with get_session() as s:
    print('syntheses:', s.execute(select(func.count()).select_from(NotebookSynthesis)).scalar())
"

# 3. Analysis tables populated with real notebook UUIDs (not test UUIDs)
python -c "
from db.session import get_session
from db.models import PaperAnalysisRecord
from sqlalchemy import select
with get_session() as s:
    recs = s.execute(select(PaperAnalysisRecord)).scalars().all()
    for r in recs[:3]:
        print(r.model, '|', (r.summary or '')[:60])
"
```

Expected after a clean 10-paper run:
- `pending=0`, `uploaded=10` (papers with PDFs), `error=0`
- `notebook_syntheses` ≥ 5 rows (one per query per active notebook)
- `paper_analyses.model` contains real UUIDs like `notebooklm/notebook:xxxxxxxx-...`

---

## 8. Potential Risks

| Risk | Mitigation |
|------|-----------|
| nlm auth cookie expired | Run `nlm notebook list` first; if it fails run `nlm login` |
| Rate limit (~50 queries/day free tier) | Stage D is the bottleneck; spread across days if needed |
| NotebookLM UI change breaks client | All calls isolated in `notebooklm/client.py`; `health_check()` before each batch |
| `object-detection` misassignment for Multistep Distillation | Minor; raise `_SECONDARY_THRESHOLD` from 0.04→0.06 in `assigner.py` if needed |
| Stage C stalls mid-batch | `source_status='pending'` per paper enables safe resume; just re-run |
| Test extraction rows (fake UUID) pollute analysis tables | Pipeline's Stage E upserts will overwrite them with real notebook UUIDs |
