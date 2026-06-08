# Entity Signal Audit — `paper_techniques`

> Read-only. No schema changes.

## Tier Summary

| Tier | Threshold | Count | % of total techniques | Total graph_degree_contrib |
| --- | --- | --- | --- | --- |
| Core | paper_count ≥ 5 | 7 | 0.7% | 123 |
| Shared | paper_count ≥ 2 | 43 | 4.3% | 91 |
| Singleton | paper_count = 1 | 948 | 95.0% | 0 |

## Graph Degree Contribution

Of the 214 technique-attributed graph contributions across all 50 techniques that appear in any edge:

- **Core** techniques account for **57.5%** of edge contributions
- **Shared** techniques: **42.5%**
- **Singleton** techniques: **0.0%**


## Core Techniques (7 — paper_count ≥ 5)

High-signal entities: appear in many papers and drive most cross-paper edges. These are the candidates for IDF down-weighting in graph v2.

| Canonical Name | Papers | % Papers | Graph Degree Contrib |
| --- | --- | --- | --- |
| Large Language Models | 9 | 9.0% | 36 |
| Multilayer perceptrons | 7 | 7.0% | 21 |
| Transformers | 7 | 7.0% | 21 |
| Diffusion Models | 6 | 6.0% | 15 |
| Chain-of-Thought | 5 | 5.0% | 10 |
| Graph convolutional network | 5 | 5.0% | 10 |
| Stochastic gradient descent | 5 | 5.0% | 10 |

## Shared Techniques (43 — paper_count ≥ 2)

Medium-signal entities: appear in at least 2 papers. Useful for cross-paper edges but less dominant than Core. These should retain current graph weight; IDF will naturally boost them relative to Core.

| Canonical Name | Papers | % Papers | Graph Degree Contrib |
| --- | --- | --- | --- |
| AdamW optimizer | 4 | 4.0% | 6 |
| GPT-4 | 4 | 4.0% | 6 |
| In-context learning | 4 | 4.0% | 6 |
| LoRA | 4 | 4.0% | 6 |
| Proximal Policy Optimization | 4 | 4.0% | 6 |
| ResNet | 4 | 4.0% | 6 |
| Chain-of-Thought prompting | 3 | 3.0% | 3 |
| Direct Preference Optimization | 3 | 3.0% | 3 |
| Gradient descent | 3 | 3.0% | 3 |
| Graph Neural Networks | 3 | 3.0% | 3 |
| Llama-2 | 3 | 3.0% | 3 |
| Normalizing flows | 3 | 3.0% | 3 |
| Optimal transport | 3 | 3.0% | 3 |
| Principal component analysis (PCA) | 3 | 3.0% | 3 |
| Reinforcement learning | 3 | 3.0% | 3 |
| Autoencoders | 2 | 2.0% | 1 |
| CodeLlama | 2 | 2.0% | 1 |
| Convolutional neural network (CNN) | 2 | 2.0% | 1 |
| Cross-entropy loss | 2 | 2.0% | 1 |
| Deep Reinforcement Learning | 2 | 2.0% | 1 |
| Dynamic programming | 2 | 2.0% | 1 |
| Empirical risk minimization | 2 | 2.0% | 1 |
| Generative models | 2 | 2.0% | 1 |
| LLaMA | 2 | 2.0% | 1 |
| Language models | 2 | 2.0% | 1 |
| Latent diffusion models | 2 | 2.0% | 1 |
| Linear probing | 2 | 2.0% | 1 |
| Linear programming | 2 | 2.0% | 1 |
| Markov Decision Process | 2 | 2.0% | 1 |
| Mistral-7B | 2 | 2.0% | 1 |
| Monte Carlo Tree Search | 2 | 2.0% | 1 |
| Multi-Agent Reinforcement Learning | 2 | 2.0% | 1 |
| Neural networks | 2 | 2.0% | 1 |
| Sinkhorn algorithm | 2 | 2.0% | 1 |
| Stable Diffusion | 2 | 2.0% | 1 |
| Supervised fine-tuning | 2 | 2.0% | 1 |
| Supervised learning | 2 | 2.0% | 1 |
| Taylor expansion | 2 | 2.0% | 1 |
| Transformer architecture | 2 | 2.0% | 1 |
| U-Net | 2 | 2.0% | 1 |
| Vision Transformers | 2 | 2.0% | 1 |
| classifier-free guidance | 2 | 2.0% | 1 |
| k-means++ | 2 | 2.0% | 1 |

## Singleton Techniques (948 — paper_count = 1)

Low-signal entities for the graph: they appear in only one paper so they can never create a cross-paper edge. Their current graph_degree_contrib is 0 for almost all. Decision needed: keep for search/display, or prune from graph weighting.

Remaining **948 singletons** have graph_degree_contrib = 0. Not listed individually (see CSV).

## Key Observations

**Top 5 techniques by graph degree contribution** (these single-handedly connect the most paper pairs):

| Canonical Name | Tier | Papers | Graph Degree Contrib |
| --- | --- | --- | --- |
| Large Language Models | Core | 9 | 36 |
| Multilayer perceptrons | Core | 7 | 21 |
| Transformers | Core | 7 | 21 |
| Diffusion Models | Core | 6 | 15 |
| Chain-of-Thought | Core | 5 | 10 |

- **948 singletons (95%)** — these cannot contribute to cross-paper edges at current corpus size. With a larger corpus, some will graduate to Shared or Core.
- **7 Core entities** drive the majority of graph connectivity. IDF weighting will down-weight these, giving Shared entities more relative influence.
- **0 singletons appear in graph edges** — indicates the graph was built before the latest normalization pass ran; rebuild graph to fix.
