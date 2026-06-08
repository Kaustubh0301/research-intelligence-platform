# HANDOFF.md

## Current Status

Project is stable.

Pipeline:
Assign → Provision → Upload → Synthesize → Extract → Normalize → Graph V2 → Explain

Current corpus:

* ~100 papers analyzed
* ~655 techniques
* ~220 categories
* ~49 datasets
* ~256 methodologies

Graph:

* 2517 paper relationships
* 2042 entity relationships
* 3 major research clusters

## Most Important Insight So Far

Graph V1 was dominated by generic concepts:

* Large Language Models
* Transformers
* Diffusion Models

Graph V2 introduced IDF weighting and significantly improved relationship quality.

## Biggest Open Problems

1. Technique taxonomy remains noisy.
2. 96% of canonical techniques are singletons.
3. Corpus size is still small (~100 papers).
4. Trend analysis is limited until corpus grows.

## Current Milestone

Corpus Intelligence Layer

Build:

* Trend detection
* Emerging techniques
* Research communities
* Technique evolution
* Influential papers
* Cross-domain convergence

Do NOT build:

* Embeddings
* Vector search
* RAG
* Agents
* Ontology tables
* Entity type redesign

## First Task For New Session

Read:

1. PROJECT_STATE.md
2. ARCHITECTURE_DECISIONS.md
3. NEXT_MILESTONE.md

Then summarize the project and propose an implementation plan for Corpus Intelligence Layer.

Do not write code until plan is approved.
