# Research Intelligence Platform — UI Technical Design

**Date:** 2026-06-08  
**Stack:** Next.js 15 (App Router) · TypeScript · Tailwind · shadcn/ui · FastAPI · SQLite  
**Corpus at design time:** 100 papers · 2,916 graph edges · 1,115 canonical techniques · 3 clusters

---

## 1. System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Browser                                   │
│                                                                  │
│  Next.js 15 (App Router)                                        │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────┐ │
│  │Dashboard │ │  Search  │ │  Paper   │ │  Graph   │ │ Chat │ │
│  │  /       │ │ /papers  │ │/papers/  │ │  /graph  │ │/chat │ │
│  │          │ │          │ │  [id]    │ │          │ │      │ │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘ └──┬───┘ │
│       │            │            │             │           │     │
│       └────────────┴────────────┴─────────────┴───────────┘     │
│                              │                                   │
│                   Next.js Route Handlers                         │
│                   (thin proxy / ISR caching)                     │
└──────────────────────────────┬──────────────────────────────────┘
                               │ HTTP/JSON
                               │
┌──────────────────────────────▼──────────────────────────────────┐
│                    FastAPI (Python 3.11)                          │
│                                                                  │
│  /api/v1/                                                        │
│  ├── stats            GET  Dashboard aggregates                  │
│  ├── papers           GET  Search + filter + paginate            │
│  ├── papers/{id}      GET  Full paper detail                     │
│  ├── papers/{id}/related  GET  Related papers from graph         │
│  ├── papers/{id}/graph    GET  Ego-graph (1-hop neighbourhood)   │
│  ├── techniques       GET  Technique browser + co-occurrence     │
│  ├── graph            GET  Full graph for D3 / Cytoscape         │
│  ├── graph/clusters   GET  Cluster membership                    │
│  └── chat             POST RAG chatbot                           │
│                                                                  │
│  Services layer                                                  │
│  ├── db.py            SQLite connection pool (aiosqlite)         │
│  ├── search.py        FTS5 + ranked keyword search               │
│  ├── graph.py         Graph payload construction                  │
│  └── rag.py           Retrieval + Claude API synthesis            │
└──────────────────────────────┬──────────────────────────────────┘
                               │ aiosqlite
                               │
┌──────────────────────────────▼──────────────────────────────────┐
│               research_platform.db  (SQLite)                     │
│  20 tables — papers, analyses, techniques, relationships,         │
│  graph_metrics, entity_relationships, syntheses …                │
└─────────────────────────────────────────────────────────────────┘
```

### Key architectural decisions

| Decision | Choice | Rationale |
|---|---|---|
| Rendering strategy | Server Components + `use client` islands | Static shell, dynamic data via RSC fetch; graph and chat are client islands |
| API layer | FastAPI, not Next.js API routes | Keep Python DB + RAG logic together; easier to extend with ML libs |
| SQLite concurrency | `aiosqlite` + WAL mode | Handles concurrent reads fine; no write contention on read-only UI |
| Graph library | `react-force-graph` (WebGL) | Handles 2,916 edges without jank; D3 too slow above ~500 edges |
| RAG retrieval | SQL-based (FTS5 + technique match) | No vector DB needed yet; SQLite FTS5 over `paper_sections.full_text` covers the corpus |
| Auth | None for MVP | Single-user local deployment; add Clerk/NextAuth in v2 |

---

## 2. Monorepo Layout

```
research-intelligence-platform/
├── apps/
│   ├── web/                          # Next.js 15
│   │   ├── app/
│   │   │   ├── layout.tsx
│   │   │   ├── page.tsx              # Dashboard
│   │   │   ├── papers/
│   │   │   │   ├── page.tsx          # Search
│   │   │   │   └── [id]/
│   │   │   │       └── page.tsx      # Paper detail
│   │   │   ├── graph/
│   │   │   │   └── page.tsx          # Knowledge graph
│   │   │   └── chat/
│   │   │       └── page.tsx          # Chatbot
│   │   ├── components/
│   │   │   ├── ui/                   # shadcn generated
│   │   │   ├── dashboard/
│   │   │   ├── papers/
│   │   │   ├── graph/
│   │   │   └── chat/
│   │   ├── lib/
│   │   │   ├── api.ts                # typed fetch wrappers
│   │   │   └── types.ts              # shared TS types
│   │   ├── tailwind.config.ts
│   │   └── next.config.ts
│   └── api/                          # FastAPI
│       ├── main.py
│       ├── routers/
│       │   ├── stats.py
│       │   ├── papers.py
│       │   ├── techniques.py
│       │   ├── graph.py
│       │   └── chat.py
│       ├── services/
│       │   ├── db.py
│       │   ├── search.py
│       │   ├── graph.py
│       │   └── rag.py
│       ├── models/                   # Pydantic response models
│       └── requirements.txt
└── research_platform.db              # existing DB (symlinked or path-configured)
```

---

## 3. Page Architecture

### 3.1 Dashboard  `/`

**Purpose:** At-a-glance corpus health and discovery entry point.

```
┌──────────────────────────────────────────────────────────────┐
│  Research Intelligence Platform            [Search]  [Graph] │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐       │
│  │ 100      │ │ 2,916    │ │ 1,115    │ │ 3        │       │
│  │ Papers   │ │ Edges    │ │ Techniques│ │ Clusters │       │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘       │
│                                                              │
│  ┌─────────────────────────┐  ┌──────────────────────────┐  │
│  │  Top Techniques         │  │  Corpus by Conference    │  │
│  │  (horizontal bar chart) │  │  (donut chart)           │  │
│  │  LLMs         ████ 9   │  │  NeurIPS 2024: 100       │  │
│  │  Transformers  ███ 7   │  │                          │  │
│  │  Diffusion     ██  6   │  └──────────────────────────┘  │
│  └─────────────────────────┘                                │
│                                                              │
│  Top Papers by Citation                                      │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ # │ Title                    │ Conf  │ Citations │ Clus │ │
│  │ 1 │ Gorilla: LLM Connected…  │ NeurIPS│   1,248  │  0   │ │
│  │ 2 │ Refusal in LMs…          │ NeurIPS│     716  │  0   │ │
│  └────────────────────────────────────────────────────────┘ │
│                                                              │
│  Recent Activity / Cluster Overview                          │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  Cluster 0 (46 papers)  avg_degree: 0.606              │ │
│  │  Cluster 1 (30 papers)  avg_degree: 0.582              │ │
│  │  Cluster 2 (24 papers)  avg_degree: 0.564              │ │
│  └────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────┘
```

**Components:**
- `<StatCard>` — metric + label (shadcn Card)
- `<TechniquesChart>` — Recharts horizontal bar (client island)
- `<ConferenceDonut>` — Recharts PieChart (client island)
- `<TopPapersTable>` — shadcn Table, links to `/papers/[id]`
- `<ClusterOverview>` — shadcn Badge + progress bars

**Data source:** `GET /api/v1/stats`

---

### 3.2 Paper Search  `/papers`

**Purpose:** Browse, filter, and full-text search the corpus.

```
┌──────────────────────────────────────────────────────────────┐
│  ← Dashboard   Papers                                        │
├────────────────────┬─────────────────────────────────────────┤
│  Filters           │  Search: [_________________________]    │
│                    │                                         │
│  Conference        │  Sort: [Relevance ▼]   100 results      │
│  ☑ NeurIPS 2024   │                                         │
│  ☐ ICLR 2024      │  ┌──────────────────────────────────┐   │
│                    │  │ Gorilla: LLM Connected with APIs  │   │
│  Year              │  │ NeurIPS 2024 · Poster · 1,248 ↑  │   │
│  2024 ▓▓▓▓▓▓▓▓▓  │  │ Techniques: LLMs · RAT · BM25    │   │
│                    │  │ Cluster 0 · Centrality: high      │   │
│  Cluster           │  └──────────────────────────────────┘   │
│  ● All             │                                         │
│  ○ 0 (LLM-heavy)  │  ┌──────────────────────────────────┐   │
│  ○ 1              │  │ Refusal in Language Models…       │   │
│  ○ 2              │  │ NeurIPS 2024 · Poster · 716 ↑     │   │
│                    │  │ Techniques: RLHF · DPO · LLMs    │   │
│  Technique         │  └──────────────────────────────────┘   │
│  [search tech…]   │                                         │
│                    │  [Load more]                            │
└────────────────────┴─────────────────────────────────────────┘
```

**Components:**
- `<SearchBar>` — debounced input, triggers `router.push` with `?q=`
- `<FilterPanel>` — conference checkboxes, cluster radio, technique combobox (shadcn)
- `<PaperCard>` — title, venue badge, citation count, top-3 techniques, cluster badge
- `<SortSelect>` — relevance / citations / centrality / date

**URL shape:** `/papers?q=diffusion&conference=NeurIPS&cluster=0&technique=LoRA&sort=citations&page=1`

**Data source:** `GET /api/v1/papers`

---

### 3.3 Paper Detail  `/papers/[id]`

**Purpose:** Full paper record — analysis, techniques, related papers, graph ego-network.

```
┌──────────────────────────────────────────────────────────────┐
│  ← Search   Gorilla: LLM Connected with Massive APIs         │
├───────────────────────────────┬──────────────────────────────┤
│  METADATA                     │  ANALYSIS (AI Summary)       │
│  NeurIPS 2024 · Poster        │  ┌──────────────────────┐   │
│  Citations: 1,248              │  │ Presents Gorilla, a  │   │
│  Cluster: 0                   │  │ LLM that can write   │   │
│  Centrality: 0.71 (top 10%)   │  │ API calls accurately │   │
│                               │  │ …                    │   │
│  PDF  ArXiv  OpenReview       │  ├──────────────────────┤   │
│                               │  │ Advantages           │   │
│  AUTHORS                      │  │ Limitations          │   │
│  Shishir G. Patil et al.      │  │ Future Work          │   │
│                               │  │ Use Cases            │   │
│  TECHNIQUES                   │  └──────────────────────┘   │
│  Introduces:                  │                              │
│    Gorilla · RAT · APIBench   │  RELATED PAPERS              │
│  Uses:                        │  ┌──────────────────────┐   │
│    LLMs · LLaMA · BM25…       │  │ Paper B  weight 4.2  │   │
│                               │  │ Paper C  weight 3.8  │   │
│  CATEGORIES                   │  │ Paper D  weight 3.1  │   │
│  LLM · API · Code Gen         │  └──────────────────────┘   │
│                               │                              │
│  DATASETS                     │  EGO GRAPH (1-hop)           │
│  HuggingFace · TorchHub       │  ┌──────────────────────┐   │
│                               │  │  [mini force graph]  │   │
│                               │  └──────────────────────┘   │
└───────────────────────────────┴──────────────────────────────┘
```

**Components:**
- `<PaperMeta>` — metadata chips, external links
- `<AnalysisPanel>` — collapsible sections from `paper_analyses`
- `<TechniqueList>` — grouped by role (introduces / uses / compares / critiques), linked to technique browser
- `<RelatedPapers>` — ranked list from `paper_relationships`, weight displayed
- `<EgoGraph>` — client island, `react-force-graph-2d`, 1-hop neighbourhood only

**Data sources:**
- `GET /api/v1/papers/{id}`
- `GET /api/v1/papers/{id}/related`
- `GET /api/v1/papers/{id}/graph`

---

### 3.4 Knowledge Graph  `/graph`

**Purpose:** Interactive exploration of the full paper-to-paper and entity-to-entity relationship graph.

```
┌──────────────────────────────────────────────────────────────┐
│  Graph Controls              ┌─────────────────────────────┐ │
│  View: ● Papers ○ Techniques │                             │ │
│  Colour by: [Cluster ▼]      │   WebGL force graph         │ │
│  Edge threshold: ──●─── 2.0  │   (react-force-graph)       │ │
│  Show labels: [●]            │                             │ │
│                              │   • 100 nodes               │ │
│  Search node: [_________]    │   • 2,916 edges             │ │
│                              │   • 3 colour-coded clusters │ │
│  Selected paper:             │                             │ │
│  ┌────────────────────────┐  └─────────────────────────────┘ │
│  │ Gorilla: LLM…          │                                  │
│  │ Cluster 0              │  Legend                          │
│  │ Centrality 0.71        │  ● Cluster 0  ● Cluster 1       │
│  │ [Open paper →]         │  ● Cluster 2                    │
│  └────────────────────────┘                                  │
└──────────────────────────────────────────────────────────────┘
```

**Components:**
- `<GraphCanvas>` — `react-force-graph-2d` (WebGL), client island
  - Nodes coloured by `cluster_id` from `paper_graph_metrics`
  - Node size proportional to `degree_centrality`
  - Edge width proportional to `weight`
  - Click node → shows `<PaperPopover>`, links to detail page
- `<GraphControls>` — edge threshold slider, label toggle, view mode (papers vs techniques), search
- `<GraphLegend>` — cluster colour key
- `<PaperPopover>` — appears on node click: title, cluster, centrality, link

**Data sources:**
- `GET /api/v1/graph` — full graph payload `{nodes, edges}`
- `GET /api/v1/graph/clusters` — cluster membership for colour mapping

**Performance note:** At 100 papers + 2,916 edges, WebGL renders at 60fps with no throttling. At 400 papers (~15,000 edges) apply edge threshold filter by default (threshold ≥ 2.0 drops to ~3,000 edges). At 1,000 papers, switch to server-side subgraph pruning before sending to client.

---

### 3.5 Research Chatbot  `/chat`

**Purpose:** Natural language Q&A over the corpus using RAG — retrieves relevant paper sections and analyses, synthesises with Claude.

```
┌──────────────────────────────────────────────────────────────┐
│  Research Chat                           [New conversation]  │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  Suggested prompts:                                          │
│  "What papers use LoRA for fine-tuning?"                     │
│  "Summarize diffusion model trends in this corpus"           │
│  "Which papers are most central to cluster 0?"               │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ [User] What are the main approaches to LLM alignment?  │ │
│  └────────────────────────────────────────────────────────┘ │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ [Assistant]                                            │ │
│  │ Based on 6 papers in the corpus, LLM alignment uses:   │ │
│  │ 1. RLHF (Refusal in LMs, LACIE)                       │ │
│  │ 2. DPO (Critical Eval of AI Feedback)                  │ │
│  │ 3. Constitutional AI methods…                          │ │
│  │                                                        │ │
│  │ Sources: [Refusal in LMs] [LACIE] [Critical Eval…]    │ │
│  └────────────────────────────────────────────────────────┘ │
│                                                              │
│  [Type your question…                           ] [Send]    │
└──────────────────────────────────────────────────────────────┘
```

**Components:**
- `<ChatWindow>` — message history, streaming response (Server-Sent Events)
- `<MessageBubble>` — user/assistant styling, source citations as chips
- `<SourceChip>` — paper title, links to `/papers/[id]`
- `<SuggestedPrompts>` — pre-seeded prompts on empty state

**Data source:** `POST /api/v1/chat`

---

## 4. API Specification

### Base URL: `http://localhost:8000/api/v1`

---

### `GET /stats`

Dashboard aggregates.

**Response:**
```json
{
  "total_papers": 100,
  "total_edges": 2916,
  "total_techniques": 1115,
  "total_clusters": 3,
  "conferences": [
    { "short_name": "NeurIPS", "year": 2024, "count": 100 }
  ],
  "clusters": [
    { "cluster_id": 0, "paper_count": 46, "avg_degree_centrality": 0.606 },
    { "cluster_id": 1, "paper_count": 30, "avg_degree_centrality": 0.582 },
    { "cluster_id": 2, "paper_count": 24, "avg_degree_centrality": 0.564 }
  ],
  "top_techniques": [
    { "canonical_name": "Large Language Models", "paper_count": 9 },
    { "canonical_name": "Transformers", "paper_count": 7 }
  ],
  "top_papers": [
    {
      "id": "...", "title": "Gorilla…", "citation_count": 1248,
      "conference": "NeurIPS", "year": 2024, "cluster_id": 0
    }
  ]
}
```

---

### `GET /papers`

Full-text search + filter + sort + paginate.

**Query params:**

| Param | Type | Default | Description |
|---|---|---|---|
| `q` | string | — | FTS5 search over title, abstract, summary |
| `conference` | string | — | `NeurIPS`, `ICLR`, etc. |
| `year` | int | — | Filter by year |
| `cluster` | int | — | 0, 1, 2 |
| `technique` | string | — | Filter by canonical_name |
| `sort` | enum | `relevance` | `relevance`, `citations`, `centrality`, `date` |
| `page` | int | 1 | |
| `per_page` | int | 20 | Max 100 |

**Response:**
```json
{
  "total": 15,
  "page": 1,
  "per_page": 20,
  "papers": [
    {
      "id": "...",
      "title": "Gorilla…",
      "abstract": "We introduce Gorilla…",
      "conference": "NeurIPS",
      "year": 2024,
      "presentation_type": "poster",
      "citation_count": 1248,
      "cluster_id": 0,
      "degree_centrality": 0.71,
      "top_techniques": ["Large Language Models", "LLaMA", "BM25"],
      "top_categories": ["LLM", "API Integration"],
      "pdf_url": "...",
      "arxiv_id": "..."
    }
  ]
}
```

---

### `GET /papers/{id}`

Full paper record.

**Response:**
```json
{
  "id": "...",
  "title": "Gorilla…",
  "abstract": "...",
  "conference": "NeurIPS",
  "year": 2024,
  "presentation_type": "poster",
  "citation_count": 1248,
  "influential_citation_count": 42,
  "pdf_url": "...",
  "arxiv_id": "...",
  "openreview_id": "...",
  "authors": [
    { "full_name": "Shishir G. Patil", "position": 1, "affiliation": "UC Berkeley" }
  ],
  "analysis": {
    "summary": "Presents Gorilla…",
    "advantages": "...",
    "limitations": "...",
    "future_work": "...",
    "use_cases": "..."
  },
  "techniques": {
    "introduces": ["Gorilla", "RAT", "APIBench"],
    "uses": ["Large Language Models", "LLaMA", "BM25"],
    "compares": [],
    "critiques": []
  },
  "categories": ["LLM", "API Integration", "Code Generation"],
  "datasets": ["HuggingFace API", "Torch Hub API", "TensorFlow Hub API"],
  "methodologies": ["Retriever-Aware Training"],
  "graph_metrics": {
    "cluster_id": 0,
    "degree_centrality": 0.71,
    "betweenness_centrality": 0.45,
    "neighbors_count": 71,
    "total_edge_weight": 89.3
  }
}
```

---

### `GET /papers/{id}/related`

Top related papers from `paper_relationships`.

**Query params:** `limit` (default 10, max 50)

**Response:**
```json
{
  "paper_id": "...",
  "related": [
    {
      "paper": { "id": "...", "title": "...", "citation_count": 150 },
      "weight": 4.2,
      "shared_techniques": ["Large Language Models", "RLHF"],
      "shared_categories": ["LLM"]
    }
  ]
}
```

---

### `GET /papers/{id}/graph`

1-hop ego-graph for the paper detail mini-visualisation.

**Response:**
```json
{
  "nodes": [
    { "id": "...", "title": "Gorilla…", "cluster_id": 0, "degree_centrality": 0.71, "is_ego": true },
    { "id": "...", "title": "Related Paper…", "cluster_id": 0, "degree_centrality": 0.55, "is_ego": false }
  ],
  "edges": [
    { "source": "...", "target": "...", "weight": 4.2 }
  ]
}
```

---

### `GET /techniques`

Technique browser with co-occurrence data.

**Query params:** `q` (search), `min_papers` (default 2), `sort` (`usage`, `papers`), `page`, `per_page`

**Response:**
```json
{
  "total": 1115,
  "techniques": [
    {
      "canonical_name": "Large Language Models",
      "paper_count": 9,
      "usage_count": 9,
      "connected_papers_count": 9,
      "top_cooccurring": ["Transformers", "RLHF", "LoRA"],
      "roles": { "introduces": 1, "uses": 8 }
    }
  ]
}
```

---

### `GET /graph`

Full graph payload for the Knowledge Graph page.

**Query params:**
- `edge_min_weight` (default 1.0) — prune low-weight edges
- `view` — `papers` (default) or `techniques`
- `cluster` — filter to single cluster

**Response (papers view):**
```json
{
  "nodes": [
    {
      "id": "...",
      "title": "Gorilla…",
      "cluster_id": 0,
      "degree_centrality": 0.71,
      "citation_count": 1248,
      "conference": "NeurIPS",
      "year": 2024
    }
  ],
  "edges": [
    { "source": "uuid-a", "target": "uuid-b", "weight": 4.2 }
  ],
  "meta": {
    "node_count": 100,
    "edge_count": 2916,
    "clusters": [0, 1, 2]
  }
}
```

---

### `POST /chat`

RAG chatbot — retrieves context from DB, synthesises with Claude.

**Request:**
```json
{
  "message": "What are the main approaches to LLM alignment in this corpus?",
  "conversation_id": "optional-uuid-for-history",
  "stream": true
}
```

**Response (streaming SSE):**
```
data: {"type": "sources", "papers": [{"id":"...","title":"Refusal in LMs…"}, ...]}
data: {"type": "token", "content": "Based on 6 papers"}
data: {"type": "token", "content": " in the corpus"}
...
data: {"type": "done"}
```

**Response (non-streaming):**
```json
{
  "answer": "Based on 6 papers in the corpus…",
  "sources": [
    { "id": "...", "title": "Refusal in Language Models…", "relevance_score": 0.92 }
  ],
  "conversation_id": "uuid"
}
```

---

## 5. Database Queries

### Dashboard

**Stats aggregate:**
```sql
-- Single query covering most stat cards
SELECT
  (SELECT COUNT(*) FROM papers)              AS total_papers,
  (SELECT COUNT(*) FROM paper_relationships) AS total_edges,
  (SELECT COUNT(DISTINCT canonical_name) 
   FROM paper_techniques 
   WHERE canonical_name IS NOT NULL)         AS total_techniques,
  (SELECT COUNT(DISTINCT cluster_id) 
   FROM paper_graph_metrics)                 AS total_clusters;
```

**Top techniques (bar chart):**
```sql
SELECT canonical_name, COUNT(DISTINCT paper_id) AS paper_count
FROM paper_techniques
WHERE canonical_name IS NOT NULL
GROUP BY canonical_name
ORDER BY paper_count DESC
LIMIT 15;
```

**Cluster overview:**
```sql
SELECT
  cluster_id,
  COUNT(*)                     AS paper_count,
  AVG(degree_centrality)       AS avg_degree,
  AVG(betweenness_centrality)  AS avg_betweenness
FROM paper_graph_metrics
GROUP BY cluster_id
ORDER BY cluster_id;
```

**Top papers:**
```sql
SELECT
  p.id, p.title, p.citation_count, p.presentation_type,
  co.short_name AS conference, ce.year,
  pgm.cluster_id, pgm.degree_centrality
FROM papers p
LEFT JOIN conference_editions ce ON p.conference_edition_id = ce.id
LEFT JOIN conferences co ON ce.conference_id = co.id
LEFT JOIN paper_graph_metrics pgm ON p.id = pgm.paper_id
ORDER BY p.citation_count DESC
LIMIT 10;
```

---

### Paper Search

**FTS5 full-text search (requires FTS5 virtual table — see setup note):**
```sql
-- Create once at startup (if not exists):
CREATE VIRTUAL TABLE IF NOT EXISTS papers_fts USING fts5(
  paper_id UNINDEXED,
  title,
  abstract,
  summary,
  content='',
  tokenize='porter unicode61'
);

-- Search query:
SELECT
  p.id, p.title, p.abstract, p.citation_count, p.year,
  p.presentation_type, p.pdf_url, p.arxiv_id,
  co.short_name AS conference,
  pgm.cluster_id, pgm.degree_centrality,
  bm25(papers_fts) AS rank
FROM papers_fts
JOIN papers p ON papers_fts.paper_id = p.id
LEFT JOIN conference_editions ce ON p.conference_edition_id = ce.id
LEFT JOIN conferences co ON ce.conference_id = co.id
LEFT JOIN paper_graph_metrics pgm ON p.id = pgm.paper_id
WHERE papers_fts MATCH :query
ORDER BY bm25(papers_fts)  -- or citation_count, or degree_centrality
LIMIT :per_page OFFSET :offset;
```

**Without FTS (fallback, LIKE):**
```sql
SELECT p.*, co.short_name, pgm.cluster_id, pgm.degree_centrality
FROM papers p
LEFT JOIN conference_editions ce ON p.conference_edition_id = ce.id
LEFT JOIN conferences co ON ce.conference_id = co.id
LEFT JOIN paper_graph_metrics pgm ON p.id = pgm.paper_id
WHERE (p.title LIKE :q OR p.abstract LIKE :q)
  AND (:conference IS NULL OR co.short_name = :conference)
  AND (:cluster     IS NULL OR pgm.cluster_id = :cluster)
  AND (:year        IS NULL OR p.year = :year)
ORDER BY p.citation_count DESC
LIMIT :per_page OFFSET :offset;
```

**Filter by technique:**
```sql
SELECT DISTINCT p.id
FROM papers p
JOIN paper_techniques pt ON pt.paper_id = p.id
WHERE pt.canonical_name = :technique;
-- Use as subquery or CTE combined with main search
```

---

### Paper Detail

**Full paper + analysis + graph metrics:**
```sql
SELECT
  p.*, pa.summary, pa.advantages, pa.limitations, pa.future_work, pa.use_cases,
  pgm.cluster_id, pgm.degree_centrality, pgm.betweenness_centrality,
  pgm.neighbors_count, pgm.total_edge_weight,
  co.short_name AS conference, ce.year
FROM papers p
LEFT JOIN paper_analyses pa ON pa.paper_id = p.id
LEFT JOIN paper_graph_metrics pgm ON pgm.paper_id = p.id
LEFT JOIN conference_editions ce ON p.conference_edition_id = ce.id
LEFT JOIN conferences co ON ce.conference_id = co.id
WHERE p.id = :id;
```

**Techniques by role:**
```sql
SELECT name, canonical_name, role
FROM paper_techniques
WHERE paper_id = :id
ORDER BY role, name;
```

**Authors:**
```sql
SELECT a.full_name, a.primary_affiliation, pa.position, pa.is_corresponding
FROM paper_authors pa
JOIN authors a ON a.id = pa.author_id
WHERE pa.paper_id = :id
ORDER BY pa.position;
```

**Related papers:**
```sql
SELECT
  pr.weight, pr.shared_techniques, pr.shared_categories,
  pr.technique_score, pr.category_score,
  p.id, p.title, p.citation_count, p.year,
  pgm.cluster_id, pgm.degree_centrality
FROM paper_relationships pr
JOIN papers p ON p.id = pr.target_paper_id
LEFT JOIN paper_graph_metrics pgm ON pgm.paper_id = p.id
WHERE pr.source_paper_id = :id
ORDER BY pr.weight DESC
LIMIT :limit;
```

---

### Knowledge Graph

**Full graph payload:**
```sql
-- Nodes
SELECT
  p.id, p.title, p.citation_count, p.year,
  co.short_name AS conference,
  pgm.cluster_id, pgm.degree_centrality, pgm.betweenness_centrality
FROM papers p
LEFT JOIN paper_graph_metrics pgm ON pgm.paper_id = p.id
LEFT JOIN conference_editions ce ON p.conference_edition_id = ce.id
LEFT JOIN conferences co ON ce.conference_id = co.id;

-- Edges (filtered by weight threshold)
SELECT source_paper_id AS source, target_paper_id AS target, weight
FROM paper_relationships
WHERE weight >= :min_weight
ORDER BY weight DESC;
```

**Technique graph:**
```sql
-- Nodes
SELECT canonical_name, usage_count, connected_papers_count
FROM technique_graph_metrics
WHERE usage_count >= :min_usage;

-- Edges
SELECT source_entity, target_entity, co_occurrence_count, weight
FROM entity_relationships
WHERE entity_type = 'technique' AND weight >= :min_weight;
```

---

### RAG Retrieval

**Step 1 — Extract candidate technique names from query (keyword match):**
```sql
SELECT DISTINCT canonical_name
FROM paper_techniques
WHERE canonical_name LIKE :term OR name LIKE :term
LIMIT 10;
```

**Step 2 — Find papers matching extracted techniques:**
```sql
SELECT DISTINCT paper_id
FROM paper_techniques
WHERE canonical_name IN (:tech_list);
```

**Step 3 — Pull context for matched papers:**
```sql
SELECT
  p.title, p.abstract,
  pa.summary, pa.advantages, pa.limitations, pa.future_work,
  ps.methodology, ps.results, ps.conclusion
FROM papers p
LEFT JOIN paper_analyses pa ON pa.paper_id = p.id
LEFT JOIN paper_sections ps ON ps.paper_id = p.id
WHERE p.id IN (:paper_ids)
LIMIT 8;
```

**Step 4 — Fallback: FTS5 search on question terms:**
```sql
SELECT paper_id, bm25(papers_fts) AS rank
FROM papers_fts
WHERE papers_fts MATCH :query
ORDER BY rank
LIMIT 8;
```

**Context assembly** (Python in `rag.py`):
```python
context_blocks = []
for paper in retrieved_papers:
    block = f"PAPER: {paper.title}\n"
    block += f"SUMMARY: {paper.summary}\n"
    if paper.methodology:
        block += f"METHODOLOGY: {paper.methodology[:500]}\n"
    context_blocks.append(block)

system_prompt = """You are a research assistant with access to a curated ML paper corpus.
Answer questions based ONLY on the provided paper excerpts.
Always cite which papers your answer draws from.
If the corpus does not contain relevant information, say so clearly."""
```

---

## 6. Component Library (shadcn/ui usage)

```
Core layout:     Sheet, Separator, ScrollArea, Breadcrumb
Navigation:      NavigationMenu, Badge
Data display:    Table, Card, Avatar, HoverCard, Tooltip
Forms/search:    Input, Button, Select, Combobox, Slider, Checkbox, RadioGroup
Charts:          (Recharts) — BarChart, PieChart, LineChart
Feedback:        Skeleton, Spinner, Alert, Toast
Chat:            (custom) using ScrollArea + Input + Button
Graph:           (react-force-graph-2d) — not shadcn, full client island
```

---

## 7. Development Order (MVP Plan)

### Week 1 — Backend + core pages

**Day 1: FastAPI scaffold + DB connection**
- [ ] Create `apps/api/` structure
- [ ] `db.py` — aiosqlite connection pool, WAL mode, read-only flag
- [ ] `GET /stats` router — dashboard aggregates query
- [ ] `GET /papers` router — LIKE search (FTS5 in Day 3), filters, sort, pagination
- [ ] CORS configured for `localhost:3000`
- [ ] Test with `curl` / httpx

**Day 2: Next.js scaffold + Dashboard**
- [ ] `npx create-next-app@latest apps/web --typescript --tailwind --app`
- [ ] Install shadcn: `npx shadcn@latest init`
- [ ] Add required components: card, table, badge, skeleton
- [ ] Install Recharts: `npm i recharts`
- [ ] Build `<StatCard>`, `<TechniquesChart>`, `<TopPapersTable>`
- [ ] Dashboard page (`/`) wired to `GET /stats`
- [ ] Skeleton loading states

**Day 3: Paper Search page**
- [ ] `GET /papers` full implementation with FTS5 virtual table setup
- [ ] FTS5 population script (runs at API startup if table empty)
- [ ] `<SearchBar>` with debounce (300ms)
- [ ] `<FilterPanel>` — conference, cluster, technique combobox
- [ ] `<PaperCard>` component
- [ ] URL-driven state (`useSearchParams`)

**Day 4: Paper Detail page**
- [ ] `GET /papers/{id}` router
- [ ] `GET /papers/{id}/related` router
- [ ] `<PaperMeta>`, `<AnalysisPanel>`, `<TechniqueList>`, `<RelatedPapers>`
- [ ] Loading skeletons
- [ ] External links (PDF, ArXiv, OpenReview)

**Day 5: Knowledge Graph page**
- [ ] `GET /graph` router with edge threshold param
- [ ] Install `react-force-graph`: `npm i react-force-graph-2d`
- [ ] `<GraphCanvas>` client island — nodes, edges, cluster colours
- [ ] `<GraphControls>` — edge threshold slider, search
- [ ] Node click → `<PaperPopover>` → link to detail page
- [ ] Cluster colour legend

---

### Week 2 — RAG Chatbot + polish

**Day 6: RAG chatbot backend**
- [ ] `POST /chat` router
- [ ] `rag.py` — retrieval pipeline (technique match + FTS5 fallback)
- [ ] Context assembly (max 8 papers, max 4,000 tokens of context)
- [ ] Claude API call with `anthropic` SDK (streaming)
- [ ] SSE streaming response
- [ ] Source citation extraction from retrieved papers

**Day 7: Chatbot frontend**
- [ ] `<ChatWindow>`, `<MessageBubble>` components
- [ ] SSE streaming via `EventSource` or `fetch` with `ReadableStream`
- [ ] `<SourceChip>` with paper link
- [ ] `<SuggestedPrompts>` on empty state
- [ ] Conversation history (in-memory, `useState`)

**Day 8: Ego graph on Paper Detail + Technique browser**
- [ ] `GET /papers/{id}/graph` router
- [ ] `<EgoGraph>` mini force-graph on paper detail page
- [ ] `GET /techniques` router
- [ ] Technique browser page (optional, linked from technique chips)

**Day 9: Polish + loading states + error handling**
- [ ] Global error boundary (`error.tsx`)
- [ ] `not-found.tsx` for invalid paper IDs
- [ ] API error responses standardised (`{"error": "...", "code": 404}`)
- [ ] Mobile-responsive layout pass (search + detail)
- [ ] shadcn Toast notifications for API errors

**Day 10: Integration testing + deployment prep**
- [ ] End-to-end smoke tests (Playwright — 5 key flows)
- [ ] `Dockerfile` for FastAPI
- [ ] `next.config.ts` — set `output: 'standalone'` for Docker
- [ ] Environment variable setup (`ANTHROPIC_API_KEY`, `DB_PATH`, `API_URL`)
- [ ] `docker-compose.yml` — web + api services

---

## 8. MVP Definition

The MVP is **fully usable** after Day 7 (end of Week 1 + 2 days). Features by tier:

### MVP (Days 1–7)
- ✅ Dashboard with live corpus stats
- ✅ Paper search with full-text + filters
- ✅ Paper detail with AI analysis, techniques, related papers
- ✅ Knowledge graph with cluster colours, edge filtering, node click
- ✅ RAG chatbot with streaming and source citations

### V1.1 (Days 8–10)
- Ego graph on paper detail page
- Technique browser page
- Mobile-responsive polish
- Error boundaries + loading skeletons throughout

### V2 (post-MVP, after Phase 1 corpus expansion)
- Conference timeline chart (once ICLR + ICML ingested)
- Technique trend charts over time
- Author profile pages
- Saved searches / bookmarks (requires auth)
- Export to CSV / BibTeX
- Graph cluster labelling (auto-named via top techniques)

---

## 9. Environment Setup

### FastAPI

```bash
cd apps/api
python -m venv .venv && source .venv/bin/activate
pip install fastapi uvicorn aiosqlite anthropic python-dotenv

# .env
DB_PATH=../../research_platform.db
ANTHROPIC_API_KEY=sk-ant-...
CORS_ORIGIN=http://localhost:3000

# Run
uvicorn main:app --reload --port 8000
```

### Next.js

```bash
cd apps/web
npm install

# .env.local
NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1

# Run
npm run dev   # port 3000
```

### FastAPI main.py bootstrap

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import stats, papers, techniques, graph, chat
from services.db import init_db

app = FastAPI(title="Research Intelligence Platform API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.getenv("CORS_ORIGIN", "http://localhost:3000")],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup():
    await init_db()   # enables WAL, creates FTS5 table if needed

app.include_router(stats.router, prefix="/api/v1")
app.include_router(papers.router, prefix="/api/v1")
app.include_router(techniques.router, prefix="/api/v1")
app.include_router(graph.router, prefix="/api/v1")
app.include_router(chat.router, prefix="/api/v1")
```

### db.py (key pattern)

```python
import aiosqlite, os

DB_PATH = os.getenv("DB_PATH", "research_platform.db")

async def get_db():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        await db.execute("PRAGMA journal_mode=WAL")
        await db.execute("PRAGMA query_only=ON")   # safety: no writes from API
        yield db
```

---

## 10. Risk Register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| FTS5 not enabled in SQLite build | Low | Medium | Test at startup; fall back to LIKE search automatically |
| Graph page slow at 400 papers / ~15K edges | Medium | Medium | Default edge threshold 2.0 prunes to ~3K edges; WebGL handles fine |
| Claude API latency on chat (RAG) | Medium | Low | Stream tokens so perceived latency is near-zero |
| `react-force-graph` SSR incompatible | High | Low | Already a `"use client"` island with `dynamic(() => import(...), { ssr: false })` |
| SQLite concurrent read contention | Low | Low | WAL mode + read-only API flag; 100 papers → microsecond queries |
| FTS5 index out of sync after corpus expansion | Medium | Low | Rebuild FTS table at API startup if paper count differs from FTS row count |
