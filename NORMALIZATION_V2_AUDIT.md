# Normalization V2 Audit — Technique Singleton Analysis

**Date:** 2026-06-05  
**Question:** Why does the technique singleton rate remain at 95.1% after the full-text rebuild?  
**Source data:** `outputs/entity_signal_audit.csv` (1,115 canonical entries), `normalize/technique_aliases.json`, `normalize/rules.py`  
**Scope:** Techniques only. Dataset aliases are separate and not audited here.

---

## 1. Current Normalization Coverage

### Architecture

The normalizer runs two passes on distinct `(name, row_count)` pairs:

**Pass 1 — Explicit alias map** (`normalize/technique_aliases.json`)  
Handles: acronym expansions, cross-group aliases, parenthetical acronym stripping (for alias lookup only), wording aliases, singular/plural normalization.  
The key constraint: parenthetical stripping only activates during an alias map lookup. If a name like `"Multi-Head Attention (MHA)"` has no alias entry, the strip fires but finds nothing, and the full string passes unchanged to Pass 2.

**Pass 2 — Case-fold grouping** (automatic)  
Groups names by `name.lower()` and picks the most-common/title-case winner. Only works for names that are identical after lowercasing. `"Multi-Head Attention (MHA)"` and `"Multi-Head Attention"` lowercase to different strings, so Pass 2 leaves them as separate canonicals.

**Incremental-only default:** Without `--force`, only rows where `canonical_name IS NULL` are processed. Rows normalized in a prior run keep their old canonical — even if running with the full corpus would pick a different winner under case-fold grouping.

### What the alias file currently covers

| Group | Entries | Coverage |
|---|---|---|
| LLM family | 5 entries | LLMs, language models (generic) |
| Transformers family | 7 entries | Transformer variants, vision transformers |
| Diffusion models | 6 entries | Generic + specific subtypes |
| Reinforcement learning family | 6 entries | RL, DRL, MARL, RLHF |
| Acronym expansions | 17 entries | MCTS, RAT, RVFS, TSCI, FRLC, PERM, POMDP, NER |
| Parenthetical stripping (explicit) | 6 entries | ALS, MBR, MPR, and 3 others |
| Wording aliases | 8 entries | Iterative self-reflection, custom kernels, etc. |
| Singular/plural | 6 entries | Latent variable graphical models, logit margins, etc. |
| Case normalisation | 28 entries | AdamW, gradient descent, neural networks, etc. |
| **Total mappings** | **~89** | |

**What the alias file does NOT cover:** parenthetical variants for ~60+ technique pairs, plural/singular for most technique names, acronym expansions for common abbreviations (SGD, PPO, MLP, LoRA), cross-format variants (with/without hyphen, with/without "algorithm" suffix), and case-fold normalization of names that are identical but differ only in title casing.

---

## 2. Why the Singleton Rate Barely Moved

### Finding 1: Pass 2 case-fold cannot run globally after incremental updates

The most significant structural problem: normalization is run incrementally (no `--force`) after each Stage E extraction. When paper A extracts "Forward gradients" and paper B extracts "forward gradients" in separate pipeline runs, each is processed as a singleton at the time it is written. Paper A's row gets `canonical_name = "Forward gradients"`. Paper B's row later gets `canonical_name = "forward gradients"` (lowercase wins when only one row is being folded). The entity signal audit then groups by `canonical_name` and sees two different strings — both appear as singletons.

Running `--force` re-processes all rows simultaneously, allowing Pass 2 to see both "Forward gradients" and "forward gradients" at once and assign the same winner. This is why the entity signal audit note says "graph was built before the latest normalization pass ran" — the stale graph was built when these pairs still had inconsistent canonical_names.

**Evidence:** At least 30 singleton pairs in the CSV have names that lowercase to identical strings:

| Raw A | Raw B | Type |
|---|---|---|
| Forward gradients | forward gradients | Case-fold pair |
| Meta-learning | meta-learning | Case-fold pair |
| Visual search | visual search | Case-fold pair |
| Adversarial training | adversarial training | Case-fold pair |
| Weight noise | weight noise | Case-fold pair |
| Dynamic programming | dynamic programming | Case-fold pair |
| Gradient boosting | gradient boosting | Case-fold pair |
| Transfer learning | transfer learning | Case-fold pair |
| Value function approximation | value function approximation | Case-fold pair |
| Process Reward Model | Process reward model (PRM) | Case-fold + paren |
| Outcome Reward Model | Outcome reward model (ORM) | Case-fold + paren |
| Minimum norm interpolating solutions | minimum norm interpolating solutions | Case-fold pair |
| Iteratively reweighted least squares | Iteratively reweighted least squares (IRLS) | Paren variant |
| Counterfactual explanations | counterfactual explanations | Case-fold pair |
| Bisimulation metrics | bisimulation metrics | Case-fold pair |
| Spectral graph theory | spectral graph theory | Case-fold pair |
| Multilayer perceptron | multilayer perceptron | Case-fold pair |
| Dynamic Rescaling | dynamic rescaling | Case-fold pair |

Each such pair is two singletons that should be one. A single `--force` run fixes all of these.

### Finding 2: Parenthetical acronym strip only works during alias lookup, not during case-fold

The regex `\([A-Z][A-Z0-9\-]+\)$` fires in `resolve_alias()` to find alias map entries. If no alias entry exists for the stripped name, the full string (with parens) goes to Pass 2 unchanged. Pass 2 then sees `"Multi-Head Attention (MHA)"` and `"Multi-Head Attention"` as different lowercase strings.

**Impact:** ~60 singleton pairs of the form `"Foo (BAR)"` + `"Foo"` remain uncollapsed.

Selected examples:

| With parens (Singleton) | Without parens (Singleton/Shared) | Merged paper count |
|---|---|---|
| DDIM (Denoising Diffusion Implicit Model) | DDIM | 2 |
| Coarse-grained Sparsity (CSparse) | Coarse-grained Sparsity | 2 |
| Fine-grained Sparsity (FSparse) | Fine-grained Sparsity | 2 |
| Contextual Sparsity (CS) | Contextual Sparsity | 2 |
| Multi-Head Attention (MHA) | Multi-Head Attention | 2 |
| Multihead Attention (MHA) | Multi-Head Attention | 2–3 |
| Grouped-Query Attention (GQA) | Grouped-Query Attention | 2 |
| Multi-Query Attention (MQA) | Multi-Query Attention | 2 |
| Cross-Layer Attention (CLA) | Cross-Layer Attention | 2 |
| Butterfly Orthogonal Fine-Tuning (BOFT) | Butterfly Orthogonal Fine-Tuning | 2 |
| Orthogonal Fine-Tuning (OFT) | Orthogonal Fine-Tuning | 2 |
| GSOFT (GS Orthogonal Fine-Tuning) | GSOFT | 2 |
| Supervised fine-tuning (SFT) | Supervised fine-tuning | 2 |
| Supervised fine-tuning (SFT) | Supervised finetuning | 2–3 |
| Vision Transformers (ViTs) | Vision Transformers [Shared, 2] | 3 |
| Neural Tangent Kernel (NTK) | Neural Tangent Kernel | 2 |
| Neural Tangent Ensemble (NTE) | Neural Tangent Ensemble | 2 |
| Nonlocal Attention Operator (NAO) | Nonlocal Attention Operator | 2 |
| Factorized Self-Attention Module (FSAM) | Factorized Self-Attention Module | 2 |
| Temporal Activation Controller (TAC) | Temporal Activation Controller | 2 |
| Static single assignment (SSA) | Static single assignment | 2 |
| Joint Embedding Predictive Architecture (JEPA) | Joint Embedding Predictive Architectures | 2 |
| Pretraining and finetuning (PT+FT) | Pretraining and finetuning | 2 |
| Factor Relaxation with Latent Coupling algorithm | Factor Relaxation with Latent Coupling | 2 |
| Independent Cascade (IC) model | Independent Cascade model | 2 |

Fix: extend Pass 2 to strip parenthetical acronyms before building the lowercase grouping key. This is a one-line code change in `case_fold_canonical`.

### Finding 3: Missing alias entries for well-known abbreviations

Several common abbreviations that should map to Shared-tier canonicals are absent from the alias file:

| Abbreviation (Singleton, 1 paper) | Should map to | Canonical paper_count after merge |
|---|---|---|
| SGD | Stochastic gradient descent | 4 → **6** (Core) |
| PPO | Proximal Policy Optimization | 4 → **5** (Core) |
| Low Rank Adaptation (LoRA) | LoRA | 3 → **4–5** |
| Low-rank adaptation | LoRA | 3 → **4–5** |
| QLoRA | LoRA | debatable — distinct technique |
| ResNets | ResNet | 3 → **4** |
| Residual Network | ResNet | 3 → **4** |
| Monte-Carlo Tree Search | Monte Carlo Tree Search | 2 → **3** |
| Autoencoder | Autoencoders | 2 → **3** |
| Convolutional neural networks | Convolutional neural network (CNN) | 2 → **3** |
| Graph neural networks | Graph Neural Networks | 3 → **4** |

### Finding 4: Shared-tier entries that are obvious duplicates of each other

Five Shared-tier canonical names are clearly aliases of the same underlying concept. They should be a single canonical but were never combined. Each "paper_count" is the current value for that canonical:

| Canonical A | Count | Canonical B | Count | Canonical C | Count | Should be |
|---|---|---|---|---|---|---|
| Direct Preference Optimization | 2 | Direct Preference Optimization (DPO) | 2 | Direct preference optimization | 2 | **1 canonical, ~5 papers (Core)** |
| Chain-of-Thought | 3 | Chain-of-Thought (CoT) | 3 | Chain-of-Thought prompting | 3 | **1 canonical, ~5–6 papers (Core)** |
| Graph convolutional network | 4 | Graph Convolutional Networks | 2 | — | — | **1 canonical, ~5–6 papers (Core)** |
| Large Language Models | 9 | Large language models (LLMs) | 7 | — | — | **1 canonical, ~10–12 papers (Core)** |
| Multilayer perceptron (MLP) | 2 | Multilayer perceptrons | 2 | — | — | **1 canonical, ~3–4 papers** |

The LLM case is the most significant: "Large language models (LLMs)" should have been merged into "Large Language Models" by the existing alias rule via parenthetical stripping (`"large language models (llms)"` → strip `(LLMs)` → `"large language models"` → alias → `"Large Language Models"`). That it appears as a separate Core entry suggests the paren regex requires the acronym to be all uppercase (`[A-Z][A-Z0-9\-]+`), and `"LLMs"` contains a lowercase `s`. The regex fails to match `(LLMs)` because `s` is not in `[A-Z0-9\-]`.

**This is a bug in the parenthetical acronym regex.** The pattern `\([A-Z][A-Z0-9\-]+\)` requires all characters after the first to be uppercase or digits. Common acronyms with lowercase trailing letters (`LLMs`, `ViTs`, `GATs`, `GNNs`, `MLPs`) all fail this pattern.

---

## 3. Missed Alias Categories

| Category | Description | Estimated pairs affected | Fix type |
|---|---|---|---|
| **A. Case-fold drift** | Same name, different capitalisation across incremental normalization runs | ~30 pairs | Run `--force` once |
| **B. Paren-acronym not in alias** | `"Foo (BAR)"` + `"Foo"` where no alias entry covers either form | ~60 pairs | Extend Pass 2 to strip paren before grouping |
| **C. Paren regex misses mixed-case** | Regex `[A-Z][A-Z0-9\-]+` excludes `LLMs`, `ViTs`, `GNNs` | ~5 high-value cases | Fix regex to `[A-Z][A-Za-z0-9\-]+` |
| **D. Missing abbreviation aliases** | PPO, SGD, LoRA variants, ResNets, etc. | ~15 entries | Add to alias JSON |
| **E. Shared-tier inter-aliases** | DPO×3, CoT×3, GCN×2, LLM×2, MLP×2 in Shared tier | 5 merge groups | Add cross-canonical alias entries |
| **F. Plural/singular gaps** | ResNet/ResNets, Autoencoder/Autoencoders, GNN variants | ~10 pairs | Add to alias JSON |
| **G. Algorithmic name variants** | "Foo algorithm" + "Foo" (e.g., Alternating Least Squares) | ~15 pairs | Add to alias JSON |

---

## 4. Top 50 Merge Opportunities

Ranked by estimated impact: graph edges gained, paper_count of resulting canonical, and reduction in singleton count.

### Tier 1 — Fix the regex (immediate, very high impact)

**Merge 1: Large Language Models / Large language models (LLMs)**  
*Type: Paren regex bug — `(LLMs)` has lowercase `s`*  
Current: Core (9) + Core (7) = 16 total assignments across 2 canonicals  
After fix: 1 Core canonical, ~10–12 papers, graph_degree_contrib ~66 → eliminates 1 Core duplicate  

**Merge 2: Vision Transformers (ViTs) → Vision Transformers**  
*Type: Paren regex bug*  
Current: "Vision Transformers (ViTs)" Singleton (1), "Vision Transformers" Shared (2)  
After: Shared → 3 papers  

### Tier 2 — Run `--force` (zero code change, immediate)

All ~30 case-fold drift pairs are fixed by one `normalize_entities.py --force` run. Selected high-value ones:

**Merge 3: Forward gradients / forward gradients** → 2 papers  
**Merge 4: Meta-learning / meta-learning** → 2 papers  
**Merge 5: Visual search / visual search** → 2 papers  
**Merge 6: Adversarial training / adversarial training** → 2 papers  
**Merge 7: Weight noise / weight noise** → 2 papers  
**Merge 8: Dynamic programming / dynamic programming** → 2 papers  
**Merge 9: Gradient boosting / gradient boosting** → 2 papers  
**Merge 10: Transfer learning / transfer learning** → 2 papers  
**Merge 11: Value function approximation / value function approximation** → 2 papers  
**Merge 12: Process Reward Model / Process reward model (PRM)** → 2 papers  
**Merge 13: Outcome Reward Model / Outcome reward model (ORM)** → 2 papers  
**Merge 14: Dynamic Rescaling / dynamic rescaling** → 2 papers  
**Merge 15: Bisimulation metrics / bisimulation metrics** → 2 papers  
**Merge 16: Counterfactual explanations / counterfactual explanations** → 2 papers  
**Merge 17: Spectral graph theory / spectral graph theory** → 2 papers  
**Merge 18: Multilayer perceptron / multilayer perceptron** → 2 papers  
**Merge 19: Minimum norm interpolating solutions / minimum norm interpolating solutions** → 2 papers  
**Merge 20: Satisficing paths / satisficing paths** → 2 papers  
**Merge 21: Mutual fairness / mutual fairness** → 2 papers  
**Merge 22: $\Phi$-equilibria / $\Phi$-equilibrium** (singular/plural LaTeX variants) → 2 papers  
**Merge 23: Ranking algorithm / ranking algorithm** → 2 papers  
**Merge 24: Alternating optimization / alternating optimization** → 2 papers  
**Merge 25: Concept space framework / concept space framework** → 2 papers  
**Merge 26: Synthetic data generation framework / synthetic data generation framework** → 2 papers  
**Merge 27: Pseudo-programs / pseudo-programs** → 2 papers  
**Merge 28: Numerical estimation / numerical estimation** → 2 papers  
**Merge 29: Stochastic-process approach / stochastic-process approach** → 2 papers  
**Merge 30: Dual training algorithm / dual training algorithm** → 2 papers  

### Tier 3 — Extend Pass 2 paren-strip (one code change, high impact)

After fixing Pass 2 to strip parens before building the group key, these pairs collapse automatically:

**Merge 31: Supervised fine-tuning (SFT) / Supervised fine-tuning / Supervised finetuning** → 3 papers  
**Merge 32: DDIM (Denoising Diffusion Implicit Model) / DDIM** → 2 papers  
**Merge 33: Multi-Head Attention (MHA) / Multihead Attention (MHA) / Multi-Head Attention** → 2–3 papers  
**Merge 34: Grouped-Query Attention (GQA) / Grouped-Query Attention** → 2 papers  
**Merge 35: Multi-Query Attention (MQA) / Multi-Query Attention** → 2 papers  
**Merge 36: Cross-Layer Attention (CLA) / Cross-Layer Attention** → 2 papers  
**Merge 37: Neural Tangent Kernel (NTK) / Neural Tangent Kernel** → 2 papers  
**Merge 38: Neural Tangent Ensemble (NTE) / Neural Tangent Ensemble** → 2 papers  
**Merge 39: Butterfly Orthogonal Fine-Tuning (BOFT) / Butterfly Orthogonal Fine-Tuning** → 2 papers  
**Merge 40: Orthogonal Fine-Tuning (OFT) / Orthogonal finetuning** → 2 papers  
**Merge 41: Nonlocal Attention Operator (NAO) / Nonlocal Attention Operator** → 2 papers  
**Merge 42: Factorized Self-Attention Module (FSAM) / Factorized Self-Attention Module** → 2 papers  
**Merge 43: Coarse-grained Sparsity (CSparse) / Coarse-grained Sparsity** → 2 papers  
**Merge 44: Fine-grained Sparsity (FSparse) / Fine-grained Sparsity** → 2 papers  
**Merge 45: Contextual Sparsity (CS) / Contextual Sparsity** → 2 papers  
**Merge 46: Independent Cascade (IC) model / Independent Cascade model** → 2 papers  
**Merge 47: Iteratively reweighted least squares (IRLS) / Iteratively reweighted least squares** → 2 papers  
**Merge 48: Joint Embedding Predictive Architecture (JEPA) / Joint Embedding Predictive Architectures** → 2 papers  
**Merge 49: Pretraining and finetuning (PT+FT) / Pretraining and finetuning** → 2 papers  

### Tier 4 — New alias entries

**Merge 50: SGD → Stochastic gradient descent** (Singleton 1 → Shared, raises to 6 papers, Core tier)

Additional alias additions not in Top 50 but high-value:
- PPO → Proximal Policy Optimization (4 → 5 papers, Core)
- Low-rank adaptation / Low Rank Adaptation (LoRA) → LoRA (3 → 5, Core)
- ResNets / Residual Network → ResNet (3 → 5, Core)
- Monte-Carlo Tree Search → Monte Carlo Tree Search (2 → 3)
- Graph Convolutional Networks → Graph convolutional network (4+2 → 6, Core)
- Graph neural networks → Graph Neural Networks (3+1 → 4)
- Autoencoder → Autoencoders (2+1 → 3)
- Convolutional neural networks → Convolutional neural network (CNN) (2+1 → 3)
- Direct Preference Optimization / DPO variants → 1 canonical (~5 papers, Core)
- Chain-of-Thought variants → 1 canonical (~6 papers, Core)

---

## 5. Estimated Singleton Rate After Merges

### Conservative estimate (run `--force` only, no code changes)

Fixes: ~30 case-fold drift pairs (Merges 3–30).

| Metric | Current | After --force |
|---|---|---|
| Singleton pairs merged | 0 | ~30 pairs = 60 singleton rows → 30 new Shared |
| Total distinct techniques | 1,115 | ~1,085 |
| Singleton count | 1,060 | ~1,000 |
| Singleton rate | 95.1% | **~92.2%** |
| Shared+Core count | 55 | ~85 |

### Moderate estimate (--force + regex fix + extend Pass 2 paren-strip)

Adds: ~19 paren-variant pairs (Merges 31–49) + LLM regex fix (Merge 1–2).

| Metric | Current | After moderate fixes |
|---|---|---|
| Singleton pairs merged | 0 | ~50 pairs = 100 singleton rows → 50 new Shared |
| Total distinct techniques | 1,115 | ~1,050 |
| Singleton count | 1,060 | ~960 |
| Singleton rate | 95.1% | **~91.4%** |
| Shared+Core count | 55 | ~90 |
| New Core promotions | 0 | ~2 (LLM consolidation, possibly DPO) |

### Aggressive estimate (all fixes + new alias entries)

Adds: 10 new abbreviation aliases (SGD, PPO, LoRA variants, ResNets, GCN merge, CoT merge, DPO merge).

| Metric | Current | After all fixes |
|---|---|---|
| Singleton pairs merged | 0 | ~70 pairs total |
| Total distinct techniques | 1,115 | ~1,020 |
| Singleton count | 1,060 | ~920 |
| Singleton rate | 95.1% | **~90.2%** |
| Shared+Core count | 55 | ~95–100 |
| New Core promotions | 0 | ~4–6 (SGD→6 papers, PPO→5, LoRA→5, ResNet→5, GCN→6, DPO→5) |

**Key takeaway:** Even with all normalization fixes applied, the singleton rate falls only from 95.1% to ~90%. The projected 70–80% target requires corpus expansion, not normalization alone. Corpus size is the primary driver; normalization is a multiplier.

---

## 6. Graph Connectivity Suppression from Normalization Gaps

**Yes — graph connectivity is being artificially suppressed.** The degree of suppression is quantifiable from the data.

### Direct suppression: missed shared techniques

Every pair of singletons that should be one shared technique represents a missing graph edge (or missing weight contribution to an existing edge). The 50 merge opportunities above each correspond to a technique that appears in 2 papers but is not recognized as shared.

**Estimated missing technique-weighted edge contributions:**
- ~70 merged pairs × average 1 paper pair per shared technique = ~70 missing technique-score contributions
- At the current IDF weight for newly-specialized techniques (likely SPECIALIZED tier, weight ×2), each contributes ~3–6 to edge weight
- Estimated suppressed total weight across the graph: ~210–420 weight units distributed across ~70 edges

These are not new edges in most cases — the paper pairs likely already have a category-based edge. The suppression manifests as artificially low technique_score components on existing edges, pulling average weight below the expected 1.8–2.2 range.

### Core-tier duplicate suppression: LLM/LLMs split

The "Large Language Models" (9 papers) and "Large language models (LLMs)" (7 papers) are the same technique. The graph treats them as two distinct entities. A paper pair sharing both names gets double credit. A paper pair where one paper used "LLM" and the other used "LLMs" gets zero technique credit for this shared technique.

Given that 9 + 7 = 16 total assignments likely span ~10–12 distinct papers, and C(12,2) = 66 possible pairs all sharing the same underlying technique, the LLM split alone suppresses meaningful weight on all 66 of those pairs.

### IDF tier misclassification

The IDF formula requires knowing the true paper_count for a technique. A technique appearing in 2 papers under variant names A and B has:
- A: paper_count = 1 → GENERIC or invisible (no edge contribution)
- B: paper_count = 1 → GENERIC or invisible

But as a merged canonical with paper_count = 2, it would be SHARED tier (IDF = ln(100/2) = 3.91 ≥ 3.69), receiving weight multiplier 2×. Every unmerged alias pair that should be paper_count=2 is being assigned paper_count=1 and contributing zero to graph edges.

At 70 such pairs, this represents ~70 missed SPECIALIZED-tier edge contributions that currently register as zero.

### Summary of suppression impact

| Suppression type | Estimated missing contributions | Primary effect |
|---|---|---|
| Case-fold drift (30 pairs) | ~30 missing technique edge contributions | Average weight slightly below target |
| Paren-variant gaps (50+ pairs) | ~50 missing contributions | Same |
| Missing abbreviation aliases (10) | ~10 missing contributions | Same |
| LLM/LLMs Core split | Misweighted 66+ paper pairs | Technique score inaccurate for LLM-adjacent papers |
| DPO 3-way split (6 rows → ~5 papers) | All DPO paper pairs have triple counting for some papers, zero for others | Edge weights inconsistent |

---

## 7. Recommended Normalization Improvements (Ranked by Impact)

### Rank 1 — Fix the parenthetical acronym regex (1 line change)

**Change:** In `rules.py`, line 37, change:
```python
_PAREN_ACRONYM_RE = re.compile(r"\s*\([A-Z][A-Z0-9\-]+\)\s*$")
```
to:
```python
_PAREN_ACRONYM_RE = re.compile(r"\s*\([A-Z][A-Za-z0-9\-]+\)\s*$")
```

**Why:** The current regex excludes `(LLMs)`, `(ViTs)`, `(GNNs)`, `(MLPs)` because the trailing lowercase `s` is not in `[A-Z0-9\-]`. The fix allows mixed-case acronyms.

**Impact:** Immediately fixes the LLM/LLMs split (two Core entries collapse to one), the Vision Transformers/ViTs pair, and prevents similar failures for new papers.  
**Estimated effect:** ~5 high-value merges, including the most-weighted technique in the graph.

### Rank 2 — Run `normalize_entities.py --force` once

**Why:** The `--force` flag re-processes all rows simultaneously, allowing Pass 2 to see all variants at once and assign a consistent case-fold winner. Without `--force`, incremental runs produce inconsistent canonical assignments for the same concept across papers.

**Impact:** Fixes all ~30 case-fold drift pairs (Merges 3–30). Zero code changes required.  
**Estimated singleton rate improvement:** 95.1% → ~92%.  
**Action:** Run once after the regex fix above.

### Rank 3 — Extend Pass 2 to strip parenthetical acronyms before grouping

**Change:** In `rules.py`, `case_fold_canonical()`, compute the group key as:
```python
key = _PAREN_ACRONYM_RE.sub("", name).strip().lower()
```
instead of `name.lower()`.

**Why:** This collapses `"Multi-Head Attention (MHA)"` and `"Multi-Head Attention"` into the same group without requiring an alias entry for every such pair. New papers that introduce novel techniques with parenthetical acronyms will automatically merge with their bare-name equivalents.

**Impact:** Fixes ~50–60 singleton pairs (Merges 31–49 plus future extractions). After this change + Rank 2 run, approximately 100 singleton pairs collapse.  
**Estimated singleton rate improvement:** ~91% after Rank 2 alone → ~89% after this fix.

### Rank 4 — Add missing abbreviation-to-canonical alias entries

**Add to `normalize/technique_aliases.json`:**

```json
"=== GROUP: Common abbreviations ===": null,
"sgd":                              "Stochastic gradient descent",
"ppo":                              "Proximal Policy Optimization",
"recurrent ppo":                    "Proximal Policy Optimization",
"low rank adaptation":              "LoRA",
"low-rank adaptation":              "LoRA",
"low rank adaptation (lora)":       "LoRA",
"resnets":                          "ResNet",
"residual network":                 "ResNet",
"monte-carlo tree search":          "Monte Carlo Tree Search",
"autoencoder":                      "Autoencoders",
"convolutional neural networks":    "Convolutional neural network (CNN)",
"graph neural networks":            "Graph Neural Networks",
"graph convolutional networks":     "Graph convolutional network",

"=== GROUP: DPO unification ===": null,
"direct preference optimization":       "Direct Preference Optimization",
"direct preference optimization (dpo)": "Direct Preference Optimization",

"=== GROUP: Chain-of-Thought unification ===": null,
"chain-of-thought (cot)":          "Chain-of-Thought",
"chain-of-thought prompting":      "Chain-of-Thought",
"chain-of-thought (cot) prompting": "Chain-of-Thought",
"few-shot cot":                    "Chain-of-Thought",

"=== GROUP: Supervised fine-tuning unification ===": null,
"supervised finetuning":           "Supervised fine-tuning",
"supervised fine-tuning (sft)":    "Supervised fine-tuning"
```

**Impact:** Promotes SGD (6 papers → Core), PPO (5 papers → Core), LoRA (5 papers → Core), ResNet (5 papers → Core), GCN (6 papers → Core). Collapses DPO to 1 canonical (~5 papers, Core), CoT to 1 canonical (~6 papers, Core). Estimated 6 new Core promotions.

**Estimated singleton rate improvement:** ~89% → ~87–88%.

### Rank 5 — Add plural/singular alias entries for common technique families

**Add to alias file:**

```json
"=== GROUP: Singular/plural technique names ===": null,
"resnet":                    "ResNet",
"multilayer perceptron":     "Multilayer perceptrons",
"multi-layer perceptrons":   "Multilayer perceptrons",
"multi-layer perceptron (mlp)": "Multilayer perceptrons",
"normalizing flow":          "Normalizing flows",
"recurrent neural network":  "Recurrent neural networks",
"recurrent neural network (rnn)": "Recurrent neural networks"
```

**Impact:** Addresses the MLP cluster (currently 2 Shared + 3 Singletons → 1 Shared, ~5 papers).  
**Estimated additional improvement:** ~5–8 merges.

---

## 8. Summary

| Fix | Type | Effort | New Shared created | Singleton rate after |
|---|---|---|---|---|
| Fix paren regex (LLMs, ViTs, etc.) | Code, 1 line | Minutes | ~5 | 95.0% |
| Run --force | CLI only | Minutes | ~30 | ~92.2% |
| Extend Pass 2 paren-strip | Code, 3 lines | 30 min | ~50 | ~89.5% |
| Add abbreviation aliases (SGD, PPO, etc.) | JSON only | 1 hour | ~15 + 6 Core | ~88.5% |
| Add plural/singular aliases | JSON only | 1 hour | ~8 | ~87.5% |
| **All fixes combined** | | **~2 hours** | **~110** | **~87–88%** |

**The 70–80% singleton rate target is not achievable through normalization alone at 100 papers.** Even with perfect alias coverage, most NeurIPS-specific technique names (e.g., LACIE, CIPHER, COTACS, NeuralSteiner) are genuinely unique to one paper. The 87–88% achievable floor represents the true lower bound for a 100-paper corpus. The remaining ~7–8 pp gap between the achievable floor and the 80% target requires Phase 1 corpus expansion (~300 additional papers) where many currently-singleton techniques will gain a second paper match.

**The graph connectivity suppression is real but bounded.** Fixing all normalization gaps recovers ~70–100 missing technique-weighted edge contributions, raising the average edge weight by an estimated 0.1–0.2 toward the 1.8–2.2 target. The majority of the weight gap is still corpus-size-driven.
