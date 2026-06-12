# Graph V2 Report

> IDF-weighted technique edges. Read-only comparison vs Graph V1.

## Summary: V1 vs V2

| Metric | V1 | V2 | Δ |
| --- | --- | --- | --- |
| Paper edges | 2929 | 15978 | +13049 ▲ |
| Average edge weight | 1.607 | 1.563 | -0.04 ▼ |
| Max edge weight | 15.0 | 26.0 | +11.0 ▼ |
| Clusters | 3 | 3 | +0 |
| Isolated papers | 0 | 0 | +0 |

## Edge Weight Distribution

| Weight Range | V1 edges | V2 edges | Δ |
| --- | --- | --- | --- |
| 0–1 | 15 | 0 | -15 |
| 1–2 | 1917 | 11704 | +9787 |
| 2–4 | 846 | 3395 | +2549 |
| 4–8 | 128 | 604 | +476 |
| 8+ | 23 | 275 | +252 |

> IDF weighting redistributes technique edges downward for GENERIC entities (LLMs, Transformers) and upward for SPECIALIZED entities. Expect a shift from higher buckets toward mid-range.

## Score Component Breakdown (V2)

Technique, dataset, and category scores stored per edge. Methodology score not stored separately (included in final weight).

| Score Component | Sum across all edges | Mean per edge |
| --- | --- | --- |
| Technique (IDF-weighted) | 144.00 | 14.400 |
| Dataset (flat ×2) | 22.00 | 2.200 |
| Category (flat ×1) | 19.00 | 1.900 |

*Shown for top-10 edges only. Full breakdown available in DB.*

## Top 10 Strongest Paper Pairs (V2)

**1. weight = 26.00**  (technique=18.00 / dataset=6.00 / category=2.00)

- A: RECOMP: Improving Retrieval-Augmented LMs with Context Compression and Selective Augmentation

- B: SuRe: Summarizing Retrievals using Answer Candidates for Open-domain QA of LLMs

- Shared techniques: BM25, Contriever, DPR

- Shared categories: LLM, Retrieval


**2. weight = 23.00**  (technique=18.00 / dataset=2.00 / category=2.00)

- A: Improving Generalization of Alignment with Human Preferences through Group Invariant Learning

- B: A Critical Evaluation of AI Feedback for Aligning Large Language Models

- Shared techniques: Direct Preference Optimization, Proximal Policy Optimization, Supervised fine-tuning

- Shared categories: LLM, RL


**3. weight = 22.00**  (technique=18.00 / dataset=0.00 / category=3.00)

- A: Limits of Transformer Language Models on Learning to Compose Algorithms

- B: Learning to Reason via Program Generation, Emulation, and Search

- Shared techniques: Chain-of-Thought prompting, GPT-4, In-context learning

- Shared categories: Code, LLM, NLP


**4. weight = 21.00**  (technique=18.00 / dataset=0.00 / category=2.00)

- A: Aligning LLM Agents by Learning Latent Preference from User Edits

- B: Limits of Transformer Language Models on Learning to Compose Algorithms

- Shared techniques: Chain-of-Thought, Chain-of-thought prompting, In-context learning

- Shared categories: LLM, NLP


**5. weight = 18.00**  (technique=15.00 / dataset=2.00 / category=1.00)

- A: Better by default: Strong pre-tuned MLPs and boosted trees on tabular data

- B: TabR: Tabular Deep Learning Meets Nearest Neighbors

- Shared techniques: Gradient-boosted decision trees, Multilayer perceptrons, TabR

- Shared categories: Efficiency


**6. weight = 18.00**  (technique=6.00 / dataset=10.00 / category=2.00)

- A: Reducing Transformer Key-Value Cache Size with Cross-Layer Attention

- B: Communication Efficient Distributed Training with Distributed Lion

- Shared techniques: AdamW optimizer

- Shared categories: Efficiency, LLM


**7. weight = 17.00**  (technique=15.00 / dataset=0.00 / category=1.00)

- A: Aligning LLM Agents by Learning Latent Preference from User Edits

- B: Detecting Bugs with Substantial Monetary Consequences by LLM and Rule-based Reasoning

- Shared techniques: Chain-of-Thought, Large Language Models, Large language models

- Shared categories: LLM


**8. weight = 16.00**  (technique=12.00 / dataset=0.00 / category=3.00)

- A: Learning to Reason via Program Generation, Emulation, and Search

- B: Can Models Learn Skill Composition from Examples?

- Shared techniques: GPT-4, Llama-2

- Shared categories: Generative, LLM, NLP


**9. weight = 15.00**  (technique=12.00 / dataset=2.00 / category=1.00)

- A: Universality of AdaGrad Stepsizes for Stochastic Optimization: Inexact Oracle, Acceleration and Variance Reduction

- B: Universality in Transfer Learning for Linear Models

- Shared techniques: Stochastic Gradient Descent, Stochastic gradient descent

- Shared categories: Theory


**10. weight = 15.00**  (technique=12.00 / dataset=0.00 / category=2.00)

- A: Low-Rank Optimal Transport through Factor Relaxation with Latent Coupling

- B: Bisimulation Metrics are Optimal Transport Distances, and Can be Computed Efficiently

- Shared techniques: Optimal transport, Sinkhorn algorithm

- Shared categories: Efficiency, Theory


## Top 10 Strongest Paper Pairs (V1, for comparison)

**1. weight = 15.00**

- A: Reducing Transformer Key-Value Cache Size with Cross-Layer Attention

- B: Communication Efficient Distributed Training with Distributed Lion

- Shared: AdamW optimizer


**2. weight = 12.00**

- A: Low-Rank Optimal Transport through Factor Relaxation with Latent Coupling

- B: Bisimulation Metrics are Optimal Transport Distances, and Can be Computed Efficiently

- Shared: Optimal transport, Sinkhorn algorithm


**3. weight = 12.00**

- A: Dynamics of Supervised and Reinforcement Learning in the Non-Linear Perceptron

- B: Towards Effective Planning Strategies for Dynamic Opinion Networks

- Shared: Reinforcement learning, Supervised learning


**4. weight = 12.00**

- A: Non-asymptotic Convergence of Training Transformers for Next-token Prediction

- B: The Implicit Bias of Gradient Descent on Separable Multiclass Data

- Shared: Cross-entropy loss


**5. weight = 11.00**

- A: Multistep Distillation of Diffusion Models via Moment Matching

- B: On improved Conditioning Mechanisms and Pre-training Strategies for Diffusion Models

- Shared: classifier-free guidance


**6. weight = 10.00**

- A: Learning to Reason via Program Generation, Emulation, and Search

- B: Can Models Learn Skill Composition from Examples?

- Shared: GPT-4, Llama-2


**7. weight = 9.75**

- A: Non-asymptotic Convergence of Training Transformers for Next-token Prediction

- B: Normalization Layer Per-Example Gradients are Sufficient to Predict Gradient Noise Scale in Transformers

- Shared: Transformer architecture, Transformers


**8. weight = 9.00**

- A: Inductive biases of multi-task learning and finetuning: multiple regimes of feature reuse

- B: Beyond the Doors of Perception: Vision Transformers Represent Relations Between Objects

- Shared: Vision Transformers


**9. weight = 9.00**

- A: LACIE: Listener-Aware Finetuning for Calibration in Large Language Models

- B: Can Models Learn Skill Composition from Examples?

- Shared: Mistral-7B


**10. weight = 9.00**

- A: Limits of Transformer Language Models on Learning to Compose Algorithms

- B: Learning to Reason via Program Generation, Emulation, and Search

- Shared: Chain-of-Thought prompting, GPT-4


## Top 10 Papers by Betweenness Centrality

| Rank | Paper (truncated) | V2 BC | V2 Cluster | V2 Neighbors |
| --- | --- | --- | --- | --- |
| 1 | Learning to grok: Emergence of in-context learning and skill | 0.0078 | 0 | 184 |
| 2 | Abstractors and relational cross-attention: An inductive bia | 0.0076 | 0 | 180 |
| 3 | In-Context Learning Dynamics with Random Binary Sequences | 0.0076 | 0 | 179 |
| 4 | Understanding In-Context Learning in Transformers and LLMs b | 0.0074 | 0 | 181 |
| 5 | In-Context Learning through the Bayesian Prism | 0.0069 | 0 | 196 |
| 6 | Attack-Aware Noise Calibration for Differential Privacy | 0.0069 | 2 | 204 |
| 7 | Is This the Subspace You Are Looking for? An Interpretabilit | 0.0068 | 0 | 189 |
| 8 | Realistic Evaluation of Semi-supervised Learning Algorithms  | 0.0067 | 2 | 195 |
| 9 | Fairness in Social Influence Maximization via Optimal Transp | 0.0063 | 1 | 165 |
| 10 | Towards Faithful Explanations: Boosting Rationalization with | 0.0063 | 1 | 165 |

### V1 Centrality (for comparison)

| Rank | Paper (truncated) | V1 BC | V1 Cluster | V1 Neighbors |
| --- | --- | --- | --- | --- |
| 1 | Generalization Analysis for Label-Specific Representation Le | 0.0309 | 0 | 60 |
| 2 | Multi-Group Proportional Representation in Retrieval | 0.0217 | 1 | 52 |
| 3 | Bisimulation Metrics are Optimal Transport Distances, and Ca | 0.0211 | 0 | 79 |
| 4 | Nonlocal Attention Operator: Materializing Hidden Knowledge  | 0.0173 | 1 | 75 |
| 5 | Beyond the Doors of Perception: Vision Transformers Represen | 0.0163 | 1 | 81 |
| 6 | Boosting Sample Efficiency and Generalization in Multi-agent | 0.0155 | 0 | 49 |
| 7 | Normalization Layer Per-Example Gradients are Sufficient to  | 0.0155 | 2 | 89 |
| 8 | Tangent Space Causal Inference: Leveraging Vector Fields for | 0.0154 | 0 | 60 |
| 9 | Learning to grok: Emergence of in-context learning and skill | 0.0143 | 2 | 79 |
| 10 | Mutual Information Estimation via Normalizing Flows | 0.0143 | 0 | 71 |

## Cluster Comparison

| Cluster ID | V1 size | V2 size |
| --- | --- | --- |
| 0 | 44 | 91 |
| 1 | 31 | 89 |
| 2 | 25 | 70 |

## Interpretation

**Centrality changes:**

Papers entering top-10 BC under V2 (not in V1 top-10):

- Abstractors and relational cross-attention: An inductive bias for explicit relat

- In-Context Learning Dynamics with Random Binary Sequences

- Understanding In-Context Learning in Transformers and LLMs by Learning to Learn 

- In-Context Learning through the Bayesian Prism

- Attack-Aware Noise Calibration for Differential Privacy

- Is This the Subspace You Are Looking for? An Interpretability Illusion for Subsp

- Realistic Evaluation of Semi-supervised Learning Algorithms in Open Environments

- Fairness in Social Influence Maximization via Optimal Transport

- Towards Faithful Explanations: Boosting Rationalization with Shortcuts Discovery


Papers leaving top-10 BC under V2:

- Generalization Analysis for Label-Specific Representation Learning

- Multi-Group Proportional Representation in Retrieval

- Bisimulation Metrics are Optimal Transport Distances, and Can be Computed Effici

- Nonlocal Attention Operator: Materializing Hidden Knowledge Towards Interpretabl

- Beyond the Doors of Perception: Vision Transformers Represent Relations Between 

- Boosting Sample Efficiency and Generalization in Multi-agent Reinforcement Learn

- Normalization Layer Per-Example Gradients are Sufficient to Predict Gradient Noi

- Tangent Space Causal Inference: Leveraging Vector Fields for Causal Discovery in

- Mutual Information Estimation via Normalizing Flows


**Weight distribution shift:**

- Edges with weight ≥ 4: 151 → 879 (+728)
- Edges with weight < 2: 1932 → 11704 (+9772)
- Average weight: 1.607 → 1.563 (-0.044)


**IDF formula applied:**

```
idf(t) = ln(N / paper_count(t))
GENERIC     idf < 3.00  →  base_weight × 0.25
SHARED      idf < 3.69  →  base_weight × 1.00
SPECIALIZED idf ≥ 3.69  →  base_weight × 2.00
```
