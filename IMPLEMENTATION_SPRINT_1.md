# Implementation Sprint 1 — Research Intelligence Platform UI

**Goal:** Working, demo-able MVP in ~9 focused hours across 2 days  
**Date:** 2026-06-08  
**Reference:** UI_TECHNICAL_DESIGN.md

---

## What Already Exists (Do Not Rebuild)

| Asset | Location | Reuse |
|---|---|---|
| FastAPI app | `api/search.py` | Extend with new routers |
| SQLAlchemy ORM (all 20 tables) | `db/models.py` | Import directly |
| DB session factory | `db/session.py` | Import `get_session` |
| Paper search logic | `search/query.py` | Wrap in new router |
| Dashboard metrics | `metrics/dashboard.py` | Port to API response |
| Graph builder | `graph/builder.py` | Query pre-built tables |
| Graph analytics | `graph/analytics.py` | Import for chat context |

**Critical:** The existing code uses **synchronous SQLAlchemy** (`SessionLocal`, `get_session()` context manager). All new backend code must follow the same pattern. Do not introduce aiosqlite.

---

## Build Order — Fastest Visible Progress

```
Hour 1    Backend foundation       Stats + Papers endpoints live at localhost:8000
Hour 2    Next.js scaffold         Shell + nav visible at localhost:3000
Hour 3    Dashboard                First full page rendering real data ← DEMO 1
Hour 4    Search page              Browse 100 papers with filters
Hour 5    Paper detail             Full paper view + related papers ← DEMO 2
Hour 6    Graph page               WebGL graph rendering ← DEMO 3
Hour 7–8  Chat backend + UI        Streaming RAG chatbot ← DEMO 4
Hour 9    Polish + integration     Error states, loading skeletons, smoke test
```

The first demable moment arrives at **Hour 3**, before the graph or chat are built.

---

## Part 1 — Backend API

**Estimated time:** 2 hours  
**Strategy:** Restructure `api/search.py` into routers; add three new routers (stats, graph, chat). No new ORM sessions needed — use existing `db/session.py` pattern.

---

### 1.1 Files to Create

#### `api/routers/__init__.py`
Empty init. Makes `api/routers/` a package.

---

#### `api/routers/stats.py`
Single endpoint. Reads from `papers`, `paper_relationships`, `paper_techniques`, `paper_graph_metrics`, `conferences`, `conference_editions`.

**Endpoint:** `GET /api/v1/stats`

**SQL queries needed:**

```sql
-- Scalar counts (one query)
SELECT
  (SELECT COUNT(*) FROM papers)                                     AS total_papers,
  (SELECT COUNT(*) FROM paper_relationships)                        AS total_edges,
  (SELECT COUNT(DISTINCT canonical_name) FROM paper_techniques
   WHERE canonical_name IS NOT NULL)                               AS total_techniques,
  (SELECT COUNT(DISTINCT cluster_id) FROM paper_graph_metrics)     AS total_clusters;

-- Top techniques
SELECT canonical_name, COUNT(DISTINCT paper_id) AS paper_count
FROM paper_techniques
WHERE canonical_name IS NOT NULL
GROUP BY canonical_name
ORDER BY paper_count DESC
LIMIT 15;

-- Cluster overview
SELECT cluster_id, COUNT(*) AS paper_count,
       ROUND(AVG(degree_centrality), 4)      AS avg_degree,
       ROUND(AVG(betweenness_centrality), 4) AS avg_betweenness
FROM paper_graph_metrics
GROUP BY cluster_id
ORDER BY cluster_id;

-- Top papers (for dashboard table)
SELECT p.id, p.title, p.citation_count, p.presentation_type,
       co.short_name AS conference, ce.year,
       pgm.cluster_id, pgm.degree_centrality
FROM papers p
LEFT JOIN conference_editions ce ON p.conference_edition_id = ce.id
LEFT JOIN conferences co ON ce.conference_id = co.id
LEFT JOIN paper_graph_metrics pgm ON p.id = pgm.paper_id
ORDER BY p.citation_count DESC
LIMIT 10;

-- Conference breakdown (for donut chart)
SELECT co.short_name, ce.year, COUNT(*) AS count
FROM papers p
JOIN conference_editions ce ON p.conference_edition_id = ce.id
JOIN conferences co ON ce.conference_id = co.id
GROUP BY co.short_name, ce.year
ORDER BY co.short_name;
```

**Pydantic response models to define in this file:**
`StatsResponse`, `ClusterStat`, `TechniqueStat`, `TopPaper`, `ConferenceStat`

---

#### `api/routers/papers.py`
Replaces the paper search/detail logic currently inline in `api/search.py`. Wraps existing `search/query.py` functions and adds graph metrics to every response.

**Endpoints:**
- `GET /api/v1/papers` — search + filter + paginate
- `GET /api/v1/papers/{id}` — full paper detail
- `GET /api/v1/papers/{id}/related` — related papers from `paper_relationships`
- `GET /api/v1/papers/{id}/graph` — 1-hop ego-graph for mini-visualisation

**`GET /papers` SQL queries:**

```sql
-- Full-text search (FTS5 virtual table — built at startup)
-- Table created once:
CREATE VIRTUAL TABLE IF NOT EXISTS papers_fts USING fts5(
  paper_id UNINDEXED,
  title, abstract, summary,
  content='', tokenize='porter unicode61'
);
-- Populate if empty:
INSERT INTO papers_fts(paper_id, title, abstract, summary)
SELECT p.id, p.title, COALESCE(p.abstract,''), COALESCE(pa.summary,'')
FROM papers p LEFT JOIN paper_analyses pa ON pa.paper_id = p.id;

-- Search with FTS:
SELECT p.id, p.title, p.abstract, p.citation_count, p.year,
       p.presentation_type, p.pdf_url, p.arxiv_id,
       co.short_name AS conference,
       pgm.cluster_id, pgm.degree_centrality,
       bm25(papers_fts) AS rank
FROM papers_fts
JOIN papers p ON papers_fts.paper_id = p.id
LEFT JOIN conference_editions ce ON p.conference_edition_id = ce.id
LEFT JOIN conferences co ON ce.conference_id = co.id
LEFT JOIN paper_graph_metrics pgm ON p.id = pgm.paper_id
WHERE papers_fts MATCH :q
  AND (:conference IS NULL OR co.short_name = :conference)
  AND (:cluster    IS NULL OR pgm.cluster_id = :cluster)
ORDER BY bm25(papers_fts) LIMIT :per_page OFFSET :offset;

-- Browse (no query), with technique filter:
SELECT p.id, p.title, p.abstract, p.citation_count, p.year,
       p.presentation_type, p.pdf_url, p.arxiv_id,
       co.short_name AS conference,
       pgm.cluster_id, pgm.degree_centrality
FROM papers p
LEFT JOIN conference_editions ce ON p.conference_edition_id = ce.id
LEFT JOIN conferences co ON ce.conference_id = co.id
LEFT JOIN paper_graph_metrics pgm ON p.id = pgm.paper_id
-- technique join (only when technique filter set):
JOIN (SELECT DISTINCT paper_id FROM paper_techniques
      WHERE canonical_name = :technique) tf ON tf.paper_id = p.id
WHERE (:conference IS NULL OR co.short_name = :conference)
  AND (:cluster    IS NULL OR pgm.cluster_id = :cluster)
ORDER BY p.citation_count DESC LIMIT :per_page OFFSET :offset;

-- Top 3 techniques per paper (called in Python after fetching papers, one query for all IDs):
SELECT paper_id, canonical_name, COUNT(*) AS c
FROM paper_techniques
WHERE paper_id IN (:ids) AND canonical_name IS NOT NULL
GROUP BY paper_id, canonical_name
ORDER BY paper_id, c DESC;
```

**Query params for `GET /papers`:**

| Param | Type | Default |
|---|---|---|
| `q` | string | — |
| `conference` | string | — |
| `cluster` | int | — |
| `technique` | string | — |
| `sort` | `citations`\|`centrality`\|`date`\|`relevance` | `citations` |
| `page` | int | 1 |
| `per_page` | int | 20 |

**`GET /papers/{id}` SQL queries:**

```sql
-- Paper + analysis + graph metrics in one query
SELECT p.*, pa.summary, pa.advantages, pa.limitations, pa.future_work, pa.use_cases,
       pgm.cluster_id, pgm.degree_centrality, pgm.betweenness_centrality,
       pgm.neighbors_count, pgm.total_edge_weight,
       co.short_name AS conference, ce.year
FROM papers p
LEFT JOIN paper_analyses pa  ON pa.paper_id  = p.id
LEFT JOIN paper_graph_metrics pgm ON pgm.paper_id = p.id
LEFT JOIN conference_editions ce  ON p.conference_edition_id = ce.id
LEFT JOIN conferences co          ON ce.conference_id = co.id
WHERE p.id = :id;

-- Authors
SELECT a.full_name, a.primary_affiliation, pa2.position, pa2.is_corresponding
FROM paper_authors pa2 JOIN authors a ON a.id = pa2.author_id
WHERE pa2.paper_id = :id ORDER BY pa2.position;

-- Techniques by role
SELECT name, canonical_name, role FROM paper_techniques
WHERE paper_id = :id ORDER BY role, name;

-- Categories
SELECT canonical_name FROM paper_categories
WHERE paper_id = :id ORDER BY confidence DESC;

-- Datasets
SELECT canonical_name, name, task FROM paper_datasets
WHERE paper_id = :id;
```

**`GET /papers/{id}/related` SQL query:**

```sql
SELECT pr.weight, pr.shared_techniques, pr.shared_categories,
       pr.technique_score, pr.category_score,
       p.id, p.title, p.citation_count, p.year,
       pgm.cluster_id, pgm.degree_centrality
FROM paper_relationships pr
JOIN papers p ON p.id = pr.target_paper_id
LEFT JOIN paper_graph_metrics pgm ON pgm.paper_id = p.id
WHERE pr.source_paper_id = :id
ORDER BY pr.weight DESC LIMIT :limit;
-- UNION mirror (edges are directed; check both directions)
UNION
SELECT pr.weight, pr.shared_techniques, pr.shared_categories,
       pr.technique_score, pr.category_score,
       p.id, p.title, p.citation_count, p.year,
       pgm.cluster_id, pgm.degree_centrality
FROM paper_relationships pr
JOIN papers p ON p.id = pr.source_paper_id
LEFT JOIN paper_graph_metrics pgm ON pgm.paper_id = p.id
WHERE pr.target_paper_id = :id
ORDER BY weight DESC LIMIT :limit;
```

**`GET /papers/{id}/graph` SQL queries:**

```sql
-- Ego node
SELECT p.id, p.title, pgm.cluster_id, pgm.degree_centrality
FROM papers p JOIN paper_graph_metrics pgm ON pgm.paper_id = p.id
WHERE p.id = :id;

-- 1-hop neighbours (both edge directions)
SELECT p.id, p.title, pgm.cluster_id, pgm.degree_centrality,
       pr.weight
FROM paper_relationships pr
JOIN papers p ON p.id = pr.target_paper_id
LEFT JOIN paper_graph_metrics pgm ON pgm.paper_id = p.id
WHERE pr.source_paper_id = :id AND pr.weight >= 2.0
ORDER BY pr.weight DESC LIMIT 30;
```

---

#### `api/routers/graph.py`
Serves the full graph payload for the Knowledge Graph page.

**Endpoints:**
- `GET /api/v1/graph` — full graph (paper nodes + edges)
- `GET /api/v1/graph/techniques` — technique entity graph

**`GET /graph` SQL queries:**

```sql
-- All paper nodes
SELECT p.id, p.title, p.citation_count, p.year,
       co.short_name AS conference,
       pgm.cluster_id, pgm.degree_centrality, pgm.betweenness_centrality
FROM papers p
LEFT JOIN paper_graph_metrics pgm ON pgm.paper_id = p.id
LEFT JOIN conference_editions ce  ON p.conference_edition_id = ce.id
LEFT JOIN conferences co          ON ce.conference_id = co.id;

-- Edges above threshold
SELECT source_paper_id AS source, target_paper_id AS target, weight
FROM paper_relationships
WHERE weight >= :min_weight
ORDER BY weight DESC;
```

**Query params:** `min_weight` (default 1.5), `cluster` (optional filter)

**`GET /graph/techniques` SQL queries:**

```sql
-- Technique nodes
SELECT canonical_name, usage_count, connected_papers_count
FROM technique_graph_metrics
WHERE usage_count >= :min_usage;

-- Technique co-occurrence edges
SELECT source_entity, target_entity, co_occurrence_count, weight
FROM entity_relationships
WHERE entity_type = 'technique' AND weight >= :min_weight;
```

---

#### `api/routers/chat.py`
RAG pipeline. Retrieves context from DB, calls Claude API, streams response.

**Endpoint:** `POST /api/v1/chat`

**Retrieval SQL queries (run in sequence inside `rag.py`):**

```sql
-- Step 1: keyword → technique match
SELECT DISTINCT canonical_name FROM paper_techniques
WHERE canonical_name LIKE :term OR name LIKE :term
LIMIT 10;

-- Step 2: papers using matched techniques (top by centrality)
SELECT DISTINCT pt.paper_id, pgm.degree_centrality
FROM paper_techniques pt
LEFT JOIN paper_graph_metrics pgm ON pgm.paper_id = pt.paper_id
WHERE pt.canonical_name IN (:tech_list)
ORDER BY pgm.degree_centrality DESC NULLS LAST
LIMIT 8;

-- Step 3: FTS fallback (if technique match returns < 3 papers)
SELECT paper_id, bm25(papers_fts) AS rank
FROM papers_fts WHERE papers_fts MATCH :query
ORDER BY rank LIMIT 8;

-- Step 4: pull context for matched papers
SELECT p.id, p.title, p.abstract,
       pa.summary, pa.advantages, pa.limitations, pa.future_work, pa.use_cases,
       ps.methodology, ps.results, ps.conclusion
FROM papers p
LEFT JOIN paper_analyses pa  ON pa.paper_id  = p.id
LEFT JOIN paper_sections ps  ON ps.paper_id  = p.id
WHERE p.id IN (:paper_ids);
```

**Pydantic models:** `ChatRequest`, `ChatResponse`, `SourcePaper`

---

#### `api/routers/techniques.py`
Technique browser — used by search filter combobox autocomplete.

**Endpoint:** `GET /api/v1/techniques`

**SQL query:**

```sql
SELECT tgm.canonical_name, tgm.usage_count, tgm.connected_papers_count,
       tgm.top_cooccurring,
       COUNT(CASE WHEN pt.role='introduces' THEN 1 END) AS introduces_count,
       COUNT(CASE WHEN pt.role='uses'       THEN 1 END) AS uses_count
FROM technique_graph_metrics tgm
LEFT JOIN paper_techniques pt ON pt.canonical_name = tgm.canonical_name
WHERE tgm.usage_count >= :min_papers
  AND (:q IS NULL OR tgm.canonical_name LIKE :q)
GROUP BY tgm.canonical_name
ORDER BY tgm.usage_count DESC
LIMIT :per_page OFFSET :offset;
```

**Query params:** `q`, `min_papers` (default 1), `page`, `per_page` (default 50)

---

#### `api/main.py`  ← NEW entry point (replaces running `api/search.py` directly)
Mounts all routers. Handles CORS, startup events (FTS5 table creation).

```
Registers: /api/v1/stats, /api/v1/papers, /api/v1/graph,
           /api/v1/chat, /api/v1/techniques
Run with: uvicorn api.main:app --reload --port 8000
```

---

#### `api/services/fts.py`
FTS5 table setup. Called once at API startup.

**Responsibilities:**
- Check if `papers_fts` virtual table exists
- Create it if missing
- Populate it if row count doesn't match `papers` table count
- Expose `rebuild_fts(session)` for manual refresh

---

#### `api/services/rag.py`
Retrieval + synthesis service. Called from `api/routers/chat.py`.

**Responsibilities:**
- `extract_query_terms(query: str) → list[str]` — simple tokenisation
- `retrieve_papers(terms, session, limit=8) → list[dict]` — technique match + FTS fallback
- `build_context(papers: list[dict]) → str` — formats context blocks for Claude prompt
- `stream_response(context, question) → AsyncGenerator[str, None]` — calls `anthropic.Anthropic().messages.stream()`

---

### 1.2 Files to Modify

#### `api/search.py`
**Change:** Convert from standalone app to importable router module.
- Remove `app = FastAPI(...)` instantiation
- Remove direct `uvicorn.run()` if present
- Extract paper endpoints into functions importable by `api/main.py`
- Keep all existing logic intact — just reorganise the entry point

**Why:** `api/main.py` needs to own CORS, startup events, and router mounting. `api/search.py` should become `api/routers/papers_legacy.py` or have its routes absorbed into `api/routers/papers.py`.

---

#### `requirements.txt` (root) or new `api/requirements.txt`
**Add:**
```
anthropic>=0.25.0
python-dotenv>=1.0.0
```
Everything else (fastapi, sqlalchemy, uvicorn) is already present.

---

### 1.3 Environment

**`.env` (root — already used by db/session.py):**
```
DATABASE_URL=sqlite:///research_platform.db
ANTHROPIC_API_KEY=sk-ant-...
CORS_ORIGIN=http://localhost:3000
```

**Run command:**
```bash
source .venv/bin/activate
export DATABASE_URL=sqlite:///research_platform.db
uvicorn api.main:app --reload --port 8000
```

**Verify:**
```bash
curl http://localhost:8000/api/v1/stats | python3 -m json.tool
# Must return total_papers: 100
```

---

## Part 2 — Frontend Setup

**Estimated time:** 45 minutes  
**Location:** `apps/web/` (new directory, sibling to existing Python modules)

---

### 2.1 Files to Create

#### Shell commands (run once)

```bash
# From repo root
npx create-next-app@latest apps/web \
  --typescript --tailwind --app --src-dir \
  --import-alias "@/*" --no-eslint

cd apps/web
npx shadcn@latest init          # style: default, base colour: zinc, CSS variables: yes

# shadcn components needed across all pages:
npx shadcn@latest add card table badge skeleton button input \
  select separator scroll-area tooltip hover-card command \
  popover sheet dialog alert

# Other dependencies:
npm install recharts react-force-graph-2d @types/react-force-graph-2d
npm install lucide-react        # icons (already included via shadcn usually)
npm install eventsource-parser  # SSE parsing for chat stream
```

---

#### `apps/web/src/lib/types.ts`
TypeScript interfaces mirroring every API response shape.

**Interfaces to define:**
```
StatsResponse, ClusterStat, TechniqueStat, TopPaper, ConferenceStat
PaperSummary, PaperDetail, PaperAnalysis, PaperTechniques, Author
RelatedPaper, GraphNode, GraphEdge, GraphResponse
TechniqueItem
ChatRequest, ChatMessage, SourcePaper
```

---

#### `apps/web/src/lib/api.ts`
Typed fetch wrappers. All functions return typed responses, throw on non-2xx.

**Functions to define:**

```typescript
fetchStats(): Promise<StatsResponse>
searchPapers(params: PaperSearchParams): Promise<PaperSearchResponse>
fetchPaper(id: string): Promise<PaperDetail>
fetchRelatedPapers(id: string, limit?: number): Promise<RelatedPaper[]>
fetchEgoGraph(id: string): Promise<GraphResponse>
fetchGraph(minWeight?: number, cluster?: number): Promise<GraphResponse>
fetchTechniques(params?: TechniqueParams): Promise<TechniqueResponse>
sendChatMessage(req: ChatRequest): Promise<Response>  // returns raw Response for SSE
```

**Base URL:** reads from `process.env.NEXT_PUBLIC_API_URL` (defaults to `http://localhost:8000/api/v1`)

---

#### `apps/web/src/app/layout.tsx`
Root layout with navigation sidebar/topbar.

**Contains:**
- `<nav>` with links: Dashboard, Papers, Graph, Chat
- Active state highlighting via `usePathname()`
- `<Toaster>` for error notifications (shadcn)
- Root font setup (Geist or Inter)

---

#### `apps/web/src/app/error.tsx`
Global error boundary — catches fetch failures, shows retry button.

---

#### `apps/web/src/app/not-found.tsx`
404 page for invalid paper IDs etc.

---

#### `apps/web/.env.local`
```
NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
```

---

#### `apps/web/next.config.ts`
```typescript
const config = {
  output: 'standalone',          // Docker-ready
  experimental: { typedRoutes: true },
}
export default config
```

---

### 2.2 Files to Modify

None at this stage — this is a fresh Next.js scaffold.

---

## Part 3 — Dashboard Page

**Estimated time:** 60 minutes  
**Route:** `/`  
**Data:** `GET /api/v1/stats`

---

### 3.1 Files to Create

#### `apps/web/src/app/page.tsx`
Server Component. Fetches stats at render time (no client-side loading state needed for initial data).

**Renders:**
- `<StatCards>` — 4 metric tiles
- `<TechniquesChart>` — horizontal bar
- `<ConferenceBreakdown>` — donut
- `<TopPapersTable>` — top 10 by citations
- `<ClusterOverview>` — 3 cluster cards

---

#### `apps/web/src/components/dashboard/StatCards.tsx`
Client component (`"use client"` — uses Recharts animation).

**Props:** `{ total_papers, total_edges, total_techniques, total_clusters }`

**4 cards:** Papers · Graph Edges · Techniques · Clusters  
**Uses:** shadcn `<Card>`, `<CardHeader>`, `<CardContent>`  
**Icon per card:** `FileText`, `Network`, `Layers`, `GitBranch` (lucide-react)

---

#### `apps/web/src/components/dashboard/TechniquesChart.tsx`
`"use client"` — Recharts `<BarChart>` horizontal.

**Props:** `{ techniques: TechniqueStat[] }`  
**Behaviour:** Displays top 12 techniques, bar length = paper count, hover tooltip.  
**Recharts components:** `BarChart`, `Bar`, `XAxis`, `YAxis`, `Tooltip`, `ResponsiveContainer`

---

#### `apps/web/src/components/dashboard/ConferenceDonut.tsx`
`"use client"` — Recharts `<PieChart>`.

**Props:** `{ conferences: ConferenceStat[] }`  
**Note:** At 100 papers this is a single-segment donut (NeurIPS 2024). Still useful — proves the component works and will show multiple segments post-Phase 1 ingestion.

---

#### `apps/web/src/components/dashboard/TopPapersTable.tsx`
Server-renderable (no interactivity needed).

**Props:** `{ papers: TopPaper[] }`  
**Columns:** Rank · Title (link to `/papers/[id]`) · Conference · Citations · Cluster  
**Uses:** shadcn `<Table>`, `<Badge>` for cluster, `<Link>` for title

---

#### `apps/web/src/components/dashboard/ClusterOverview.tsx`
**Props:** `{ clusters: ClusterStat[] }`  
**Renders:** 3 cards, each showing cluster_id, paper_count, avg_degree as a percentage bar.  
**Uses:** shadcn `<Card>`, `<Progress>`

---

### 3.2 Files to Modify

None.

---

## Part 4 — Search Page

**Estimated time:** 60 minutes  
**Route:** `/papers`  
**Data:** `GET /api/v1/papers`, `GET /api/v1/techniques` (for filter combobox)

---

### 4.1 Files to Create

#### `apps/web/src/app/papers/page.tsx`
Server Component shell. Reads `searchParams` from URL.

**URL shape:** `/papers?q=diffusion&conference=NeurIPS&cluster=0&technique=LoRA&sort=citations&page=1`

**Behaviour:**
- Passes `searchParams` as props to `<PaperSearchClient>`
- Fetches initial paper list server-side (first render is fast)

---

#### `apps/web/src/components/papers/PaperSearchClient.tsx`
`"use client"` — owns URL-driven state via `useSearchParams` + `useRouter`.

**Sub-components rendered:**
- `<SearchBar>` — debounced (300ms) input, updates `?q=`
- `<FilterPanel>` — left sidebar
- `<SortSelect>` — right of search bar
- `<PaperGrid>` — list of `<PaperCard>`
- `<Pagination>` — prev/next, page count

**State management:** URL params are the single source of truth. No `useState` for filters — push to router, re-fetch on param change.

---

#### `apps/web/src/components/papers/SearchBar.tsx`
**Props:** `{ defaultValue: string, onChange: (q: string) => void }`  
**Uses:** shadcn `<Input>`, lucide `<Search>` icon prefix  
**Debounce:** 300ms via `useEffect` + `setTimeout`

---

#### `apps/web/src/components/papers/FilterPanel.tsx`
`"use client"`

**Sections:**
1. **Conference** — checkboxes (hardcoded: NeurIPS, ICLR, ICML for MVP; dynamic post-Phase-1)
2. **Cluster** — radio group (All / 0 / 1 / 2)
3. **Technique** — combobox with search, populates from `GET /api/v1/techniques?q=<input>`

**Uses:** shadcn `<Checkbox>`, `<RadioGroup>`, `<Command>` (combobox pattern), `<Popover>`

---

#### `apps/web/src/components/papers/PaperCard.tsx`
**Props:** `PaperSummary`

**Displays:**
- Title as `<Link href="/papers/[id]">` (hover underline)
- Conference + year badge, presentation type badge (oral/spotlight/poster)
- Citation count with `<TrendingUp>` icon
- Cluster badge with colour coding (cluster 0=blue, 1=green, 2=orange)
- Top 3 techniques as small chips (click → adds technique filter)
- Degree centrality shown as a subtle percentile bar

**Uses:** shadcn `<Card>`, `<Badge>`, `<HoverCard>` (shows abstract on title hover)

---

#### `apps/web/src/components/papers/Pagination.tsx`
**Props:** `{ page, totalPages, onPageChange }`  
**Uses:** shadcn `<Button>` for prev/next, page count display

---

### 4.2 Files to Modify

None.

---

## Part 5 — Paper Detail Page

**Estimated time:** 90 minutes  
**Route:** `/papers/[id]`  
**Data:** `GET /api/v1/papers/{id}`, `GET /api/v1/papers/{id}/related`, `GET /api/v1/papers/{id}/graph`

---

### 5.1 Files to Create

#### `apps/web/src/app/papers/[id]/page.tsx`
Server Component. Fetches paper + related in parallel on the server.

```typescript
// Parallel fetch
const [paper, related] = await Promise.all([
  fetchPaper(id),
  fetchRelatedPapers(id, 8),
])
if (!paper) notFound()
```

**Renders:** Two-column layout:
- Left: `<PaperMeta>`, `<TechniqueList>`, `<DatasetList>`, `<MethodologyList>`
- Right: `<AnalysisPanel>`, `<RelatedPapers>`, `<EgoGraphWrapper>`

---

#### `apps/web/src/components/papers/PaperMeta.tsx`
**Props:** `PaperDetail`

**Displays:**
- Title (h1)
- Authors: inline list, first author bold, "et al." if >4
- Venue badges: conference, year, presentation_type
- External link buttons: PDF, ArXiv, OpenReview (lucide `<ExternalLink>`)
- Citation metrics: citation_count + influential_citation_count
- Graph metrics: cluster badge, degree centrality percentile, betweenness centrality

---

#### `apps/web/src/components/papers/AnalysisPanel.tsx`
**Props:** `PaperAnalysis | null`

**Renders 5 collapsible sections** using shadcn `<Collapsible>` (open by default for summary):
1. Summary (always expanded)
2. Advantages
3. Limitations
4. Future Work
5. Use Cases

If analysis is null: grey placeholder "Analysis not yet available."

---

#### `apps/web/src/components/papers/TechniqueList.tsx`
**Props:** `PaperTechniques`

**4 sections (only render if non-empty):**
- 🟢 Introduces — green chip
- 🔵 Uses — blue chip
- 🟡 Compares — yellow chip
- 🔴 Critiques — red chip

Each chip is a `<Link>` that navigates to `/papers?technique=<canonical_name>`.

---

#### `apps/web/src/components/papers/RelatedPapers.tsx`
**Props:** `{ papers: RelatedPaper[] }`

**Renders:** Ranked list of up to 8 related papers.

Each row shows:
- Title (link to `/papers/[id]`)
- Weight score (shown as `⚡ 4.2`)
- Shared techniques as small badges (from `shared_techniques` JSON string)
- Cluster badge

---

#### `apps/web/src/components/papers/EgoGraphWrapper.tsx`
`"use client"` — dynamic import wrapper to avoid SSR issues.

```typescript
const EgoGraph = dynamic(() => import('./EgoGraph'), { ssr: false })
```

**Fetches ego graph data client-side** via `useEffect` → `fetchEgoGraph(id)`.
Shows `<Skeleton>` while loading.

---

#### `apps/web/src/components/papers/EgoGraph.tsx`
`"use client"` — the actual `react-force-graph-2d` component.

**Props:** `{ nodes: GraphNode[], edges: GraphEdge[], egoId: string }`

**Visual encoding:**
- Ego node: larger (radius 8), white outline
- Neighbour nodes: sized by degree_centrality, coloured by cluster_id
- Edge width: proportional to weight
- Click neighbour node → navigate to `/papers/[id]`

**Config:**
```typescript
<ForceGraph2D
  graphData={{ nodes, links: edges }}
  nodeRelSize={4}
  nodeColor={(n) => CLUSTER_COLOURS[n.cluster_id]}
  linkWidth={(l) => Math.log(l.weight + 1)}
  onNodeClick={(n) => router.push(`/papers/${n.id}`)}
  width={400} height={300}
/>
```

---

### 5.2 Files to Modify

None.

---

## Part 6 — Knowledge Graph Page

**Estimated time:** 90 minutes  
**Route:** `/graph`  
**Data:** `GET /api/v1/graph`

---

### 6.1 Files to Create

#### `apps/web/src/app/graph/page.tsx`
Thin server wrapper. Because the graph is a fully client-side WebGL canvas, this page has almost no server logic.

```typescript
export default function GraphPage() {
  return (
    <div className="h-screen flex">
      <GraphControls />         // left sidebar, ~280px
      <GraphCanvas />           // fills remaining width
    </div>
  )
}
```

---

#### `apps/web/src/components/graph/GraphCanvas.tsx`
`"use client"` — core WebGL graph component.

**Behaviour:**
1. On mount, fetches `GET /api/v1/graph?min_weight=1.5`
2. Shows `<Skeleton>` while loading
3. Renders `<ForceGraph2D>` with full dataset once loaded
4. Exposes `selectedNode` state via `GraphContext`
5. On node click → updates `selectedNode` → `<GraphControls>` shows paper popover

**Config:**
```typescript
<ForceGraph2D
  graphData={graphData}
  nodeLabel="title"
  nodeColor={(n) => CLUSTER_COLOURS[n.cluster_id ?? 0]}
  nodeVal={(n) => n.degree_centrality * 100}   // node size
  linkWidth={(l) => Math.sqrt(l.weight)}
  linkColor={() => 'rgba(156,163,175,0.3)'}    // tailwind gray-400
  onNodeClick={handleNodeClick}
  onBackgroundClick={() => setSelected(null)}
  nodeCanvasObjectMode={() => 'after'}
  nodeCanvasObject={drawLabel}  // draw title label on hover
/>
```

**Performance note:** At 100 papers / 2,916 edges, WebGL renders at 60fps with no throttling needed. At 400+ papers, `min_weight` filtering in the API request keeps edge count manageable.

---

#### `apps/web/src/components/graph/GraphControls.tsx`
`"use client"` — left sidebar.

**Sections:**

**View controls:**
- Toggle: Papers / Techniques (switches graph endpoint)
- Colour by: Cluster (only option for MVP)
- Edge threshold slider: 1.0 → 5.0 (step 0.5) — triggers refetch with new `min_weight`
- Label toggle: show/hide node labels

**Node search:**
- `<Input>` — filters visible nodes by title substring
- Matching nodes highlighted, non-matching nodes dimmed (opacity 0.1)

**Selected paper panel** (shown when a node is clicked):
- Title (truncated to 2 lines)
- Conference badge, cluster badge, citation count
- Centrality score
- `<Button>` → navigate to `/papers/[id]`

**Legend:**
- 3 colour swatches: Cluster 0 / 1 / 2 with paper counts

**Uses:** shadcn `<Slider>`, `<Switch>`, `<Input>`, `<Card>`, `<Badge>`, `<Button>`, `<Separator>`

---

#### `apps/web/src/components/graph/GraphContext.tsx`
React context for sharing `selectedNode` state between `<GraphCanvas>` and `<GraphControls>`.

```typescript
export const GraphContext = createContext<{
  selected: GraphNode | null
  setSelected: (n: GraphNode | null) => void
  filters: GraphFilters
  setFilters: (f: GraphFilters) => void
}>({...})
```

---

#### `apps/web/src/lib/graphColours.ts`
```typescript
export const CLUSTER_COLOURS: Record<number, string> = {
  0: '#3b82f6',   // blue-500
  1: '#22c55e',   // green-500
  2: '#f97316',   // orange-500
  // fallback for future clusters
  3: '#a855f7',
  4: '#ec4899',
}
```

Imported by both `<GraphCanvas>` and `<EgoGraph>` and `<ClusterOverview>`.

---

### 6.2 Files to Modify

None.

---

## Part 7 — Chat Page

**Estimated time:** 2 hours (backend 1hr + frontend 1hr)  
**Route:** `/chat`  
**Data:** `POST /api/v1/chat` (streaming SSE)

---

### 7.1 Files to Create

#### `apps/web/src/app/chat/page.tsx`
Server Component shell (static chrome only — no data fetched server-side).

```typescript
export default function ChatPage() {
  return (
    <div className="flex flex-col h-screen">
      <ChatHeader />
      <ChatWindow />
    </div>
  )
}
```

---

#### `apps/web/src/components/chat/ChatWindow.tsx`
`"use client"` — owns all chat state.

**State:**
```typescript
const [messages, setMessages] = useState<ChatMessage[]>([])
const [input, setInput] = useState('')
const [isStreaming, setIsStreaming] = useState(false)
const [conversationId, setConversationId] = useState<string | null>(null)
```

**`handleSend()` flow:**
1. Append user message to `messages`
2. Call `sendChatMessage({ message: input, conversation_id: conversationId, stream: true })`
3. Parse SSE stream using `eventsource-parser`
4. On `sources` event → set source citations on the assistant message being built
5. On `token` event → append to streaming message in progress
6. On `done` event → finalise message, `setIsStreaming(false)`

**Renders:**
- `<ScrollArea>` containing message list
- `<SuggestedPrompts>` when `messages.length === 0`
- `<ChatInput>` at bottom

**Auto-scroll:** `useEffect` with `messagesEndRef.current?.scrollIntoView()` on messages change.

---

#### `apps/web/src/components/chat/MessageBubble.tsx`
**Props:** `{ message: ChatMessage }`

**User messages:** Right-aligned, blue background, white text.  
**Assistant messages:** Left-aligned, white card, text rendered with simple markdown-to-JSX (just bold + line breaks — no full markdown parser needed for MVP).

**Source chips** (shown below assistant message when sources available):
```
Sources: [Gorilla: LLM…] [Refusal in LMs…]
```
Each chip is a `<Link href="/papers/[id]">` with title truncated to 30 chars.

**Streaming indicator:** Blinking cursor `▍` appended to message text while `isStreaming`.

---

#### `apps/web/src/components/chat/SuggestedPrompts.tsx`
Shown only on empty state.

**4 suggested prompts (hardcoded):**
1. "What are the main LLM alignment techniques in this corpus?"
2. "Which papers introduce novel architectures?"
3. "Summarize the diffusion model research here"
4. "What are the most central papers in cluster 0?"

Each is a `<Button variant="outline">` that fills `<ChatInput>` and auto-submits.

---

#### `apps/web/src/components/chat/ChatInput.tsx`
**Props:** `{ onSend, disabled }`  
**Uses:** shadcn `<Input>` + `<Button>` (Send icon)  
**Keyboard:** Enter sends, Shift+Enter newline  
**Disabled** while streaming.

---

#### `api/services/rag.py` (new file — backend)
RAG retrieval + synthesis service.

**Functions:**

`extract_query_terms(query: str) → list[str]`
- Lowercase, split on spaces/punctuation
- Filter stop words (< 4 chars)
- Return up to 8 candidate terms

`retrieve_papers(terms: list[str], session: Session, limit: int = 8) → list[dict]`
- Technique match query (Step 1 + 2 from SQL above)
- FTS5 fallback if technique match returns < 3 results
- Deduplicates results, sorts by centrality
- Returns list of dicts with id, title, abstract, summary, methodology, results, conclusion

`build_context(papers: list[dict]) → tuple[str, list[dict]]`
- Returns (context_string, sources_list)
- context_string: up to 4,000 chars, one block per paper:
  ```
  PAPER: {title}
  SUMMARY: {summary}
  METHODOLOGY: {methodology[:300]}
  ```

`stream_chat(context: str, question: str, history: list) → AsyncGenerator`
- Calls `anthropic.Anthropic().messages.stream()`
- System prompt (constant):
  ```
  You are a research assistant for an ML paper corpus.
  Answer questions using ONLY the provided paper excerpts.
  Always cite which papers your answer draws from by title.
  If the corpus doesn't contain relevant information, say so.
  Keep answers concise and structured.
  ```
- Yields SSE strings: `data: {"type":"token","content":"..."}` for each text chunk
- Yields `data: {"type":"done"}` at end

---

### 7.2 Files to Modify

#### `api/routers/chat.py`
Imports `rag.py` services. Implements the streaming endpoint using FastAPI `StreamingResponse` with `media_type="text/event-stream"`.

```python
@router.post("/chat")
async def chat(req: ChatRequest):
    session = next(get_db())
    terms = extract_query_terms(req.message)
    papers = retrieve_papers(terms, session)
    context, sources = build_context(papers)

    async def event_generator():
        # First: emit sources
        yield f"data: {json.dumps({'type':'sources','papers':sources})}\n\n"
        # Then: stream tokens
        async for token in stream_chat(context, req.message, req.history or []):
            yield token
        yield "data: {\"type\":\"done\"}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
```

---

## Part 8 — Polish + Integration (Hour 9)

**Estimated time:** 60 minutes

### 8.1 Files to Create

#### `apps/web/src/components/ui/LoadingSkeleton.tsx`
Reusable skeleton patterns for each page:
- `<DashboardSkeleton>` — 4 stat cards + table rows
- `<SearchSkeleton>` — 6 paper card outlines
- `<PaperDetailSkeleton>` — two-column layout with text lines
- `<GraphSkeleton>` — full-height grey rectangle

Used in `loading.tsx` files for each route.

---

#### `apps/web/src/app/loading.tsx`
Root loading state (shown while layouts hydrate).

#### `apps/web/src/app/papers/loading.tsx`
#### `apps/web/src/app/papers/[id]/loading.tsx`
#### `apps/web/src/app/graph/loading.tsx`
#### `apps/web/src/app/chat/loading.tsx`

Each imports its relevant skeleton component.

---

#### `apps/web/src/components/ui/ErrorAlert.tsx`
Reusable error display:
```typescript
<Alert variant="destructive">
  <AlertCircle />
  <AlertTitle>Failed to load data</AlertTitle>
  <AlertDescription>{message}</AlertDescription>
  <Button onClick={retry}>Retry</Button>
</Alert>
```

---

### 8.2 Files to Modify

#### `apps/web/src/app/papers/page.tsx`
Add `<Suspense>` boundary around `<PaperSearchClient>` with `<SearchSkeleton>` fallback.

#### `apps/web/src/app/graph/page.tsx`
Ensure `<GraphCanvas>` is wrapped in `dynamic(..., { ssr: false, loading: () => <GraphSkeleton /> })`.

---

## Complete File Manifest

### Backend (`api/`)

| File | Status | Action |
|---|---|---|
| `api/main.py` | 🆕 New | Create — app entry point, router mounting |
| `api/routers/__init__.py` | 🆕 New | Create — empty init |
| `api/routers/stats.py` | 🆕 New | Create — `GET /stats` |
| `api/routers/papers.py` | 🆕 New | Create — absorbs search + adds detail/related/graph |
| `api/routers/graph.py` | 🆕 New | Create — `GET /graph`, `GET /graph/techniques` |
| `api/routers/chat.py` | 🆕 New | Create — `POST /chat` streaming |
| `api/routers/techniques.py` | 🆕 New | Create — `GET /techniques` |
| `api/services/__init__.py` | 🆕 New | Create — empty init |
| `api/services/fts.py` | 🆕 New | Create — FTS5 setup/populate |
| `api/services/rag.py` | 🆕 New | Create — RAG retrieval + Claude streaming |
| `api/search.py` | ✏️ Modify | Remove `app = FastAPI()` instantiation; keep route logic |

### Frontend (`apps/web/src/`)

| File | Status | Action |
|---|---|---|
| `lib/types.ts` | 🆕 New | All TypeScript interfaces |
| `lib/api.ts` | 🆕 New | Typed fetch wrappers |
| `lib/graphColours.ts` | 🆕 New | Cluster colour map |
| `app/layout.tsx` | ✏️ Modify | Generated by scaffolding — add nav |
| `app/page.tsx` | ✏️ Modify | Dashboard (replaces Next.js default) |
| `app/error.tsx` | 🆕 New | Global error boundary |
| `app/not-found.tsx` | 🆕 New | 404 page |
| `app/loading.tsx` | 🆕 New | Root loading |
| `app/papers/page.tsx` | 🆕 New | Search page |
| `app/papers/loading.tsx` | 🆕 New | Search skeleton |
| `app/papers/[id]/page.tsx` | 🆕 New | Paper detail |
| `app/papers/[id]/loading.tsx` | 🆕 New | Detail skeleton |
| `app/graph/page.tsx` | 🆕 New | Graph page |
| `app/graph/loading.tsx` | 🆕 New | Graph skeleton |
| `app/chat/page.tsx` | 🆕 New | Chat page |
| `app/chat/loading.tsx` | 🆕 New | Chat skeleton |
| `components/dashboard/StatCards.tsx` | 🆕 New | |
| `components/dashboard/TechniquesChart.tsx` | 🆕 New | |
| `components/dashboard/ConferenceDonut.tsx` | 🆕 New | |
| `components/dashboard/TopPapersTable.tsx` | 🆕 New | |
| `components/dashboard/ClusterOverview.tsx` | 🆕 New | |
| `components/papers/PaperSearchClient.tsx` | 🆕 New | |
| `components/papers/SearchBar.tsx` | 🆕 New | |
| `components/papers/FilterPanel.tsx` | 🆕 New | |
| `components/papers/PaperCard.tsx` | 🆕 New | |
| `components/papers/Pagination.tsx` | 🆕 New | |
| `components/papers/PaperMeta.tsx` | 🆕 New | |
| `components/papers/AnalysisPanel.tsx` | 🆕 New | |
| `components/papers/TechniqueList.tsx` | 🆕 New | |
| `components/papers/RelatedPapers.tsx` | 🆕 New | |
| `components/papers/EgoGraphWrapper.tsx` | 🆕 New | |
| `components/papers/EgoGraph.tsx` | 🆕 New | |
| `components/graph/GraphCanvas.tsx` | 🆕 New | |
| `components/graph/GraphControls.tsx` | 🆕 New | |
| `components/graph/GraphContext.tsx` | 🆕 New | |
| `components/chat/ChatWindow.tsx` | 🆕 New | |
| `components/chat/MessageBubble.tsx` | 🆕 New | |
| `components/chat/SuggestedPrompts.tsx` | 🆕 New | |
| `components/chat/ChatInput.tsx` | 🆕 New | |
| `components/ui/LoadingSkeleton.tsx` | 🆕 New | |
| `components/ui/ErrorAlert.tsx` | 🆕 New | |

**Total:** 11 backend files (1 modified) · 39 frontend files (2 modified from scaffold)

---

## Time Estimate Summary

| Part | Work | Estimated Time |
|---|---|---|
| 1. Backend API | 11 files, 5 routers, FTS5, RAG service | 2 hr |
| 2. Frontend setup | Scaffold + install + lib/types + lib/api + layout | 45 min |
| 3. Dashboard | 5 components + page | 60 min |
| 4. Search | 5 components + page | 60 min |
| 5. Paper detail | 6 components + page | 90 min |
| 6. Graph | 3 components + context + page | 90 min |
| 7. Chat | 4 components + rag.py + page | 2 hr |
| 8. Polish | Skeletons + error states | 45 min |
| **Total** | | **~10.5 hr** |

Day 1 (5 hr): Parts 1–4 → dashboard + search are live and demable  
Day 2 (5.5 hr): Parts 5–8 → full MVP including graph + chat

---

## Integration Smoke Test (End of Sprint)

Run after all parts are complete:

```bash
# Backend
curl http://localhost:8000/api/v1/stats | python3 -m json.tool | grep total_papers
# Expected: "total_papers": 100

curl "http://localhost:8000/api/v1/papers?q=diffusion&per_page=5" | python3 -m json.tool | grep title
# Expected: 5 paper titles containing diffusion-related content

curl "http://localhost:8000/api/v1/graph?min_weight=2.0" | python3 -m json.tool | grep node_count
# Expected: "node_count": 100

curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"What is LoRA?","stream":false}' | python3 -m json.tool | grep answer
# Expected: answer field with content, sources with ≥1 paper

# Frontend (manual)
open http://localhost:3000           # Dashboard: 4 stat cards visible
open http://localhost:3000/papers    # Search: 20 paper cards visible
open http://localhost:3000/graph     # Graph: 100 nodes, 3 cluster colours
open http://localhost:3000/chat      # Chat: suggested prompts visible
```

---

## Known Gotchas

| Issue | Location | Resolution |
|---|---|---|
| `react-force-graph-2d` breaks SSR | `EgoGraph.tsx`, `GraphCanvas.tsx` | Wrap with `dynamic(..., { ssr: false })` |
| FTS5 may not be in SQLite build | `api/services/fts.py` | Check at startup; fall back to LIKE search |
| `shared_techniques` is a JSON string in DB, not array | `paper_relationships.shared_techniques` | `json.loads()` in API before returning |
| SQLAlchemy sync sessions — not `async` | All routers | Use `get_session()` context manager, not `async with` |
| `eventsource-parser` SSE — CORS headers needed | `api/main.py` | Include `Access-Control-Allow-Origin` in `StreamingResponse` headers |
| `paper_graph_metrics` may not have all 100 papers | `api/routers/papers.py` | `LEFT JOIN` not `INNER JOIN` to avoid dropping papers |
| Graph edge table is directed (A→B, not B→A) | `GET /papers/{id}/related` | UNION both directions as shown in SQL above |
