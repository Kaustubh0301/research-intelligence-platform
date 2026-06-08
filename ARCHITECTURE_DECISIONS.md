# Architecture Decisions

**Project:** Research Intelligence Platform  
**Last updated:** June 5, 2026

Each entry records a decision that was made, why it was made, what alternatives were considered, and under what conditions it should be revisited. Decisions are ordered from earliest to most recent.

---

## Decision 1 — Use NotebookLM for paper analysis

**Decision:** Use Google NotebookLM (via `notebooklm-mcp-cli`) as the LLM analysis engine for extracting structured knowledge from papers, rather than calling an LLM API directly.

**Reason:** The manager requirement explicitly stated "NotebookLM handles analysis, summarization, extraction" and "no Gemini API dependency." NotebookLM operates as a notebook — each topic gets a dedicated notebook loaded with the relevant papers as sources, then queried with structured prompts. This produces topically-aware, source-grounded analysis across groups of papers rather than analysing each paper in isolation.

**Alternatives considered:**
- Direct Gemini API (rejected: manager explicitly forbade it)
- OpenAI/Anthropic API for per-paper analysis (rejected: no cross-paper synthesis, and each analysis would have no awareness of other papers in the same topic area)
- Offline models (rejected: quality gap too large for structured extraction)

**Future revisit conditions:**
- Google changes the NotebookLM internal API and breaks `notebooklm-mcp-cli`
- NotebookLM adds an official API with structured output support
- Corpus grows past ~500 papers and the 50-source notebook limit becomes a bottleneck that outweighs the quality benefit

---

## Decision 2 — Use SQLite for development, PostgreSQL schema for production

**Decision:** Run the development database as SQLite (`research_platform.db`) and maintain a separate PostgreSQL reference DDL (`db/schema.sql`) for production. The ORM (`db/models.py`) targets SQLite behavior.

**Reason:** SQLite requires zero infrastructure during development. The corpus is small (currently 100 papers) and all workloads are single-process. PostgreSQL is the right production target because of full-text search (`pg_trgm`), concurrent writes, and better JSON support, but those capabilities are not needed yet.

**Alternatives considered:**
- PostgreSQL from day one (rejected: adds Docker/service dependency for local development with no benefit at current scale)
- DuckDB (considered but not chosen: less common ORM support, and PostgreSQL is the natural production target for a web-backed service)

**Future revisit conditions:**
- Corpus exceeds ~500 papers and SQLite single-write lock becomes a bottleneck
- Multiple processes need to write to the DB simultaneously (e.g. parallel ingestion workers)
- Full-text search across `paper_sections.full_text` is needed

---

## Decision 3 — Add `canonical_name` column rather than modifying `name`

**Decision:** When normalizing entities (techniques, datasets), write the normalized form to a new `canonical_name` column and leave the original `name` column unchanged.

**Reason:** The raw extracted value is ground truth — it is what NotebookLM actually said. Overwriting it would make debugging impossible (you cannot tell what was extracted vs what was normalized). Keeping both allows the normalization to be re-run, corrected, or reversed without re-running the extraction pipeline. The graph builder and API use `canonical_name` where available, falling back to `name`.

**Alternatives considered:**
- Overwriting `name` in-place (rejected: destroys extraction ground truth; normalization errors become unrecoverable)
- Separate normalization table with foreign key (considered: cleaner but over-engineered for current scale; the flat column approach is simpler and sufficient)

**Future revisit conditions:**
- Entity deduplication needs to happen across papers (e.g. "the same technique extracted from different notebooks") — at that point a normalized entity registry table would be the right model

---

## Decision 4 — Deprecate Gemini PDF analyser (Stage 4)

**Decision:** Mark `pdf_pipeline/analyser.py` as deprecated. Stage 4 of the PDF pipeline (Gemini per-paper analysis) was replaced entirely by the NotebookLM pipeline. The file is kept as a lazy import for reference but is never called.

**Reason:** The Gemini stage produced per-paper analysis without cross-paper awareness and required a `GEMINI_API_KEY`. The NotebookLM pipeline replaced it with topic-aware analysis that groups papers and queries across them, producing higher-quality extraction. The manager requirement also forbade Gemini API dependency.

**Alternatives considered:**
- Running both Gemini (per-paper) and NotebookLM (cross-paper) in parallel (rejected: redundant; NotebookLM produces superior output for the use case)

**Future revisit conditions:**
- If per-paper analysis quality is insufficient and NotebookLM's cross-paper approach misses paper-specific details, a fast per-paper pass could be added as a supplementary step using a different provider

---

## Decision 5 — Use flat `paper_techniques` table, not a normalized entity registry

**Decision:** Store all extracted entities as per-paper rows in flat tables (`paper_techniques`, `paper_datasets`, etc.) rather than maintaining a normalized entity registry with foreign keys.

**Reason:** At the time of initial schema design, the total number of distinct entities was unknown. A flat table is simpler to write to from the extraction pipeline, simpler to query, and does not require an entity resolution step before insertion. The `canonical_name` column provides a soft link to a conceptual entity without requiring a formal entity table.

**Alternatives considered:**
- Entity registry with `entities(id, name, type)` and `paper_entities(paper_id, entity_id)` (considered: cleaner for deduplication but requires entity resolution at write time, which is hard when extraction is probabilistic)

**Future revisit conditions:**
- PostgreSQL migration — the production schema (`db/schema.sql`) already has normalized entity tables. The migration from flat to normalized is a deliberate future step.
- Entity type redesign (see Decision 8) will make the case for a registry stronger once types are stable

---

## Decision 6 — Graph V1 was insufficient (flat technique weighting)

**Decision:** Graph V1 used flat weights: `3 × |shared_techniques| + 2 × |shared_datasets| + 1 × |shared_categories| + 1 × |shared_methodologies|`. This was identified as insufficient and replaced by Graph V2.

**Reason:** The entity signal audit showed that 3 techniques (Large Language Models, Transformers, Diffusion Models) contributed 77% of all technique-driven graph edges under V1. "Both papers use Transformers" is near-meaningless signal for research discovery — it connects papers on wildly different topics through a generic shared term. The weight formula treated Transformers the same as a rare, specific technique like Direct Preference Optimization, which is wrong.

**Alternatives considered:**
- Manual technique blacklist (rejected: brittle; requires manual maintenance as corpus grows; doesn't scale)
- Binary presence/absence (rejected: removes all fine-grained signal)
- Per-entity-type weights (considered: reasonable, but requires entity_type to be implemented first — see Decision 8)

**Future revisit conditions:**
- Entity type redesign is complete — at that point base weights can be differentiated by type (Model vs Technique vs Optimizer) rather than treating all techniques identically

---

## Decision 7 — Graph V2 uses IDF-based classification multipliers, not continuous IDF scores

**Decision:** Rather than using `idf(t)` directly as a multiplier, classify each technique into one of three tiers (GENERIC, SHARED, SPECIALIZED) and apply a discrete multiplier (×0.25, ×1.0, ×2.0). Thresholds are `idf < 3.00` and `idf < 3.69`.

**Reason:** Continuous IDF multiplication would make edge weights hard to interpret and diagnose. A paper pair connected by a technique with idf=4.0 vs idf=4.5 would have different weights for no semantically meaningful reason. The three-tier approach is auditable, interpretable, and maps cleanly to the intuition: generic concepts down-weighted, rare concepts up-weighted, middle ground unchanged. The thresholds were validated against the `concept_selection_audit.py` output and match the example cases provided in the design spec.

**Alternatives considered:**
- Continuous IDF weight: `WEIGHT_TECHNIQUE * idf(t)` (rejected: makes weights hard to interpret; small differences in paper_count produce arbitrary weight differences)
- BM25-style weighting (considered: mathematically richer but adds complexity with no clear benefit at current scale)

**Future revisit conditions:**
- Corpus is large enough (≥ 1,000 papers) that continuous IDF becomes more meaningful and the tier thresholds become stale

---

## Decision 8 — Entity type redesign postponed

**Decision:** Do not add an `entity_type` column to `paper_techniques` yet, even though the audit showed clear type mixing (Models, Optimizers, Frameworks, Metrics all stored as "techniques").

**Reason:** The entity audit showed 78% of canonical techniques (405 of 517) could not be classified by the heuristic rules — they were labeled "Unknown." The classification rules that could be written with confidence (known model names, known optimizer names, known frameworks) only cover ~22% of the corpus. At 100 papers, the corpus is too small to determine whether "Unknown" entities are truly unclassifiable or just too domain-specific to match general rules. Writing classification rules and schema now would likely need to be redone after corpus expansion. The deliberate sequence is: expand corpus → re-audit → design classification rules → implement entity_type.

**Alternatives considered:**
- Implement entity_type now with partial coverage (rejected: partial coverage is worse than no coverage — it creates a false sense of completeness and the partially-classified DB would need migration again after rules improve)
- Manual classification (rejected: 517 entities is manageable manually, but will grow to thousands after corpus expansion)

**Future revisit conditions:**
- Corpus expanded to ≥ 500 papers and entity audit re-run
- Singleton percentage below 80% (currently 96%) — meaning enough entities appear in multiple papers to make type classification meaningful for graph weighting
- SHARED tier has ≥ 20 techniques — enough for classification rules to have real impact

---

## Decision 9 — Ontology / entity hierarchy postponed

**Decision:** Do not build a parent-child ontology (e.g. Optimizers → Adam/AdamW/SGD, Architectures → Transformer/CNN/LSTM) yet.

**Reason:** The ontology depends on entity_type being implemented and stable (see Decision 8). Building a hierarchy on top of untyped entities would require rebuilding it after entity_type is added. Additionally, the hierarchy design requires seeing the full entity distribution to know which groupings are meaningful — a 100-paper corpus is insufficient for this.

**Alternatives considered:**
- Flat hierarchy defined as a Python dict (considered: low-cost, no schema change needed — `normalize/` already has a similar pattern with alias JSON files — but without entity_type, the hierarchy has nowhere useful to attach)

**Future revisit conditions:**
- Entity_type column is implemented and populated with ≥ 80% coverage
- A clear use case emerges that requires hierarchy traversal (e.g. "find papers related to any optimizer" rather than just "AdamW papers")

---

## Decision 10 — Vector embeddings postponed

**Decision:** Do not add paper or entity embeddings to the platform.

**Reason:** (1) No embedding model is selected or deployed. (2) No vector storage layer (pgvector, FAISS, Chroma, etc.) is in the stack. (3) At 100 papers, similarity search via embeddings would return the same results as keyword search — the value of embeddings emerges at scale. (4) The platform already has a knowledge graph that captures semantic relationships between papers through shared structured entities; embeddings would add a second, overlapping similarity layer without clear differentiation in purpose.

**Alternatives considered:**
- Sentence-transformers for abstract embeddings (considered: easy to add, but no clear downstream use case that isn't already served by the graph)
- OpenAI or Anthropic embeddings API (considered: high quality but adds API dependency and ongoing cost)

**Future revisit conditions:**
- Corpus exceeds 1,000 papers and cross-paper discovery via graph traversal becomes insufficient
- A specific use case emerges that requires similarity search (e.g. "find papers similar to this abstract I just wrote")
- PostgreSQL migration happens and pgvector becomes available at no additional infrastructure cost

---

## Decision 11 — Vector search / semantic search postponed

**Decision:** Do not add vector/semantic search to the `/search` endpoint.

**Reason:** The current `/search` endpoint uses multi-field keyword scoring (title, technique, category, dataset) and works correctly for all intended use cases at current scale. Adding semantic search requires embedding infrastructure (see Decision 10) and would add complexity without clear benefit until the corpus is large enough that keyword search returns too many irrelevant results.

**Alternatives considered:**
- SQLite FTS5 for full-text search (considered: reasonable intermediate step; would add full-text search across `paper_sections.full_text` without embedding infrastructure)

**Future revisit conditions:**
- Same as Decision 10 (embeddings); or
- Full-text search across paper sections is needed and FTS5 becomes the right lightweight intermediate step

---

## Decision 12 — RAG (Retrieval-Augmented Generation) postponed

**Decision:** Do not build a RAG pipeline or question-answering interface over the paper corpus.

**Reason:** The manager requirement explicitly specified "no chatbot." RAG implies a conversational or query interface that synthesizes answers from retrieved documents — this is precisely what was ruled out. The platform is designed for structured discovery (filter, browse, explore relationships), not for answering free-form questions. NotebookLM already provides a form of RAG for the synthesis step, but that is an internal pipeline tool, not a user-facing interface.

**Alternatives considered:**
- Internal RAG for generating relationship explanations (rejected: the `graph/explainer.py` approach of rule-based synthesis from structured DB data is more predictable and auditable than LLM-generated explanations)

**Future revisit conditions:**
- Manager requirements change to explicitly permit a question-answering interface
- A clear use case emerges that cannot be served by structured search + graph exploration

---

## Decision 13 — Recommendation engine postponed

**Decision:** Do not build a paper recommendation engine.

**Reason:** A good recommendation engine requires (1) sufficient corpus size to make meaningful recommendations, (2) a stable knowledge graph with high-quality edge weights, (3) user behavior signals (views, saves, follows) that do not yet exist in the system, and (4) a frontend to surface recommendations. None of these preconditions are met. Building recommendations now would produce low-quality output and would need to be rebuilt after corpus expansion and entity_type redesign.

**Future revisit conditions:**
- Corpus ≥ 1,000 papers
- Entity type redesign and ontology complete
- Graph V3 (with entity-type weights) built and validated
- User-facing frontend exists

---

## Decision 14 — Relationship explanations use rule-based synthesis, not LLM calls

**Decision:** `graph/explainer.py` generates all explanation components (differences, research connection) from structured DB data using templates and heuristics. It makes no LLM API calls.

**Reason:** (1) Predictability — the same pair always returns the same explanation; (2) Speed — no network round-trip; (3) Auditability — the reasoning is traceable through the data; (4) Cost — no API tokens consumed per explanation; (5) The structured data already present (summaries, techniques with roles, categories, methodologies) is sufficient to produce useful explanations at current quality requirements. The `introduces` role on techniques is particularly valuable — it identifies what each paper *contributes* versus what it *uses*, which is the core of the difference description.

**Alternatives considered:**
- LLM-generated explanations using paper summaries as context (considered: higher quality ceiling, but non-deterministic, costly, slow, and would break if summaries are missing)
- Template-only without any DB data (rejected: too generic; "Both papers are related by shared techniques" is not useful)

**Future revisit conditions:**
- Explanation quality is insufficient for the use case (e.g. the template coverage misses important category combinations as the corpus expands)
- An LLM call budget is established and explanation quality becomes a priority feature

---

## Decision 15 — Three-tier knowledge audit before any redesign

**Decision:** Before implementing entity_type, ontology, or Graph V3, perform a full knowledge audit phase: `entity_audit.py`, `entity_signal_audit.py`, `concept_selection_audit.py`. These produce read-only reports from existing data. No schema changes during audit phase.

**Reason:** Past experience with premature schema design (Graph V1 flat weights, deprecated Gemini stage) showed that building on incomplete understanding requires rework. The audit phase makes the data quality problems explicit and quantifiable before committing to a redesign. The audit outputs are permanent records that justify the decisions made in subsequent phases.

**Alternatives considered:**
- Design entity_type schema first, then audit to validate (rejected: inverts the correct order; audit findings should drive design choices)

**Future revisit conditions:**
- This decision is complete — audit phase is done. The three audit scripts and their outputs in `outputs/` are the evidence base for all upcoming decisions.
