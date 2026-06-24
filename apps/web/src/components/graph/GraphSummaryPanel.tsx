"use client";

import { useState } from "react";
import { ChevronDown, ChevronUp } from "lucide-react";
import { CLUSTER_COLOURS, CLUSTER_LABELS } from "@/lib/constants";
import type { GraphNode } from "@/lib/types";

interface Props {
  totalNodes: number;
  visibleNodes: number;
  visibleEdges: number;
  totalEdges: number;
  density: number;
  topNode: GraphNode | null;
  clusterCounts: Record<number, number>;
  minWeight: number;
}

export function GraphSummaryPanel({
  totalNodes,
  visibleNodes,
  visibleEdges,
  totalEdges,
  density,
  topNode,
  clusterCounts,
  minWeight,
}: Props) {
  const [collapsed, setCollapsed] = useState(false);

  const maxClusterCount = Math.max(...Object.values(clusterCounts), 1);
  const clusterIds = Object.keys(clusterCounts)
    .map(Number)
    .sort((a, b) => a - b);

  const showingAll = visibleNodes >= totalNodes;

  return (
    <div className="absolute top-3 right-3 z-10 w-56 rounded-xl border border-white/10 bg-gray-950/80 backdrop-blur-sm text-white text-xs shadow-xl">
      {/* Header row */}
      <button
        onClick={() => setCollapsed((c) => !c)}
        className="w-full flex items-center justify-between px-3 py-2 hover:bg-white/5 rounded-t-xl transition-colors"
        aria-label={collapsed ? "Expand graph summary" : "Collapse graph summary"}
      >
        <span className="font-semibold text-white/90 tracking-wide uppercase text-[10px]">
          Graph Summary
        </span>
        {collapsed ? (
          <ChevronDown className="h-3 w-3 text-white/50" />
        ) : (
          <ChevronUp className="h-3 w-3 text-white/50" />
        )}
      </button>

      {!collapsed && (
        <>
          {/* Node / edge counts */}
          <div className="px-3 pb-2 border-t border-white/10 pt-2 space-y-1">
            <div className="flex justify-between text-white/60">
              <span>Nodes visible</span>
              <span className="font-mono text-white">
                {visibleNodes}
                {!showingAll && (
                  <span className="text-white/40"> / {totalNodes}</span>
                )}
              </span>
            </div>
            <div className="flex justify-between text-white/60">
              <span>Edges shown</span>
              <span className="font-mono text-white">
                {visibleEdges.toLocaleString()}
                {visibleEdges !== totalEdges && (
                  <span className="text-white/40"> / {totalEdges.toLocaleString()}</span>
                )}
              </span>
            </div>
            <div className="flex justify-between text-white/60">
              <span>Density</span>
              <span className="font-mono text-white">{density.toFixed(3)}</span>
            </div>
            <div className="flex justify-between text-white/60">
              <span>Min weight</span>
              <span className="font-mono text-white">≥ {minWeight.toFixed(1)}</span>
            </div>
          </div>

          {/* Cluster distribution */}
          {clusterIds.length > 0 && (
            <div className="px-3 py-2 border-t border-white/10 space-y-1.5">
              {clusterIds.map((cid) => {
                const count = clusterCounts[cid] ?? 0;
                const pct = Math.round((count / maxClusterCount) * 100);
                const label = CLUSTER_LABELS[cid] ?? `Cluster ${cid}`;
                const colour = CLUSTER_COLOURS[cid] ?? "#6b7280";
                return (
                  <div key={cid} className="space-y-0.5">
                    <div className="flex justify-between text-white/60">
                      <span className="flex items-center gap-1.5 min-w-0">
                        <span
                          className="w-1.5 h-1.5 rounded-full shrink-0"
                          style={{ backgroundColor: colour }}
                        />
                        <span className="truncate">{label}</span>
                      </span>
                      <span className="font-mono text-white/80 shrink-0 ml-1">
                        {count}
                      </span>
                    </div>
                    {/* Mini bar */}
                    <div className="h-0.5 w-full rounded-full bg-white/10">
                      <div
                        className="h-full rounded-full transition-all duration-300"
                        style={{ width: `${pct}%`, backgroundColor: colour }}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          )}

          {/* Most connected paper */}
          {topNode && (
            <div className="px-3 py-2 border-t border-white/10">
              <p className="text-white/40 text-[10px] uppercase tracking-wide mb-1">
                Most connected
              </p>
              <p className="text-white/85 leading-snug line-clamp-2">
                {topNode.title}
              </p>
              <p className="text-white/40 mt-0.5">
                centrality {topNode.degree_centrality.toFixed(3)}
              </p>
            </div>
          )}
        </>
      )}
    </div>
  );
}
