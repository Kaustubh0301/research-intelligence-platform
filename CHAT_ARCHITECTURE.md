# Research Assistant Chat — Architecture Document

**Date:** 2026-06-08  
**Status:** Pre-implementation design — awaiting review  
**Milestone baseline:** v0.1-mvp-foundation (5147176)

---

## 1. Codebase Inventory

### 1.1 Existing API routes (all at `/api/v1/`)

| Method | Route | File | Relevance to Chat |
|---|---|---|---|
| `GET` | `/stats` | `api/routers/stats.py` | — |
| `GET` | `/papers` | `api/routers/papers.py` | Used indirectly via search |
| `GET` | `/papers/{id}` | `api/routers/papers.py` | Reused for source panel deep-link |
| `GET` | `/papers/{id}/related` | `api/routers/papers.py` | — |
| `GET` | `/papers/{id}/graph` | `api/routers/papers.py` | — |
| `POST` | `/search` | `api/routers/search.py` | **Direct reuse as retrieval engine** |
| `GET` | `/graph` | `api/routers/graph.py` | — |
| `GET` | `/graph/clusters` | `api/routers/graph.py` | — |
| `GET` | `/graph/techniques` | `api/routers/graph.py` | — |
| `GET` | `/techniques` | `api/routers/techniques.py` | — |

### 1.2 Existing search logic (`api/routers/search.py`)

The `POST /api/v1/search` endpoint already implements exactly the retrieval signals needed:

| Signal | Weight | Covers |
|---|---|---|
| Exact title match | +40 | titles |
| Title contains | +20 | titles |
| Abstract contains | +15 | abstracts |
| Category name contains | +15 | `paper_categories` |
| Technique name contains | +12 | `paper_techniques` |
| Dataset name contains | +10 | `paper_datasets` |
| `log1p(citation_count)` | tiebreaker | relevance bias toward high-impact |

This covers all five required retrieval fields (titles, abstracts, paper_techniques, paper_analyses [via summary stored in paper_analyses], categories). **The search router is the retrieval engine — no new retrieval logic is needed.**

### 1.3 Existing data available per paper

From `db/models.py` and `api/helpers.py`:

| Table | Fields available for context building |
|---|---|
| `papers` | `title`, `abstract`, `citation_count`, `year` |
| `paper_analyses` | `summary`, `advantages` (JSON), `limitations` (JSON), `future_work` (JSON), `use_cases` (JSON) |
| `paper_techniques` | `name`, `canonical_name`, `role` |
| `paper_categories` | `name`, `canonical_name`, `confidence` |
| `paper_sections` | `abstract`, `introduction`, `methodology`, `results`, `conclusion` (full-text from PDF) |

`build_paper_detail()` in `api/helpers.py` already assembles all of this per paper. It can be called directly from the new chat router.

---

## 2. What Needs to Be Built

### 2.1 New backend: `POST /api/v1/chat`

One new endpoint. Everything else is reuse.

**Request:**
```json
{
  "message": "What techniques are used for LLM alignment in this corpus?",
  "conversation_id": null
}
```

**Response (non-streaming — simplest demo-ready approach):**
```json
{
  "answer": "Based on the papers in this corpus...",
  "sources": [
    {
      "id": "uuid",
      "title": "...",
      "citation_count": 716,
      "cluster_id": 2,
      "degree_centrality": 0.414,
      "top_techniques": ["RLHF", "DPO"],
      "categories": ["LLM", "Alignment"],
      "match_score": 47.0,
      "matched_in": ["title", "technique:RLHF"]
    }
  ],
  "conversation_id": "uuid"
}
```

**Why non-streaming:** Streaming requires SSE/chunked response handling, adds frontend complexity, and risks CORS edge cases. A simple JSON response is sufficient for demo readiness. Streaming can be added in v2.

### 2.2 Retrieval pipeline (inside the new chat router)

**Step 1 — Reuse `POST /search` logic directly**  
Call the same scoring logic used by `api/routers/search.py` — not the HTTP endpoint, but the underlying DB queries — to retrieve the top 5 most relevant papers for the user's message.

The key helpers already exist in `api/helpers.py`:
- `base_paper_query()` — joined query over papers + conference + graph metrics
- `fetch_top_techniques_batch()` — batch technique fetch for result set
- `paper_summary()` — shapes a DB row into `PaperSummary`

The scoring logic from `search.py` will be extracted into a shared helper `api/helpers.py` → `retrieve_papers_for_query(term, session, limit=5)` that returns `list[SearchMatch]`.

**Step 2 — Build context string from top 5 papers**  
For each retrieved paper, assemble:
```
PAPER: {title} ({year}, {conference})
CITATIONS: {citation_count}
SUMMARY: {analysis.summary[:500]}
TECHNIQUES: {top_3_technique_names}
CATEGORIES: {category_names}
ABSTRACT: {abstract[:300]}
```
Max context: ~3,000 chars (stays well within Claude's context window).

**Step 3 — Call Claude API**  
System prompt instructs the model to answer ONLY from the provided papers, cite by title, and flag if the corpus doesn't cover the question.

**Step 4 — Return answer + sources**  
Return both the synthesised answer and the full source metadata so the frontend can render the source panel.

### 2.3 New frontend: `/chat` page

Three-column layout:

```
┌──────────────┬───────────────────────────────┬──────────────────┐
│  Left sidebar│  Main chat area               │  Source panel    │
│  ~240px      │  flex-1                        │  ~280px          │
│              │                               │                  │
│  Recent      │  [Question bubble]            │  Supporting      │
│  questions   │                               │  papers (up to 5)│
│              │  [Thinking indicator]         │                  │
│  Saved       │                               │  For each:       │
│  papers      │  [Answer with citations]      │  - Title (link)  │
│              │                               │  - Citations     │
│  Quick       │  [Input bar]                  │  - Techniques    │
│  prompts     │                               │  - Categories    │
│              │                               │  - Open Paper → │
└──────────────┴───────────────────────────────┴──────────────────┘
```

---

## 3. Files to Create

### Backend

| File | Action | Description |
|---|---|---|
| `api/routers/chat.py` | **Create** | `POST /api/v1/chat` endpoint |

No new service files needed — all retrieval logic lives in `api/helpers.py` additions.

### Backend modification

| File | Change | Description |
|---|---|---|
| `api/helpers.py` | **Modify** | Add `retrieve_papers_for_query(term, session, limit)` — the search scoring logic extracted from `search.py`, callable without HTTP overhead |
| `api/models.py` | **Modify** | Add `ChatRequest`, `ChatSource`, `ChatResponse` Pydantic models |
| `api/main.py` | **Modify** | Register `chat.router` |

### Frontend

| File | Action | Description |
|---|---|---|
| `apps/web/src/app/chat/page.tsx` | **Create** | Route entry — static shell |
| `apps/web/src/app/chat/loading.tsx` | **Create** | Loading skeleton |
| `apps/web/src/components/chat/ChatPageClient.tsx` | **Create** | `"use client"` — owns all chat state |
| `apps/web/src/components/chat/MessageList.tsx` | **Create** | Scrollable conversation history |
| `apps/web/src/components/chat/MessageBubble.tsx` | **Create** | User/assistant message rendering |
| `apps/web/src/components/chat/ChatInput.tsx` | **Create** | Input bar + send button |
| `apps/web/src/components/chat/SourcePanel.tsx` | **Create** | Right panel: source paper cards |
| `apps/web/src/components/chat/SourceCard.tsx` | **Create** | Single source paper card |
| `apps/web/src/components/chat/SidebarHistory.tsx` | **Create** | Left: recent questions + example prompts |
| `apps/web/src/lib/types.ts` | **Modify** | Add `ChatRequest`, `ChatSource`, `ChatResponse`, `ChatMessage` |
| `apps/web/src/lib/api.ts` | **Modify** | Add `api.chat(req)` |
| `apps/web/src/components/ui/NavLinks.tsx` | **Modify** | Add Chat link |

---

## 4. Backend Endpoint Specification

### `POST /api/v1/chat`

**Request body:**
```typescript
interface ChatRequest {
  message: string;          // required, min 1 char
  conversation_id?: string; // optional, for history (MVP: ignored, returned as echo)
}
```

**Response:**
```typescript
interface ChatResponse {
  answer: string;
  sources: ChatSource[];
  conversation_id: string;  // new UUID each call (history in-memory on frontend)
}

interface ChatSource {
  id: string;
  title: string;
  conference: string | null;
  year: number;
  citation_count: number;
  cluster_id: number | null;
  degree_centrality: number;
  top_techniques: string[];   // up to 3 canonical names
  categories: string[];       // up to 3 category names
  match_score: number;
  matched_in: string[];
  abstract_snippet: string | null;
}
```

---

## 5. Retrieval Design

### Why reuse `POST /search` logic rather than call the HTTP endpoint

Calling `http://localhost:8000/api/v1/search` from within the same process would be a loopback HTTP call — unnecessary network overhead and serialisation. Instead, the scoring logic will be extracted to a shared helper `retrieve_papers_for_query()` in `api/helpers.py` and called directly from the chat router. The search router will continue calling it too.

### Retrieval signal coverage

| Required field | How it's covered |
|---|---|
| Paper titles | Signal 1: `+20` title contains, `+40` exact |
| Abstracts | Signal 2: `+15` abstract contains |
| `paper_techniques` | Signal 4: `+12` per technique name match |
| `paper_analyses` | Signal 2 covers `summary` (stored in `paper_analyses`, exposed via abstract snippet); additional context building step pulls `summary`, `advantages`, `limitations` |
| Categories | Signal 3: `+15` category name match |

### Context building per paper (for Claude prompt)

```
PAPER: {title} ({conference} {year})
CITATIONS: {citation_count}
SUMMARY: {analysis.summary[:400]}
ADVANTAGES: {advantages[:2] joined}
TECHNIQUES: {top_3_canonical_names}
CATEGORIES: {category_names}
ABSTRACT: {abstract[:200]}
```

Target: ≤ 600 chars per paper × 5 papers = ~3,000 chars context. Leaves ample room within claude-sonnet-4-6's context window.

### Claude API setup

- **Model:** `claude-sonnet-4-6` (available in `.venv` environment check needed)
- **Max tokens:** 1024 (sufficient for a structured answer with citations)
- **System prompt:** Instructs to answer from provided papers only, cite by exact title, be concise
- **No streaming** for MVP

---

## 6. Frontend State Design

All state lives in `ChatPageClient` — no URL-driven state needed (chat is inherently session-based).

```typescript
interface ChatMessage {
  id: string;             // local UUID
  role: "user" | "assistant";
  content: string;
  sources?: ChatSource[]; // only on assistant messages
  isLoading?: boolean;    // true while request in flight
  timestamp: Date;
}

// State
const [messages, setMessages] = useState<ChatMessage[]>([])
const [input, setInput] = useState("")
const [activeSources, setActiveSources] = useState<ChatSource[]>([])
const [isLoading, setIsLoading] = useState(false)
```

`activeSources` is set from the most recent assistant message and drives the right-panel source display. Clicking a previous assistant message re-sets `activeSources` to its sources.

**Conversation history** is in-memory `useState`. On refresh it resets. No persistence for MVP.

---

## 7. Example Prompts (hardcoded for demo)

```
1. "What techniques are used for LLM alignment in this corpus?"
2. "Which papers introduce novel architectures for transformers?"
3. "Summarise the diffusion model research represented here"
4. "What are the most central papers in cluster 0?"
5. "What papers work on reinforcement learning from human feedback?"
```

---

## 8. Dependencies

### Backend
- `anthropic` SDK — check if installed: `pip show anthropic`
- All other dependencies already present (`fastapi`, `sqlalchemy`, `pydantic`)

### Frontend
- No new npm packages required
- All needed shadcn components already exist (`card`, `badge`, `button`, `input`, `skeleton`, `separator`)
- `lucide-react` already installed (for icons)

---

## 9. What Is Explicitly Excluded

| Item | Reason |
|---|---|
| Streaming (SSE) | Adds complexity; JSON response sufficient for demo |
| Vector embeddings | Prohibited by design constraints |
| Vector DB | Prohibited by design constraints |
| Conversation persistence | In-memory only; DB persistence is post-demo |
| Multi-turn context sent to Claude | MVP sends only the current question + retrieved context |
| Technique graph / entity relationships | Not needed for chat retrieval |
| `/chat` backend beyond `POST /api/v1/chat` | No history, no session management |

---

## 10. Implementation Order

1. `api/helpers.py` — add `retrieve_papers_for_query()` (extract from `search.py`)
2. `api/models.py` — add `ChatRequest`, `ChatSource`, `ChatResponse`
3. `api/routers/chat.py` — create, implement context building + Claude call
4. `api/main.py` — register chat router
5. Frontend types + api client additions
6. `ChatPageClient` + child components
7. Nav link
8. Smoke test end-to-end
