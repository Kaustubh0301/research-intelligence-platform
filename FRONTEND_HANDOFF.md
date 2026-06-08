# Frontend Sprint 1 Handoff

**Date:** 2026-06-08  
**Purpose:** Complete context for a fresh session to implement the Next.js frontend without any prior knowledge of this codebase.  
**Scope:** Dashboard · Paper Search · Paper Detail (Sprint 1 of 3)

---

## 1. Current Project Status

### What this project is
A research intelligence platform that ingests ML conference papers, extracts techniques/datasets/categories using NotebookLM + LLM analysis, builds a knowledge graph of paper relationships, and exposes everything via a FastAPI REST API. The frontend will be a Next.js 15 app that visualises the corpus.

### Corpus
| Item | Status |
|---|---|
| Papers ingested | **100** (NeurIPS 2024 only — Phase 1 expansion to 400 not yet run) |
| Conferences | NeurIPS 2024 |
| PDF pipeline | Complete — 98/100 papers have PDFs and segmented sections |
| LLM extraction | Complete — 100/100 papers have `paper_analyses` rows |
| Entity normalization | Applied — `canonical_name` populated on all 1,369 technique rows; 1,115 distinct canonicals |
| Graph | Built — 2,916 paper-to-paper edges, 3 clusters, centrality scores computed |
| Backend API | **Complete and tested** — 11 REST endpoints live |

### Pre-ingestion normalization (pending)
The PHASE1_EXECUTION_CHECKLIST.md lists Steps 0A–0E (regex fix, alias additions, re-normalization) that should be applied before the next corpus expansion. **Do not run these during frontend work** — they would require re-running the pipeline and are irrelevant to the frontend.

---

## 2. Database Metrics (Verified 2026-06-08)

**File:** `research_platform.db` (SQLite, at repo root — 35 MB)

| Table | Rows | Notes |
|---|---|---|
| `papers` | 100 | All NeurIPS 2024 |
| `paper_analyses` | 100 | 100% coverage — summary, advantages, limitations, future_work, use_cases |
| `paper_techniques` | 1,369 | raw rows; 1,115 distinct canonical names |
| `paper_datasets` | 333 | extracted dataset mentions |
| `paper_categories` | 251 | research area tags with confidence scores |
| `paper_methodologies` | 466 | methodology labels |
| `paper_sections` | 98 | full-text PDF sections (abstract, intro, methodology, results, conclusion) |
| `paper_relationships` | 2,916 | weighted graph edges between papers |
| `entity_relationships` | 9,413 | technique co-occurrence edges |
| `paper_graph_metrics` | 100 | degree_centrality, betweenness_centrality, cluster_id per paper |
| `technique_graph_metrics` | 1,115 | usage_count, connected_papers_count, top_cooccurring per technique |
| `authors` | 444 | linked to papers via `paper_authors` |
| `notebooks` | 23 | NotebookLM notebooks (internal pipeline artefact, not used by frontend) |
| `notebook_syntheses` | 115 | Internal — not exposed in API |

**Graph edge weight distribution:**

| Weight range | Edge count |
|---|---|
| ≥ 10 (very strong) | 7 |
| 5–10 (strong) | 91 |
| 2–5 (moderate) | 909 |
| 1–2 (weak) | 1,909 |
| < 1 | 0 |

**Recommended default `min_weight` for graph visualisation:** `2.0` (returns ~1,007 edges — manageable for WebGL)

**Clusters (3 total):**

| Cluster | Papers | Avg degree centrality | Character |
|---|---|---|---|
| 0 | 46 | 0.6063 | Largest — theory, optimization, graphs |
| 1 | 30 | 0.5825 | Mid — RL, structured learning |
| 2 | 24 | 0.5644 | Smallest — LLMs, generative models |

**Top cited papers:**

| Title (truncated) | Citations | Cluster |
|---|---|---|
| Gorilla: LLM Connected with Massive APIs | 1,248 | 2 |
| Refusal in Language Models Is Mediated by a Single Direction | 716 | 2 |
| Toward Self-Improvement of LLMs via Imagination… | 150 | 2 |
| Reducing Transformer KV Cache Size with Cross-Layer Attention | 118 | 2 |
| Multistep Distillation of Diffusion Models via Moment Matching | 76 | 1 |

**Top techniques by unique paper count:**

| Technique | Papers |
|---|---|
| Large Language Models | 9 |
| Transformers | 7 |
| Large language models (LLMs) | 7 |
| Diffusion Models | 6 |
| Stochastic gradient descent | 4 |
| Proximal Policy Optimization | 4 |
| In-context learning | 4 |
| Graph convolutional network | 4 |

> **Note:** "Large Language Models" and "Large language models (LLMs)" are two separate canonical names — a normalization gap that will be resolved in the next pre-ingestion run. Display both as-is for now; do not merge them in the frontend.

---

## 3. Existing Backend Architecture

### Repository root
```
research-intelligence-platfrom/          ← note the typo in the directory name
├── research_platform.db                 ← SQLite database (source of truth)
├── .env                                 ← DATABASE_URL=sqlite:///research_platform.db
├── api/                                 ← FastAPI v1 app  ← FOCUS HERE
│   ├── main.py                          ← Entry point (run this)
│   ├── deps.py                          ← get_db() SQLAlchemy dependency
│   ├── models.py                        ← All Pydantic response/request models
│   ├── helpers.py                       ← base_paper_query(), paper_summary(), build_paper_detail()
│   ├── routers/
│   │   ├── stats.py                     ← GET /api/v1/stats
│   │   ├── papers.py                    ← GET /api/v1/papers, /papers/{id}, /papers/{id}/related, /papers/{id}/graph
│   │   ├── search.py                    ← POST /api/v1/search
│   │   ├── graph.py                     ← GET /api/v1/graph, /graph/clusters, /graph/techniques
│   │   └── techniques.py               ← GET /api/v1/techniques
│   └── search.py                        ← LEGACY app (do not modify; runs on a different port if needed)
├── db/
│   ├── models.py                        ← SQLAlchemy ORM models (20 tables)
│   └── session.py                       ← get_session() context manager (synchronous SQLAlchemy)
├── api/search.py                        ← Original FastAPI app (untouched; ignore for frontend work)
└── [ingestion/, graph/, normalize/, ...] ← Pipeline code — do not touch during frontend work
```

### Stack
- **FastAPI** 0.136.3 + **Uvicorn** 0.49.0
- **SQLAlchemy** 2.0.50 (synchronous — **not** async; all DB access uses `get_session()` context manager)
- **Pydantic** v2 (2.13.4)
- **SQLite** via `sqlite:///research_platform.db` (relative path from repo root)
- `python-dotenv` loads `.env` automatically on startup

### How to start the backend
```bash
cd /path/to/research-intelligence-platfrom   # repo root (note typo in dirname)
source .venv/bin/activate
# .env already contains DATABASE_URL — no export needed
uvicorn api.main:app --reload --port 8000
```

- Interactive docs: `http://localhost:8000/docs`
- Health check: `http://localhost:8000/health` → `{"status":"ok","db":"connected"}`
- OpenAPI schema: `http://localhost:8000/openapi.json`

**If port 8000 is already in use** (by the legacy `api/search.py` app), use `--port 8001`.

---

## 4. Frontend Requirements

### Stack (mandated)
| Layer | Technology | Version |
|---|---|---|
| Framework | Next.js | 15 (App Router) |
| Language | TypeScript | 5.x |
| Styling | Tailwind CSS | 3.x |
| Component library | shadcn/ui | latest |
| Server state | **TanStack Query** (react-query) | v5 |
| Charts | Recharts | 2.x |
| Graph | react-force-graph-2d | latest |
| Icons | lucide-react | (comes with shadcn) |

> **TanStack Query is newly required** (not in the original design doc). Use it for all API calls that need caching, refetch-on-focus, or loading/error states. Use server components only for static page shells.

### Location
Create the Next.js app at:
```
apps/web/                      ← does not exist yet; create with npx create-next-app
```

This directory is a sibling of `api/`, `db/`, `graph/` etc. at the repo root.

### Bootstrap commands (run once)
```bash
cd /path/to/research-intelligence-platfrom

# Scaffold
npx create-next-app@latest apps/web \
  --typescript --tailwind --app --src-dir \
  --import-alias "@/*" --no-eslint

cd apps/web

# shadcn (choose: style=default, base colour=zinc, CSS variables=yes)
npx shadcn@latest init

# shadcn components needed for Sprint 1
npx shadcn@latest add card table badge skeleton button input \
  select separator scroll-area tooltip hover-card command \
  popover collapsible alert progress

# npm packages
npm install @tanstack/react-query @tanstack/react-query-devtools
npm install recharts
npm install lucide-react    # likely already installed via shadcn
```

### Environment
```bash
# apps/web/.env.local
NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
```

### Dev server
```bash
cd apps/web
npm run dev    # http://localhost:3000
```

---

## 5. Sprint 1 Scope

Sprint 1 builds three pages. **Graph and Chat are deferred to Sprint 2.**

| Page | Route | Priority | Status |
|---|---|---|---|
| Dashboard | `/` | 1 | Not started |
| Paper Search | `/papers` | 2 | Not started |
| Paper Detail | `/papers/[id]` | 3 | Not started |
| Knowledge Graph | `/graph` | — | **Sprint 2** |
| Chat (RAG) | `/chat` | — | **Sprint 2** |

---

## 6. API Endpoints the Frontend Should Consume

Base URL: `http://localhost:8000/api/v1` (from `NEXT_PUBLIC_API_URL`)

All endpoints return JSON. No authentication required.

---

### `GET /stats`
**Used by:** Dashboard  
**Returns:** Corpus counts, cluster distribution, top techniques, top papers, conference breakdown.

```typescript
// Response shape
interface StatsResponse {
  total_papers:     number          // 100
  total_edges:      number          // 2916
  total_techniques: number          // 1115
  total_clusters:   number          // 3
  conferences: Array<{
    short_name: string              // "NeurIPS"
    year:       number              // 2024
    count:      number              // 100
  }>
  clusters: Array<{
    cluster_id:      number         // 0 | 1 | 2
    paper_count:     number         // 46
    avg_degree:      number         // 0.6063
    avg_betweenness: number         // 0.0067
  }>
  top_techniques: Array<{
    canonical_name: string          // "Large Language Models"
    paper_count:    number          // 9
  }>
  top_papers: Array<{
    id:                string
    title:             string
    citation_count:    number
    conference:        string | null
    year:              number | null
    presentation_type: string | null  // "oral" | "spotlight" | "poster" | null
    cluster_id:        number | null
    degree_centrality: number
  }>
}
```

---

### `GET /papers`
**Used by:** Search page (browse mode), Dashboard (top papers table links)  
**Query params:**

| Param | Type | Default | Notes |
|---|---|---|---|
| `title` | string | — | Substring match |
| `conference` | string | — | e.g. `"NeurIPS"` |
| `year` | number | — | e.g. `2024` |
| `cluster` | number | — | `0`, `1`, or `2` |
| `technique` | string | — | Exact canonical name match (case-insensitive) |
| `min_citations` | number | — | |
| `presentation_type` | string | — | `"oral"` \| `"spotlight"` \| `"poster"` |
| `sort` | string | `"citations"` | `"citations"` \| `"centrality"` \| `"date"` \| `"title"` |
| `page` | number | `1` | |
| `per_page` | number | `20` | Max 100 |

```typescript
// Response shape
interface PapersResponse {
  total:    number
  page:     number
  per_page: number
  results:  PaperSummary[]
}

interface PaperSummary {
  id:                       string
  title:                    string
  year:                     number
  conference:               string | null
  presentation_type:        string | null   // "oral" | "spotlight" | "poster" | null
  citation_count:           number
  influential_citation_count: number
  is_open_access:           boolean
  has_pdf:                  boolean
  abstract_snippet:         string | null   // first 300 chars of abstract
  pdf_url:                  string | null
  arxiv_id:                 string | null
  openreview_id:            string | null
  cluster_id:               number | null   // 0 | 1 | 2 | null
  degree_centrality:        number          // 0.0 – 1.0
  top_techniques:           string[]        // up to 3 canonical names
}
```

---

### `POST /search`
**Used by:** Search page (when user types a query)  
**Content-Type:** `application/json`

```typescript
// Request body
interface SearchRequest {
  query:    string              // required, min length 1
  filters?: {
    conference?: string
    year?:       number
    cluster?:    number         // 0 | 1 | 2
    technique?:  string         // canonical name
  }
  sort?:    "relevance" | "citations" | "centrality" | "date"  // default "relevance"
  page?:    number              // default 1
  per_page?: number             // default 20, max 100
}

// Response shape
interface SearchResponse {
  query:    string
  total:    number
  page:     number
  per_page: number
  results:  Array<{
    paper:       PaperSummary   // same shape as GET /papers results
    match_score: number         // additive relevance score
    matched_in:  string[]       // e.g. ["title", "technique:LoRA", "abstract"]
  }>
}
```

**Scoring logic** (for UI hint text):
- `+40` exact title match, `+20` title contains, `+15` abstract/category match
- `+12` technique name match, `+10` dataset name match
- `+ log1p(citation_count)` tiebreaker

---

### `GET /papers/{id}`
**Used by:** Paper Detail page  
**Path param:** `id` — UUID string

```typescript
// Response shape
interface PaperDetail {
  id:                       string
  title:                    string
  abstract:                 string | null
  year:                     number
  conference:               string | null
  edition_year:             number | null
  presentation_type:        string | null
  citation_count:           number
  influential_citation_count: number
  is_open_access:           boolean
  pdf_url:                  string | null
  openreview_id:            string | null
  semantic_scholar_id:      string | null
  arxiv_id:                 string | null
  authors: Array<{
    id:                  string
    full_name:           string
    position:            number        // 1 = first author
    affiliation:         string | null
    semantic_scholar_id: string | null
    homepage:            string | null
  }>
  techniques: Array<{
    name:           string
    canonical_name: string | null
    role:           "introduces" | "uses" | "compares" | "critiques"
  }>
  datasets: Array<{
    name:           string
    canonical_name: string | null
    task:           string | null
    description:    string | null
  }>
  categories: Array<{
    name:           string
    canonical_name: string | null
    confidence:     number          // 0.0 – 1.0
  }>
  methodologies: Array<{
    name: string
  }>
  analysis: {
    summary:     string | null
    advantages:  string[]           // parsed from JSON-stored list
    limitations: string[]
    future_work: string[]
    use_cases:   string[]
    model:       string | null      // LLM model used for extraction
  } | null
  graph_metrics: {
    cluster_id:             number | null
    degree_centrality:      number
    betweenness_centrality: number
    neighbors_count:        number
    total_edge_weight:      number
  } | null
}
```

**Returns 404** with `{"detail": "Paper '...' not found"}` for invalid IDs.

---

### `GET /papers/{id}/related`
**Used by:** Paper Detail page (Related Papers section)  
**Query params:** `limit` (default 10, max 50), `min_weight` (default 1.0)

```typescript
interface RelatedPapersResponse {
  paper_id:     string
  title:        string
  graph_metrics: GraphMetrics | null
  related: Array<{
    paper:               PaperSummary    // same shape as list endpoint
    weight:              number          // edge weight (higher = more related)
    shared_techniques:   string[]        // canonical names
    shared_datasets:     string[]
    shared_categories:   string[]
    shared_methodologies: string[]
  }>
}
```

---

### `GET /techniques`
**Used by:** Search page filter panel (technique combobox autocomplete)  
**Query params:** `q` (substring search), `min_papers` (default 1), `per_page` (default 50, max 200)

```typescript
interface TechniquesResponse {
  total:      number
  page:       number
  per_page:   number
  techniques: Array<{
    canonical_name:         string
    usage_count:            number    // papers this technique appears in
    connected_papers_count: number
    top_cooccurring:        string[]  // names of most co-occurring techniques
    introduces_count:       number    // papers that introduce this technique
    uses_count:             number    // papers that use this technique
  }>
}
```

---

### Endpoints NOT needed for Sprint 1 (Sprint 2)

| Endpoint | Sprint |
|---|---|
| `GET /api/v1/graph` | Sprint 2 (Graph page) |
| `GET /api/v1/graph/clusters` | Sprint 2 |
| `GET /api/v1/graph/techniques` | Sprint 2 |
| `GET /api/v1/papers/{id}/graph` | Sprint 2 (ego-graph on detail) |
| `POST /api/v1/chat` | Sprint 3 (Chat page — not yet implemented) |

---

## 7. Recommended Implementation Order

Work in this exact order for the fastest path to a demable product.

### Step 1 — Project scaffold and API client (45 min)
Create `apps/web/` using the bootstrap commands in Section 4.

Files to create:
```
apps/web/src/lib/api.ts          ← all typed fetch functions
apps/web/src/lib/types.ts        ← TypeScript interfaces (copy from Section 6 above)
apps/web/src/lib/queryClient.ts  ← TanStack Query client config
apps/web/src/app/layout.tsx      ← root layout with nav + QueryClientProvider
apps/web/src/app/providers.tsx   ← client component wrapping QueryClientProvider
```

`api.ts` pattern — every function should:
1. Read base URL from `process.env.NEXT_PUBLIC_API_URL`
2. `throw` on non-2xx responses with a structured error message
3. Return a typed Promise

```typescript
// apps/web/src/lib/api.ts  (skeleton)
const BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000/api/v1'

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, init)
  if (!res.ok) throw new Error(`API ${res.status}: ${path}`)
  return res.json() as Promise<T>
}

export const api = {
  stats:           ()  => apiFetch<StatsResponse>('/stats'),
  papers:          (p) => apiFetch<PapersResponse>(`/papers?${new URLSearchParams(p)}`),
  paper:           (id) => apiFetch<PaperDetail>(`/papers/${id}`),
  paperRelated:    (id, limit=8) => apiFetch<RelatedPapersResponse>(`/papers/${id}/related?limit=${limit}`),
  search:          (body: SearchRequest) => apiFetch<SearchResponse>('/search', {
    method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify(body)
  }),
  techniques:      (q?) => apiFetch<TechniquesResponse>(`/techniques${q ? `?q=${q}` : ''}`),
}
```

TanStack Query keys convention:
```typescript
export const queryKeys = {
  stats:        ['stats']              as const,
  papers:       (p) => ['papers', p]  as const,
  paper:        (id) => ['paper', id] as const,
  paperRelated: (id) => ['paper', id, 'related'] as const,
  search:       (q, f) => ['search', q, f] as const,
  techniques:   (q) => ['techniques', q] as const,
}
```

---

### Step 2 — Dashboard (60 min)

**Route:** `apps/web/src/app/page.tsx`

This is a **server component**. Fetch stats at render time using `fetch()` directly (no TanStack Query needed on the server). Pass data as props to client chart components.

```
apps/web/src/app/page.tsx                    ← server component, fetches /stats
apps/web/src/components/dashboard/
  StatCards.tsx                              ← 4 metric tiles (client — Recharts animation)
  TechniquesChart.tsx                        ← horizontal bar chart (client)
  ConferenceDonut.tsx                        ← donut chart (client)
  TopPapersTable.tsx                         ← server-renderable table
  ClusterOverview.tsx                        ← 3 cluster cards
```

**StatCards** — 4 tiles showing:
- Papers: `total_papers` (FileText icon)
- Graph Edges: `total_edges` (Network icon)
- Techniques: `total_techniques` (Layers icon)
- Clusters: `total_clusters` (GitBranch icon)

**TechniquesChart** — Recharts horizontal `<BarChart>` with `top_techniques` (15 items). X-axis = paper_count. Show the duplicate "LLMs"/"Large language models" issue as-is.

**ConferenceDonut** — Recharts `<PieChart>` with `conferences`. At 100 papers this is a single segment (NeurIPS 2024). That's fine — it validates the component and will show multi-conference breakdown after Phase 1 expansion.

**TopPapersTable** — shadcn `<Table>` with columns: Rank · Title (link) · Conference · Citations · Cluster badge. Link title to `/papers/[id]`.

**ClusterOverview** — 3 cards. Each shows cluster_id, paper_count, and avg_degree as a shadcn `<Progress>` bar (normalise to the highest avg_degree = 100%).

**Cluster colour convention** (use consistently across all pages):
```typescript
export const CLUSTER_COLOURS = {
  0: '#3b82f6',   // blue-500
  1: '#22c55e',   // green-500
  2: '#f97316',   // orange-500
} as const
```

---

### Step 3 — Paper Search (60 min)

**Route:** `apps/web/src/app/papers/page.tsx`

This page is **URL-driven** — all filter state lives in the URL's search params, not in React state. This makes deep-linking and back/forward navigation work for free.

```
apps/web/src/app/papers/
  page.tsx                                   ← server component, reads searchParams
apps/web/src/components/papers/
  PaperSearchClient.tsx                      ← "use client" — owns URL state + TanStack Query
  SearchBar.tsx                              ← debounced input (300ms)
  FilterPanel.tsx                            ← conference checkboxes, cluster radio, technique combobox
  PaperCard.tsx                              ← single paper result card
  Pagination.tsx                             ← prev/next page controls
```

**URL shape:**
```
/papers?q=diffusion&conference=NeurIPS&cluster=0&technique=LoRA&sort=citations&page=1
```

**Data fetching strategy:**
- When `q` is empty: call `GET /papers` with filter params
- When `q` is non-empty: call `POST /search` with query + filters
- Both paths return `PaperSummary[]` — render the same `<PaperCard>` component

**PaperSearchClient** TanStack Query usage:
```typescript
// browse mode (no query)
const { data, isLoading } = useQuery({
  queryKey: queryKeys.papers({ conference, cluster, technique, sort, page }),
  queryFn: () => api.papers({ conference, cluster, technique, sort, page, per_page: 20 }),
  enabled: !searchQuery,
})

// search mode
const { data: searchData, isLoading: searchLoading } = useQuery({
  queryKey: queryKeys.search(searchQuery, filters),
  queryFn: () => api.search({ query: searchQuery, filters, sort, page }),
  enabled: !!searchQuery && searchQuery.length >= 2,
})
```

**FilterPanel** technique combobox:
```typescript
// Fetch techniques for autocomplete
const { data: techniques } = useQuery({
  queryKey: queryKeys.techniques(techInput),
  queryFn: () => api.techniques(techInput),
  enabled: techInput.length >= 1,
  staleTime: 5 * 60 * 1000,   // technique list changes rarely
})
```

**PaperCard** must display:
- Title as `<Link href={`/papers/${paper.id}`}>` (hover underline, no external icon)
- Conference + year `<Badge>` (e.g. "NeurIPS 2024")
- Presentation type `<Badge>` variant: oral=green, spotlight=blue, poster=default
- Citation count with `<TrendingUp>` icon
- Cluster `<Badge>` coloured with `CLUSTER_COLOURS[cluster_id]`
- Top 3 techniques as small grey chips — each chip click sets `?technique=<name>` in URL
- Abstract snippet (first 120 chars) in muted text below

**Skeleton loading:** Show 6 `<PaperCard>` skeletons while `isLoading`.

---

### Step 4 — Paper Detail (90 min)

**Route:** `apps/web/src/app/papers/[id]/page.tsx`

Two-column layout on ≥ lg screens; single column on mobile.

```
apps/web/src/app/papers/[id]/
  page.tsx                                   ← server component, fetch paper + related in parallel
apps/web/src/components/papers/
  PaperMeta.tsx                              ← title, authors, badges, external links
  AnalysisPanel.tsx                          ← collapsible analysis sections
  TechniqueList.tsx                          ← grouped by role
  RelatedPapers.tsx                          ← ranked related paper list
```

**Server-side data fetch:**
```typescript
// app/papers/[id]/page.tsx
export default async function PaperPage({ params }: { params: { id: string } }) {
  const [paper, related] = await Promise.all([
    api.paper(params.id),
    api.paperRelated(params.id, 8),
  ])
  // render components with data as props
}
```

**404 handling:** If `api.paper()` throws (HTTP 404), call `notFound()` from `next/navigation`.

**PaperMeta** displays:
- `<h1>` title
- Authors: first 4 shown inline (`Position 1 · Position 2 · et al.`), `is_corresponding` authors bold
- Badges: conference, year, presentation_type (colour-coded: oral=green, spotlight=blue, poster=default)
- External link `<Button variant="outline" size="sm">` buttons: PDF (if `pdf_url`), OpenReview (if `openreview_id`), Semantic Scholar (if `semantic_scholar_id`)
- Metrics row: citation_count, influential_citation_count, `is_open_access` checkmark
- Graph metrics box: cluster badge, degree centrality percentile bar, betweenness centrality

**AnalysisPanel** — shadcn `<Collapsible>` for each section. Default open: Summary. Others closed.
- Summary (open by default)
- Advantages (bullet list)
- Limitations (bullet list)
- Future Work (bullet list)
- Use Cases (bullet list)

If `analysis` is null: grey card saying "Analysis not available for this paper."

**TechniqueList** — 4 role groups, only render if non-empty:
- 🟢 Introduces (green chip)
- 🔵 Uses (blue chip)
- 🟡 Compares (yellow chip)
- 🔴 Critiques (red chip)

Each chip is a `<Link href={`/papers?technique=${encodeURIComponent(t.canonical_name)}`}>`. Use `canonical_name` for the link, `name` for display (they can differ).

**RelatedPapers** — list of up to 8. Each row:
- Title (link to `/papers/[id]`)
- Weight score shown as `⚡ 4.2` in muted text
- Shared technique chips (up to 3 from `shared_techniques`)
- Cluster badge

---

### Step 5 — Polish (45 min)

```
apps/web/src/app/loading.tsx               ← root loading skeleton
apps/web/src/app/papers/loading.tsx        ← search page skeleton
apps/web/src/app/papers/[id]/loading.tsx   ← detail page skeleton
apps/web/src/app/error.tsx                 ← global error boundary
apps/web/src/app/not-found.tsx             ← 404 page
```

---

## 8. Commands Required to Run the Backend

```bash
# Terminal 1 — backend
cd /path/to/research-intelligence-platfrom
source .venv/bin/activate
uvicorn api.main:app --reload --port 8000

# Terminal 2 — frontend (after scaffold is created)
cd /path/to/research-intelligence-platfrom/apps/web
npm run dev
```

**Verify backend is healthy before starting frontend work:**
```bash
curl http://localhost:8000/health
# Expected: {"status":"ok","db":"connected"}

curl http://localhost:8000/api/v1/stats | python3 -m json.tool | grep total_papers
# Expected: "total_papers": 100
```

**CORS** is already configured in `api/main.py` to allow `http://localhost:3000`. No additional setup needed.

**Python virtual environment:** `.venv/` is at the repo root. It contains all required packages (fastapi, sqlalchemy, uvicorn, pydantic, python-dotenv). The `anthropic` package is **not installed** — this is only needed for the Chat page (Sprint 3).

---

## 9. Known Technical Debt and Pending Issues

### Normalization gaps (do not fix in frontend)
- `"Large Language Models"` and `"Large language models (LLMs)"` are two separate canonical names (should be one). This is a known alias gap tracked in `NORMALIZATION_V2_AUDIT.md`. Display both as-is in the UI.
- The `top_techniques` field on `PaperSummary` uses the raw canonical names — they may include duplicates like the above. Filter by `canonical_name` not `name` in the frontend.

### `top_techniques` sometimes empty
In the `/papers/{id}/related` response, `related[n].paper.top_techniques` may be an empty array `[]`. This is because the batch technique fetch is only done for list endpoints, not nested paper summaries inside related. Safe to render as "no techniques" — not a bug to fix now.

### Cluster IDs are not labelled
The 3 clusters (0, 1, 2) don't have human-readable names. The `outputs/corpus_intel/community_profiles.md` file has character descriptions ("theory/optimization cluster", "LLM cluster", etc.) but they aren't in the API. Use the colour convention and bare cluster IDs in the UI. Do not display cluster names in Sprint 1.

### `paper_graph_metrics` has 100 rows but `papers` has 100 rows
All 100 papers have graph metrics — good. However, `cluster_id` is NULL for 0 papers (all assigned). After Phase 1 expansion, new papers will have NULL cluster_id until `build_graph_v2.py` is re-run.

### `shared_techniques` in paper_relationships is a JSON string
The `shared_techniques` field in the DB is stored as a JSON-encoded string (e.g. `'["LLaMA", "Large Language Models"]'`). The API's `helpers.py` already calls `json.loads()` and returns a proper `string[]` — no parsing needed in the frontend.

### Legacy `api/search.py`
The original FastAPI app (`api/search.py`) still exists and still runs if invoked directly. **Do not start it during frontend development** — it has no CORS headers and the routes don't have the `/api/v1/` prefix. Only use `api/main.py` (via `uvicorn api.main:app`).

### No authentication
The API has no auth. Both legacy and v1 apps are fully open. This is intentional for the MVP.

### SQLite write lock
If the ingestion pipeline (`python -m notebooklm.run_pipeline`, `python build_graph_v2.py`, etc.) runs while the API is serving requests, SQLite may briefly lock. The API is read-only (`PRAGMA query_only` is **not** set — this was planned but not implemented). In practice, query durations are < 10ms so this doesn't cause visible issues. Do not run the ingestion pipeline and the frontend simultaneously during a demo.

### `anthropic` package not installed
`pip install anthropic` is required before implementing the Chat page (Sprint 3). Don't worry about it for Sprint 1.

### `apps/web/` directory does not exist
Must be created with `npx create-next-app`. There is no existing frontend scaffolding.

---

## 10. Quick Orientation: What a Paper Looks Like

Here is the complete response for the top cited paper (`Gorilla`) as a mental model:

```json
{
  "id": "f16b682e-2f02-4627-9aa1-c593e350f5f5",
  "title": "Gorilla: Large Language Model Connected with Massive APIs",
  "year": 2024,
  "conference": "NeurIPS",
  "presentation_type": "poster",
  "citation_count": 1248,
  "influential_citation_count": 121,
  "is_open_access": true,
  "has_pdf": true,
  "pdf_url": "https://openreview.net/pdf?id=tBRNC6YemY",
  "openreview_id": "tBRNC6YemY",
  "cluster_id": 2,
  "degree_centrality": 0.414141,
  "top_techniques": ["Retriever-Aware Training", "Self-instruct", "AST Sub-Tree Matching"],
  "abstract_snippet": "Large Language Models (LLMs) have seen an impressive growth ...",

  "authors": [
    {"full_name": "Shishir G Patil", "position": 1, "affiliation": null},
    {"full_name": "Tianjun Zhang", "position": 2, "affiliation": null}
  ],

  "techniques": [                         // 23 total, roles: introduces / uses
    {"name": "APIBench", "canonical_name": "APIBench", "role": "introduces"},
    {"name": "LLaMA", "canonical_name": "LLaMA", "role": "uses"}
  ],

  "categories": [
    {"name": "LLM", "canonical_name": "LLM", "confidence": 1.0},
    {"name": "Code", "canonical_name": "Code", "confidence": 1.0}
  ],

  "analysis": {
    "summary": "This paper introduces Gorilla, a fine-tuned LLaMA-based model...",
    "advantages": ["Accurate API call generation", "Reduces hallucinations"],
    "limitations": ["Limited to evaluated APIs", "Single-turn conversations"],
    "future_work": ["Extend to multi-turn", "Add more API categories"],
    "use_cases": ["Software development", "API integration"],
    "model": "claude-3-5-sonnet-20241022"
  },

  "graph_metrics": {
    "cluster_id": 2,
    "degree_centrality": 0.414141,
    "betweenness_centrality": 0.000934,
    "neighbors_count": 41,
    "total_edge_weight": 83.5
  }
}
```

---

## 11. File Checklist for Sprint 1

After Sprint 1 is complete, these files should exist:

```
apps/web/
├── .env.local                              ← NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
├── next.config.ts
├── tailwind.config.ts
├── package.json
└── src/
    ├── app/
    │   ├── layout.tsx                      ← nav + QueryClientProvider
    │   ├── providers.tsx                   ← "use client" QueryClientProvider wrapper
    │   ├── page.tsx                        ← Dashboard
    │   ├── loading.tsx
    │   ├── error.tsx
    │   ├── not-found.tsx
    │   └── papers/
    │       ├── page.tsx                    ← Search
    │       ├── loading.tsx
    │       └── [id]/
    │           ├── page.tsx                ← Paper Detail
    │           └── loading.tsx
    ├── components/
    │   ├── ui/                             ← shadcn generated
    │   ├── dashboard/
    │   │   ├── StatCards.tsx
    │   │   ├── TechniquesChart.tsx
    │   │   ├── ConferenceDonut.tsx
    │   │   ├── TopPapersTable.tsx
    │   │   └── ClusterOverview.tsx
    │   └── papers/
    │       ├── PaperSearchClient.tsx
    │       ├── SearchBar.tsx
    │       ├── FilterPanel.tsx
    │       ├── PaperCard.tsx
    │       ├── Pagination.tsx
    │       ├── PaperMeta.tsx
    │       ├── AnalysisPanel.tsx
    │       ├── TechniqueList.tsx
    │       └── RelatedPapers.tsx
    └── lib/
        ├── api.ts                          ← fetch wrappers
        ├── types.ts                        ← TypeScript interfaces
        ├── queryClient.ts                  ← TanStack Query client
        └── constants.ts                    ← CLUSTER_COLOURS, etc.
```

**Total new files:** ~25  
**Estimated time:** 3.5–4.5 hours of focused implementation
