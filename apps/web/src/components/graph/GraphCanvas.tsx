"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import ForceGraph2D from "react-force-graph-2d";
import type { ForceGraphMethods } from "react-force-graph-2d";
import { useQuery } from "@tanstack/react-query";
import { api, queryKeys } from "@/lib/api";
import { CLUSTER_COLOURS } from "@/lib/constants";
import { useGraphContext } from "./GraphContext";
import { Skeleton } from "@/components/ui/skeleton";
import type { GraphNode } from "@/lib/types";

interface FGNode extends GraphNode {
  x?: number;
  y?: number;
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

  const { data, isLoading } = useQuery({
    queryKey: queryKeys.graph(filters.minWeight, filters.clusterFilter),
    queryFn: () => api.graph(filters.minWeight, filters.clusterFilter),
    staleTime: 60_000,
  });

  // Track container size
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

  const graphData = useMemo(() => {
    if (!data) return { nodes: [], links: [] };

    const query = filters.searchQuery.toLowerCase().trim();
    let nodes: FGNode[] = data.nodes.map((n) => ({ ...n }));

    if (query) {
      // dim non-matching nodes — keep all, but tag them
      nodes = nodes.map((n) => ({
        ...n,
        _dimmed: !n.title.toLowerCase().includes(query),
      }));
    }

    return {
      nodes,
      links: data.edges.map((e) => ({ ...e })),
    };
  }, [data, filters.searchQuery]);

  const handleNodeClick = useCallback(
    (node: FGNode) => {
      setSelected(node);
    },
    [setSelected]
  );

  const handleBgClick = useCallback(() => {
    setSelected(null);
  }, [setSelected]);

  const nodeColor = useCallback((node: FGNode & { _dimmed?: boolean }) => {
    if (node._dimmed) return "rgba(156,163,175,0.2)";
    return CLUSTER_COLOURS[node.cluster_id ?? 0] ?? "#6b7280";
  }, []);

  const nodeVal = useCallback((node: FGNode) => {
    return Math.max(2, node.degree_centrality * 80);
  }, []);

  const linkWidth = useCallback((link: FGLink) => {
    return Math.sqrt(link.weight) * 0.6;
  }, []);

  const linkColor = useCallback(() => "rgba(156,163,175,0.25)", []);

  const nodeCanvasObject = useCallback(
    (
      node: FGNode & { _dimmed?: boolean },
      ctx: CanvasRenderingContext2D,
      globalScale: number
    ) => {
      const r = Math.max(2, Math.sqrt(nodeVal(node)) * 1.5);
      const color = nodeColor(node);

      ctx.beginPath();
      ctx.arc(node.x ?? 0, node.y ?? 0, r, 0, 2 * Math.PI);
      ctx.fillStyle = color;
      ctx.fill();

      if (filters.showLabels && globalScale >= 1.5 && !node._dimmed) {
        const label = node.title.length > 30
          ? node.title.slice(0, 28) + "…"
          : node.title;
        const fontSize = Math.max(4, 10 / globalScale);
        ctx.font = `${fontSize}px Sans-Serif`;
        ctx.fillStyle = "rgba(255,255,255,0.85)";
        ctx.textAlign = "center";
        ctx.fillText(label, node.x ?? 0, (node.y ?? 0) + r + fontSize + 1);
      }
    },
    [nodeColor, nodeVal, filters.showLabels]
  );

  if (isLoading) {
    return (
      <div className="flex-1 flex items-center justify-center bg-muted/20">
        <Skeleton className="w-full h-full rounded-none" />
      </div>
    );
  }

  return (
    <div ref={containerRef} className="flex-1 overflow-hidden bg-gray-950">
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
        cooldownTicks={120}
        d3AlphaDecay={0.02}
        d3VelocityDecay={0.3}
      />
    </div>
  );
}
