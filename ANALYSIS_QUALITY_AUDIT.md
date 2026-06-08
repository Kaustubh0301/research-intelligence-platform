# Analysis Quality Audit

**Date:** 2026-06-08  
**Scope:** Full pipeline from NotebookLM synthesis → DB storage → frontend rendering  
**Papers audited:** 100 NeurIPS 2024 (all have `paper_analyses` rows)

---

## Executive Summary

Paper analyses are short (avg 354 chars / ~60 words of summary) and structurally incomplete because the **synthesis prompt deliberately caps the summary at 2 sentences**, and the schema stores only 5 shallow fields. The analyses are not wrong — they are accurate and well-written — but they are truncated by design at the prompt level. Four of the seven fields proposed for the new schema don't exist anywhere in the pipeline: methodology explanation, experimental findings, practical applications, and future research directions as a distinct analyst-generated field.

A secondary issue: the `llm-architectures` notebook has 45 papers loaded against a practical NLM synthesis limit of ~9. When queried, NLM silently truncated its summary response to 106 words covering only 9 papers and returned internal planning text ("I've decided to refine the paper list…") rather than failing cleanly. The remaining 36 papers in that notebook have analyses sourced from a secondary notebook assignment, so no data was lost in this corpus — but this is a latent reliability risk at larger scale.

---

## Root Causes

### Root Cause 1 — Prompt hard-caps summary at 2 sentences

The `summary` prompt in `notebooklm/pipeline.py` (line 43–54) explicitly instructs:

```
SUMMARY: [2 sentences]
```

NotebookLM faithfully obeys. Every summary is exactly 2 sentences. The resulting text averages **354 characters** (~55 words). For a research paper, a 55-word summary captures roughly:
- What the paper proposes (sentence 1)
- What benchmark it beats (sentence 2)

Missing entirely: *how* it works, what the experimental design is, what the numbers are, why it matters beyond the benchmark.

**Evidence from stored data:**

| Paper | Summary length | What's captured | What's missing |
|---|---|---|---|
| Gorilla (1,248 citations) | 358 chars | Introduces fine-tuned LLaMA for API calls; beats GPT-4 on APIBench | How RAT works, what APIBench contains, by how much it beats GPT-4, why this matters |
| Refusal Direction (716 citations) | 385 chars | Refusal is one-dimensional in residual stream; ablating it enables jailbreak | Mechanistic details of extraction, which models were tested, intervention vs. observation results |
| AlphaLLM (150 citations) | 397 chars | MCTS + LLM loop, no human labels needed; improves math reasoning | What the 3 critic models do, what math benchmarks were used, the score improvement delta |
| Cross-Layer Attention (118 citations) | 379 chars | KV cache sharing across layers; halves memory | Which transformer architectures, what accuracy degradation means numerically, training details |
| Moment Matching Distillation (76 citations) | 405 chars | Matches conditional expectations along trajectory; beats teacher | Distillation objective formulation, FID scores, comparison vs. prior diffusion distillation methods |

---

### Root Cause 2 — Schema stores 5 fields; 4 proposed fields have no storage

The `paper_analyses` table (`db/models.py` line 218–240):

```python
summary:     Text       # 2-sentence string
advantages:  Text       # JSON array, avg 2 items
limitations: Text       # JSON array, avg 1.7 items (17 papers have 0)
future_work: Text       # JSON array, avg 1.3 items (31 papers have 0)
use_cases:   Text       # JSON array, avg 2.1 items
```

**No column exists for:**
- `methodology` — how the paper's core method works
- `experimental_findings` — concrete benchmark results and comparisons
- `practical_applications` — richer than `use_cases` (which are already present but thin at 1 sentence each)
- `future_research_directions` — analyst-synthesized directions beyond the paper's own stated future work

The `future_work` field currently stores what the *paper itself* says about future directions. That is useful but different from an analyst-generated assessment of open questions and research opportunities.

---

### Root Cause 3 — Advantage/limitation prompts generate labels, not explanations

The `ADVANTAGE:` and `LIMITATION:` format asks for `[key strength] | [key strength]` — short pipe-separated labels. The stored results reflect this:

```
ADVANTAGES: ['Adapts dynamically to API documentation changes at test time',
             'Successfully reasons through user-defined constraints when selecting APIs']
```

These are 10–12 word labels. They name the benefit but don't explain the mechanism. A reader does not learn *why* Gorilla adapts dynamically (because RAT conditions on live documentation rather than baking it into weights) or *how* it reasons through constraints (via structured retrieval + constrained decoding).

---

### Root Cause 4 — NotebookLM silent truncation on overloaded notebooks

`llm-architectures` had **45 sources uploaded** (the hard `_max_sources=45` limit in the assigner). When Stage D queried this notebook with the `summary` prompt, NLM:

1. Returned 106 words of internal reasoning text starting with `**Expanding the Sources**`
2. Covered only 9 of 45 papers
3. Did not return any PAPER:/SUMMARY: blocks — the extractor found 0 matches
4. Did NOT raise an error; Stage E wrote nothing for those 36 papers from this notebook

The 36 affected papers all had secondary notebook assignments from smaller notebooks, so their analyses were populated from those. **No paper lost its analysis** in the current 100-paper corpus. But this failure mode is silent and will recur at scale: any notebook loaded to capacity will silently produce incomplete synthesis.

**Detection:** The synthesis `word_count` of 106 vs. the expected 800–2,000+ for a full-notebook summary is the only signal. There is no validation step after Stage D that checks whether all papers in a notebook appear in its synthesis response.

---

### Root Cause 5 — Frontend renders exactly what is stored, no enrichment

The `AnalysisPanel` component (`apps/web/src/components/papers/AnalysisPanel.tsx`) passes through all 5 stored fields to the UI without transformation:

```tsx
<p className="text-sm leading-relaxed text-foreground/80">
  {analysis.summary}    {/* raw 2-sentence string */}
</p>
<BulletList items={analysis.advantages} />    {/* short label list */}
<BulletList items={analysis.limitations} />
<BulletList items={analysis.future_work} />
<BulletList items={analysis.use_cases} />
```

Nothing is being lost at the rendering layer. What is in the DB is exactly what appears in the UI. The quality problem is entirely upstream.

---

## Evidence: 5 Representative Papers

### Paper 1: Gorilla: Large Language Model Connected with Massive APIs
**Citations:** 1,248 | **Conference:** NeurIPS 2024

**Raw NotebookLM synthesis (agentic-ai notebook, summary prompt):**
```
PAPER: Gorilla: Large Language Model Connected with Massive APIs
SUMMARY: This paper introduces Gorilla, a fine-tuned LLaMA-based model designed to accurately 
write API calls by leveraging a novel Retriever Aware Training method. Evaluated on the newly 
introduced APIBench dataset, Gorilla surpasses state-of-the-art models like GPT-4 in generating 
functionally correct API calls while significantly mitigating hallucination errors.
ADVANTAGE: Adapts dynamically to API documentation changes at test time | Successfully reasons 
through user-defined constraints when selecting APIs
LIMITATION: Retrieval augmentation does not always lead to improved performance and can sometimes 
hurt it | Hallucinations still occur, such as invoking commands with arbitrary GitHub repository names
FUTURE_WORK: Transition Large Language Models from knowledge-bound models into flexible interfaces 
interacting with the digital world
===
```
**Stored in `paper_analyses`:** Identical to raw — no transformation loss  
**UI renders:** Same 2-sentence summary + 2 advantages + 2 limitations + 1 future_work + 2 use_cases  
**Information gap vs. a human analyst reading the paper:**
- RAT mechanism: how retrieval-aware training differs from standard RAG
- APIBench composition: 3 subsets (Torch Hub, TensorFlow Hub, HuggingFace), test methodology
- Quantitative improvement: exact % hallucination reduction vs. GPT-4
- Methodology: fine-tuning approach, model size, training data construction

---

### Paper 2: Refusal in Language Models Is Mediated by a Single Direction
**Citations:** 716 | **Conference:** NeurIPS 2024

**Raw synthesis (ai-safety notebook):**
```
PAPER: Refusal in Language Models Is Mediated by a Single Direction
SUMMARY: This paper demonstrates that the refusal behavior of conversational large language models 
is mediated by a single one-dimensional subspace in their residual stream activations. By ablating 
this specific direction, the authors show that models lose their ability to refuse harmful 
instructions, leading to the proposal of a novel white-box jailbreak method via weight 
orthogonalization.
ADVANTAGE: Bypasses refusal without gradient-based optimization or harmful examples | Simple weight 
modification preserves general model capabilities and coherence
LIMITATION: Findings may not generalize to untested or future models at greater scale | Semantic 
meaning of the refusal direction remains unclear
FUTURE_WORK: Methodological improvements to the heuristic extraction of the refusal direction | 
Comprehensive mechanistic understanding of adversarial suffixes
===
```
**Stored / UI:** Identical to raw  
**Information gap:** No description of how the refusal direction is extracted (mean difference of harmful vs. harmless activations), which models were tested (Llama, Claude, Gemma), the jailbreak success rate, or why a single direction suffices (residual stream geometry).

---

### Paper 3: Toward Self-Improvement of LLMs via Imagination, Searching, and Criticizing
**Citations:** 150 | **Conference:** NeurIPS 2024

**Raw synthesis (llm-reasoning notebook):**
```
PAPER: Toward Self-Improvement of LLMs via Imagination, Searching, and Criticizing
SUMMARY: This paper presents ALPHALLM, a framework that integrates Monte Carlo Tree Search with 
language models to establish a self-improving loop that functions without additional human-annotated 
data. By employing a prompt synthesizer, an optimized search tailored for language tasks, and a 
trio of critic models for precise feedback, the system significantly enhances mathematical 
reasoning performance.
ADVANTAGE: Eliminates the need for extensive human-annotated data... | Significantly improves 
search efficiency...
LIMITATION: Current evaluation is primarily limited to mathematical reasoning tasks... | The 
outcome reward model struggles...
FUTURE_WORK: [empty — 0 items stored]
===
```
**Information gap:** MCTS adaptation details (state merging, branching factor), exact benchmark scores on GSM8K / MATH, how the 3 critics interact, training-inference separation.

---

### Paper 4: Reducing Transformer Key-Value Cache Size with Cross-Layer Attention
**Citations:** 118 | **Conference:** NeurIPS 2024

**Information gap:** Layer grouping strategy, which layers share KV heads, model sizes tested (7B, 13B?), perplexity delta, comparison against GQA and MQA on exact benchmarks.

---

### Paper 5: Multistep Distillation of Diffusion Models via Moment Matching
**Citations:** 76 | **Conference:** NeurIPS 2024

**Information gap:** What "matching conditional expectations" means mathematically, the sampling trajectory design, FID scores at 2/4/8 steps vs teacher, comparison to consistency distillation and progressive distillation.

---

## Quantitative Scope

| Metric | Value |
|---|---|
| Papers with analyses | 100 / 100 |
| Avg summary length | 354 chars (~55 words) |
| Median summary length | 356 chars |
| Papers with summary < 300 chars | 14 |
| Papers with summary > 400 chars | 20 |
| Papers with 0 limitations | 17 (17%) |
| Papers with 0 future_work | 31 (31%) |
| Papers with 0 use_cases | 0 |
| Missing fields in schema | 4 (methodology, findings, applications, analyst directions) |
| llm-architectures notebook: papers covered by synthesis | 9 / 45 |
| Papers whose analysis came from secondary notebook only | ~36 (estimated) |

---

## Proposed New Analysis Schema

### Rationale

The proposed schema replaces the single 2-sentence summary with 7 distinct fields. Each field maps to a specific synthesis prompt. The total analysis content per paper should be **500–900 words** rather than the current ~100–150 words.

### New `paper_analyses` columns

| Column | Type | Content | Target length |
|---|---|---|---|
| `summary` | Text | High-level overview — what the paper does, why it matters | 300–500 words / 3–5 paragraphs |
| `methodology` | Text | How the core method works — architecture, algorithm, key design decisions | 150–250 words |
| `experimental_findings` | Text (JSON array) | Concrete results: benchmark names, numbers, what baselines were beaten by how much | 3–6 bullet strings |
| `strengths` | Text (JSON array) | Substantive explanation of what makes the approach work, not just labels | 2–4 bullet strings, 30–60 words each |
| `limitations` | Text (JSON array) | Substantive explanation of constraints, failure modes, scope restrictions | 2–4 bullet strings, 30–60 words each |
| `practical_applications` | Text (JSON array) | Specific deployment scenarios with enough detail to evaluate feasibility | 2–4 bullet strings, 40–80 words each |
| `future_research_directions` | Text (JSON array) | Analyst-synthesized open questions and research opportunities — distinct from the paper's stated future work | 2–4 bullet strings |

The current `advantages`, `future_work`, and `use_cases` columns are superseded by `strengths`, `future_research_directions`, and `practical_applications` respectively. `limitations` stays but is expanded.

### New synthesis prompts

The 5-prompt structure would expand to **7 prompts** (one per analysis field), each queried separately:

**Prompt: `summary`** (replace current 2-sentence constraint)
```
For each paper in this notebook, write a detailed summary.
Use the EXACT paper title as it appears in the source.
Format strictly as shown:

PAPER: [exact title]
SUMMARY: [3-5 paragraphs covering: (1) what problem the paper addresses and why it matters,
(2) the core proposed approach at a conceptual level, (3) key results and how they compare to
prior work, (4) the main contribution in one sentence]
===

Rules:
- Target 300-500 words per summary.
- Write for a ML researcher who has not read the paper.
- Include specific technique names, dataset names, and quantitative claims from the paper.
- Do not use bullet points inside SUMMARY.
- Repeat the block for EVERY paper in the notebook.
```

**Prompt: `methodology`**
```
For each paper in this notebook, explain the core methodology.
Use the EXACT paper title as it appears in the source.
Format strictly as shown:

PAPER: [exact title]
METHODOLOGY: [2-3 paragraphs: (1) the technical approach — architecture, algorithm, or framework
design, (2) key implementation decisions that distinguish it from prior work, (3) training or
evaluation procedure if relevant]
===

Rules:
- Target 150-250 words.
- Use precise technical terms. Name specific components, loss functions, and design choices.
- Do not restate the motivation — focus on mechanism.
- Repeat the block for EVERY paper in the notebook.
```

**Prompt: `experimental_findings`**
```
For each paper in this notebook, extract the key experimental results.
Use the EXACT paper title as it appears in the source.
Format strictly as shown — one FINDING line per result:

PAPER: [exact title]
FINDING: [dataset or benchmark name] :: [metric] :: [this paper's score] vs [baseline score]
FINDING: [second result]
===

Rules:
- Use the canonical benchmark name (e.g. ImageNet, GSM8K, MMLU, not 'the benchmark').
- Include the numeric values when available.
- List the strongest 3-6 results.
- If no benchmark experiments exist, write: FINDING: No quantitative benchmark evaluation
- Repeat the block for EVERY paper in the notebook.
```

**Prompt: `strengths`** (replaces current `ADVANTAGE:` labels)
```
For each paper in this notebook, explain the key strengths of the approach.
Use the EXACT paper title as it appears in the source.
Format strictly as shown:

PAPER: [exact title]
STRENGTH: [1-2 sentences explaining WHY this aspect works, not just that it works]
STRENGTH: [second strength]
===

Rules:
- Each STRENGTH must explain the mechanism, not just name the property.
- Wrong: "Efficient inference"
- Right: "Inference is efficient because KV activations are shared across layers,
  halving memory bandwidth without changing the attention computation graph."
- Write 2-4 STRENGTH lines per paper.
- Repeat the block for EVERY paper in the notebook.
```

**Prompt: `limitations`** (same structure, expanded guidance)
```
For each paper in this notebook, explain the key limitations.
Use the EXACT paper title as it appears in the source.
Format strictly as shown:

PAPER: [exact title]
LIMITATION: [1-2 sentences: what the constraint is AND why it exists or what would be needed to
overcome it]
===

Rules:
- Each LIMITATION must explain the constraint, not just name it.
- Write 2-4 LIMITATION lines per paper.
- Include scope limitations (e.g. only evaluated on X), failure modes, and
  assumptions that may not hold in practice.
- Repeat the block for EVERY paper in the notebook.
```

**Prompt: `practical_applications`** (replaces thin `use_cases`)
```
For each paper in this notebook, describe practical deployment scenarios.
Use the EXACT paper title as it appears in the source.
Format strictly as shown:

PAPER: [exact title]
APPLICATION: [2-3 sentences: the deployment context, what the paper's contribution enables
specifically, and what the practical benefit is vs. the alternative]
===

Rules:
- Each APPLICATION must name a specific industry or use context.
- Explain what is *newly possible* with this paper's method vs. prior approaches.
- Write 2-3 APPLICATION lines per paper.
- Repeat the block for EVERY paper in the notebook.
```

**Prompt: `future_research_directions`**
```
For each paper in this notebook, identify open research directions.
Use the EXACT paper title as it appears in the source.
Format strictly as shown:

PAPER: [exact title]
DIRECTION: [1-2 sentences: an open question or research opportunity that this paper creates or
that would extend its contributions — from the perspective of a researcher building on this work]
===

Rules:
- DIRECTION lines should be analyst-generated, not just restated from the paper's conclusion.
- Focus on gaps the paper leaves open: unexplored settings, untested assumptions, potential
  extensions to other domains.
- Write 2-4 DIRECTION lines per paper.
- Repeat the block for EVERY paper in the notebook.
```

---

## Proposed Fix

### Step 1 — Add 4 new columns to `paper_analyses`

```sql
ALTER TABLE paper_analyses ADD COLUMN methodology TEXT;
ALTER TABLE paper_analyses ADD COLUMN experimental_findings TEXT;  -- JSON array
ALTER TABLE paper_analyses ADD COLUMN strengths TEXT;              -- JSON array (replaces advantages)
ALTER TABLE paper_analyses ADD COLUMN practical_applications TEXT; -- JSON array (replaces use_cases)
ALTER TABLE paper_analyses ADD COLUMN future_research_directions TEXT; -- JSON array (replaces future_work)
```

Existing `advantages`, `future_work`, `use_cases` columns remain for backward compatibility with the current 100 papers until re-synthesis is complete, then can be deprecated.

### Step 2 — Add 2 new prompts to `pipeline.py` PROMPTS dict

Replace the `summary` prompt (2-sentence → 300-500 word). Add `methodology`, `experimental_findings`, `strengths`, `limitations_v2`, `practical_applications`, `future_research_directions` prompts.

This expands from 5 to 7 prompts per notebook. The 2 new prompts (methodology + experimental_findings) increase NLM synthesis calls by 40%.

### Step 3 — Add parsers for new structured fields in `extractor.py`

New parsers needed:
- `parse_methodology()` — same structure as `parse_summary`, stores `METHODOLOGY:` multi-line text
- `parse_experimental_findings()` — same structure as `parse_datasets`, stores `FINDING: name :: metric :: score` triples
- `parse_strengths()` — same multi-value line structure as current `ADVANTAGE:`
- `parse_practical_applications()` — same as current `USE_CASE:` but for `APPLICATION:` label
- `parse_future_directions()` — same as `parse_strengths` for `DIRECTION:` label

### Step 4 — Update `normalizer.py` to write new columns

Add writes for new fields in `_upsert_analysis()`.

### Step 5 — Update API models and frontend type

Add new fields to `AnalysisOut` in `api/helpers.py`, `PaperAnalysis` in `types.ts`, and `AnalysisPanel.tsx` rendering.

### Step 6 — Add synthesis coverage validation to Stage D

After Stage D completes for a notebook, count PAPER: blocks in each synthesis response and compare against the notebook's paper count. Log a warning if coverage < 80%. This catches the silent truncation failure.

---

## Estimated Regeneration Cost

### Current 100 NeurIPS papers (re-synthesis only, no new ingestion)

Under the new 7-prompt schema:

| Call type | Count | Notes |
|---|---|---|
| Synthesis queries | ~115 | 23 notebooks × 5 existing prompts (overwrite) |
| New prompt queries | ~46 | 23 notebooks × 2 new prompts |
| **Total NLM calls** | **~161** | |

Runtime estimate: ~161 queries × 30s = ~80 minutes (one session).

All 23 notebooks already have sources uploaded. Only Stage D (`--stage synthesize --force`) + Stage E (`--stage extract`) need to run. No new uploads.

### Phase 1A: +150 ICLR papers (after NotebookLM pipeline runs)

Under the new schema, the 150 new ICLR papers will need re-synthesis with 7 prompts instead of 5:

| Call type | Count | Notes |
|---|---|---|
| Uploads | ~255 | Already estimated (unchanged) |
| Synthesis (7 prompts × ~30 touched notebooks) | ~210 | vs. ~110 under old 5-prompt schema |
| **Total Phase 1A NLM calls (new schema)** | **~465** | vs. ~367 under old schema |
| **Δ cost** | **+98 calls** | ~+50 minutes per session |

### Full Phase 1 (400 papers, ICLR + ICML)

| Scenario | Old 5-prompt | New 7-prompt | Δ |
|---|---|---|---|
| Incremental NLM calls | ~667 | ~934 | +267 |
| Synthesis only delta | ~150 | ~210 | +60 |

The additional cost is 40% more synthesis calls. At ~30s each, this adds ~30 minutes per synthesis session. The tradeoff is analyses that are 4–5× richer in content and cover the 4 fields that are currently absent entirely.

---

## Summary Table

| Issue | Severity | Location | Fix |
|---|---|---|---|
| Summary prompt caps at 2 sentences | **HIGH** | `pipeline.py` PROMPTS["summary"] | Rewrite prompt: 300–500 words, 3–5 paragraphs |
| 4 analysis fields missing from schema | **HIGH** | `db/models.py`, `paper_analyses` table | Add `methodology`, `experimental_findings`, `strengths`, `future_research_directions` columns |
| Advantage/limitation prompts generate labels not explanations | **MEDIUM** | `pipeline.py` PROMPTS["summary"] | Rewrite ADVANTAGE/STRENGTH prompt to require mechanism explanation |
| Silent notebook overload truncation | **MEDIUM** | Stage D, `pipeline.py run_synthesize()` | Add post-synthesis coverage validation; cap notebook assignment at 15–20 papers |
| No methodology field anywhere | **MEDIUM** | Schema + prompts | New `methodology` prompt + column |
| No experimental findings anywhere | **MEDIUM** | Schema + prompts | New `experimental_findings` prompt + column |
| Frontend renders storage directly | **LOW** | `AnalysisPanel.tsx` | No fix needed — output quality is a pipeline problem |
