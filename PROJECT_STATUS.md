# Project Status

## Current status

### Pipeline
- Stage A–E complete
- 250 papers ingested
- 250 `paper_analyses` rows
- ~97–100% V2 field coverage (`summary`, `methodology`, `experimental_findings`, `strengths`, `limitations`, `practical_applications`, `future_research_directions`)
- 5 retryable PDF download errors (openreview.net timeouts) — papers uploaded as `abstract_only`

### Graph
- Phase 1 UX complete
  - Progressive disclosure (`visibleNodeCount`, Show More control)
  - Important node labels (top nodes by `degree_centrality` + `betweenness_centrality`)
  - Cluster centroid labels rendered via `onRenderFramePost`
  - Graph summary panel (`GraphSummaryPanel`) — node count, edge count, density, cluster distribution

### Chat
- Multi-turn conversation history implemented (`history: ConversationMessage[]` in request, last 10 turns forwarded to Claude)
- Rich V2 context implemented — `_build_context()` now renders `Methodology`, `Key results`, `Strengths`, `Limitations`, `Applications`, `Future work` sections (~8,000 chars / 3 papers vs ~3,000 chars before)
- Retrieval audit complete (see notes below)

---

## Next priority

### Improve retrieval quality (before Phase 2 routing)

The current retrieval treats the entire query as a single substring match. This causes:
- **Zero results** for most natural-language queries (`"hallucination in language models"` → 0 results despite relevant papers existing)
- **False positives** from incidental phrase matches (`"transformer architecture"` surfaces a robotics paper)
- **Technique-name collisions** (`"LoRA"` substring matches `"exploration"` in unrelated RL papers)

**Recommended fix — token-split retrieval** (~10 lines in `api/helpers.py`):
Split query on whitespace, skip stop words, run `retrieve_papers_for_query()` per significant token, union and aggregate scores. Fixes zero-result problem for most natural-language queries with no new dependencies.

### Phase 2 — synthesis routing (blocked on retrieval fix)
- Notebook synthesis routing as designed does not address the identified failure modes
- Meta queries (`"what are the trends in LLM research"`) return 0 papers, so routing never triggers
- `notebook_syntheses` content is per-paper (not cross-paper topic summaries), providing no new signal over `paper_analyses`
- Revisit after token-split retrieval is in place

---

## Known issues

- **Chat API key**: `ANTHROPIC_API_KEY` is not in `.env` — must be exported in the shell before starting uvicorn. The `/chat` endpoint returns HTTP 503 if the key is absent. Fix: add key to `.env` or handle via environment injection in the start script.
- **CORS**: frontend runs on port 3002; `api/main.py` now allows `localhost:3000` and `localhost:3002`. If port changes again, update `_cors_origins` in `api/main.py`.
- **9 papers** in `llm-architectures` instance 3 missing `strengths`, `limitations`, `practical_applications` — the notebook produced only 10/11 synthesis rows (`use_cases` absent). `_build_context()` handles this gracefully (sections omitted, not errored).
