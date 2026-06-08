# Corpus Expansion Execution Plan

**Date:** 2026-06-08  
**Branch:** `notebooklm-pipeline`  
**Current state:** 100 papers (NeurIPS 2024), 23 notebooks, 2,916 graph edges  
**Target:** 400 papers (+ ICLR 2024 + ICML 2024)  
**Authoritative source documents:** PHASE1_EXPANSION_RUNBOOK.md, NORMALIZATION_V2_AUDIT.md, PHASE1_EXECUTION_PLAN.md

---

## Constraints

- Do NOT modify frontend files (`apps/web/`)
- Do NOT modify API contracts (`api/`)
- Do NOT modify ingestion, extraction, normalization, or graph schemas
- All changes are additive (new paper rows, new alias entries, regex fix in rules.py, new graph edges)
- Do NOT start any step without completing the pre-flight checklist

---

## Scope of Changes

### What this plan touches

| Area | Changes |
|---|---|
| `normalize/rules.py` | One 1-line regex fix (Step 0A) + three-line Pass 2 paren-strip extension (Step 0C) |
| `normalize/technique_aliases.json` | ~25 new alias entries (Step 0B) |
| `research_platform.db` | New rows in papers, paper_sections, notebook_papers, notebooks, notebook_syntheses, paper_analyses, paper_techniques, paper_relationships |

### What this plan does NOT touch

- `api/` — no changes to any API file
- `apps/web/` — no frontend changes
- `ingestion/` — run as-is, no code changes
- `pdf_pipeline/` — run as-is, no code changes
- `notebooklm/` — run as-is, no code changes
- `build_graph_v2.py`, `normalize_entities.py`, audit scripts — run as-is, no code changes

---

## Discrepancy Resolution: Two Plans in Conflict

PHASE1_EXECUTION_PLAN.md and PHASE1_EXPANSION_RUNBOOK.md agree on ingestion steps but diverge on the NotebookLM pipeline:

| Dimension | PHASE1_EXECUTION_PLAN.md | PHASE1_EXPANSION_RUNBOOK.md | Decision |
|---|---|---|---|
| NLM synthesis model | Model A — synthesize new notebooks only (~35 calls) | Model B — re-synthesize all touched notebooks (~150 calls) | **Use Model B** |
| NLM call estimate | ~342 incremental | ~667 incremental | Runbook is correct |
| NLM pipeline command | `run_pipeline --limit 50` (all stages) | Stages split: upload first, then `--stage synthesize --force`, then `--stage extract` | **Use Runbook stage split** |
| Synthesis checkpoint | Not explicit | Required after stage synthesize | **Include checkpoint** |
| Normalization before ingestion | Not mentioned | Steps 0A–0E required before ingestion | **Include pre-ingestion steps** |

**Rationale for Model B:** New papers uploaded to existing high-capacity notebooks (llm-architectures, optimization-theory) will NOT be analyzed under Model A — Stage D skips notebooks that already have synthesis rows. These are exactly the notebooks where cross-paper signal is highest. Model B re-synthesizes all touched notebooks, producing 100% coverage at the cost of ~115 additional NLM calls (~60 minutes extra runtime).

---

## Current State Verification

Run before doing anything:

```bash
# Activate environment
source .venv/bin/activate
export DATABASE_URL=sqlite:///research_platform.db

# Confirm DB baseline
python3 -c "
import sqlite3; c=sqlite3.connect('research_platform.db').cursor()
c.execute('SELECT COUNT(*) FROM papers'); print('Papers:', c.fetchone()[0])
c.execute('SELECT COUNT(*) FROM paper_analyses'); print('Analyses:', c.fetchone()[0])
c.execute('SELECT COUNT(*) FROM notebooks WHERE notebooklm_id IS NOT NULL'); print('Active notebooks:', c.fetchone()[0])
c.execute('SELECT source_status, COUNT(*) FROM notebook_papers GROUP BY source_status')
print('NP status:', dict(c.fetchall()))
c.execute('SELECT COUNT(DISTINCT canonical_name) FROM paper_techniques')
print('Distinct canonicals:', c.fetchone()[0])
"
# Expected:
#   Papers: 100
#   Analyses: 100
#   Active notebooks: 23
#   NP status: {'uploaded': 166, 'abstract_only': 4}
#   Distinct canonicals: 1,115 (will decrease after Step 0D)
```

---

## Phase 0 — Pre-Ingestion Normalization Fixes

**Runtime:** ~15 minutes. No NLM calls. No irreversible operations.  
**Must complete before any ingestion step.**

### Step 0A — Fix parenthetical acronym regex

**File:** `normalize/rules.py`, line 36  
**Change:** `[A-Z0-9\-]+` → `[A-Za-z0-9\-]+`

This allows the regex to match acronyms with trailing lowercase letters: `(LLMs)`, `(ViTs)`, `(GNNs)`, `(MLPs)`. The current regex rejects these because lowercase `s` is not in `[A-Z0-9\-]`, causing "Large language models (LLMs)" and "Large Language Models" to remain as two separate Core-tier canonicals — the single highest-impact bug.

**Before:**
```python
_PAREN_ACRONYM_RE = re.compile(r"\s*\([A-Z][A-Z0-9\-]+\)\s*$")
```

**After:**
```python
_PAREN_ACRONYM_RE = re.compile(r"\s*\([A-Z][A-Za-z0-9\-]+\)\s*$")
```

**Impact:** Fixes LLM/LLMs Core split (~16 assignments merged), Vision Transformers/ViTs pair, and prevents same failure for all future mixed-case acronym extractions.

---

### Step 0B — Add missing alias entries

**File:** `normalize/technique_aliases.json`

**What is NOT already covered** (verified by inspecting current file):

The file already has:
- `"stochastic gradient descent"` → `"Stochastic gradient descent"` in GROUP 14 (but NOT `"sgd"`)
- `"chain-of-thought"` → `"Chain-of-Thought"` in GROUP 11 (but NOT `"chain-of-thought (cot)"` or `"chain-of-thought prompting"`)
- `"graph convolutional network"` → `"Graph convolutional network"` in GROUP 14 (but NOT `"graph convolutional networks"`)
- `"orthogonal finetuning"` and `"pretraining and finetuning"` in GROUP 14

**What must be ADDED:**

```json
"=== GROUP: Common abbreviations (missing) ===": null,
"sgd":                               "Stochastic gradient descent",
"ppo":                               "Proximal Policy Optimization",
"proximal policy optimization":      "Proximal Policy Optimization",
"recurrent ppo":                     "Proximal Policy Optimization",
"low rank adaptation":               "LoRA",
"low-rank adaptation":               "LoRA",
"low rank adaptation (lora)":        "LoRA",
"resnets":                           "ResNet",
"residual network":                  "ResNet",
"resnet":                            "ResNet",
"monte-carlo tree search":           "Monte Carlo Tree Search",
"autoencoder":                       "Autoencoders",
"convolutional neural networks":     "Convolutional neural network (CNN)",
"graph neural networks":             "Graph Neural Networks",
"graph convolutional networks":      "Graph convolutional network",

"=== GROUP: DPO unification ===": null,
"direct preference optimization":        "Direct Preference Optimization",
"direct preference optimization (dpo)":  "Direct Preference Optimization",

"=== GROUP: Chain-of-Thought unification ===": null,
"chain-of-thought (cot)":            "Chain-of-Thought",
"chain-of-thought prompting":        "Chain-of-Thought prompting",
"chain-of-thought (cot) prompting":  "Chain-of-Thought prompting",
"few-shot cot":                      "Chain-of-Thought",

"=== GROUP: Supervised fine-tuning unification ===": null,
"supervised finetuning":             "Supervised fine-tuning",
"supervised fine-tuning (sft)":      "Supervised fine-tuning",

"=== GROUP: Singular/plural technique names ===": null,
"multilayer perceptron":             "Multilayer perceptrons",
"multi-layer perceptrons":           "Multilayer perceptrons",
"multi-layer perceptron (mlp)":      "Multilayer perceptrons",
"normalizing flow":                  "Normalizing flows",
"recurrent neural network":          "Recurrent neural networks",
"recurrent neural network (rnn)":    "Recurrent neural networks"
```

**Impact:** Promotes ~6 new Core-tier techniques (SGD→6 papers, PPO→5, LoRA→5, ResNet→5, GCN→6, DPO→5). Unifies CoT variants. Net effect: ~15 new Shared+ entries.

---

### Step 0C — Extend Pass 2 paren-strip

**File:** `normalize/rules.py`, `case_fold_canonical()` function, line ~113  

Change the grouping key from `name.lower()` to strip parenthetical acronyms first:

**Before:**
```python
    groups: dict[str, list[tuple[str, int]]] = defaultdict(list)
    for name, count in names_with_counts:
        groups[name.lower()].append((name, count))
```

**After:**
```python
    groups: dict[str, list[tuple[str, int]]] = defaultdict(list)
    for name, count in names_with_counts:
        key = _PAREN_ACRONYM_RE.sub("", name).strip().lower()
        groups[key].append((name, count))
```

**Impact:** Collapses ~50–60 singleton pairs of the form `"Foo (BAR)"` + `"Foo"` without requiring individual alias entries for each. Examples: Multi-Head Attention (MHA)/Multi-Head Attention, DDIM (Denoising Diffusion Implicit Model)/DDIM, Grouped-Query Attention (GQA)/Grouped-Query Attention. Also prevents all future extractions from introducing the same pattern.

**Winner selection:** The existing `max()` sort (highest count, then title-case, then alphabetical) picks the bare-name form over the paren form when counts are equal, which is the correct behavior.

---

### Step 0D — Run `normalize_entities.py --force`

```bash
python normalize_entities.py --force
```

**Why `--force`:** Incremental runs (no `--force`) produced inconsistent canonical assignments for the same concept across papers processed in separate pipeline sessions. Approximately 30 singleton pairs have names that lowercase identically (e.g., "Forward gradients"/"forward gradients") but were assigned different canonicals. `--force` re-processes all 1,115 rows simultaneously, allowing Pass 2 to see all variants at once.

**Checkpoint:**
```bash
python3 -c "
import sqlite3; c=sqlite3.connect('research_platform.db').cursor()
c.execute('SELECT COUNT(*) FROM paper_techniques WHERE canonical_name IS NULL')
print('Missing canonical:', c.fetchone()[0])
c.execute('SELECT COUNT(DISTINCT canonical_name) FROM paper_techniques')
print('Distinct canonicals:', c.fetchone()[0])
"
# Required: 0 missing canonical
# Expected: distinct canonicals < 1,115 (merges collapsed — aim for ~1,020–1,050)
```

---

### Step 0E — Rebuild graph (baseline snapshot)

```bash
python build_graph_v2.py
```

This re-builds `paper_relationships` using the corrected canonical technique assignments. Fixes the known staleness ("0 singletons appear in graph edges" — graph was built before the latest normalization pass).

**Checkpoint:**
```bash
python entity_signal_audit.py
# Expected: singleton rate lower than 95.1%; Core/Shared count higher than 55
# Estimated post-fix: ~87–90% singleton rate, ~85–100 Shared+Core
```

---

## Phase 1 — Ingestion (Session 1, ~1 hour, 0 NLM calls)

### Step 1 — Prerequisites check

```bash
source .venv/bin/activate
export DATABASE_URL=sqlite:///research_platform.db

# Confirm NLM auth (needed for Session 2)
nlm notebook list --json | python3 -c "
import sys, json; d=json.load(sys.stdin)
print(f'Auth OK — {len(d)} notebooks')
"
# Required: "Auth OK — 23 notebooks"
# If expired: nlm login

# Confirm Phase 0 was applied
python3 -c "
import sqlite3; c=sqlite3.connect('research_platform.db').cursor()
c.execute('SELECT COUNT(*) FROM papers'); print('Papers:', c.fetchone()[0])
c.execute('SELECT COUNT(DISTINCT canonical_name) FROM paper_techniques')
print('Distinct canonicals (should be <1115):', c.fetchone()[0])
"
```

**STOP if:** papers ≠ 100, or distinct canonicals = 1,115 (Phase 0 not applied).

---

### Step 2 — ICLR 2024 smoke test

```bash
python -m ingestion.run_ingestion -c ICLR -y 2024 --limit 5
```

**Checkpoint:**
```bash
python3 -c "
import sqlite3; c=sqlite3.connect('research_platform.db').cursor()
c.execute(\"SELECT co.short_name, ce.year, COUNT(*) FROM papers p JOIN conference_editions ce ON p.conference_edition_id=ce.id JOIN conferences co ON ce.conference_id=co.id GROUP BY co.short_name, ce.year ORDER BY co.short_name\")
print(c.fetchall())
"
# Expected: [('ICLR', 2024, 5), ('NeurIPS', 2024, 100)]
```

**STOP if 0 ICLR papers received.** The OpenReview invitation ID for ICLR 2024 is `ICLR.cc/2024/Conference/-/Blind_Submission` — already configured in `ingestion/conferences_config.py`. If the API returns 0 papers, verify OpenReview availability before proceeding.

---

### Step 3 — ICLR 2024 full ingestion

```bash
python -m ingestion.run_ingestion -c ICLR -y 2024 --limit 150
```

**Recovery:** Upsert is idempotent. Re-run the same command if interrupted — smoke test papers update as no-op, remaining papers insert.

**Checkpoint:**
```bash
python3 -c "
import sqlite3; c=sqlite3.connect('research_platform.db').cursor()
c.execute('SELECT COUNT(*) FROM papers'); print('Total:', c.fetchone()[0])
"
# Expected: ~250
```

---

### Step 4 — Citation enrichment (ICLR batch)

```bash
python -m ingestion.enrich_citations
```

Enriches new ICLR papers with `semantic_scholar_id` and `citation_count`. Skips already-enriched rows.

---

### Step 5 — ICML 2024 smoke test

```bash
python -m ingestion.run_ingestion -c ICML -y 2024 --limit 5
```

**Checkpoint:** Verify 5 ICML papers appear. **STOP if 0 received.** ICML 2024 is on OpenReview (`ICML.cc/2024/Conference/-/Submission` — already configured).

---

### Step 6 — ICML 2024 full ingestion

```bash
python -m ingestion.run_ingestion -c ICML -y 2024 --limit 150
```

**Checkpoint:**
```bash
python3 -c "
import sqlite3; c=sqlite3.connect('research_platform.db').cursor()
c.execute(\"SELECT co.short_name, ce.year, COUNT(*) FROM papers p JOIN conference_editions ce ON p.conference_edition_id=ce.id JOIN conferences co ON ce.conference_id=co.id GROUP BY co.short_name, ce.year ORDER BY co.short_name\")
print(c.fetchall())
c.execute('SELECT COUNT(*) FROM papers'); print('Total:', c.fetchone()[0])
"
# Expected: [('ICLR', 2024, 150), ('ICML', 2024, 150), ('NeurIPS', 2024, 100)], Total: 400
```

---

### Step 7 — Citation enrichment (ICML batch)

```bash
python -m ingestion.enrich_citations
```

---

### Step 8 — PDF pipeline

```bash
python -m pdf_pipeline.run_pipeline --limit 400
```

Downloads and segments PDFs for all 300 new papers. Skips already-processed papers.

**Expected failure rate:** 10–20% (unavailable PDFs → abstract fallback in NotebookLM).

**Checkpoint:**
```bash
python3 -c "
import sqlite3; c=sqlite3.connect('research_platform.db').cursor()
c.execute('SELECT COUNT(*) FROM papers WHERE pdf_local_path IS NOT NULL')
print('Papers with PDFs:', c.fetchone()[0])
c.execute('SELECT COUNT(DISTINCT paper_id) FROM paper_sections')
print('Papers with sections:', c.fetchone()[0])
"
# Expected: 250–380 with PDFs; 200–350 with segmented sections
```

---

## Phase 1 — NLM Pipeline, Model B (Sessions 2 + 3, ~4–5 hours, ~667 NLM calls)

**Model B selected** — re-synthesize all notebooks that receive new papers. Rationale: Stage D skips existing notebooks by default; new papers uploaded to the 23 existing notebooks will have zero extraction coverage without `--force` re-synthesis.

**Before starting Session 2, confirm auth is live:**
```bash
nlm notebook list --json | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'Auth OK — {len(d)} notebooks')"
```

### Step 9 — Upload (6 batches of 50 papers)

Run Stages A (assign), B (provision), C (upload) for new papers. Synthesis and extraction are held for Step 10 to enable `--force` re-synthesis.

```bash
# Batch 1
python -m notebooklm.run_pipeline --limit 50

# Batch 2
python -m notebooklm.run_pipeline --limit 50

# Batch 3
python -m notebooklm.run_pipeline --limit 50

# Batch 4
python -m notebooklm.run_pipeline --limit 50

# Batch 5
python -m notebooklm.run_pipeline --limit 50

# Batch 6
python -m notebooklm.run_pipeline --limit 50
```

**After each batch:**
```bash
python3 -c "
import sqlite3; c=sqlite3.connect('research_platform.db').cursor()
c.execute('SELECT source_status, COUNT(*) FROM notebook_papers GROUP BY source_status')
print(dict(c.fetchall()))
"
```

**Auth recovery:** `nlm login`, then re-run same `--limit 50` command. Already-uploaded sources are skipped.

**Checkpoint after all 6 batches:**
```bash
python3 -c "
import sqlite3; c=sqlite3.connect('research_platform.db').cursor()
c.execute('SELECT source_status, COUNT(*) FROM notebook_papers GROUP BY source_status')
statuses = dict(c.fetchall())
print('pending:', statuses.get('pending', 0), '← must be 0')
print('uploaded:', statuses.get('uploaded', 0))
print('abstract_only:', statuses.get('abstract_only', 0))
print('error:', statuses.get('error', 0), '← investigate if > 0')
c.execute('SELECT COUNT(*) FROM notebooks WHERE notebooklm_id IS NOT NULL')
print('Active notebooks:', c.fetchone()[0], '(expected ~30)')
"
# Required: pending = 0
# Expected: uploaded = ~570-600; abstract_only = ~80-120
```

---

### Step 10 — Re-synthesize all touched notebooks (Model B)

```bash
python -m notebooklm.run_pipeline --stage synthesize --force
```

**What this does:** Re-queries all notebooks (existing 23 + ~7 new), producing fresh synthesis responses that incorporate the newly uploaded sources. Overwrites existing `notebook_syntheses` rows where `normalized=True`; writes new rows for new notebooks.

**Runtime:** ~150 NLM queries × 30s = ~75 minutes.

**Checkpoint:**
```bash
python3 -c "
import sqlite3; c=sqlite3.connect('research_platform.db').cursor()
c.execute('SELECT COUNT(*) FROM notebook_syntheses'); total = c.fetchone()[0]
c.execute('SELECT COUNT(*) FROM notebooks WHERE notebooklm_id IS NOT NULL'); nb = c.fetchone()[0]
c.execute('SELECT COUNT(*) FROM notebook_syntheses WHERE normalized=0'); unnorm = c.fetchone()[0]
print(f'Synthesis rows: {total} (expected ~{nb*5})')
print(f'Unnormalized (ready for extract): {unnorm}')
"
# Required: unnorm > 0 (needed for Stage E)
# If synthesis is incomplete: re-run same command — idempotent, skips complete notebooks
```

---

### Step 11 — Extraction (Stage E)

```bash
python -m notebooklm.run_pipeline --stage extract
```

Parses all `normalized=False` synthesis rows. Upserts into `paper_analyses`, `paper_techniques`, `paper_datasets`, `paper_categories`, `paper_methodologies`.

**Checkpoint:**
```bash
python3 -c "
import sqlite3; c=sqlite3.connect('research_platform.db').cursor()
c.execute('SELECT COUNT(*) FROM paper_analyses'); print('paper_analyses:', c.fetchone()[0])
c.execute('SELECT COUNT(*) FROM paper_techniques'); print('paper_techniques:', c.fetchone()[0])
c.execute('SELECT COUNT(*) FROM notebook_syntheses WHERE normalized=0')
print('Un-normalized remaining:', c.fetchone()[0])
"
# Expected: paper_analyses: ~400 (100% coverage)
# Expected: paper_techniques: ~3,500–4,500
# Required: un-normalized = 0
```

---

## Phase 1 — Normalization + Graph + Audit (~30 min, 0 NLM calls)

### Step 12 — Entity normalization

```bash
python normalize_entities.py --force
```

`--force` required because new extractions have been added and the alias map was updated in Step 0B. Forces a full re-pass over all rows so new techniques pick up alias mappings correctly.

**Checkpoint:**
```bash
python3 -c "
import sqlite3; c=sqlite3.connect('research_platform.db').cursor()
c.execute('SELECT COUNT(*) FROM paper_techniques WHERE canonical_name IS NULL')
print('Missing canonical_name:', c.fetchone()[0])
c.execute('SELECT COUNT(DISTINCT canonical_name) FROM paper_techniques')
print('Distinct canonical techniques:', c.fetchone()[0])
"
# Required: 0 missing canonical_name
```

---

### Step 13 — Graph rebuild

```bash
python build_graph_v2.py
```

Re-computes IDF weights on expanded corpus (N≈400). Rebuilds `paper_relationships`.

**Expected graph stats:**

| Metric | NeurIPS 100 (current) | Phase 1 ~400 (target) |
|---|---|---|
| Paper edges | 2,916 | ~12,000–18,000 |
| Average edge weight | 1.625 | ~1.8–2.1 |
| Clusters | 3 | 5–8 |
| Singleton rate | 95.1% | ~75–85% |
| Shared+Core techniques | 55 | ~150–250 |

---

### Step 14 — Entity audit V2

```bash
python entity_audit.py
python entity_signal_audit.py
python concept_selection_audit.py
```

**Phase 1 definition of done:**

| Metric | Before Phase 1 | Target | Action if not met |
|---|---|---|---|
| Singleton rate | 95.1% | < 80% | Add ACL 2024 (+100 papers) or accept and proceed |
| Shared+Core techniques | 55 | ≥ 100 | Same |
| paper_analyses coverage | 100% | 100% | Re-run Step 11 |
| ICLR/ICML papers in top centrality | — | Appear in top-20 | Investigate graph build |

---

## Session Structure

| Session | Steps | Approx runtime | NLM calls |
|---|---|---|---|
| Session 0 (Pre-ingestion) | 0A, 0B, 0C, 0D, 0E | ~15 min | 0 |
| Session 1 (Ingestion + PDF) | 1–8 | ~1 hr | 0 |
| Session 2 (NLM upload) | 9 | ~2 hr | ~510 uploads + ~7 creates |
| Session 3 (Synthesis + extraction) | 10–11 | ~2 hr | ~150 synthesis queries |
| Final (Norm + graph + audit) | 12–14 | ~30 min | 0 |
| **Total** | | **~5.5–6 hr** | **~667** |

Sessions can be spread across days. All steps are resumable. Session 1 is independent of NLM auth and can be run offline.

---

## NotebookLM Call Budget

| Call type | Count | Notes |
|---|---|---|
| Source uploads | ~510 | 300 new papers × 1.7 avg assignments |
| Notebook creates | ~7 | Stage B auto-provisions on overflow |
| Synthesis queries (Model B) | ~150 | ~30 notebooks × 5 prompts |
| **Total incremental** | **~667** | |
| **Cumulative at 400 papers** | **~1,255** | Current ~588 + ~667 |

**Model B vs Model A delta:** ~115 additional synthesis calls (~60 min extra) for full extraction coverage. Model A would leave ~240 new papers (those assigned to existing notebooks) with zero analysis data.

**Session length risk:** A single continuous session covering all 667 calls takes ~4 hours. NotebookLM cookie sessions last 2–4 weeks, so auth expiry is not the binding concern. The binding concern is total clock time per sitting. Run Sessions 2 and 3 in separate sittings if needed.

---

## Failure Recovery

| Failure | Detection | Recovery |
|---|---|---|
| OpenReview returns 0 papers | Step 2/5 log output | Wait 5 min, retry; API may be rate-limiting |
| Ingestion interrupted | Paper count below expected | Re-run same command — upsert is idempotent |
| NLM auth expired mid-upload | CLI auth error | `nlm login`, re-run `--limit 50`; already-uploaded skip |
| Synthesis timeout for a notebook | Step 10 checkpoint shows missing rows | Re-run `--stage synthesize --force` — idempotent |
| Stage E incomplete | unnorm > 0 after Step 11 | Re-run `--stage extract` |
| Graph builder crashes | Stack trace | Run Step 12 first; check for NULL canonical_name |
| DB locked | `sqlite3.OperationalError` | Kill all Python processes; retry |

---

## Phase 1b Decision Gate

After Step 14 evaluate:

**If singleton rate < 80% AND Shared+Core ≥ 100:**  
Phase 1 targets met. Proceed to entity_type column design or optional ACL 2024 addition.

**If singleton rate ≥ 80% or Shared+Core < 100:**  
Options (in order):
1. Add ACL 2024 (+100 papers) as Phase 1b — run Steps 2–14 with `-c ACL -y 2024 --limit 100`
2. Accept partial targets — singleton rate is corpus-size-limited; 87–90% is the achievable floor at 100 papers without expansion

**Do NOT begin Phase 2 (EMNLP, CVPR, ECCV) until Phase 1 audits are complete and the entity audit targets have been reviewed.**

---

## Frontend Impact

**Zero.** The API contract is unchanged. The frontend reads from the same endpoints. The only observable change from the user's perspective after Phase 1 completes:

- Dashboard stats: 400 papers, 3 conferences, ~15,000+ edges, ~30 notebooks
- Papers page: 300 new papers from ICLR/ICML appear in search and filters
- Graph page: denser graph with 5–8 clusters instead of 3; ICLR/ICML conference filter now returns results
- Chat page: broader retrieval coverage; ICLR/ICML techniques and findings included in answers

The `FilterPanel.tsx` conference checkboxes for ICLR and ICML currently return 0 results — they will automatically return results once ingestion is complete.
