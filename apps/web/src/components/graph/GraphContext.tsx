"use client";

import { createContext, useContext, useState } from "react";
import type { GraphNode } from "@/lib/types";

interface GraphFilters {
  minWeight: number;
  clusterFilter: number | undefined;
  searchQuery: string;
  showLabels: boolean;
  /** How many nodes are currently visible (progressive disclosure). */
  visibleNodeCount: number;
}

interface GraphContextValue {
  selected: GraphNode | null;
  setSelected: (n: GraphNode | null) => void;
  filters: GraphFilters;
  setFilters: (f: GraphFilters) => void;
}

const defaultFilters: GraphFilters = {
  minWeight: 2.0,
  clusterFilter: undefined,
  searchQuery: "",
  showLabels: true,
  visibleNodeCount: 50,
};

const GraphContext = createContext<GraphContextValue>({
  selected: null,
  setSelected: () => {},
  filters: defaultFilters,
  setFilters: () => {},
});

export function GraphProvider({ children }: { children: React.ReactNode }) {
  const [selected, setSelected] = useState<GraphNode | null>(null);
  const [filters, setFilters] = useState<GraphFilters>(defaultFilters);

  return (
    <GraphContext.Provider value={{ selected, setSelected, filters, setFilters }}>
      {children}
    </GraphContext.Provider>
  );
}

export function useGraphContext() {
  return useContext(GraphContext);
}

export type { GraphFilters };
