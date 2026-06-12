"use client";

import { useCallback, useEffect, useMemo, useRef } from "react";
import { useState } from "react";
import ForceGraph2D from "react-force-graph-2d";
import type { ForceGraphMethods } from "react-force-graph-2d";
import { useQuery } from "@tanstack/react-query";
import { api, queryKeys } from "@/lib/api";
import { CLUSTER_COLOURS, CLUSTER_LABELS } from "@/lib/constants";
import { useGraphContext } from "./GraphContext";
import { GraphSummaryPanel } from "./GraphSummaryPanel";
import { Skeleton } from "@/components/ui/skeleton";
import type { GraphNode } from "@/lib/types";

interface FGNode extends GraphNode {
  x?: number;
  y?: number;
  _dimmed?: boolean;
}

// react-force-graph mutates source/target from string to object after layout
interface FGLink {
  source: string | FGNode;
  target: string | FGNode;
  weight: number;
}

export function GraphCanvas() {
  const { filters, setSelected } = useGraphContext();
  const containerRef = useRef<HTMLDivElement>(null);
  const graphRef = useRef<ForceGraphMethods<FGNode, FGLink>>(undefined);
  const [dimensions, setDimensions] = useState({ width: 800, height: 600 });

  // Keep a live ref to the current visible nodes so onRenderFramePost
  // can read positions without being re-created every render.
  const nodesRef = useRef<FGNode[]>([]);

  const { data, isLoading } = useQuery({
    queryKey: queryKeys.graph(filters.minWeight, filters.clusterFilter),
    queryFn: () => api.graph(filters.minWeight, filters.clusterFilter),
    staleTime: 60_000,
  });

  // ── Container sizing ──────────────────────────────────────────────────────
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const ro = new ResizeObserver(() => {
      setDimensions({ width: el.clientWidth, height: el.clientHeight });
    });
    ro.observe(el);
    setDimensions({ width: el.clientWidth, height: el.clientHeight });
    return () => ro.disconnect();
  }, []);

  // ── Ranked node list (stable — only recomputes when API data changes) ─────
  // Importance = weighted combination of degree and betweenness centrality.
  const rankedNodes = useMemo<GraphNode[]>(() => {
    if (!data) return [];
    return [...data.nodes].sort(
      (a, b) =>
        (b.degree_centrality * 0.7 + b.betweenness_centrality * 0.3) -
        (a.degree_centrality * 0.7 + a.betweenness_centrality * 0.3)
    );
  }, [data]);

  // Top-10 node IDs always get visible labels regardless of zoom level.
  const topNodeIds = useMemo<Set<string>>(
    () => new Set(rankedNodes.slice(0, 10).map((n) => n.id)),
    [rankedNodes]
  );

  // ── Graph data with progressive disclosure + search dimming ───────────────
  const graphData = useMemo(() => {
    if (!data) return { nodes: [] as FGNode[], links: [] as FGLink[] };

    const query = filters.searchQuery.toLowerCase().trim();

    // Progressive disclosure: slice to visible count.
    // Search dims nodes within the current visible set — it does NOT expand
    // the visible set (that would destabilise the layout unexpectedly).
    const visibleNodes = rankedNodes.slice(0, filters.visibleNodeCount);
    const visibleIds = new Set(visibleNodes.map((n) => n.id));

    const nodes: FGNode[] = visibleNodes.map((n) => ({
      ...n,
      ...(query ? { _dimmed: !n.title.toLowerCase().includes(query) } : {}),
    }));

    // Only include edges where both endpoints are in the visible set.
    const links: FGLink[] = data.edges
      .filter(
        (e) =>
          visibleIds.has(e.source as string) &&
          visibleIds.has(e.target as string)
      )
      .map((e) => ({ ...e }));

    return { nodes, links };
  }, [data, rankedNodes, filters.searchQuery, filters.visibleNodeCount]);

  // Keep nodesRef in sync so onRenderFramePost is always stable.
  useEffect(() => {
    nodesRef.current = graphData.nodes;
  }, [graphData.nodes]);

  // ── Summary stats (derived from full API data, not just visible nodes) ────
  const summary = useMemo(() => {
    if (!data || data.nodes.length === 0) return null;
    const nodes = data.nodes;
    const n = nodes.length;
    const e = data.meta.edge_count;
    const density = n > 1 ? (2 * e) / (n * (n - 1)) : 0;
    const topNode = rankedNodes[0] ?? null;
    const clusterCounts: Record<number, number> = {};
    nodes.forEach((node) => {
      const c = node.cluster_id;
      if (c != null) clusterCounts[c] = (clusterCounts[c] ?? 0) + 1;
    });
    return { density, topNode, clusterCounts };
  }, [data, rankedNodes]);

  // ── Interaction handlers ──────────────────────────────────────────────────
  const handleNodeClick = useCallback(
    (node: FGNode) => setSelected(node),
    [setSelected]
  );

  const handleBgClick = useCallback(() => setSelected(null), [setSelected]);

  // ── Node appearance ───────────────────────────────────────────────────────
  const nodeColor = useCallback((node: FGNode) => {
    if (node._dimmed) return "rgba(156,163,175,0.15)";
    return CLUSTER_COLOURS[node.cluster_id ?? 0] ?? "#6b7280";
  }, []);

  const nodeVal = useCallback(
    (node: FGNode) => Math.max(2, node.degree_centrality * 80),
    []
  );

  const linkWidth = useCallback(
    (link: FGLink) => Math.sqrt(link.weight) * 0.6,
    []
  );

  const linkColor = useCallback(() => "rgba(156,163,175,0.25)", []);

  const nodeCanvasObject = useCallback(
    (node: FGNode, ctx: CanvasRenderingContext2D, globalScale: number) => {
      const r = Math.max(2, Math.sqrt(nodeVal(node)) * 1.5);
      const x = node.x ?? 0;
      const y = node.y ?? 0;

      // Draw node circle
      ctx.beginPath();
      ctx.arc(x, y, r, 0, 2 * Math.PI);
      ctx.fillStyle = nodeColor(node);
      ctx.fill();

      // ── Labels ──────────────────────────────────────────────────────────
      if (!filters.showLabels || node._dimmed) return;

      const isTop = topNodeIds.has(node.id);

      // Top-10 nodes: always labelled (they anchor the graph visually).
      // All others: only at zoom ≥ 1.5× to avoid clutter.
      if (!isTop && globalScale < 1.5) return;

      const label =
        node.title.length > 30 ? node.title.slice(0, 28) + "…" : node.title;

      const fontSize = isTop
        ? Math.max(5, 11 / globalScale)
        : Math.max(4, 10 / globalScale);

      ctx.font = `${isTop ? "bold " : ""}${fontSize}px Sans-Serif`;
      ctx.textAlign = "center";

      const labelY = y + r + fontSize + 1;

      // For top nodes that are still far out (low globalScale), draw a
      // semi-transparent pill behind the text for readability.
      if (isTop && globalScale < 1.2) {
        const tw = ctx.measureText(label).width;
        const pad = fontSize * 0.4;
        ctx.fillStyle = "rgba(0,0,0,0.55)";
        ctx.beginPath();
        ctx.roundRect(
          x - tw / 2 - pad,
          labelY - fontSize,
          tw + pad * 2,
          fontSize * 1.4,
          3 / globalScale
        );
        ctx.fill();
      }

      ctx.fillStyle = isTop
        ? "rgba(255,255,255,0.95)"
        : "rgba(255,255,255,0.80)";
      ctx.fillText(label, x, labelY);
    },
    [nodeColor, nodeVal, topNodeIds, filters.showLabels]
  );

  // ── Cluster labels (drawn after all nodes, in graph-coordinate space) ─────
  // Uses a stable ref for node positions so this callback never changes.
  const onRenderFramePost = useCallback(
    (ctx: CanvasRenderingContext2D, globalScale: number) => {
      // Hide at extreme zoom levels where labels would be unreadable or
      // collide badly with individual node labels.
      if (globalScale < 0.25 || globalScale > 3) return;

      // Opacity fades in as zoom approaches 0.25 to avoid a hard cut.
      const alpha = Math.min(1, (globalScale - 0.25) / 0.25);

      // Compute centroids from live node positions (x/y set by force sim).
      const acc: Record<number, { sx: number; sy: number; n: number }> = {};
      for (const node of nodesRef.current) {
        const c = node.cluster_id;
        if (c == null || node.x == null || node.y == null) continue;
        if (!acc[c]) acc[c] = { sx: 0, sy: 0, n: 0 };
        acc[c].sx += node.x;
        acc[c].sy += node.y;
        acc[c].n += 1;
      }

      const fontSize = Math.max(10, 18 / globalScale);

      ctx.save();
      ctx.globalAlpha = alpha * 0.88;
      ctx.font = `bold ${fontSize}px Sans-Serif`;
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";

      for (const [cidStr, { sx, sy, n }] of Object.entries(acc)) {
        if (n === 0) continue;
        const cid = Number(cidStr);
        const label = CLUSTER_LABELS[cid];
        if (!label) continue;

        const cx = sx / n;
        const cy = sy / n;

        // Stroke for contrast against light and dark nodes alike.
        ctx.strokeStyle = "rgba(0,0,0,0.65)";
        ctx.lineWidth = 3.5 / globalScale;
        ctx.strokeText(label, cx, cy);

        ctx.fillStyle = CLUSTER_COLOURS[cid] ?? "#6b7280";
        ctx.fillText(label, cx, cy);
      }

      ctx.restore();
    },
    [] // stable — reads from nodesRef
  );

  // ── Render ────────────────────────────────────────────────────────────────
  if (isLoading) {
    return (
      <div className="flex-1 flex items-center justify-center bg-gray-950">
        <Skeleton className="w-full h-full rounded-none opacity-10" />
      </div>
    );
  }

  return (
    <div ref={containerRef} className="relative flex-1 overflow-hidden bg-gray-950">
      <ForceGraph2D
        ref={graphRef}
        graphData={graphData}
        width={dimensions.width}
        height={dimensions.height}
        nodeLabel={(n: FGNode) => n.title}
        nodeColor={nodeColor}
        nodeVal={nodeVal}
        nodeCanvasObject={nodeCanvasObject}
        nodeCanvasObjectMode={() => "replace"}
        linkWidth={linkWidth}
        linkColor={linkColor}
        onNodeClick={handleNodeClick}
        onBackgroundClick={handleBgClick}
        onRenderFramePost={onRenderFramePost}
        cooldownTicks={120}
        d3AlphaDecay={0.02}
        d3VelocityDecay={0.3}
      />

      {/* Graph summary overlay — top-right of canvas */}
      {data && summary && (
        <GraphSummaryPanel
          totalNodes={data.meta.node_count}
          visibleNodes={graphData.nodes.length}
          visibleEdges={graphData.links.length}
          totalEdges={data.meta.edge_count}
          density={summary.density}
          topNode={summary.topNode}
          clusterCounts={summary.clusterCounts}
          minWeight={filters.minWeight}
        />
      )}
    </div>
  );
}
