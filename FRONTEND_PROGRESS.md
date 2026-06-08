# Frontend Progress

**Date:** 2026-06-08  
**Baseline tag:** v0.1-mvp-foundation (5147176)

---

## Completed Pages

| Page | Route | Status | Notes |
|---|---|---|---|
| Dashboard | `/` | ✅ Complete | Stats cards, techniques bar chart, conference donut, top papers table, cluster overview |
| Paper Search | `/papers` | ✅ Complete | URL-driven filters, search + browse modes, TanStack Query caching, pagination |
| Paper Detail | `/papers/[id]` | ✅ Complete | Full metadata, analysis panel, technique list, related papers, 404 handling |
| Knowledge Graph | `/graph` | ✅ Complete | WebGL force graph, cluster filtering, edge threshold, node search, selected paper panel |
| Research Assistant | `/chat` | ✅ Complete | Three-column layout, typing indicator, simulated streaming, source panel |

---

## Completed Components

### Dashboard (`src/components/dashboard/`)
| Component | Description |
|---|---|
| `StatCards.tsx` | Four metric tiles (papers, edges, techniques, clusters) |
| `TechniquesChart.tsx` | Recharts horizontal bar chart of top techniques |
| `ConferenceDonut.tsx` | Recharts pie/donut chart by conference |
| `TopPapersTable.tsx` | Top 10 papers by citations with cluster badges |
| `ClusterOverview.tsx` | Three cluster cards with progress bars |

### Papers (`src/components/papers/`)
| Component | Description |
|---|---|
| `PaperSearchClient.tsx` | URL-driven search client with TanStack Query |
| `SearchBar.tsx` | Debounced search input |
| `FilterPanel.tsx` | Conference, cluster, technique, presentation type filters |
| `PaperCard.tsx` | Paper result card with badges and abstract snippet |
| `Pagination.tsx` | Prev/next pagination controls |
| `PaperHero.tsx` | Paper detail hero section |
| `PaperMeta.tsx` | Metadata, authors, external links |
| `AnalysisPanel.tsx` | Collapsible AI analysis sections |
| `TechniqueList.tsx` | Techniques grouped by role |
| `TagSection.tsx` | Categories, datasets, methodologies display |
| `MetricsCard.tsx` | Graph metrics (centrality, cluster) |
| `AbstractCard.tsx` | Abstract display card |
| `RelatedPapers.tsx` | Related paper list with edge weights |

### Graph (`src/components/graph/`)
| Component | Description |
|---|---|
| `GraphContext.tsx` | Shared state (selected node, filters) |
| `GraphCanvas.tsx` | react-force-graph-2d WebGL canvas |
| `GraphControls.tsx` | Left sidebar: search, threshold, cluster filter, legend, selected paper panel |
| `GraphPageClient.tsx` | SSR-safe dynamic import wrapper |

### Chat (`src/components/chat/`)
| Component | Description |
|---|---|
| `ChatPageClient.tsx` | Main orchestrator: state management, API calls, layout |
| `MessageBubble.tsx` | User/assistant message rendering with simulated streaming |
| `ChatInput.tsx` | Auto-growing textarea, Enter-to-send, disabled while loading |
| `SidebarHistory.tsx` | Recent questions, example prompts, cited papers |
| `SourcePanel.tsx` | Right panel: loading skeletons, empty state, source cards |
| `SourceCard.tsx` | Single supporting paper card with techniques, categories, open link |

### Shared UI (`src/components/ui/`)
| Component | Notes |
|---|---|
| `NavLinks.tsx` | All four nav links: Dashboard, Papers, Graph, Research Assistant |
| `badge.tsx`, `button.tsx`, `card.tsx` | shadcn-compatible, no Slot/asChild support |
| `input.tsx`, `progress.tsx`, `select.tsx` | Standard form components |
| `separator.tsx`, `skeleton.tsx` | Layout utilities |

---

## Library Files

| File | Contents |
|---|---|
| `src/lib/types.ts` | All TypeScript interfaces: StatsResponse, PaperSummary, PaperDetail, GraphNode/Edge/Response, ChatMessage, ChatSource, ChatResponse, etc. |
| `src/lib/api.ts` | Typed fetch wrappers for all 12 API endpoints including `api.chat()` |
| `src/lib/constants.ts` | `CLUSTER_COLOURS`, `CLUSTER_LABELS`, `PRESENTATION_TYPE_COLOURS` |
| `src/lib/queryClient.ts` | TanStack Query client config |
| `src/lib/utils.ts` | `cn()` helper |

---

## App Routes

| File | Type | Notes |
|---|---|---|
| `app/layout.tsx` | Server | Root layout with nav and QueryClientProvider |
| `app/providers.tsx` | Client | TanStack Query provider wrapper |
| `app/page.tsx` | Server | Dashboard — fetches /stats server-side |
| `app/loading.tsx` | — | Root loading skeleton |
| `app/error.tsx` | Client | Global error boundary |
| `app/not-found.tsx` | — | 404 page |
| `app/papers/page.tsx` | Server | Search page shell |
| `app/papers/loading.tsx` | — | Search skeleton |
| `app/papers/[id]/page.tsx` | Server | Paper detail — parallel server fetch |
| `app/papers/[id]/loading.tsx` | — | Detail skeleton |
| `app/graph/page.tsx` | Server | Graph page shell (dynamic import, ssr:false) |
| `app/graph/loading.tsx` | — | Graph skeleton |
| `app/chat/page.tsx` | Server | Chat page shell |
| `app/chat/loading.tsx` | — | Three-column chat skeleton |

---

## Remaining Work

### High priority (demo blockers)
| Item | Status | Notes |
|---|---|---|
| `ANTHROPIC_API_KEY` must be set | ⚠️ Required | Add to `.env`: `ANTHROPIC_API_KEY=sk-ant-...` — without it, `/chat` returns HTTP 503 with a clear message |

### Nice-to-have (post-demo)
| Item | Notes |
|---|---|
| Ego-graph on paper detail | `GET /papers/{id}/graph` endpoint exists; mini force-graph component not built |
| Chat conversation persistence | In-memory only; resets on page reload |
| Multi-turn context | Currently only current question is sent to Claude; prior turns not included |
| Mobile responsive pass | Graph and chat pages use fixed-width sidebars that collapse poorly on narrow viewports |
| PaperMeta `asChild` fix | Pre-existing TS error: Button doesn't support `asChild`; external links render but type-check fails |

---

## Known Issues

| Issue | Severity | File | Notes |
|---|---|---|---|
| `PaperMeta.tsx` — `asChild` on Button | Low | `src/components/papers/PaperMeta.tsx` | Pre-existing. Button doesn't have Slot support. External links still render correctly; only a type error. Fix: wrap with `<a>` instead of `Button asChild`. |
| Graph `nodeCanvasObjectMode` warning | Low | `GraphCanvas.tsx` | react-force-graph-2d logs a console warning when `nodeCanvasObject` mode is `"replace"` on first render. Does not affect functionality. |
| Simulated streaming is client-only | Low | `MessageBubble.tsx` | If the user navigates away and back, past messages render instantly (correct). Streaming only plays on newly arrived messages. |
| Chat history resets on reload | Low | `ChatPageClient.tsx` | In-memory state. Intentional for MVP. |

---

## Exact Files Modified This Session

### Backend
| File | Change |
|---|---|
| `api/models.py` | Added `ChatRequest`, `ChatSource`, `ChatResponse` Pydantic models |
| `api/helpers.py` | Added `retrieve_papers_for_query()` — shared retrieval helper using existing search scoring |
| `api/main.py` | Registered `chat.router`; added `POST /api/v1/chat` to root endpoint list |
| `.env` | Added `ANTHROPIC_API_KEY=` placeholder with comment |

### Backend created
| File | Description |
|---|---|
| `api/routers/chat.py` | `POST /api/v1/chat` — context building, Claude API call, source shaping |

### Frontend modified
| File | Change |
|---|---|
| `src/lib/types.ts` | Added `ChatSource`, `ChatRequest`, `ChatResponse`, `ChatMessage` interfaces |
| `src/lib/api.ts` | Added `ChatRequest`/`ChatResponse` imports; added `api.chat()` method |
| `src/components/ui/NavLinks.tsx` | Added "Research Assistant" link to `/chat` |

### Frontend created
| File | Description |
|---|---|
| `src/app/chat/page.tsx` | Route entry point |
| `src/app/chat/loading.tsx` | Three-column loading skeleton |
| `src/components/chat/ChatPageClient.tsx` | Main state orchestrator |
| `src/components/chat/MessageBubble.tsx` | Message rendering + simulated streaming + typing indicator |
| `src/components/chat/ChatInput.tsx` | Auto-growing textarea input |
| `src/components/chat/SidebarHistory.tsx` | Left sidebar: prompts, recent questions, cited papers |
| `src/components/chat/SourcePanel.tsx` | Right panel: loading state + source card list |
| `src/components/chat/SourceCard.tsx` | Individual source paper card |

---

## How to Run Locally

```bash
# Terminal 1 — Backend
cd /path/to/research-intelligence-platfrom
source .venv/bin/activate
# Set your Anthropic API key (required for /chat)
export ANTHROPIC_API_KEY=sk-ant-...
uvicorn api.main:app --reload --port 8000

# Terminal 2 — Frontend
cd apps/web
npm run dev   # http://localhost:3000
```

**Verify backend:**
```bash
curl http://localhost:8000/health
# {"status":"ok","db":"connected"}

curl -s -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"What techniques are used for diffusion models?"}' \
  | python3 -m json.tool | head -20
```

**Test the chat page:**
1. Open `http://localhost:3000/chat`
2. Click any example prompt in the left sidebar — it populates the input
3. Press Enter or click Send
4. Watch the typing indicator (three bouncing dots)
5. Answer streams in character-by-character via the simulated streaming effect
6. Source panel on the right shows up to 5 supporting papers with techniques and categories
7. Click "Open →" on any source card to navigate to the full paper detail
8. Click any previous assistant message to restore its source panel

**If ANTHROPIC_API_KEY is not set:**  
The frontend shows: `Error: API 503 /chat: ...ANTHROPIC_API_KEY is not set...`  
Set the key in `.env` and restart the backend.
