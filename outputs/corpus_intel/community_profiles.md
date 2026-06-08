# Community Profiles — NeurIPS 2024

**Generated:** 2026-06-05 07:15 UTC
**Corpus:** 100 papers · 1 conference · 1 year (NeurIPS 2024)
**Clusters:** 3 (detected by greedy modularity on Graph V2)

> ⚠ **Snapshot only.** Community structure at N=100 is coarse.
> With 3 clusters, two large and one satellite, boundaries are broad.
> Profiles will differentiate substantially after corpus expansion.

---

## Cluster Overview

| Cluster | Label | Papers | Avg citations | Avg betweenness | Cohesion ratio |
|---|---|---:|---:|---:|---:|
| 0 | Theory-dominated | 53 | 8.7 | 0.00708 | 1.090 |
| 1 | LLM + Vision | 45 | 68.4 | 0.00582 | 1.325 |
| 2 | Satellite (RL + Robotics) | 2 | 22.5 | 0.00096 | 0.889 |

---

## Community Identities

| Cluster | Identity |
|---|---|
| Cluster 0 | Theory-dominated research community focused on stochastic gradient descent and optimal transport with foundational theoretical focus (low citation count). |
| Cluster 1 | LLM and Vision research community focused on in-context learning and adamw optimizer with high external impact (avg 68 citations). |
| Cluster 2 | Satellite cluster: RL and Robotics (2 papers — insufficient for stable profiling). |

---

## Bridge Papers

38 papers have bridge\_strength ≥ 0.3
(at least 30% of their edges connect to papers in other clusters).
Full list in `community_bridges.csv`.

---

## Cluster 0 — Theory-dominated


> Theory-dominated research community focused on stochastic gradient descent and optimal transport with foundational theoretical focus (low citation count).

### Overview

| Metric | Value |
|---|---|
| Papers | 53 |
| Average citations | 8.7 |
| Average betweenness centrality | 0.00708 |
| Average degree centrality | 0.5916 |
| Intra-cluster avg edge weight | 1.319 |
| Inter-cluster avg edge weight | 1.210 |
| Cohesion ratio (intra/inter) | 1.090 |
| Bridge papers (strength ≥ 0.3) | 14 |

### Dominant Categories

| Category | Papers | % of cluster |
|---|---:|---:|
| Theory | 48 | 91% |
| Graph | 12 | 23% |
| Vision | 7 | 13% |
| Efficiency | 7 | 13% |
| RL | 5 | 9% |
| Biomedical | 4 | 8% |
| Safety | 3 | 6% |
| LLM | 3 | 6% |

### Dominant Techniques (SHARED / SPECIALIZED IDF tier)

| Technique | Papers in cluster |
|---|---:|
| Stochastic gradient descent | 2 |
| Optimal transport | 2 |
| Neural networks | 2 |
| Multi-Agent Reinforcement Learning | 2 |
| Gradient descent | 2 |
| Cross-entropy loss | 2 |
| weight rescaling | 1 |
| weight noise | 1 |

> **GENERIC tier** (suppressed in identity, shown for completeness): Transformers (2p)

### Top 5 Papers by Betweenness Centrality

| Title | Betweenness | Citations |
|---|---:|---:|
| Beyond the Doors of Perception: Vision Transformers Represent Relations… | 0.02310 | 17 |
| Bisimulation Metrics are Optimal Transport Distances, and Can be Comput… | 0.02191 | 6 |
| Dynamic Rescaling for Training GNNs | 0.01703 | 2 |
| Low-Rank Optimal Transport through Factor Relaxation with Latent Coupli… | 0.01703 | 0 |
| Attack-Aware Noise Calibration for Differential Privacy | 0.01685 | 18 |

### Top Bridge Papers (highest bridge\_strength)

Bridge strength = cross-cluster edges ÷ total neighbors.

| Title | Cross-cluster edges | Bridge strength | Betweenness |
|---|---:|---:|---:|
| Boosting Sample Efficiency and Generalization in Multi-agen… | 22 | 0.56 | 0.01287 |
| Beyond the Doors of Perception: Vision Transformers Represe… | 31 | 0.40 | 0.02310 |
| Inductive biases of multi-task learning and finetuning: mul… | 30 | 0.39 | 0.01036 |
| Unified Insights: Harnessing Multi-modal Data for Phenotype… | 8 | 0.38 | 0.00352 |
| Non-asymptotic Convergence of Training Transformers for Nex… | 28 | 0.37 | 0.00733 |
---## Cluster 1 — LLM + Vision


> LLM and Vision research community focused on in-context learning and adamw optimizer with high external impact (avg 68 citations).

### Overview

| Metric | Value |
|---|---|
| Papers | 45 |
| Average citations | 68.4 |
| Average betweenness centrality | 0.00582 |
| Average degree centrality | 0.4285 |
| Intra-cluster avg edge weight | 1.560 |
| Inter-cluster avg edge weight | 1.177 |
| Cohesion ratio (intra/inter) | 1.325 |
| Bridge papers (strength ≥ 0.3) | 22 |

### Dominant Categories

| Category | Papers | % of cluster |
|---|---:|---:|
| LLM | 23 | 51% |
| Vision | 17 | 38% |
| Generative | 15 | 33% |
| Efficiency | 15 | 33% |
| Safety | 11 | 24% |
| NLP | 11 | 24% |
| Theory | 7 | 16% |
| Code | 5 | 11% |

### Dominant Techniques (SHARED / SPECIALIZED IDF tier)

| Technique | Papers in cluster |
|---|---:|
| In-context learning | 3 |
| AdamW optimizer | 3 |
| Monte Carlo Tree Search | 2 |
| Language models | 2 |
| Generative models | 2 |
| Direct preference optimization | 2 |
| Chain-of-Thought | 2 |
| ηMCTS | 1 |

> **GENERIC tier** (suppressed in identity, shown for completeness): Large Language Models (9p), Transformers (5p), Diffusion Models (5p)

### Top 5 Papers by Betweenness Centrality

| Title | Betweenness | Citations |
|---|---:|---:|
| Incentivizing Quality Text Generation via Statistical Contracts | 0.02589 | 15 |
| Normalization Layer Per-Example Gradients are Sufficient to Predict Gra… | 0.02123 | 5 |
| Learning to grok: Emergence of in-context learning and skill compositio… | 0.01632 | 48 |
| Communication Efficient Distributed Training with Distributed Lion | 0.01609 | 18 |
| The Power of Resets in Online Reinforcement Learning | 0.01153 | 13 |

### Top Bridge Papers (highest bridge\_strength)

Bridge strength = cross-cluster edges ÷ total neighbors.

| Title | Cross-cluster edges | Bridge strength | Betweenness |
|---|---:|---:|---:|
| The Power of Resets in Online Reinforcement Learning | 52 | 0.87 | 0.01153 |
| Emergence of Hidden Capabilities: Exploring Learning Dynami… | 48 | 0.72 | 0.00589 |
| Learning to grok: Emergence of in-context learning and skil… | 48 | 0.66 | 0.01632 |
| An Analysis of Tokenization: Transformers under Markov Data | 48 | 0.64 | 0.00643 |
| Communication Efficient Distributed Training with Distribut… | 49 | 0.60 | 0.01609 |
---## Cluster 2 — Satellite (RL + Robotics)


> ⚠ **Satellite cluster**: only 2 papers. Community statistics are not meaningful at this size. Expect this cluster to merge or grow with corpus expansion.

> Satellite cluster: RL and Robotics (2 papers — insufficient for stable profiling).

### Overview

| Metric | Value |
|---|---|
| Papers | 2 |
| Average citations | 22.5 |
| Average betweenness centrality | 0.00096 |
| Average degree centrality | 0.1061 |
| Intra-cluster avg edge weight | 1.000 |
| Inter-cluster avg edge weight | 1.125 |
| Cohesion ratio (intra/inter) | 0.889 |
| Bridge papers (strength ≥ 0.3) | 2 |

### Dominant Categories

| Category | Papers | % of cluster |
|---|---:|---:|
| RL | 2 | 100% |
| Robotics | 1 | 50% |

### Dominant Techniques (SHARED / SPECIALIZED IDF tier)

| Technique | Papers in cluster |
|---|---:|
| task prioritisation metrics | 1 |
| suite of RL algorithms | 1 |
| method directly training on scenarios with high learnability | 1 |
| adversarial evaluation procedure | 1 |
| Unsupervised Environment Design | 1 |
| Task-structured RL algorithms | 1 |
| Reward Machines | 1 |
| Partially observable Markov decision processes | 1 |

### Top 5 Papers by Betweenness Centrality

| Title | Betweenness | Citations |
|---|---:|---:|
| No Regrets: Investigating and Improving Regret Approximations for Curri… | 0.00178 | 29 |
| Reward Machines for Deep RL in Noisy and Uncertain Environments | 0.00013 | 16 |

### Top Bridge Papers (highest bridge\_strength)

Bridge strength = cross-cluster edges ÷ total neighbors.

| Title | Cross-cluster edges | Bridge strength | Betweenness |
|---|---:|---:|---:|
| No Regrets: Investigating and Improving Regret Approximatio… | 11 | 0.92 | 0.00178 |
| Reward Machines for Deep RL in Noisy and Uncertain Environm… | 8 | 0.89 | 0.00013 |

