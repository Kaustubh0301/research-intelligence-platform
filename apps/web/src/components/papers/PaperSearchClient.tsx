"use client";

import { useRouter, useSearchParams, usePathname } from "next/navigation";
import { useCallback, useRef } from "react";
import { useQuery, keepPreviousData } from "@tanstack/react-query";
import { SlidersHorizontal, X, Loader2 } from "lucide-react";
import { useState } from "react";
import { api, queryKeys } from "@/lib/api";
import type { SearchRequest } from "@/lib/types";
import { SearchBar } from "./SearchBar";
import { FilterPanel } from "./FilterPanel";
import { PaperCard } from "./PaperCard";
import { Pagination } from "./Pagination";
import { Button } from "@/components/ui/button";
import { Select } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Separator } from "@/components/ui/separator";
import { cn } from "@/lib/utils";

const PER_PAGE = 20;

const SORT_OPTIONS = [
  { value: "citations",     label: "Citations ↓" },
  { value: "citations_asc", label: "Citations ↑" },
  { value: "date",          label: "Newest year" },
  { value: "oldest",        label: "Oldest year" },
  { value: "centrality",    label: "Most connected" },
  { value: "title",         label: "Alphabetical" },
  { value: "relevance",     label: "Relevance" },
];

// ── Active filter chips ──────────────────────────────────────────────────────

interface Chip {
  key: string;
  label: string;
  onRemove: () => void;
}

function ActiveChips({ chips }: { chips: Chip[] }) {
  if (!chips.length) return null;
  return (
    <div className="flex flex-wrap items-center gap-1.5">
      <span className="text-xs text-muted-foreground">Filters:</span>
      {chips.map((chip) => (
        <span
          key={chip.key}
          className="inline-flex items-center gap-1 rounded-full bg-primary/10 border border-primary/20 px-2.5 py-0.5 text-xs font-medium text-primary"
        >
          {chip.label}
          <button
            type="button"
            onClick={chip.onRemove}
            className="ml-0.5 hover:text-primary/60 transition-colors"
            aria-label={`Remove ${chip.label} filter`}
          >
            <X className="h-3 w-3" />
          </button>
        </span>
      ))}
    </div>
  );
}

// ── Card skeletons ───────────────────────────────────────────────────────────

function CardSkeleton() {
  return (
    <div className="rounded-lg border bg-card p-4 space-y-2.5">
      <div className="flex gap-2">
        <Skeleton className="h-5 w-20 rounded-full" />
        <Skeleton className="h-5 w-14 rounded-full" />
      </div>
      <Skeleton className="h-4 w-5/6" />
      <Skeleton className="h-3.5 w-full" />
      <Skeleton className="h-3.5 w-4/5" />
      <div className="flex justify-between pt-1">
        <div className="flex gap-1.5">
          <Skeleton className="h-5 w-16 rounded" />
          <Skeleton className="h-5 w-20 rounded" />
        </div>
        <Skeleton className="h-4 w-12" />
      </div>
    </div>
  );
}

// ── Empty state ──────────────────────────────────────────────────────────────

function EmptyState({ query, hasFilters }: { query: string; hasFilters: boolean }) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center">
      <div className="mb-3 text-4xl">🔍</div>
      <p className="text-sm font-medium">No papers found</p>
      <p className="mt-1 text-xs text-muted-foreground max-w-xs">
        {query
          ? `No results for "${query}".${hasFilters ? " Try removing some filters." : " Try a different search term."}`
          : "No papers match the current filters."}
      </p>
    </div>
  );
}

// ── Main component ───────────────────────────────────────────────────────────

export function PaperSearchClient() {
  const router = useRouter();
  const pathname = usePathname();
  const sp = useSearchParams();
  const resultsRef = useRef<HTMLDivElement>(null);
  const [mobileFiltersOpen, setMobileFiltersOpen] = useState(false);

  const q = sp.get("q") ?? "";
  const conference = sp.get("conference") ?? "";
  const cluster = sp.get("cluster") ?? "";
  const technique = sp.get("technique") ?? "";
  const sort = sp.get("sort") ?? "citations";
  const page = Math.max(1, Number(sp.get("page") ?? "1"));

  // ── URL helpers ────────────────────────────────────────────────────────────

  const pushParams = useCallback(
    (updates: Record<string, string>, resetPage = true) => {
      const next = new URLSearchParams(sp.toString());
      for (const [k, v] of Object.entries(updates)) {
        if (v) next.set(k, v);
        else next.delete(k);
      }
      if (resetPage) next.set("page", "1");
      router.push(`${pathname}?${next.toString()}`, { scroll: false });
    },
    [router, pathname, sp]
  );

  const setPage = useCallback(
    (p: number) => {
      pushParams({ page: String(p) }, false);
      // Scroll results area back to top on page change.
      resultsRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    },
    [pushParams]
  );

  const clearAll = () =>
    router.push(pathname, { scroll: false });

  // ── Queries ────────────────────────────────────────────────────────────────

  const isSearch = q.length >= 2;

  const filters = {
    ...(conference ? { conference } : {}),
    ...(cluster !== "" ? { cluster: Number(cluster) } : {}),
    ...(technique ? { technique } : {}),
  };

  const browseQuery = useQuery({
    queryKey: queryKeys.papers({ conference, cluster, technique, sort, page }),
    queryFn: () =>
      api.papers({ conference, cluster, technique, sort, page, per_page: PER_PAGE }),
    enabled: !isSearch,
    placeholderData: keepPreviousData,
    staleTime: 30 * 1000,
  });

  const searchQuery = useQuery({
    queryKey: queryKeys.search(q, { ...filters, sort, page }),
    queryFn: () =>
      api.search({
        query: q,
        filters,
        sort: sort as SearchRequest["sort"],
        page,
        per_page: PER_PAGE,
      }),
    enabled: isSearch,
    placeholderData: keepPreviousData,
    staleTime: 30 * 1000,
  });

  const activeQuery = isSearch ? searchQuery : browseQuery;
  const isLoading = activeQuery.isLoading;           // true only on first load (no cached data)
  const isFetching = activeQuery.isFetching;         // true whenever a bg refresh is running
  const error = activeQuery.error;

  const results = isSearch
    ? (searchQuery.data?.results.map((r) => r.paper) ?? [])
    : (browseQuery.data?.results ?? []);

  const total = isSearch
    ? (searchQuery.data?.total ?? 0)
    : (browseQuery.data?.total ?? 0);

  const totalPages = Math.max(1, Math.ceil(total / PER_PAGE));

  // ── Active filter chips ────────────────────────────────────────────────────

  const chips: Chip[] = [];
  if (conference)
    chips.push({ key: "conference", label: conference, onRemove: () => pushParams({ conference: "" }) });
  if (cluster !== "")
    chips.push({
      key: "cluster",
      label: `Cluster ${cluster}`,
      onRemove: () => pushParams({ cluster: "" }),
    });
  if (technique)
    chips.push({ key: "technique", label: technique, onRemove: () => pushParams({ technique: "" }) });
  const hasFilters = chips.length > 0;

  // ── Sort: hide "relevance" when not searching ──────────────────────────────
  const sortOptions = isSearch
    ? SORT_OPTIONS
    : SORT_OPTIONS.filter((o) => o.value !== "relevance");

  // ── Active filter count for mobile badge ──────────────────────────────────
  const filterCount = chips.length;

  return (
    <div className="grid grid-cols-1 gap-0 md:grid-cols-[240px_1fr]">
      {/* ── Sidebar (desktop always-visible, mobile drawer) ──────────────── */}
      <aside
        className={cn(
          "md:sticky md:top-20 md:h-[calc(100vh-5rem)] md:overflow-y-auto md:pr-6 md:border-r",
          // Mobile: render as an overlay drawer
          "md:block",
          mobileFiltersOpen
            ? "fixed inset-0 z-40 bg-background p-6 overflow-y-auto"
            : "hidden md:block"
        )}
      >
        <div className="flex items-center justify-between mb-5 md:hidden">
          <span className="font-semibold text-sm">Filters</span>
          <button
            type="button"
            onClick={() => setMobileFiltersOpen(false)}
            className="text-muted-foreground hover:text-foreground"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <FilterPanel
          conference={conference}
          cluster={cluster}
          technique={technique}
          onConferenceChange={(v) => { pushParams({ conference: v }); setMobileFiltersOpen(false); }}
          onClusterChange={(v) => { pushParams({ cluster: v }); setMobileFiltersOpen(false); }}
          onTechniqueChange={(v) => { pushParams({ technique: v }); setMobileFiltersOpen(false); }}
        />

        {hasFilters && (
          <>
            <Separator className="my-4" />
            <button
              type="button"
              onClick={() => { clearAll(); setMobileFiltersOpen(false); }}
              className="text-xs text-muted-foreground hover:text-destructive transition-colors"
            >
              Clear all filters
            </button>
          </>
        )}
      </aside>

      {/* ── Results pane ─────────────────────────────────────────────────── */}
      <div className="min-w-0 md:pl-6 space-y-4" ref={resultsRef}>
        {/* Toolbar */}
        <div className="flex gap-2 items-center">
          {/* Mobile filter toggle */}
          <Button
            variant="outline"
            size="sm"
            className="md:hidden flex-shrink-0 relative"
            onClick={() => setMobileFiltersOpen(true)}
          >
            <SlidersHorizontal className="h-4 w-4 mr-1.5" />
            Filters
            {filterCount > 0 && (
              <span className="absolute -top-1.5 -right-1.5 flex h-4 w-4 items-center justify-center rounded-full bg-primary text-[10px] font-bold text-primary-foreground">
                {filterCount}
              </span>
            )}
          </Button>

          <div className="flex-1">
            <SearchBar defaultValue={q} onChange={(v) => pushParams({ q: v })} />
          </div>

          <Select
            options={sortOptions}
            value={sort}
            onChange={(e) => pushParams({ sort: e.target.value })}
            className="w-40 flex-shrink-0"
            aria-label="Sort by"
          />
        </div>

        {/* Results summary + active filters */}
        <div className="flex flex-wrap items-center justify-between gap-2 min-h-[1.5rem]">
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            {isFetching && !isLoading && (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            )}
            {isLoading ? (
              <span>Loading…</span>
            ) : (
              <span>
                {total.toLocaleString()} paper{total !== 1 ? "s" : ""}
                {isSearch && (
                  <> for <span className="font-medium text-foreground">"{q}"</span></>
                )}
              </span>
            )}
          </div>

          {hasFilters && (
            <button
              type="button"
              onClick={clearAll}
              className="text-xs text-muted-foreground hover:text-destructive transition-colors hidden md:block"
            >
              Clear all
            </button>
          )}
        </div>

        <ActiveChips chips={chips} />

        {/* Error */}
        {error && (
          <div className="rounded-md border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive">
            {(error as Error).message}
          </div>
        )}

        {/* Cards */}
        {isLoading ? (
          <div className="space-y-3">
            {[...Array(6)].map((_, i) => (
              <CardSkeleton key={i} />
            ))}
          </div>
        ) : results.length === 0 ? (
          <EmptyState query={q} hasFilters={hasFilters} />
        ) : (
          <div
            className={cn(
              "space-y-3 transition-opacity duration-150",
              isFetching && "opacity-60"
            )}
          >
            {results.map((paper) => (
              <PaperCard
                key={paper.id}
                paper={paper}
                onTechniqueClick={(t) => pushParams({ technique: t })}
              />
            ))}
          </div>
        )}

        {/* Pagination */}
        {!isLoading && totalPages > 1 && (
          <Pagination
            page={page}
            totalPages={totalPages}
            total={total}
            perPage={PER_PAGE}
            onPageChange={setPage}
          />
        )}
      </div>
    </div>
  );
}
