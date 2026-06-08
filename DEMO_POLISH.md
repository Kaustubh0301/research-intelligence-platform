# Demo Polish Audit

**Date:** 2026-06-08  
**Scope:** All five pages — Dashboard, Papers, Paper Detail, Graph, Research Assistant

---

## Issues Found

### 1. Build-blocking TypeScript error
**File:** `src/components/papers/PaperMeta.tsx`  
**Severity:** CRITICAL — blocks `next build`  
**Detail:** `<Button asChild>` used four times; the project's `Button` component has no `asChild`/Slot support.  
**Note:** `PaperMeta.tsx` is unused — `PaperHero.tsx` is the actual rendered component on the detail page — but Next.js type-checks all files during build regardless.  
**Fix:** Replace `<Button asChild>` with `<a className={buttonVariants(...)}>`, matching the pattern already used in `PaperHero.tsx`.

---

### 2. Mobile layout — Graph page broken
**File:** `src/components/graph/GraphPageClient.tsx`, `GraphControls.tsx`  
**Severity:** HIGH — layout collapses on mobile; canvas gets near-zero width  
**Detail:** Left sidebar is `w-72` (288px) and right source panel is also `w-72`. On a 375px iPhone the graph canvas would be 375-288 = 87px wide, rendering as a thin strip with overlapping UI.  
**Fix:** Hide the sidebar on mobile behind a drawer toggle; show a bottom sheet or collapse it entirely under a button.

---

### 3. Mobile layout — Chat page broken  
**File:** `src/components/chat/ChatPageClient.tsx`  
**Severity:** HIGH — three fixed-width columns overflow on mobile  
**Detail:** Left sidebar `w-60` (240px) + right panel `w-72` (288px) = 528px of sidebars on a 375px screen. Main chat area gets negative width.  
**Fix:** Hide both sidebars on mobile; left sidebar behind a menu button, right panel behind a "Sources" toggle button.

---

### 4. Dashboard — no error boundary for backend-down state
**File:** `src/app/page.tsx`  
**Severity:** MEDIUM — demo risk  
**Detail:** `api.stats()` throws if the backend is unreachable. Next.js catches it and renders `error.tsx`, which shows a raw error message like `API 500 /stats: ...`. During a demo this surfaces an unhelpful error.  
**Fix:** Wrap the server fetch in a try/catch and render a friendly "Backend unavailable" fallback inline rather than throwing to the error boundary.

---

### 5. Graph page — node labels on-by-default is too noisy
**File:** `src/components/graph/GraphCanvas.tsx`  
**Severity:** LOW — visual quality  
**Detail:** `showLabels` defaults to `false` in `GraphContext` but `nodeCanvasObjectMode` is always `"replace"`, meaning the custom `nodeCanvasObject` runs for every node every frame regardless. When labels are off, the function still runs and draws the circle — correct but slightly wasteful. More importantly: the first impression of the graph on a demo shows 100 unlabelled dots with no orientation hint.  
**Fix:** Default `showLabels` to `true`, but only show labels when `globalScale >= 1.2` (already in the code). This gives orientation on load without clutter when zoomed out.

---

### 6. Chat page — "Research Assistant" nav label too long
**File:** `src/components/ui/NavLinks.tsx`  
**Severity:** LOW — visual overflow on narrow screens  
**Detail:** "Research Assistant" is 19 characters. On a 375px screen with 4 nav items this overflows the header.  
**Fix:** Shorten to "Assistant" on mobile via responsive text class.

---

### 7. Graph controls — cluster labels use hardcoded descriptions not aligned with data
**File:** `src/components/graph/GraphControls.tsx`  
**Severity:** LOW — visual inconsistency  
**Detail:** The GraphControls sidebar displays `CLUSTER_LABELS` from `constants.ts` ("Theory & Optimization", etc.), but these are not shown in the Papers page `FilterPanel.tsx` which only shows "Cluster 0/1/2". Inconsistency across pages.  
**Fix:** Use the same `CLUSTER_LABELS` constant in `FilterPanel.tsx` so cluster descriptions appear consistently.

---

### 8. Papers page — FilterPanel cluster descriptions missing
**File:** `src/components/papers/FilterPanel.tsx`  
**Severity:** LOW — inconsistency with Graph page  
**Detail:** Cluster filter shows only "Cluster 0/1/2" without descriptions. Graph controls show full labels.  
**Fix:** Import and display `CLUSTER_LABELS` in the cluster radio options.

---

### 9. MessageBubble streaming — renders bold HTML literally if `<strong>` tags present
**File:** `src/components/chat/MessageBubble.tsx`  
**Severity:** LOW — cosmetic  
**Detail:** The `renderContent` function uses `dangerouslySetInnerHTML` to render `**text**` → `<strong>text</strong>`. If Claude's response contains actual `<` characters (e.g. in code), these are rendered raw. Claude is instructed to not use code blocks, so risk is low, but the approach is fragile.  
**Fix:** Escape HTML before injecting bold tags (replace `<` with `&lt;` before doing the bold substitution).

---

### 10. Paper detail — `paper` and `relatedData` can be `undefined` after Promise.all
**File:** `src/app/papers/[id]/page.tsx`  
**Severity:** LOW — type safety  
**Detail:** The try/catch pattern assigns `paper` and `relatedData` via destructuring inside a try block. If the catch fires, they are `undefined`, but TypeScript doesn't complain because they're declared with `let`. The `notFound()` call after the catch is correct but TypeScript doesn't know the variables are guaranteed defined after it.  
**Fix:** Use `!` non-null assertions or restructure to make the types explicit, suppressing potential runtime issues.

---

## Summary Table

| # | Issue | Severity | File | Status |
|---|---|---|---|---|
| 1 | `PaperMeta.tsx` `asChild` — build blocker | CRITICAL | `PaperMeta.tsx` | ✅ Fixed |
| 2 | Graph mobile layout broken | HIGH | `GraphPageClient.tsx`, `GraphControls.tsx` | ✅ Fixed |
| 3 | Chat mobile layout broken | HIGH | `ChatPageClient.tsx` | ✅ Fixed |
| 4 | Dashboard no backend-down fallback | MEDIUM | `app/page.tsx` | ✅ Fixed |
| 5 | Graph default label state | LOW | `GraphContext.tsx` | ✅ Fixed |
| 6 | Nav "Research Assistant" too long mobile | LOW | `NavLinks.tsx` | ✅ Fixed |
| 7 | Cluster labels inconsistent | LOW | `FilterPanel.tsx` | ✅ Fixed |
| 8 | MessageBubble HTML injection | LOW | `MessageBubble.tsx` | ✅ Fixed |
| 9 | Paper detail undefined assignment | LOW | `papers/[id]/page.tsx` | ✅ Fixed |

---

## Fixes Applied

All 9 issues fixed. `next build` passes with zero TypeScript errors and zero warnings.

### What each fix did

**1 — PaperMeta.tsx build blocker**  
Replaced `<Button variant="outline" size="sm" asChild>` with `<a className={buttonVariants({...})}>`, matching the pattern already used in the co-located `PaperHero.tsx`. `PaperMeta.tsx` is not actually rendered anywhere (PaperHero is used instead) but TypeScript checks all files regardless.

**2 — Graph mobile**  
`GraphPageClient.tsx`: Added `sidebarOpen` state. On `md+` the sidebar is always visible (same as before). On mobile it's `position: absolute`, starts off-screen (`-translate-x-full`), and slides in when the "Controls" button (bottom-left of canvas) is tapped. A semi-transparent overlay dismisses it.  
`GraphControls.tsx`: Added `onClose?` prop; renders an `×` button in the header on mobile only.

**3 — Chat mobile**  
`ChatPageClient.tsx`: Added `leftOpen` / `rightOpen` state. Both sidebars are now `position: absolute` on mobile, slide in/out from their respective edges. A mobile toolbar at the top of the chat area provides "Menu" (left) and "Sources (N)" (right) buttons. When a response arrives with sources, `rightOpen` is auto-set to `true`.

**4 — Dashboard backend-down**  
`app/page.tsx`: Wrapped `api.stats()` in a try/catch. On failure renders a friendly "Backend unavailable" card with the exact `uvicorn` command to start the server, instead of propagating the error to the error boundary.

**5 — Graph labels default on**  
`GraphContext.tsx`: Changed `showLabels` default from `false` to `true`. Labels only paint when `globalScale >= 1.2` (already in `GraphCanvas.tsx`), so at the default zoom level (zoomed out) labels are invisible anyway — they appear as you zoom in, providing orientation without initial clutter.

**6 — Nav mobile truncation**  
`NavLinks.tsx`: Each link now has a `shortLabel`. Shows full label on `sm+`, short label on mobile (`<span className="hidden sm:inline">` / `<span className="sm:hidden">`). "Research Assistant" → "Assistant".

**7 — Cluster labels consistent**  
`FilterPanel.tsx`: Imports `CLUSTER_LABELS` from constants and derives `CLUSTERS` array from it, so Paper Search and Graph pages now show identical cluster descriptions ("Theory & Optimization", "RL & Structured Learning", "LLMs & Generative").

**8 — MessageBubble HTML escaping**  
Added `escapeHtml()` that escapes `&`, `<`, `>`, `"` before the bold `**...**` substitution. Prevents any `<` characters in Claude's response from being interpreted as HTML tags.

**9 — Paper detail type safety**  
`papers/[id]/page.tsx`: Changed `let paper, relatedData` to explicit `let paper: Awaited<ReturnType<typeof api.paper>>` types. TypeScript now correctly understands the variables are always defined when execution reaches the JSX (since `notFound()` throws otherwise).
