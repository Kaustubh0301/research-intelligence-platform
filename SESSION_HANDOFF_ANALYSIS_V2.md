# Session Handoff — Analysis V2 Implementation

**Date:** 2026-06-08  
**Branch:** `notebooklm-pipeline`  
**Last commit:** `3c66424` — feat: graph page, chat UI and demo polish  
**Uncommitted changes:** normalization fixes (rules.py, technique_aliases.json), ingestion fixes (conferences_config.py, fetch_openreview.py), updated audit outputs — **not yet committed**

---

## 1. Current Project Status

### What exists and works

All five frontend pages are live and building clean. The backend API is complete. The corpus has been expanded from 100 → 250 papers this session (100 NeurIPS 2024 analyzed + 150 ICLR 2024 ingested but not yet analyzed). The normalization pipeline has been patched and re-run. The graph has been rebuilt.

**Pending approval:** Analysis V2 — a new synthesis prompt set and schema expansion to produce richer per-paper analyses (currently ~55 words / 2 sentences; target 500–900 words across 7 fields).

---

## 2. Corpus Status

| Metric | Value |
|---|---|
| **Total papers** | **250** |
| NeurIPS 2024 | 100 papers |
| ICLR 2024 | 150 papers |
| Papers with `paper_analyses` | **100** (NeurIPS only — ICLR not yet analyzed) |
| Papers with PDFs / sections | 247 (3 ICLR failed download) |
| Papers with graph metrics | 100 (pre-expansion graph) |
| Papers unassigned to notebooks | **150** (all ICLR — awaiting NLM pipeline) |

### ICLR ingestion state (ready for NLM pipeline)

- 150 ICLR 2024 papers ingested via `ingestion.run_ingestion`
- All 150 have citation counts; 140/150 have Semantic Scholar IDs
- 147/150 have PDFs and segmented sections; 3 failed download (abstract-only fallback)
- 0 notebook_papers rows for ICLR papers — Stage A (assign) not yet run
- NLM auth status: unknown at session end — **verify with `nlm notebook list --json` before any NLM work**

---

## 3. Graph Status

Built on NeurIPS 100-paper corpus only (pre-Phase 1A). Will need rebuild after ICLR analysis is complete.

| Metric | Value |
|---|---|
| Paper edges | 2,929 |
| Avg edge weight | 1.607 |
| Max edge weight | 15.0 |
| Clusters | 3 |
| Distinct canonical techniques | 998 (down from 1,115 after Phase 0 normalization) |
| Isolated papers | 0 |

The graph is stale relative to the new 150 ICLR papers but this is expected — graph rebuild is Step 13 in the expansion plan, after ICLR analyses are complete.

---

## 4. Frontend Status

All five pages are complete and building clean (`next build` — 0 errors, 0 warnings):

| Page | Route | Status |
|---|---|---|
| Dashboard | `/` | ✅ Ready — shows NeurIPS 100 stats; will auto-update after ICLR analyses |
| Paper Search | `/papers` | ✅ Ready — ICLR/ICML filter checkboxes exist but return 0 until analysis complete |
| Paper Detail | `/papers/[id]` | ✅ Ready — shows AnalysisPanel; ICLR papers show "Analysis not available" |
| Knowledge Graph | `/graph` | ✅ Ready — renders NeurIPS 100-paper graph |
| Research Assistant | `/chat` | ⚠️ Requires `ANTHROPIC_API_KEY` in `.env` |

**Do not modify any frontend files during Analysis V2 implementation.** The `AnalysisPanel` component and `PaperAnalysis` TypeScript type will need to be updated in a later pass once the new fields are defined and populated.

---

## 5. Files Modified This Session (Not Yet Committed)

| File | Change | Why |
|---|---|---|
| `normalize/rules.py` | Regex fix (`[A-Z0-9\-]+` → `[A-Za-z0-9\-]+`); Pass 2 paren-strip in `case_fold_canonical()` | Phase 0: fixes LLMs/ViTs/GNNs merge bug + collapses Foo (BAR)/Foo singleton pairs |
| `normalize/technique_aliases.json` | 38 new alias entries (SGD, PPO, LoRA, DPO unification, CoT unification, SFT, plurals) | Phase 0: promotes 6 new Core-tier techniques |
| `ingestion/conferences_config.py` | ICLR 2024 invitation: `Blind_Submission` → `Submission` | Bug fix: old ID returned 0 notes from OpenReview |
| `ingestion/fetch_openreview.py` | `_is_accepted()`: added "withdrawn", "desk rejected", "rejected" exclusion terms | Bug fix: withdrawn submissions were passing the accepted filter |

---

## 6. Analysis Quality Audit Findings

Full audit is in `ANALYSIS_QUALITY_AUDIT.md`. Summary below.

### Current analysis schema (`paper_analyses` table)

```python
summary:     Text   # 2-sentence string, avg 354 chars / ~55 words
advantages:  Text   # JSON array, avg 2.0 items (10–12 word labels)
limitations: Text   # JSON array, avg 1.7 items, 17 papers have 0
future_work: Text   # JSON array, avg 1.3 items, 31 papers have 0
use_cases:   Text   # JSON array, avg 2.1 items (1-sentence descriptions)
```

**Other columns present but unused:** `model`, `input_tokens`, `output_tokens`, `cost_usd`, `processing_ms`, `created_at`, `updated_at`

### Root causes

**Root Cause 1 — Prompt hard-caps summary at 2 sentences (primary)**  
`notebooklm/pipeline.py` PROMPTS["summary"] line 43: `SUMMARY: [2 sentences]`  
NotebookLM obeys perfectly. Output is accurate but thin. Nothing is lost in parsing or storage — the upstream instruction is simply too restrictive.

**Root Cause 2 — Four fields entirely absent from schema and prompts**  
The pipeline never asks for, and the DB never stores: methodology explanation (HOW it works), experimental findings (benchmark numbers), practical applications (richer than 1-sentence use_cases), or analyst-generated future research directions. These are structural absences.

**Root Cause 3 — Advantage/limitation format generates labels, not explanations**  
`ADVANTAGE: [key strength] | [key strength]` produces 10–12 word noun phrases. No mechanism, no "why".

**Root Cause 4 — Silent notebook overload truncation**  
`llm-architectures` notebook had 45 papers. NLM returned 106 words of internal planning text (`**Expanding the Sources** — I've decided to refine the paper list...`) covering only 9 papers. The extractor found 0 matches and wrote nothing. The 36 affected papers were covered by secondary notebook assignments, so no analysis was lost in this corpus. But the failure is silent — no validation step detects it. **Do not load more than 20 papers per notebook.**

### Representative analysis examples (stored vs. needed)

**Gorilla (1,248 citations) — current 358-char summary:**
> "This paper introduces Gorilla, a fine-tuned LLaMA-based model designed to accurately write API calls by leveraging a novel Retriever Aware Training method. Evaluated on the newly introduced APIBench dataset, Gorilla surpasses state-of-the-art models like GPT-4 in generating functionally correct API calls while significantly mitigating hallucination errors."

Missing: how RAT differs from standard RAG, APIBench composition, % hallucination reduction, model size, training data construction.

**Refusal Direction (716 citations) — current 385-char summary:**
> "This paper demonstrates that the refusal behavior of conversational large language models is mediated by a single one-dimensional subspace in their residual stream activations..."

Missing: which models were tested, extraction method (mean-difference of activations), jailbreak success rate, why a single direction suffices.

---

## 7. Proposed Analysis V2 Architecture

### New `paper_analyses` schema (7 fields)

| Column | Type | Content | Target |
|---|---|---|---|
| `summary` | Text | 3–5 paragraph overview: problem, approach, results, contribution | 300–500 words |
| `methodology` | Text | How the core method works: architecture, algorithm, key design decisions | 150–250 words |
| `experimental_findings` | Text (JSON array) | Concrete benchmark results: `name :: metric :: this score vs baseline score` | 3–6 items |
| `strengths` | Text (JSON array) | Mechanism-explaining strength descriptions (replaces `advantages`) | 2–4 items, 30–60 words each |
| `limitations` | Text (JSON array) | Constraint + reason explanations (replaces current thin `limitations`) | 2–4 items, 30–60 words each |
| `practical_applications` | Text (JSON array) | Deployment scenarios with specific context and "newly possible vs. alternative" (replaces `use_cases`) | 2–3 items, 40–80 words each |
| `future_research_directions` | Text (JSON array) | Analyst-synthesized open questions (distinct from paper's stated future work; replaces `future_work`) | 2–4 items |

**Keep existing columns** (`advantages`, `future_work`, `use_cases`) for backward compatibility until all 100 NeurIPS papers are re-synthesized, then deprecate.

### New synthesis prompts (7 total, up from 5)

The 5 existing prompts become 7. Two entirely new prompts (`methodology`, `experimental_findings`). Three existing prompts are rewritten (`summary`, `summary`→`strengths`, `use_cases`→`practical_applications`).

**Prompt key changes:**

| Old key | New key | Change |
|---|---|---|
| `summary` | `summary` | Rewrite: remove "2 sentences" constraint; target 300–500 words, 3–5 paragraphs |
| `techniques` | `techniques` | No change |
| `datasets` | `datasets` | No change |
| `categories` | `categories` | No change |
| `use_cases` | `use_cases` | Rename label to `APPLICATION:`, require 40–80 words with deployment context |
| *(new)* | `methodology` | New: `METHODOLOGY:` multi-paragraph field, 150–250 words, mechanism-focused |
| *(new)* | `experimental_findings` | New: `FINDING: benchmark :: metric :: score vs baseline` structured triples |

The `summary` prompt's `ADVANTAGE:` and `LIMITATION:` labels are also rewritten to require mechanism explanation rather than labels. Rename to `STRENGTH:` and keep `LIMITATION:`.

**New `summary` prompt (exact text for `PROMPTS["summary"]`):**
```python
"summary": (
    "For each paper in this notebook, write a detailed structured analysis.\n"
    "Use the EXACT paper title as it appears in the source.\n"
    "Format strictly as shown — no markdown, no bullets:\n\n"
    "PAPER: [exact title]\n"
    "SUMMARY: [3-5 paragraphs: (1) what problem the paper addresses and why it matters, "
    "(2) the core proposed approach at a conceptual level, (3) key results and how they "
    "compare to prior work, (4) main contribution in one sentence. "
    "Target 300-500 words. Include specific technique names, dataset names, "
    "and quantitative claims from the paper.]\n"
    "STRENGTH: [1-2 sentences explaining WHY this aspect works mechanistically, "
    "not just that it works] | [second strength]\n"
    "LIMITATION: [1-2 sentences: what the constraint is AND why it exists] | [second limitation]\n"
    "FUTURE_WORK: [one direction] | [one direction]\n"
    "===\n\n"
    "Rules:\n"
    "- SUMMARY must be 3-5 paragraphs of prose, not bullets.\n"
    "- STRENGTH must explain mechanism, not just name property.\n"
    "- If a field has no content, write NONE.\n"
    "- Do not add any text before the first PAPER: line.\n"
    "- Repeat the block for EVERY paper in the notebook."
),
```

**New `methodology` prompt (exact text for `PROMPTS["methodology"]`):**
```python
"methodology": (
    "For each paper in this notebook, explain the core methodology.\n"
    "Use the EXACT paper title as it appears in the source.\n"
    "Format strictly as shown — no markdown, no bullets:\n\n"
    "PAPER: [exact title]\n"
    "METHODOLOGY: [2-3 paragraphs: (1) the technical approach — architecture, algorithm, "
    "or framework design, (2) key implementation decisions that distinguish it from prior "
    "work, (3) training or evaluation procedure if relevant. "
    "Target 150-250 words. Use precise technical terms.]\n"
    "===\n\n"
    "Rules:\n"
    "- Do not restate the motivation — focus on mechanism.\n"
    "- Name specific components, loss functions, and design choices.\n"
    "- If methodology is unclear from sources, write METHODOLOGY: NONE.\n"
    "- Repeat the block for EVERY paper in the notebook."
),
```

**New `experimental_findings` prompt (exact text for `PROMPTS["experimental_findings"]`):**
```python
"experimental_findings": (
    "For each paper in this notebook, extract the key experimental results.\n"
    "Use the EXACT paper title as it appears in the source.\n"
    "Format strictly as shown — one FINDING line per result:\n\n"
    "PAPER: [exact title]\n"
    "FINDING: [benchmark or dataset name] :: [metric name] :: "
    "[this paper's score] vs [baseline or prior work score]\n"
    "===\n\n"
    "Rules:\n"
    "- Use the canonical benchmark name (e.g. ImageNet, GSM8K, MMLU).\n"
    "- Include numeric values when available in the source.\n"
    "- List the 3-6 strongest results.\n"
    "- If no quantitative experiments exist, write: "
    "FINDING: No quantitative benchmark evaluation\n"
    "- Repeat the block for EVERY paper in the notebook."
),
```

**Updated `use_cases` prompt (rename label to `APPLICATION:`):**
```python
"use_cases": (
    "For each paper in this notebook, describe practical deployment scenarios.\n"
    "Use the EXACT paper title as it appears in the source.\n"
    "Format strictly as shown:\n\n"
    "PAPER: [exact title]\n"
    "APPLICATION: [2-3 sentences: the deployment context, what the paper's contribution "
    "enables specifically, and what the practical benefit is vs. the current alternative]\n"
    "===\n\n"
    "Rules:\n"
    "- Each APPLICATION must name a specific industry or use context.\n"
    "- Explain what is newly possible with this method vs. prior approaches.\n"
    "- Write 2-3 APPLICATION lines per paper.\n"
    "- Do not repeat the method name — describe the downstream use.\n"
    "- Repeat the block for EVERY paper in the notebook."
),
```

---

## 8. Files to Modify for Analysis V2

Listed in implementation order. Do not implement until handoff is reviewed.

### File 1: `db/models.py`
Add 5 new columns to `PaperAnalysisRecord` (after line 228):
```python
methodology:               Mapped[str|None] = mapped_column(Text)
experimental_findings:     Mapped[str|None] = mapped_column(Text)   # JSON array of "name :: metric :: score" strings
strengths:                 Mapped[str|None] = mapped_column(Text)   # JSON array (replaces advantages)
practical_applications:    Mapped[str|None] = mapped_column(Text)   # JSON array (replaces use_cases)
future_research_directions: Mapped[str|None] = mapped_column(Text)  # JSON array (replaces future_work)
```

### File 2: `db/migrate.py`
Add 5 `_add_column_if_missing` calls in `run_migrations()`:
```python
_add_column_if_missing("paper_analyses", "methodology",               "TEXT")
_add_column_if_missing("paper_analyses", "experimental_findings",     "TEXT")
_add_column_if_missing("paper_analyses", "strengths",                 "TEXT")
_add_column_if_missing("paper_analyses", "practical_applications",    "TEXT")
_add_column_if_missing("paper_analyses", "future_research_directions", "TEXT")
```

### File 3: `notebooklm/pipeline.py`
- Replace `PROMPTS["summary"]` with the new 300–500 word version (STRENGTH: instead of ADVANTAGE:)
- Replace `PROMPTS["use_cases"]` with APPLICATION: label version
- Add `PROMPTS["methodology"]` (new)
- Add `PROMPTS["experimental_findings"]` (new)
- PROMPTS dict goes from 5 keys to 7 keys

### File 4: `notebooklm/extractor.py`
Add constants and parsers:
```python
LABEL_METHODOLOGY  = "METHODOLOGY:"
LABEL_FINDING      = "FINDING:"
LABEL_APPLICATION  = "APPLICATION:"
LABEL_STRENGTH     = "STRENGTH:"
```
Add `ParsedMethodology`, `ParsedFindings`, `ParsedStrengths`, `ParsedApplications` dataclasses.  
Add `parse_methodology()`, `parse_experimental_findings()`, `parse_strengths()`, `parse_applications()` functions — same block-split/field-parse pattern as existing parsers.  
Update `ExtractionResult` dataclass with new list fields.  
Update `extract_all()` to call new parsers.

Note: `STRENGTH:` uses pipe-separated multi-value format (same as existing `ADVANTAGE:`).  
`METHODOLOGY:` is multi-line prose — parse as a single text blob (same as `SUMMARY:`).  
`FINDING:` uses `name :: metric :: score` triple — parse like `DATASET:` (split on ` :: `).  
`APPLICATION:` uses repeated lines — parse like existing `USE_CASE:`.

### File 5: `notebooklm/normalizer.py`
Update `_upsert_analysis()` to write the 5 new columns from new parsed types.  
Add handling for `ParsedMethodology`, `ParsedFindings` in the `normalize()` function's per-paper loop.

### File 6: `api/models.py`
Extend `AnalysisOut` (currently lines 56–62):
```python
class AnalysisOut(BaseModel):
    summary:                    Optional[str]  = None
    methodology:                Optional[str]  = None       # NEW
    experimental_findings:      list[str]      = Field(default_factory=list)  # NEW
    strengths:                  list[str]      = Field(default_factory=list)   # NEW (replaces advantages)
    advantages:                 list[str]      = Field(default_factory=list)   # KEEP for backward compat
    limitations:                list[str]      = Field(default_factory=list)
    future_work:                list[str]      = Field(default_factory=list)   # KEEP for backward compat
    future_research_directions: list[str]      = Field(default_factory=list)  # NEW
    practical_applications:     list[str]      = Field(default_factory=list)  # NEW (replaces use_cases)
    use_cases:                  list[str]      = Field(default_factory=list)   # KEEP for backward compat
    model:                      Optional[str]  = None
```

### File 7: `api/helpers.py`
Update `_upsert_analysis` call in `paper_detail()` (around line 195–206) to also read and return new columns:
```python
analysis = AnalysisOut(
    summary                    = analysis_row.summary,
    methodology                = analysis_row.methodology,
    experimental_findings      = json_list(analysis_row.experimental_findings),
    strengths                  = json_list(analysis_row.strengths),
    advantages                 = json_list(analysis_row.advantages),      # keep
    limitations                = json_list(analysis_row.limitations),
    future_research_directions = json_list(analysis_row.future_research_directions),
    future_work                = json_list(analysis_row.future_work),     # keep
    practical_applications     = json_list(analysis_row.practical_applications),
    use_cases                  = json_list(analysis_row.use_cases),       # keep
    model                      = analysis_row.model,
)
```

### File 8 (frontend — do in a separate pass): `apps/web/src/lib/types.ts`
Add new fields to `PaperAnalysis` interface. Frontend changes should come AFTER the backend pipeline is verified working on a sample notebook.

### File 9 (frontend — separate pass): `apps/web/src/components/papers/AnalysisPanel.tsx`
Add rendering for `methodology`, `experimental_findings`, `strengths`, `practical_applications`, `future_research_directions`.

---

## 9. Migration Considerations

### Backward compatibility
- Keep `advantages`, `future_work`, `use_cases` columns in DB and API output throughout the migration. Old NeurIPS analyses continue to work.
- New columns default to NULL. `AnalysisPanel` already handles null gracefully — it only renders sections where data exists.
- The migration is additive: `db/migrate.py` ADD COLUMN statements are no-ops if columns exist.

### Re-synthesis order
1. Run `--stage synthesize --force` on all 23 existing notebooks → overwrites synthesis rows with 7-prompt output
2. Run `--stage extract` → populates new columns for all 100 NeurIPS papers
3. Verify quality on 5 representative papers before running ICLR pipeline

### Notebook size cap
**Do not assign more than 20 papers per notebook.** The `llm-architectures` notebook with 45 papers caused silent truncation. Update `notebooklm/assigner.py`'s `_MAX_SOURCES` constant (currently 45) to 20 before running the ICLR NLM pipeline.

### Coverage validation (new requirement)
After Stage D synthesizes a notebook, count `PAPER:` blocks in each response and compare against the notebook's paper count. Warn if coverage < 80%. This logic belongs in `run_synthesize()` in `pipeline.py`.

---

## 10. NotebookLM Limitations Discovered

| Limitation | Evidence | Mitigation |
|---|---|---|
| Silent truncation at high source count | 45-paper notebook → 106-word response covering 9 papers | Cap notebooks at 20 papers max |
| Leaks internal reasoning on truncation | "I've decided to refine the paper list…" in synthesis content | Add coverage validation; PAPER: block count check after each synthesis |
| No API — browser automation only | Uses `notebooklm-mcp-cli` (cookie auth) | Keep batches ≤ 50 papers; auth sessions last 2–4 weeks |
| ~30s per query call | Measured across 115 synthesis rows | Plan synthesis sessions: 7 prompts × 30 notebooks = ~210 queries × 30s = ~105 min |
| No error on query failure | Returns malformed text instead of HTTP error | Detect via: no PAPER: blocks in response, word_count anomaly |

---

## 11. NLM Call Budget for Analysis V2

### Re-synthesize 100 existing NeurIPS papers (new 7-prompt schema)

| Call type | Count | Notes |
|---|---|---|
| Synthesis queries | ~161 | 23 notebooks × 7 prompts (overwrite with `--force`) |
| No new uploads needed | 0 | All 166 sources already uploaded |
| **Total** | **~161 calls** | ~80 min runtime |

### After re-synthesis: run ICLR pipeline (Phase 1A)

| Call type | Count | Notes |
|---|---|---|
| Uploads (Stage C) | ~255 | 150 papers × 1.7 avg assignments |
| New notebook creates | ~0–2 | Stage B |
| Synthesis (Stage D, 7 prompts, Model B) | ~210 | ~30 notebooks × 7 prompts |
| **Total Phase 1A** | **~465** | ~2.5 hr runtime |

### Cumulative at 250 papers analyzed

~588 (pre-session) + ~161 (re-synthesis) + ~465 (Phase 1A) = **~1,214 cumulative NLM calls**

---

## 12. Exact Next Steps (Implementation Order)

Run these in sequence. Do not skip validation steps.

### Step 1 — Commit current work first
```bash
git add normalize/rules.py normalize/technique_aliases.json \
        ingestion/conferences_config.py ingestion/fetch_openreview.py \
        outputs/
git commit -m "feat: Phase 0 normalization fixes + ICLR 2024 ingestion pipeline fixes"
```

### Step 2 — Schema migration (db/models.py + db/migrate.py)
Add 5 new columns to `PaperAnalysisRecord`. Add migration calls. Verify:
```bash
.venv/bin/python3 -c "
from db.migrate import run_migrations
run_migrations()
import sqlite3; c=sqlite3.connect('research_platform.db').cursor()
c.execute('PRAGMA table_info(paper_analyses)')
cols = [row[1] for row in c.fetchall()]
print('Columns:', cols)
"
# Expected: includes methodology, experimental_findings, strengths, practical_applications, future_research_directions
```

### Step 3 — Update synthesis prompts (notebooklm/pipeline.py)
Replace `PROMPTS["summary"]` and `PROMPTS["use_cases"]`. Add `PROMPTS["methodology"]` and `PROMPTS["experimental_findings"]`. PROMPTS dict should have 7 keys after.

### Step 4 — Add new parsers (notebooklm/extractor.py)
Add 4 new label constants, 4 new dataclasses, 4 new parse functions, update `ExtractionResult`, update `extract_all()`.

### Step 5 — Update normalizer (notebooklm/normalizer.py)
Update `_upsert_analysis()` to write all 5 new columns. Update `normalize()` to pass new parsed objects.

### Step 6 — Update API (api/models.py + api/helpers.py)
Extend `AnalysisOut` with 5 new fields. Update `paper_detail()` in `helpers.py` to read and return them. Keep legacy fields populated.

### Step 7 — Smoke test on single notebook (no NLM call)
Write a unit test or manual test that runs `extractor.extract_all()` on a mock 7-prompt response to verify all new parsers work correctly before any NLM synthesis.

### Step 8 — Re-synthesize 1 existing notebook with new prompts
Pick `ai-safety` (5 papers, small, clean synthesis history):
```bash
source .venv/bin/activate && export DATABASE_URL=sqlite:///research_platform.db
nlm notebook list --json | python3 -c "import sys,json; print(len(json.load(sys.stdin)), 'notebooks')"
# Must show 23 notebooks before proceeding

python -m notebooklm.run_pipeline --stage synthesize --force --notebook-id <ai-safety-uuid>
python -m notebooklm.run_pipeline --stage extract
```
Verify the 5 ai-safety papers now have populated `methodology` and `experimental_findings` columns.

### Step 9 — Review quality on sample before full re-synthesis
```python
import sqlite3, json
c = sqlite3.connect('research_platform.db').cursor()
c.execute("""SELECT p.title, pa.summary, pa.methodology, pa.experimental_findings
             FROM papers p JOIN paper_analyses pa ON pa.paper_id = p.id
             WHERE pa.methodology IS NOT NULL LIMIT 3""")
for row in c.fetchall():
    print(row[0], '\n  summary:', len(row[1] or ''), 'chars')
    print('  methodology:', len(row[2] or ''), 'chars')
    print('  findings:', row[3])
```
**Target:** summary > 800 chars, methodology > 300 chars, findings has 3+ items. If quality is acceptable, proceed to Step 10.

### Step 10 — Re-synthesize all 23 existing notebooks
```bash
python -m notebooklm.run_pipeline --stage synthesize --force
python -m notebooklm.run_pipeline --stage extract
```
Expected: ~161 NLM calls, ~80 min.

### Step 11 — Run ICLR pipeline (Phase 1A)
```bash
# Update assigner max sources cap to 20 first (see Step 11a)
python -m notebooklm.run_pipeline --limit 50   # x3 batches
python -m notebooklm.run_pipeline --stage synthesize --force
python -m notebooklm.run_pipeline --stage extract
```

**Step 11a — Before ICLR pipeline: cap notebook size**  
In `notebooklm/assigner.py`, find `_MAX_SOURCES` (or equivalent constant controlling max papers per notebook) and set it to 20. This prevents the `llm-architectures` overload from recurring.

### Step 12 — Normalization + graph rebuild
```bash
python normalize_entities.py --force
python build_graph_v2.py
python entity_signal_audit.py
```

### Step 13 — Frontend update (separate pass)
Update `apps/web/src/lib/types.ts` (`PaperAnalysis` interface) and `apps/web/src/components/papers/AnalysisPanel.tsx` to render new fields. Run `next build` to verify.

---

## 13. Key File Locations

| File | Purpose |
|---|---|
| `notebooklm/pipeline.py` | Synthesis prompts (PROMPTS dict) + 5-stage orchestrator |
| `notebooklm/extractor.py` | Parse NLM synthesis text → Python objects |
| `notebooklm/normalizer.py` | Write parsed objects → DB tables |
| `notebooklm/assigner.py` | Assign papers to notebooks; contains max-sources cap |
| `notebooklm/source_prep.py` | Build source documents uploaded to NLM |
| `db/models.py` | SQLAlchemy models; `PaperAnalysisRecord` at line 218 |
| `db/migrate.py` | ADD COLUMN migration helper |
| `api/models.py` | `AnalysisOut` Pydantic model at line 56 |
| `api/helpers.py` | `paper_detail()` reads and returns analysis |
| `apps/web/src/lib/types.ts` | `PaperAnalysis` TypeScript interface |
| `apps/web/src/components/papers/AnalysisPanel.tsx` | Frontend rendering |
| `ANALYSIS_QUALITY_AUDIT.md` | Full audit with examples and cost model |
| `CORPUS_EXPANSION_EXECUTION.md` | Full Phase 1 execution plan (Steps 1–14) |

---

## 14. Do Not Touch

- `ingestion/` — pipeline is fixed and working for ICLR/ICML; no further changes needed
- `pdf_pipeline/` — working correctly; no changes needed
- `build_graph_v2.py`, `normalize_entities.py` — run as-is after analysis is complete
- `api/routers/` — API contracts must not change; only `api/models.py` and `api/helpers.py`
- `apps/web/` — frontend changes are Step 13 only, after backend pipeline is fully verified

---

## 15. Corpus Expansion Sequence After Analysis V2

Once Analysis V2 is implemented and verified on NeurIPS 100 papers:

1. **Phase 1A NLM pipeline** — 150 ICLR papers (Steps 11–12 above)
2. **Audit** — run `entity_signal_audit.py`, `entity_audit.py`, `concept_selection_audit.py`
3. **Phase 1B decision gate** — if singleton rate < 80% and Shared+Core ≥ 100: proceed to ICML. Otherwise evaluate ACL 2024 first.
4. **Phase 1B NLM pipeline** — 150 ICML papers (same sequence as Phase 1A)
5. **Final graph rebuild** — `build_graph_v2.py` on full 400-paper corpus
6. **Frontend conference filter fix** — ICLR/ICML checkboxes will now return results automatically
