"use client";

import { useRouter, useSearchParams, usePathname } from "next/navigation";
import { useCallback, useRef } from "react";
import { useQuery, keepPreviousData } from "@tanstack/react-query";
import { X, Loader2 } from "lucide-react";
import { useState } from "react";
import { api, queryKeys } from "@/lib/api";
import type { SearchRequest } from "@/lib/types";
import { SearchBar } from "./SearchBar";
import { FilterPanel } from "./FilterPanel";
import { PaperCard } from "./PaperCard";
import { Pagination } from "./Pagination";
import { cn } from "@/lib/utils";
import { CLUSTER_LABELS } from "@/lib/constants";

const PER_PAGE = 20;

const SORT_OPTIONS = [
  { value: "citations",     label: "Relevance"      },
  { value: "citations_asc", label: "Citations ↑"    },
  { value: "date",          label: "Newest"         },
  { value: "oldest",        label: "Oldest"         },
  { value: "centrality",    label: "Most connected" },
  { value: "title",         label: "Alphabetical"   },
  { value: "relevance",     label: "Best match"     },
];

// ── Active filter chips ──────────────────────────────────────────────────────

interface Chip { key: string; label: string; onRemove: () => void; }

function ActiveChips({ chips }: { chips: Chip[] }) {
  if (!chips.length) return null;
  return (
    <div className="flex flex-wrap items-center gap-xs">
      <span className="text-body-sm text-on-surface-variant">Filters:</span>
      {chips.map((chip) => (
        <span
          key={chip.key}
          className="inline-flex items-center gap-xs rounded-full bg-primary-container/10 border border-primary-container/20 px-sm py-0.5 text-[11px] font-label-md text-im-primary"
        >
          {chip.label}
          <button
            type="button"
            onClick={chip.onRemove}
            className="ml-0.5 hover:opacity-60 transition-opacity"
            aria-label={`Remove ${chip.label} filter`}
          >
            <X className="h-3 w-3" />
          </button>
        </span>
      ))}
    </div>
  );
}

// ── Card skeleton ────────────────────────────────────────────────────────────

function CardSkeleton() {
  return (
    <div className="rounded-xl border border-outline-variant bg-surface-container-low p-lg space-y-md animate-pulse">
      <div className="flex gap-sm">
        <div className="h-5 w-24 rounded bg-surface-container-highest" />
        <div className="h-5 w-16 rounded bg-surface-container-highest" />
      </div>
      <div className="h-5 w-5/6 rounded bg-surface-container-highest" />
      <div className="h-3.5 w-full rounded bg-surface-container-highest" />
      <div className="h-3.5 w-4/5 rounded bg-surface-container-highest" />
    </div>
  );
}

// ── Empty state ──────────────────────────────────────────────────────────────

function EmptyState({ query, hasFilters }: { query: string; hasFilters: boolean }) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center">
      <span className="material-symbols-outlined text-[48px] text-outline mb-md">search_off</span>
      <p className="text-body-md font-headline-md text-on-surface">No papers found</p>
      <p className="mt-1 text-body-sm text-on-surface-variant max-w-xs">
        {query
          ? `No results for "${query}".${hasFilters ? " Try removing some filters." : " Try a different term."}`
          : "No papers match the current filters."}
      </p>
    </div>
  );
}

// ── Main component ───────────────────────────────────────────────────────────

export function PaperSearchClient() {
  const router   = useRouter();
  const pathname = usePathname();
  const sp       = useSearchParams();
  const resultsRef = useRef<HTMLDivElement>(null);
  const [mobileFiltersOpen, setMobileFiltersOpen] = useState(false);

  const q          = sp.get("q") ?? "";
  const conference = sp.get("conference") ?? "";
  const cluster    = sp.get("cluster") ?? "";
  const technique  = sp.get("technique") ?? "";
  const sort       = sp.get("sort") ?? "citations";
  const page       = Math.max(1, Number(sp.get("page") ?? "1"));

  // ── URL helpers ──────────────────────────────────────────────────────────

  const pushParams = useCallback(
    (updates: Record<string, string>, resetPage = true) => {
      const next = new URLSearchParams(sp.toString());
      for (const [k, v] of Object.entries(updates)) {
        if (v) next.set(k, v); else next.delete(k);
      }
      if (resetPage) next.set("page", "1");
      router.push(`${pathname}?${next.toString()}`, { scroll: false });
    },
    [router, pathname, sp]
  );

  const setPage = useCallback(
    (p: number) => {
      pushParams({ page: String(p) }, false);
      resultsRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    },
    [pushParams]
  );

  const clearAll = () => router.push(pathname, { scroll: false });

  // ── Queries ──────────────────────────────────────────────────────────────

  const isSearch = q.length >= 2;
  const filters  = {
    ...(conference ? { conference } : {}),
    ...(cluster !== "" ? { cluster: Number(cluster) } : {}),
    ...(technique ? { technique } : {}),
  };

  const browseQuery = useQuery({
    queryKey: queryKeys.papers({ conference, cluster, technique, sort, page }),
    queryFn:  () => api.papers({ conference, cluster, technique, sort, page, per_page: PER_PAGE }),
    enabled:  !isSearch,
    placeholderData: keepPreviousData,
    staleTime: 30_000,
  });

  const searchQuery = useQuery({
    queryKey: queryKeys.search(q, { ...filters, sort, page }),
    queryFn:  () => api.search({ query: q, filters, sort: sort as SearchRequest["sort"], page, per_page: PER_PAGE }),
    enabled:  isSearch,
    placeholderData: keepPreviousData,
    staleTime: 30_000,
  });

  const activeQuery = isSearch ? searchQuery : browseQuery;
  const isLoading   = activeQuery.isLoading;
  const isFetching  = activeQuery.isFetching;
  const error       = activeQuery.error;

  const results = isSearch
    ? (searchQuery.data?.results.map((r) => r.paper) ?? [])
    : (browseQuery.data?.results ?? []);

  const total      = isSearch ? (searchQuery.data?.total ?? 0) : (browseQuery.data?.total ?? 0);
  const totalPages = Math.max(1, Math.ceil(total / PER_PAGE));

  // ── Active chips ─────────────────────────────────────────────────────────

  const chips: Chip[] = [];
  if (conference)
    chips.push({ key: "conference", label: conference, onRemove: () => pushParams({ conference: "" }) });
  if (cluster !== "")
    chips.push({ key: "cluster", label: CLUSTER_LABELS[Number(cluster)] ?? `Cluster ${cluster}`, onRemove: () => pushParams({ cluster: "" }) });
  if (technique)
    chips.push({ key: "technique", label: technique, onRemove: () => pushParams({ technique: "" }) });

  const hasFilters   = chips.length > 0;
  const filterCount  = chips.length;
  const sortOptions  = isSearch ? SORT_OPTIONS : SORT_OPTIONS.filter((o) => o.value !== "relevance");

  return (
    <div className="flex gap-lg">

      {/* ── Filter sidebar ─────────────────────────────────────────────── */}
      <aside
        className={cn(
          "w-64 flex-shrink-0",
          // Mobile: overlay drawer
          mobileFiltersOpen
            ? "fixed inset-0 z-40 bg-surface-dim p-lg overflow-y-auto"
            : "hidden md:block"
        )}
      >
        {/* Mobile close button */}
        <div className="flex items-center justify-between mb-lg md:hidden">
          <span className="text-label-md text-on-surface font-bold">Filters</span>
          <button
            type="button"
            onClick={() => setMobileFiltersOpen(false)}
            className="text-on-surface-variant hover:text-on-surface"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <FilterPanel
          conference={conference}
          cluster={cluster}
          technique={technique}
          onConferenceChange={(v) => { pushParams({ conference: v }); setMobileFiltersOpen(false); }}
          onClusterChange={(v)    => { pushParams({ cluster: v });    setMobileFiltersOpen(false); }}
          onTechniqueChange={(v)  => { pushParams({ technique: v });  setMobileFiltersOpen(false); }}
        />

        {hasFilters && (
          <div className="mt-lg pt-lg border-t border-outline-variant">
            <button
              type="button"
              onClick={() => { clearAll(); setMobileFiltersOpen(false); }}
              className="text-body-sm text-on-surface-variant hover:text-im-error transition-colors"
            >
              Clear all filters
            </button>
          </div>
        )}
      </aside>

      {/* ── Results pane ───────────────────────────────────────────────── */}
      <div className="flex-1 min-w-0 space-y-md" ref={resultsRef}>

        {/* Toolbar: mobile filter toggle + search bar + sort */}
        <div className="flex gap-sm items-center">
          {/* Mobile filter toggle */}
          <button
            type="button"
            className="md:hidden relative flex items-center gap-xs bg-surface-container border border-outline-variant px-md py-sm rounded-lg text-label-md text-on-surface-variant hover:bg-surface-container-highest transition-colors"
            onClick={() => setMobileFiltersOpen(true)}
          >
            <span className="material-symbols-outlined text-[18px]">tune</span>
            Filters
            {filterCount > 0 && (
              <span className="absolute -top-1.5 -right-1.5 flex h-4 w-4 items-center justify-center rounded-full bg-im-primary text-[10px] font-bold text-on-primary">
                {filterCount}
              </span>
            )}
          </button>

          {/* Search bar */}
          <div className="flex-1">
            <SearchBar defaultValue={q} onChange={(v) => pushParams({ q: v })} />
          </div>

          {/* Sort select */}
          <select
            value={sort}
            onChange={(e) => pushParams({ sort: e.target.value })}
            aria-label="Sort by"
            className="bg-surface border border-outline-variant text-im-primary text-label-md rounded-lg px-sm py-sm focus:ring-0 focus:outline-none cursor-pointer hover:bg-surface-container transition-colors"
          >
            {sortOptions.map((o) => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </select>
        </div>

        {/* Results summary */}
        <div className="flex flex-wrap items-center justify-between gap-sm pb-md border-b border-outline-variant">
          <div className="flex items-center gap-sm text-body-sm text-on-surface-variant">
            {isFetching && !isLoading && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
            {isLoading ? (
              <span>Loading…</span>
            ) : (
              <span>
                Showing{" "}
                <span className="text-on-surface font-bold">{total.toLocaleString()}</span>{" "}
                {isSearch
                  ? <>results for <span className="italic">"{q}"</span></>
                  : "papers"}
              </span>
            )}
          </div>
          {hasFilters && (
            <button
              type="button"
              onClick={clearAll}
              className="hidden md:block text-body-sm text-on-surface-variant hover:text-im-error transition-colors"
            >
              Clear all
            </button>
          )}
        </div>

        <ActiveChips chips={chips} />

        {/* Error */}
        {error && (
          <div className="rounded-xl border border-im-error/30 bg-error-container/10 px-lg py-md text-body-sm text-im-error">
            {(error as Error).message}
          </div>
        )}

        {/* Cards */}
        {isLoading ? (
          <div className="space-y-md">
            {[...Array(6)].map((_, i) => <CardSkeleton key={i} />)}
          </div>
        ) : results.length === 0 ? (
          <EmptyState query={q} hasFilters={hasFilters} />
        ) : (
          <div className={cn("space-y-md transition-opacity duration-150", isFetching && "opacity-60")}>
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
