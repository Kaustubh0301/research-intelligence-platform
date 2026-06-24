"use client";

import { FEATURES } from "@/lib/features";

interface Props {
  total_papers:     number;
  total_edges:      number;
  total_techniques: number;
  total_clusters:   number;
}

const buildStats = (p: Props) => [
  {
    label: "Papers",
    value: p.total_papers.toLocaleString(),
    icon: "description",
    accent: "text-im-primary",
    graph: false,
  },
  {
    label: "Graph Edges",
    value: p.total_edges.toLocaleString(),
    icon: "hub",
    accent: "text-im-secondary",
    graph: true,
  },
  {
    label: "Techniques",
    value: p.total_techniques.toLocaleString(),
    icon: "layers",
    accent: "text-im-tertiary",
    graph: false,
  },
  {
    label: "Clusters",
    value: p.total_clusters.toLocaleString(),
    icon: "account_tree",
    accent: "text-im-primary",
    graph: true,
  },
];

export function StatCards(props: Props) {
  const stats = buildStats(props).filter((s) => !s.graph || FEATURES.GRAPH);

  return (
    <div className="grid gap-md grid-cols-2 sm:grid-cols-[repeat(auto-fit,minmax(160px,1fr))]">
      {stats.map((s) => (
        <div
          key={s.label}
          className="bg-surface-container-low border border-outline-variant rounded-xl p-lg hover:border-outline transition-colors"
        >
          <div className="flex items-center justify-between mb-sm">
            <span className="text-label-md text-on-surface-variant uppercase tracking-widest">
              {s.label}
            </span>
            <span className={`material-symbols-outlined text-[20px] ${s.accent}`}>
              {s.icon}
            </span>
          </div>
          <p className="text-[28px] font-bold text-on-surface font-headline-md leading-none">
            {s.value}
          </p>
        </div>
      ))}
    </div>
  );
}
