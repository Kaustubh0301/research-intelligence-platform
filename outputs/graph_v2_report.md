# Graph V2 Report

> IDF-weighted technique edges. Read-only comparison vs Graph V1.

## Summary: V1 vs V2

| Metric | V1 | V2 | Δ |
| --- | --- | --- | --- |
| Paper edges | 2916 | 2929 | +13 ▲ |
| Average edge weight | 1.625 | 1.607 | -0.02 ▼ |
| Max edge weight | 15.0 | 15.0 | +0.0 |
| Clusters | 3 | 3 | +0 |
| Isolated papers | 0 | 0 | +0 |

## Edge Weight Distribution

| Weight Range | V1 edges | V2 edges | Δ |
| --- | --- | --- | --- |
| 0–1 | 0 | 15 | +15 |
| 1–2 | 1909 | 1917 | +8 |
| 2–4 | 843 | 846 | +3 |
| 4–8 | 140 | 128 | -12 |
| 8+ | 24 | 23 | -1 |

> IDF weighting redistributes technique edges downward for GENERIC entities (LLMs, Transformers) and upward for SPECIALIZED entities. Expect a shift from higher buckets toward mid-range.

## Score Component Breakdown (V2)

Technique, dataset, and category scores stored per edge. Methodology score not stored separately (included in final weight).

| Score Component | Sum across all edges | Mean per edge |
| --- | --- | --- |
| Technique (IDF-weighted) | 63.75 | 6.375 |
| Dataset (flat ×2) | 14.00 | 1.400 |
| Category (flat ×1) | 21.00 | 2.100 |

*Shown for top-10 edges only. Full breakdown available in DB.*

## Top 10 Strongest Paper Pairs (V2)

**1. weight = 15.00**  (technique=3.00 / dataset=10.00 / category=2.00)

- A: Reducing Transformer Key-Value Cache Size with Cross-Layer Attention

- B: Communication Efficient Distributed Training with Distributed Lion

- Shared techniques: AdamW optimizer

- Shared categories: Efficiency, LLM


**2. weight = 12.00**  (technique=9.00 / dataset=0.00 / category=2.00)

- A: Low-Rank Optimal Transport through Factor Relaxation with Latent Coupling

- B: Bisimulation Metrics are Optimal Transport Distances, and Can be Computed Efficiently

- Shared techniques: Optimal transport, Sinkhorn algorithm

- Shared categories: Efficiency, Theory


**3. weight = 12.00**  (technique=9.00 / dataset=0.00 / category=1.00)

- A: Dynamics of Supervised and Reinforcement Learning in the Non-Linear Perceptron

- B: Towards Effective Planning Strategies for Dynamic Opinion Networks

- Shared techniques: Reinforcement learning, Supervised learning

- Shared categories: RL


**4. weight = 12.00**  (technique=6.00 / dataset=2.00 / category=1.00)

- A: Non-asymptotic Convergence of Training Transformers for Next-token Prediction

- B: The Implicit Bias of Gradient Descent on Separable Multiclass Data

- Shared techniques: Cross-entropy loss

- Shared categories: Theory


**5. weight = 11.00**  (technique=6.00 / dataset=2.00 / category=3.00)

- A: Multistep Distillation of Diffusion Models via Moment Matching

- B: On improved Conditioning Mechanisms and Pre-training Strategies for Diffusion Models

- Shared techniques: classifier-free guidance

- Shared categories: Efficiency, Generative, Vision


**6. weight = 10.00**  (technique=6.00 / dataset=0.00 / category=3.00)

- A: Learning to Reason via Program Generation, Emulation, and Search

- B: Can Models Learn Skill Composition from Examples?

- Shared techniques: GPT-4, Llama-2

- Shared categories: Generative, LLM, NLP


**7. weight = 9.75**  (technique=6.75 / dataset=0.00 / category=3.00)

- A: Non-asymptotic Convergence of Training Transformers for Next-token Prediction

- B: Normalization Layer Per-Example Gradients are Sufficient to Predict Gradient Noise Scale in Transformers

- Shared techniques: Transformer architecture, Transformers

- Shared categories: LLM, NLP, Theory


**8. weight = 9.00**  (technique=6.00 / dataset=0.00 / category=2.00)

- A: Inductive biases of multi-task learning and finetuning: multiple regimes of feature reuse

- B: Beyond the Doors of Perception: Vision Transformers Represent Relations Between Objects

- Shared techniques: Vision Transformers

- Shared categories: Theory, Vision


**9. weight = 9.00**  (technique=6.00 / dataset=0.00 / category=2.00)

- A: LACIE: Listener-Aware Finetuning for Calibration in Large Language Models

- B: Can Models Learn Skill Composition from Examples?

- Shared techniques: Mistral-7B

- Shared categories: LLM, NLP


**10. weight = 9.00**  (technique=6.00 / dataset=0.00 / category=2.00)

- A: Limits of Transformer Language Models on Learning to Compose Algorithms

- B: Learning to Reason via Program Generation, Emulation, and Search

- Shared techniques: Chain-of-Thought prompting, GPT-4

- Shared categories: LLM, NLP


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

- A: LACIE: Listener-Aware Finetuning for Calibration in Large Language Models

- B: A Critical Evaluation of AI Feedback for Aligning Large Language Models

- Shared: Direct Preference Optimization (DPO)


**6. weight = 11.00**

- A: Multistep Distillation of Diffusion Models via Moment Matching

- B: On improved Conditioning Mechanisms and Pre-training Strategies for Diffusion Models

- Shared: Classifier-free guidance


**7. weight = 10.00**

- A: Learning to Reason via Program Generation, Emulation, and Search

- B: Can Models Learn Skill Composition from Examples?

- Shared: GPT-4, Llama-2


**8. weight = 9.75**

- A: Non-asymptotic Convergence of Training Transformers for Next-token Prediction

- B: Normalization Layer Per-Example Gradients are Sufficient to Predict Gradient Noise Scale in Transformers

- Shared: Transformer architecture, Transformers


**9. weight = 9.50**

- A: Aligning LLM Agents by Learning Latent Preference from User Edits

- B: Toward Self-Improvement of LLMs via Imagination, Searching, and Criticizing

- Shared: Chain-of-Thought, Chain-of-Thought (CoT), Large Language Models, Large language models (LLMs)


**10. weight = 9.00**

- A: A Critical Evaluation of AI Feedback for Aligning Large Language Models

- B: What Makes and Breaks Safety Fine-tuning? A Mechanistic Study

- Shared: Direct preference optimization


## Top 10 Papers by Betweenness Centrality

| Rank | Paper (truncated) | V2 BC | V2 Cluster | V2 Neighbors |
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

### V1 Centrality (for comparison)

| Rank | Paper (truncated) | V1 BC | V1 Cluster | V1 Neighbors |
| --- | --- | --- | --- | --- |
| 1 | Bisimulation Metrics are Optimal Transport Distances, and Ca | 0.0248 | 0 | 79 |
| 2 | Normalization Layer Per-Example Gradients are Sufficient to  | 0.0192 | 2 | 89 |
| 3 | Beyond the Doors of Perception: Vision Transformers Represen | 0.0178 | 1 | 81 |
| 4 | On the Inductive Bias of Stacking Towards Improving Reasonin | 0.0172 | 2 | 87 |
| 5 | Low-Rank Optimal Transport through Factor Relaxation with La | 0.0172 | 0 | 80 |
| 6 | Fairness in Social Influence Maximization via Optimal Transp | 0.0157 | 0 | 72 |
| 7 | Learning to grok: Emergence of in-context learning and skill | 0.0152 | 2 | 79 |
| 8 | Safe Time-Varying Optimization based on Gaussian Processes w | 0.0150 | 0 | 68 |
| 9 | Accelerating ERM for data-driven algorithm design using outp | 0.0148 | 0 | 74 |
| 10 | Mutual Information Estimation via Normalizing Flows | 0.0148 | 0 | 71 |

## Cluster Comparison

| Cluster ID | V1 size | V2 size |
| --- | --- | --- |
| 0 | 46 | 44 |
| 1 | 30 | 31 |
| 2 | 24 | 25 |

## Interpretation

**Centrality changes:**

Papers entering top-10 BC under V2 (not in V1 top-10):

- Generalization Analysis for Label-Specific Representation Learning

- Multi-Group Proportional Representation in Retrieval

- Nonlocal Attention Operator: Materializing Hidden Knowledge Towards Interpretabl

- Boosting Sample Efficiency and Generalization in Multi-agent Reinforcement Learn

- Tangent Space Causal Inference: Leveraging Vector Fields for Causal Discovery in


Papers leaving top-10 BC under V2:

- On the Inductive Bias of Stacking Towards Improving Reasoning

- Low-Rank Optimal Transport through Factor Relaxation with Latent Coupling

- Fairness in Social Influence Maximization via Optimal Transport

- Safe Time-Varying Optimization based on Gaussian Processes with Spatio-Temporal 

- Accelerating ERM for data-driven algorithm design using output-sensitive techniq


**Weight distribution shift:**

- Edges with weight ≥ 4: 164 → 151 (-13)
- Edges with weight < 2: 1909 → 1932 (+23)
- Average weight: 1.625 → 1.607 (-0.018)


**IDF formula applied:**

```
idf(t) = ln(N / paper_count(t))
GENERIC     idf < 3.00  →  base_weight × 0.25
SHARED      idf < 3.69  →  base_weight × 1.00
SPECIALIZED idf ≥ 3.69  →  base_weight × 2.00
```
