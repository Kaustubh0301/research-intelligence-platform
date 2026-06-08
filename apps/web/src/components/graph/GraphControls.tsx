"use client";

import { useRouter } from "next/navigation";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Separator } from "@/components/ui/separator";
import { CLUSTER_COLOURS, CLUSTER_LABELS } from "@/lib/constants";
import { useGraphContext } from "./GraphContext";
import { ExternalLink, Network, Search, SlidersHorizontal } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { api, queryKeys } from "@/lib/api";

const CLUSTERS = [0, 1, 2] as const;
const WEIGHT_MIN = 1.0;
const WEIGHT_MAX = 5.0;
const WEIGHT_STEP = 0.5;

export function GraphControls() {
  const { filters, setFilters, selected, setSelected } = useGraphContext();
  const router = useRouter();

  const { data: clusterData } = useQuery({
    queryKey: queryKeys.graphClusters,
    queryFn: () => api.graphClusters(),
    staleTime: 300_000,
  });

  const clusterCounts: Record<number, number> = {};
  clusterData?.clusters.forEach((c) => {
    clusterCounts[c.cluster_id] = c.paper_count;
  });

  return (
    <aside className="w-72 flex flex-col border-r bg-background overflow-y-auto shrink-0">
      <div className="p-4 border-b flex items-center gap-2">
        <Network className="h-4 w-4 text-muted-foreground" />
        <span className="font-semibold text-sm">Knowledge Graph</span>
      </div>

      <div className="p-4 space-y-5 flex-1">
        {/* Search */}
        <div>
          <p className="text-xs font-medium text-muted-foreground mb-2 uppercase tracking-wide">
            Search nodes
          </p>
          <div className="relative">
            <Search className="absolute left-2.5 top-2.5 h-3.5 w-3.5 text-muted-foreground" />
            <Input
              className="pl-8 h-8 text-sm"
              placeholder="Filter by title…"
              value={filters.searchQuery}
              onChange={(e) =>
                setFilters({ ...filters, searchQuery: e.target.value })
              }
            />
          </div>
        </div>

        <Separator />

        {/* Edge weight threshold */}
        <div>
          <div className="flex items-center justify-between mb-2">
            <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide flex items-center gap-1">
              <SlidersHorizontal className="h-3 w-3" />
              Edge threshold
            </p>
            <span className="text-xs font-mono bg-muted px-1.5 py-0.5 rounded">
              ≥ {filters.minWeight.toFixed(1)}
            </span>
          </div>
          <input
            type="range"
            min={WEIGHT_MIN}
            max={WEIGHT_MAX}
            step={WEIGHT_STEP}
            value={filters.minWeight}
            onChange={(e) =>
              setFilters({ ...filters, minWeight: parseFloat(e.target.value) })
            }
            className="w-full accent-primary"
          />
          <div className="flex justify-between text-xs text-muted-foreground mt-1">
            <span>{WEIGHT_MIN}</span>
            <span>{WEIGHT_MAX}</span>
          </div>
        </div>

        <Separator />

        {/* Cluster filter */}
        <div>
          <p className="text-xs font-medium text-muted-foreground mb-2 uppercase tracking-wide">
            Cluster filter
          </p>
          <div className="space-y-1.5">
            <button
              onClick={() => setFilters({ ...filters, clusterFilter: undefined })}
              className={`w-full flex items-center justify-between px-2.5 py-1.5 rounded text-sm transition-colors ${
                filters.clusterFilter === undefined
                  ? "bg-primary/10 text-primary font-medium"
                  : "hover:bg-muted text-muted-foreground"
              }`}
            >
              <span>All clusters</span>
              <span className="text-xs">{clusterData?.clusters.reduce((s, c) => s + c.paper_count, 0) ?? 100}</span>
            </button>
            {CLUSTERS.map((c) => (
              <button
                key={c}
                onClick={() =>
                  setFilters({
                    ...filters,
                    clusterFilter: filters.clusterFilter === c ? undefined : c,
                  })
                }
                className={`w-full flex items-center gap-2 px-2.5 py-1.5 rounded text-sm transition-colors ${
                  filters.clusterFilter === c
                    ? "bg-primary/10 font-medium"
                    : "hover:bg-muted text-muted-foreground"
                }`}
              >
                <span
                  className="w-2.5 h-2.5 rounded-full shrink-0"
                  style={{ backgroundColor: CLUSTER_COLOURS[c] }}
                />
                <span className="flex-1 text-left truncate">
                  {CLUSTER_LABELS[c] ?? `Cluster ${c}`}
                </span>
                <span className="text-xs shrink-0">{clusterCounts[c] ?? "—"}</span>
              </button>
            ))}
          </div>
        </div>

        <Separator />

        {/* Labels toggle */}
        <div className="flex items-center justify-between">
          <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
            Node labels
          </p>
          <label className="relative inline-flex items-center cursor-pointer">
            <input
              type="checkbox"
              className="sr-only peer"
              checked={filters.showLabels}
              onChange={(e) =>
                setFilters({ ...filters, showLabels: e.target.checked })
              }
            />
            <div className="w-9 h-5 bg-muted rounded-full peer peer-checked:bg-primary transition-colors after:content-[''] after:absolute after:top-0.5 after:left-0.5 after:bg-white after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:after:translate-x-4" />
          </label>
        </div>

        <Separator />

        {/* Legend */}
        <div>
          <p className="text-xs font-medium text-muted-foreground mb-2 uppercase tracking-wide">
            Legend
          </p>
          <div className="space-y-1.5">
            {CLUSTERS.map((c) => (
              <div key={c} className="flex items-center gap-2 text-xs">
                <span
                  className="w-2.5 h-2.5 rounded-full shrink-0"
                  style={{ backgroundColor: CLUSTER_COLOURS[c] }}
                />
                <span className="text-muted-foreground">
                  Cluster {c} — {CLUSTER_LABELS[c]}
                </span>
              </div>
            ))}
            <div className="flex items-center gap-2 text-xs mt-1">
              <span className="w-2.5 h-2.5 rounded-full shrink-0 bg-muted-foreground/40" />
              <span className="text-muted-foreground">Node size ∝ centrality</span>
            </div>
          </div>
        </div>
      </div>

      {/* Selected paper panel */}
      {selected && (
        <div className="border-t p-4">
          <Card className="shadow-none border-dashed">
            <CardHeader className="pb-2 pt-3 px-3">
              <CardTitle className="text-sm leading-snug line-clamp-2">
                {selected.title}
              </CardTitle>
            </CardHeader>
            <CardContent className="px-3 pb-3 space-y-2">
              <div className="flex flex-wrap gap-1">
                {selected.cluster_id !== null && (
                  <Badge
                    style={{
                      backgroundColor: CLUSTER_COLOURS[selected.cluster_id ?? 0],
                      color: "#fff",
                    }}
                    className="text-xs"
                  >
                    Cluster {selected.cluster_id}
                  </Badge>
                )}
                {selected.conference && (
                  <Badge variant="outline" className="text-xs">
                    {selected.conference} {selected.year}
                  </Badge>
                )}
              </div>
              <div className="grid grid-cols-2 gap-x-3 gap-y-1 text-xs text-muted-foreground">
                <span>Citations</span>
                <span className="font-mono text-foreground">
                  {selected.citation_count.toLocaleString()}
                </span>
                <span>Centrality</span>
                <span className="font-mono text-foreground">
                  {selected.degree_centrality.toFixed(3)}
                </span>
              </div>
              <div className="flex gap-2 pt-1">
                <Button
                  size="sm"
                  className="flex-1 h-7 text-xs"
                  onClick={() => router.push(`/papers/${selected.id}`)}
                >
                  Open paper <ExternalLink className="ml-1 h-3 w-3" />
                </Button>
                <Button
                  size="sm"
                  variant="ghost"
                  className="h-7 text-xs px-2"
                  onClick={() => setSelected(null)}
                >
                  ✕
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      )}
    </aside>
  );
}
