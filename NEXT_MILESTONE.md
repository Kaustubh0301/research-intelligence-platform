# Next Milestone: Corpus Intelligence Layer

**Status:** Not started  
**Depends on:** Corpus expansion (all 10 conferences ingested, ≥ 500 papers)  
**Branch target:** `corpus-intelligence`

---

## What This Milestone Is

The Corpus Intelligence Layer is a set of analytical capabilities that answer questions about the research landscape as a whole — not about individual papers, but about patterns, communities, trajectories, and convergences across the full corpus.

It sits on top of the existing graph and knowledge extraction infrastructure. It does not modify the schema, the graph, or the API. It produces new read-only analytical outputs: scripts, computed tables populated into existing or lightweight new tables, and report files.

**The question this milestone answers:**  
*What is happening in AI/ML research right now, across the whole corpus?*

---

## DO NOT BUILD during this milestone

The following are explicitly out of scope until the Corpus Intelligence Layer is complete and validated.

| Prohibited | Reason |
|---|---|
| **Embeddings** | No use case that the graph doesn't already serve; corpus too small; infrastructure not in place |
| **Vector search** | Depends on embeddings; same reasons |
| **RAG / question answering** | Explicitly ruled out by manager requirements; chatbot is not the goal |
| **Agents** | Out of scope for the platform |
| **Ontology tables** | Requires entity_type redesign first; entity_type redesign requires larger corpus audit |
| **New graph schemas** | Graph V2 is the current target; V3 requires ontology to be stable |
| **entity_type column** | Deferred until corpus audit V2 shows sufficient non-singleton coverage |
| **New API endpoints** | No new routes until intelligence outputs are defined and validated |
| **Frontend / UI** | Not started; no design spec |
| **PostgreSQL migration** | Deferred until corpus exceeds ~500 papers |

Breaking any of these holds requires an explicit decision entry in `ARCHITECTURE_DECISIONS.md`.

---

## Goals and Deliverables

### Goal 1 — Influential Papers

**Question:** Which papers are most important to the field, and why?

**Data available:** `paper_graph_metrics` (betweenness centrality, degree centrality, neighbors_count, total_edge_weight), `papers` (citation_count, influential_citation_count), `paper_techniques` (introduces role), `paper_categories`.

**What makes a paper influential in this platform:**
- High betweenness centrality — it bridges different research communities
- High citation count — recognized by the wider field
- Introduces a technique that others use (role = `introduces` on techniques that appear in other papers with role = `uses`)
- Bridges multiple categories (cross-domain papers)

**Deliverable:** `corpus_intel/influential.py`

Computes a composite influence score per paper:

```
influence_score =
    w1 * normalized_betweenness_centrality
  + w2 * normalized_log_citation_count
  + w3 * introduced_technique_adoption_rate
  + w4 * cross_domain_breadth
```

Where `introduced_technique_adoption_rate` = number of other papers that `use` a technique this paper `introduces`, divided by corpus size. Where `cross_domain_breadth` = number of distinct categories this paper belongs to, normalized.

Outputs:
- `outputs/influential_papers.csv` — all papers ranked by composite score
- Console table of top 20 with per-component breakdown
- Explanations of *why* each paper is influential (which component drives its score)

**Done when:** Produces a ranked list where the top papers are explainably influential — e.g. the most central paper is central because it connects Efficiency and Theory clusters, or because it introduced a technique adopted by 5 other papers.

---

### Goal 2 — Emerging Techniques

**Question:** Which techniques are new to the field (recently introduced) vs established (widely used baseline methods)?

**Data available:** `paper_techniques` (role = `introduces` vs `uses`), `paper_relationships` (shared_techniques), `technique_graph_metrics` (usage_count, connected_papers_count).

**Signal definition:**
- A technique is **Emerging** if it appears with role = `introduces` in ≥ 1 paper and role = `uses` in ≥ 1 other paper — it was invented and is already being adopted.
- A technique is **Novel** if it appears with role = `introduces` only — introduced but not yet adopted by others.
- A technique is **Established** if it appears only with role = `uses` — nobody is inventing it; everyone is using it.
- A technique is **Foundational** if it is Established and has GENERIC IDF tier (paper_count ≥ 5) — ubiquitous baseline.

**Deliverable:** `corpus_intel/emerging.py`

Classifies every canonical technique by adoption stage. Outputs:
- `outputs/emerging_techniques.csv` — all techniques with stage, adoption metrics
- Summary report: counts per stage, top 10 Emerging, top 10 Novel

**Note on corpus size:** With only NeurIPS 2024, "emerging" just means "introduced in one NeurIPS paper and cited in another." After multi-year ingestion, this becomes a true temporal signal. Build the classification logic now; the signal becomes richer automatically as corpus grows.

**Done when:** Can answer "which techniques were introduced at NeurIPS 2024 and are already being built on?" with a ranked, explainable list.

---

### Goal 3 — Research Communities

**Question:** What are the distinct research communities in the corpus, what defines each one, and which papers bridge between them?

**Data available:** `paper_graph_metrics` (cluster_id, betweenness_centrality), `paper_categories`, `paper_techniques` (canonical_name, role), `paper_methodologies`, `paper_relationships` (edges between clusters).

**Current state (NeurIPS 2024, 100 papers, 3 clusters):**
- Cluster 0: 53 papers (dominant: Theory, Vision, Efficiency, Graph)
- Cluster 1: 45 papers (dominant: LLM, Theory, NLP, Efficiency)
- Cluster 2: 2 papers

At larger corpus scale, communities will be more distinct and meaningful.

**Deliverable:** `corpus_intel/communities.py`

Produces a community profile for each cluster:
- **Identity:** the 3–4 categories and 3–5 techniques that define it
- **Size:** paper count, % of corpus
- **Bridges:** papers in this cluster with edges to other clusters (detected via neighbor cluster_ids)
- **Bridge techniques:** techniques shared between papers in different clusters
- **Cohesion score:** average intra-cluster edge weight vs average inter-cluster edge weight

Outputs:
- `outputs/community_profiles.md` — human-readable community report
- `outputs/community_bridges.csv` — papers that connect communities, with bridge strength

**Done when:** Each community has a clear identity statement (e.g. "Theoretical ML — papers contributing convergence proofs and generalization bounds") and bridge papers are identified with an explanation of what they bridge.

---

### Goal 4 — Technique Evolution

**Question:** How do techniques build on each other? Which techniques are foundational (many others build on them) and which are derivative (built on many others)?

**Data available:** `paper_techniques` (role = `introduces` vs `uses`), `entity_relationships` (co-occurrence between techniques), `paper_relationships` (shared_techniques).

**Model:** Build a directed technique influence graph.
- **Directed edge A → B** if paper P introduces A and also uses B — meaning P's novel contribution (A) was built on top of B.
- **In-degree** of a technique = how many introduced techniques were built on top of it → measures foundational importance.
- **Out-degree** of a technique = how many techniques it was used alongside when something new was introduced → measures versatility.

**Deliverable:** `corpus_intel/technique_evolution.py`

Outputs:
- `outputs/technique_evolution.csv` — per technique: in_degree, out_degree, foundation_rank, derivative_rank
- Top 10 foundational techniques (things everything else is built on)
- Top 10 cutting-edge techniques (things being introduced and building on many foundations)
- Top 10 isolated techniques (introduced in isolation, not building on much)

**Done when:** Can produce a readable description like "Transformers is foundational — 12 novel techniques introduced in this corpus are built on top of it" or "Direct Preference Optimization is cutting-edge — it was newly introduced in 2 papers and builds on RLHF and supervised fine-tuning."

---

### Goal 5 — Trend Detection

**Question:** What research trends are present in the corpus? Which areas are growing, shrinking, or stable?

**Data available:** `paper_categories` (category per paper), `paper_techniques` (techniques per paper), `papers` (year, citation_count), `paper_graph_metrics` (cluster, centrality).

**Two types of trends to detect:**

**Type A — Category-level trends:** Which research categories have the most papers, highest avg citations, most high-centrality papers. At single-year corpus this is a snapshot; at multi-year corpus it becomes a trajectory.

**Type B — Technique momentum:** Techniques with high `introduces` rate relative to `uses` rate are gaining momentum — being invented faster than they're being built upon. Techniques with high `uses` rate and low `introduces` rate are mature. Techniques with neither are niche or declining.

**Deliverable:** `corpus_intel/trends.py`

Outputs:
- `outputs/trends_report.md` — category-level analysis with paper counts, citation metrics, graph centrality
- `outputs/technique_momentum.csv` — per technique: momentum score = introduces_rate - uses_rate, interpretation label

**Important limitation:** With only NeurIPS 2024, this is a static snapshot, not a time series. Label the outputs accordingly. After multi-year ingestion, re-run this script and the temporal dimension will emerge automatically.

**Done when:** Can answer "which research area has the highest density of high-citation, high-centrality papers?" and "which techniques are gaining momentum vs plateauing?"

---

### Goal 6 — Cross-Domain Convergence

**Question:** Where are different research domains converging? Which papers, techniques, and researchers bridge multiple fields?

**Data available:** `paper_categories` (papers in ≥ 2 categories), `paper_relationships` (edges crossing cluster boundaries), `paper_graph_metrics` (betweenness centrality identifies bridges).

**Current data shows clear examples (NeurIPS 2024):**
- "Understanding the Limits of Vision Language Models" → Vision + Multimodal + Generative + LLM (4 categories)
- "Communication Efficient Distributed Training with Distributed Lion" → Efficiency + Vision + NLP + Theory (4 categories)
- "Boosting Sample Efficiency in Multi-agent RL via Equivariance" → RL + Graph + Efficiency + Agentic-AI (4 categories)

**Convergence signals:**
- Papers in ≥ 3 categories = **cross-domain paper**
- Techniques appearing in papers across ≥ 3 different categories = **convergent technique**
- Graph edges crossing cluster boundaries = **convergence edge**
- Papers with betweenness centrality > mean + 1 std = **bridge paper**

**Deliverable:** `corpus_intel/convergence.py`

Outputs:
- `outputs/convergence_report.md` — identified convergence zones, bridge papers, convergent techniques
- `outputs/cross_domain_papers.csv` — papers with ≥ 3 categories, with category combination and graph metrics

**Done when:** Can identify 3–5 convergence zones with clear labels (e.g. "LLM + Theory convergence: papers proving formal guarantees about language model training") and name the key bridge papers and techniques in each zone.

---

## Package Structure

All intelligence scripts go in `corpus_intel/`:

```
corpus_intel/
    __init__.py
    influential.py        Goal 1
    emerging.py           Goal 2
    communities.py        Goal 3
    technique_evolution.py Goal 4
    trends.py             Goal 5
    convergence.py        Goal 6
    run_all.py            Runs all six scripts, writes all outputs
```

All outputs go in `outputs/corpus_intel/`:

```
outputs/corpus_intel/
    influential_papers.csv
    emerging_techniques.csv
    community_profiles.md
    community_bridges.csv
    technique_evolution.csv
    trends_report.md
    technique_momentum.csv
    convergence_report.md
    cross_domain_papers.csv
```

Each script is **read-only**. No DB writes. No schema changes. All outputs are derived from existing tables.

---

## Prerequisites

Before this milestone produces meaningful results:

| Prerequisite | Why it matters |
|---|---|
| **≥ 500 papers ingested** across multiple conferences | 100 papers / 1 conference / 1 year = 3 clusters, limited trend signal |
| **Multi-year ingestion** (2023 + 2024 minimum) | Trend detection is a snapshot at single year; temporal signal requires ≥ 2 years |
| **NotebookLM pipeline re-run on expanded corpus** | `paper_analyses`, `paper_techniques`, `paper_categories` must cover the full corpus |
| **Entity normalization re-run** | `canonical_name` must be populated for all new techniques |
| **Graph V2 rebuilt on expanded corpus** | `paper_relationships` and `paper_graph_metrics` must reflect the full corpus |

Building the intelligence scripts can start now — they will run on the 100-paper corpus and produce preliminary outputs. Re-running them after corpus expansion produces the real results.

---

## Implementation Order

Build in this sequence within the milestone. Each script depends only on existing DB tables and produces standalone output.

```
1. corpus_intel/influential.py        (uses paper_graph_metrics + paper_techniques + papers)
2. corpus_intel/emerging.py           (uses paper_techniques roles + technique_graph_metrics)
3. corpus_intel/communities.py        (uses paper_graph_metrics + paper_categories + paper_relationships)
4. corpus_intel/technique_evolution.py (uses paper_techniques roles + entity_relationships)
5. corpus_intel/trends.py             (uses paper_categories + papers + paper_techniques)
6. corpus_intel/convergence.py        (uses paper_categories + paper_relationships + paper_graph_metrics)
7. corpus_intel/run_all.py            (orchestrates all six)
```

---

## Definition of Done

The Corpus Intelligence Layer milestone is complete when:

- [ ] All six scripts exist and run without errors on the current corpus
- [ ] All 9 output files exist in `outputs/corpus_intel/`
- [ ] Each output is human-readable and answers its goal question clearly
- [ ] `corpus_intel/run_all.py` runs the full suite in one command
- [ ] Preliminary outputs reviewed and validated against known ground truth (e.g. most influential paper should be explainably central, not random)
- [ ] Corpus has been expanded to ≥ 500 papers and all scripts re-run on expanded corpus
- [ ] At least one genuine insight documented: a finding that was not obvious before running the scripts

**After this milestone is complete and validated:** begin entity_type column, ontology design, and Graph V3.

---

## What This Milestone Does NOT Change

To be explicit about scope boundaries:

| Component | Change during this milestone? |
|---|---|
| `db/models.py` | **No** |
| `db/migrations/` | **No** |
| `graph/builder.py` | **No** |
| `graph/analytics.py` | **No** |
| `graph/explainer.py` | **No** |
| `api/search.py` | **No** |
| `paper_techniques.canonical_name` | Read-only (no writes) |
| Any existing table schema | **No** |

The only new code is in `corpus_intel/`. The only new files are in `outputs/corpus_intel/`.
