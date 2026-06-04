# Research Intelligence Platform — Product Design

**Date:** June 2026  
**Status:** Design spec — pre-implementation  
**Scope:** Dashboard · Search · Filters · Paper detail · Recommendations

---

## 0. Design Principles

| Principle | What it means here |
|-----------|-------------------|
| **Task-first** | Every screen answers a researcher's question before they have to scroll |
| **Data density without clutter** | Show citations, venue, year inline — don't hide them behind hovers |
| **Progressive disclosure** | Summary → abstract → full analysis; never dump everything at once |
| **Analysis-ready** | All UI slots are defined now; they show skeleton/placeholder until the analysis API delivers |
| **No chatbot** | Every interaction is structured (filter, click, sort) — not conversational |

---

## 1. Information Architecture

```
/                          ← Dashboard (landing)
/search                    ← Search results (also reached from dashboard)
/paper/:id                 ← Paper detail
/conference/:slug          ← Conference digest (e.g. /conference/neurips-2024)
```

Four top-level routes. No deep nesting. Breadcrumb on detail pages only.

### Global nav (persistent top bar)
```
[Logo]   [Search box — always visible]   [Conferences ▾]   [Browse ▾]
```
- Search box is always interactive — hitting Enter goes to `/search?q=…`
- **Conferences** dropdown: NeurIPS · ICML · ICLR · CVPR · ACL · EMNLP · AAAI (links to `/conference/:slug`)
- **Browse** dropdown: By Year · Top Cited · Recently Added · Open Access Only

---

## 2. Dashboard (`/`)

The dashboard is a **research landscape view** — not a feed. It answers:
*"What's happening across these conferences right now?"*

### Layout (three-column at ≥1280px, collapsing to stacked at mobile)

```
┌─────────────────────────────────────────────────────────────┐
│  [Global nav]                                               │
├────────────────┬────────────────────────┬───────────────────┤
│  LEFT PANEL    │  CENTER               │  RIGHT PANEL      │
│  (240px)       │  (flex, ~600px)       │  (320px)          │
│                │                       │                   │
│  FILTERS       │  CHARTS               │  TOP PAPERS       │
│  (sticky)      │                       │  (sticky)         │
│                │  ┌──────────────────┐ │                   │
│  Conference    │  │ Papers by venue  │ │  1. Gorilla…1,248 │
│  □ NeurIPS 100 │  │ (bar chart)      │ │  2. Refusal… 716  │
│  □ ICML    …   │  └──────────────────┘ │  3. AlphaLLM… 150 │
│  □ ICLR    …   │  ┌──────────────────┐ │  …                │
│                │  │ Papers by year   │ │                   │
│  Year          │  │ (grouped bar)    │ │  CORPUS STATS     │
│  □ 2024        │  └──────────────────┘ │                   │
│  □ 2025        │  ┌──────────────────┐ │  Papers    3,241  │
│  □ 2026        │  │ Citation dist.   │ │  Venues       10  │
│                │  │ (histogram)      │ │  Years     2024–6 │
│  Field         │  └──────────────────┘ │  With PDF    2,1k │
│  ○ All         │                       │                   │
│  ○ ML          │  RECENT HIGHLIGHTS   │  FIELD BREAKDOWN   │
│  ○ CV          │  (3-card row)        │  ML  ██████ 58%   │
│  ○ NLP         │  [card][card][card]  │  CV  ████   31%   │
│  ○ AI          │                       │  NLP ██     11%   │
│                │                       │                   │
└────────────────┴────────────────────────┴───────────────────┘
```

### Charts detail

**Papers by venue** — horizontal bar chart, one bar per conference, sorted descending. Bars are clickable → navigate to `/conference/:slug`.

**Papers by year** — grouped vertical bars (one group per year, one bar per field: ML/CV/NLP/AI). Reveals corpus growth over time.

**Citation distribution** — log-scale histogram with buckets: 0 · 1–9 · 10–49 · 50–99 · 100–499 · 500+. Tooltip shows exact count + % of corpus.

### Recent highlights (3 cards)
Curated automatically: the 3 papers added in the most recent ingestion run that have the highest citation counts. Each card shows:
- Title (truncated to 2 lines)
- Conference badge · Year badge
- Citation count (large, prominent)
- Presentation type chip (oral / spotlight / poster)
- [Analysis summary placeholder] — shows "Analysis pending" until API delivers

### Corpus stats block (right panel)
Static counters: total papers, venues covered, year range, papers with PDF, papers with analysis (0 until API). Updates on each page load.

### Interactions
- All filter checkboxes in the left panel **live-filter the charts** (no submit button). Debounce 200ms.
- Clicking a bar in "Papers by venue" adds that conference to the active filter and pushes state to the URL: `/?conference=NeurIPS,ICML`.
- A "Reset filters" link appears below the filter panel when any filter is active.
- Dashboard URL is fully shareable — filters live in query params.

---

## 3. Search Experience (`/search`)

Search is the **primary navigation mode** for users who know what they want. Secondary mode for exploration.

### Search modes

| Mode | Trigger | Behaviour |
|------|---------|-----------|
| **Keyword** | Default | Substring match on title + abstract (SQLite FTS or ILIKE) |
| **Author** | `author:name` prefix | Match on `authors.full_name` |
| **Venue** | `venue:NeurIPS` prefix | Filter to conference short name |
| **Year** | `year:2024` prefix | Filter to edition year |

Prefix operators are parsed client-side and converted to structured query params before hitting the API.

### Layout

```
┌──────────────────────────────────────────────────────────────┐
│  [Global nav — search box pre-filled]                       │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  "transformer attention"                          [X] Clear  │
│   ────────────────────────────────────────────────────────  │
│   Showing 142 papers  · Sorted by: [Relevance ▾]  [Filters] │
│                                                              │
│  ┌──────────┐  ┌──────────────────────────────────────────┐ │
│  │  FILTERS │  │  RESULTS LIST                            │ │
│  │ (280px)  │  │                                          │ │
│  │  inline  │  │  [Paper card] ×N                         │ │
│  │  (see §4)│  │                                          │ │
│  └──────────┘  └──────────────────────────────────────────┘ │
│                                                              │
│                  [Load more] (pagination anchor)             │
└──────────────────────────────────────────────────────────────┘
```

### Paper card (in search results)

```
┌────────────────────────────────────────────────────────────┐
│  NeurIPS 2024  ·  Oral  ·  📄 PDF                         │
│                                                            │
│  Gorilla: Large Language Model Connected with Massive APIs │
│                                                            │
│  Shishir G. Patil, Tianjun Zhang, Xin Wang, Joseph E. Gonzalez │
│                                                            │
│  The paper introduces Gorilla, a finetuned LLaMA model... │
│  [abstract truncated to 3 lines, "Show more" inline]       │
│                                                            │
│  ★ 1,248 citations  ·  121 influential  ·  Open Access    │
│                                                            │
│  [Analysis: pending]   [View paper →]                      │
└────────────────────────────────────────────────────────────┘
```

Fields visible on the card:
- Conference + year badge (coloured by field: ML=blue, CV=green, NLP=orange, AI=purple)
- Presentation type chip
- PDF availability icon (links to local PDF if downloaded, else openreview URL)
- Title — full, clickable, navigates to `/paper/:id`
- Author list (first 3 + "et al." if more)
- Abstract excerpt (3 lines, expandable inline)
- Citation count + influential count
- Open Access indicator
- Analysis status — "pending" placeholder now, replaced with 1-line summary when API delivers

### Sort options
- **Most Cited** (default for keyword search)
- **Most Recent**
- **Most Influential** (by `influential_citation_count`)
- **Title A–Z**

### Query suggestions
When the search box has ≥ 2 characters, a dropdown shows:
- Up to 5 title completions (substring match)
- Detected prefix operators highlighted: typing "author:Yann" suggests matching author names

### Empty state
If 0 results: show the query, suggest removing one filter, offer "Browse all papers instead".

### URL structure
All search state lives in the URL:
```
/search?q=transformer+attention&conference=NeurIPS,ICLR&year=2024&type=oral&sort=cited
```
Fully shareable and back-button safe.

---

## 4. Filter System

Filters appear in two contexts: the left panel on the dashboard and the left panel on search. They share identical components and URL-param conventions.

### Filter taxonomy

```
CONFERENCE
  □ NeurIPS  (100)
  □ ICML     (…)
  □ ICLR     (…)
  □ CVPR     (…)
  □ ACL      (…)
  □ EMNLP    (…)
  □ AAAI     (…)
  □ IJCAI    (…)
  □ ICCV     (…)
  □ ECCV     (…)

YEAR
  □ 2024  (…)
  □ 2025  (…)
  □ 2026  (…)

FIELD
  ○ All
  ○ Machine Learning
  ○ Computer Vision
  ○ Natural Language Processing
  ○ AI

PRESENTATION TYPE
  □ Oral
  □ Spotlight
  □ Poster
  □ Other

CITATION RANGE
  Min [____]   Max [____]   [Apply]
  Quick: [Top 10%] [Highly cited ≥100] [Any]

PDF AVAILABLE
  □ Has downloaded PDF

ANALYSIS (grayed out until API)
  □ Has analysis summary
  □ Has categories
  □ Has techniques
```

### Filter behaviour rules

1. **Multi-select within group = OR** — checking NeurIPS + ICML returns papers from either.
2. **Multi-select across groups = AND** — Conference=NeurIPS AND Year=2024 returns only NeurIPS 2024 papers.
3. **Active filter count badge** appears on the "Filters" button on mobile: `[Filters 3]`.
4. **Counts in parentheses** update live to reflect "how many results would remain if you also applied this filter" — computed from the current result set, not the full corpus.
5. **Clear individual filter** — each active filter shows an ×; clicking removes just that one.
6. **Clear all** — appears as a link at the top of the panel when any filter is active.
7. **Filters are collapsible** — each group has a toggle; state persists in `localStorage`.
8. **Mobile**: filters live in a bottom sheet, not a sidebar. "Apply" button commits them.

### URL param convention
```
conference=NeurIPS,ICLR    # comma-separated multi-select
year=2024,2025
field=ML
type=oral,spotlight
min_citations=100
has_pdf=1
sort=cited
page=2
```

---

## 5. Paper Detail Page (`/paper/:id`)

The detail page is a **single-paper deep-dive**. It must function fully before the analysis API delivers — all analysis slots show clear "Analysis pending" placeholders.

### Layout

```
┌─────────────────────────────────────────────────────────────────┐
│  [Global nav]                                                   │
│  Breadcrumb: Dashboard > NeurIPS 2024 > Gorilla…               │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  NeurIPS 2024  ·  Oral  ·  Open Access                         │
│                                                                 │
│  Gorilla: Large Language Model Connected with Massive APIs      │
│                                                                 │
│  Shishir G. Patil · Tianjun Zhang · Xin Wang · +1 more         │
│                                                                 │
│  ★ 1,248 citations    ◆ 121 influential    📄 View PDF          │
│                                                                 │
├────────────────────────────────┬────────────────────────────────┤
│  LEFT (content, ~700px)        │  RIGHT (sidebar, 320px)        │
│                                │                                │
│  [ABSTRACT]                    │  QUICK FACTS                   │
│  Full abstract text            │  Published  2024               │
│                                │  Venue      NeurIPS            │
│  ─────────────────             │  Type       Oral               │
│  [ANALYSIS]                    │  Citations  1,248              │
│                                │  Influential 121               │
│  Summary                       │  Open access Yes               │
│  ░░░░░░ pending ░░░░           │  PDF        Downloaded         │
│                                │                                │
│  Categories                    │  ──────────────────            │
│  ░░░░░░ pending ░░░░           │  LINKS                         │
│                                │  [OpenReview ↗]                │
│  Techniques                    │  [Semantic Scholar ↗]          │
│  ░░░░░░ pending ░░░░           │  [arXiv ↗] (if arxiv_id)       │
│                                │                                │
│  Advantages                    │  ──────────────────            │
│  ░░░░░░ pending ░░░░           │  AUTHORS (5)                   │
│                                │                                │
│  Limitations                   │  Shishir G. Patil              │
│  ░░░░░░ pending ░░░░           │  UC Berkeley                   │
│                                │                                │
│  ─────────────────             │  Tianjun Zhang                 │
│  [EXTRACTED SECTIONS]          │  UC Berkeley                   │
│  (available now for PDFs)      │  [+ 3 more]                    │
│                                │                                │
│  Abstract ✓                    │  ──────────────────            │
│  Introduction ✓                │  RECOMMENDATIONS               │
│  Methodology ✓                 │  (see §6)                      │
│  Experiments ✓                 │  [Card] [Card] [Card]          │
│  Results ✓                     │                                │
│  Conclusion ✓                  │                                │
│  [Read full section ▾]         │                                │
│                                │                                │
└────────────────────────────────┴────────────────────────────────┘
```

### Content sections (detail)

**Abstract** — always available. Full text, no truncation.

**Analysis block** — four sub-sections, each with a clear "Analysis pending" skeleton state:
- **Summary** — 2–3 sentence plain-English synopsis (when API delivers)
- **Categories** — pill badges: "Machine Learning", "Tool Learning", etc. (when API delivers)
- **Key Techniques** — tagged list with role chips: `LoRA [introduces]`, `RLHF [uses]` (when API delivers)
- **Advantages · Limitations · Future Work** — bullet lists (when API delivers)

The entire Analysis block renders as a grayed card with a subtle pulse animation while pending. No spinner — the page doesn't feel broken, it just communicates "more coming."

**Extracted sections** — available now for papers that have been through the PDF pipeline. Each section name shows a ✓ or ✗ status. Clicking a section name expands it inline to show the extracted text. Sections with empty bodies are listed as ✗ (not hidden), so users can see what the extractor missed.

**Datasets** — a table: Dataset name · Task · Source. Available once LLM populates `paper_datasets`.

### Author cards (sidebar)
Each author shown as a small card: name + affiliation (from `paper_authors.affiliation`). Clicking an author name navigates to `/search?q=author:Shishir+Patil` — pre-filled author search.

### Paper links
External links open in a new tab. Priority order: OpenReview (if `openreview_id`) > arXiv (if `arxiv_id`) > Semantic Scholar (if `semantic_scholar_id`) > DOI.

### Mobile layout
The sidebar collapses below the main content. Quick Facts and Links appear first (above the fold), then Abstract, then Analysis, then Authors.

---

## 6. Recommendation Workflow

Recommendations are **structurally similar papers** surfaced in three places:
1. The sidebar of the paper detail page ("You might also like")
2. A "Related" tab on the conference digest page
3. A "More like this" action in search results (on hover/tap)

### Recommendation tiers (in order of availability)

The system has no embeddings yet, so recommendations are computed from structured metadata. This is intentional — structured metadata is fast, deterministic, and explainable.

```
Tier 1 — Same conference + year (available now)
  Same conference edition, ordered by citation count descending.
  Label: "Also presented at NeurIPS 2024"

Tier 2 — Citation-neighbourhood (available now, requires enrich_citations)
  Papers in the same venue range (citation_count within 2× of target).
  Biases toward influential peers, not just popular ones.
  Label: "Similar impact"

Tier 3 — Technique overlap (available after analysis API)
  Papers sharing ≥1 technique tag from paper_techniques.
  Label: "Uses similar techniques"

Tier 4 — Category overlap (available after analysis API)
  Papers sharing ≥1 category tag from paper_categories.
  Label: "Same research area"
```

The system picks the highest available tier for each recommendation slot. The label shown to the user always explains the basis: "Similar impact · NeurIPS 2024".

### Recommendation card (compact)

```
┌───────────────────────────────────────────┐
│  NeurIPS 2024  ★ 716                     │
│  Refusal in Language Models Is Mediated… │
│  Similar impact · Same venue             │
└───────────────────────────────────────────┘
```

- Title truncated to 2 lines
- Conference badge + citation count
- Explanation label (the "why")
- Clicking navigates to `/paper/:id` for that paper

### Recommendation panel layout (detail page sidebar)

Shows 3 recommendation cards. A "See more" link expands to 9.

When analysis is pending: show Tier 1 + Tier 2 only. The panel renders the same — no placeholder state, just fewer signals behind the logic.

### "More like this" in search results

On hover (desktop) or long-press (mobile), a paper card reveals a `[+ Similar]` button. Clicking it:
1. Appends the paper's conference + citation range to the active filters
2. Re-runs the search
3. Shows a chip above the results: `Filtered by: Similar to "Gorilla…" [×]`

This is the closest thing to a recommendation flow within search — no navigation required.

---

## 7. Conference Digest Page (`/conference/:slug`)

Secondary page, referenced from the nav dropdown and dashboard chart clicks.

```
/conference/neurips-2024
```

Layout: full-width header (conference name, year, location, total papers, acceptance rate if known) → stats row → papers list with the full filter panel.

Essentially the search page pre-filtered to one conference edition. No special logic needed — it's a URL alias for `/search?conference=NeurIPS&year=2024`.

---

## 8. Component Inventory

| Component | Used in | Notes |
|-----------|---------|-------|
| `PaperCard` | Search, Dashboard, Recommendations | Sizes: full (search), compact (recommendations) |
| `FilterPanel` | Dashboard, Search | Identical component, different container width |
| `CitationBadge` | PaperCard, Detail header | Icon + count, colour-coded by range |
| `ConferenceBadge` | PaperCard, Detail header | Coloured by field |
| `PresentationChip` | PaperCard, Detail header | oral=gold · spotlight=silver · poster=gray |
| `AnalysisBlock` | Detail page | Shows skeleton until data arrives |
| `SectionViewer` | Detail page | Expandable extracted text sections |
| `RecommendationCard` | Detail sidebar | Compact PaperCard variant |
| `MetricsChart` | Dashboard | Bar, grouped-bar, histogram — shared chart component |
| `FilterChip` | Active filter display | Shows selected filter + × to remove |
| `SearchInput` | Global nav | With prefix detection + autocomplete |

---

## 9. API Endpoints (backend contract)

These are the data calls the frontend needs. Map directly to `search/query.py` functions built in the infrastructure phase, plus new endpoints for the detail page and recommendations.

| Endpoint | Method | Maps to | Notes |
|----------|--------|---------|-------|
| `/api/papers` | GET | `search_papers()` | All filter + sort params as query string |
| `/api/papers/:id` | GET | `get_paper()` | Full paper + sections + analysis |
| `/api/papers/:id/authors` | GET | `get_paper_authors()` | Ordered author list |
| `/api/papers/:id/sections` | GET | DB: `paper_sections` | Extracted text sections |
| `/api/papers/:id/analysis` | GET | DB: `paper_analyses` + categories + techniques | Null fields when pending |
| `/api/papers/:id/recommendations` | GET | Tier logic (§6) | Returns 9 candidates with explanation label |
| `/api/metrics` | GET | `metrics/dashboard.py` data functions | Params: conference, year, field |
| `/api/conferences` | GET | `conferences` table | For nav dropdown |

All endpoints return JSON. Pagination via `?limit=&offset=`. All filter params mirror the URL convention from §4.

---

## 10. Analysis Placeholder Strategy

The frontend must not feel broken before the analysis API delivers. Rules:

1. **Never show empty panels** — if `paper_analyses` has no row for a paper, the Analysis block renders with a subtle skeleton (pulsing gray bars), not an empty container.
2. **Never hide the block** — hiding it entirely trains users to ignore it; they'll miss it when it populates.
3. **Show what we have now** — extracted sections (introduction, methodology, etc.) are available from the PDF pipeline. Surface them prominently in the detail page under "Extracted Content" so the page has real value today.
4. **Indicate status clearly** — a one-line note: "AI analysis pending — extracted sections available below."
5. **Graceful upgrade** — when a paper's analysis populates, the skeleton smoothly replaces with real content (CSS transition). No page reload required if the frontend polls `/api/papers/:id/analysis`.

---

## 11. Out of Scope (deferred)

| Feature | Reason |
|---------|--------|
| Chatbot / conversational search | Explicitly deferred |
| User accounts, saved papers, collections | No auth layer yet |
| Email digests / alerts | Requires user accounts |
| Embedding-based similarity | No vectors yet |
| PDF viewer (inline) | Use external PDF URL for now |
| Author profile pages | Needs author disambiguation first |
| Admin/ingestion UI | CLI is sufficient at this stage |
