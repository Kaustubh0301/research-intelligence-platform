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
    label: "Total Research Papers",
    value: p.total_papers.toLocaleString(),
    icon: "menu_book",
    badge: "+4.2%",
    badgeColor: "text-im-primary bg-im-primary/10",
    graph: false,
  },
  {
    label: "Techniques",
    value: p.total_techniques.toLocaleString(),
    icon: "layers",
    badge: "Steady",
    badgeColor: "text-outline bg-outline-variant/20",
    graph: false,
  },
  {
    label: "Graph Edges",
    value: p.total_edges.toLocaleString(),
    icon: "hub",
    badge: "+128",
    badgeColor: "text-im-primary bg-im-primary/10",
    graph: true,
  },
  {
    label: "Clusters",
    value: p.total_clusters.toLocaleString(),
    icon: "account_tree",
    badge: "+12",
    badgeColor: "text-im-primary bg-im-primary/10",
    graph: true,
  },
];

export function StatCards(props: Props) {
  const stats = buildStats(props).filter((s) => !s.graph || FEATURES.GRAPH);

  return (
    <div className="grid gap-4 grid-cols-1 sm:grid-cols-2 lg:grid-cols-4">
      {stats.map((s) => (
        <div
          key={s.label}
          className="bg-surface-container-lowest p-5 rounded-xl border border-outline-variant/20 hover:border-im-primary transition-all duration-300 group"
        >
          <div className="flex justify-between items-start mb-3">
            <div className="p-2 rounded-lg bg-im-primary/5 text-im-primary group-hover:bg-im-primary group-hover:text-on-primary transition-colors">
              <span className="material-symbols-outlined text-[20px]">{s.icon}</span>
            </div>
            <span className={`text-xs font-bold px-2 py-0.5 rounded-full ${s.badgeColor}`}>
              {s.badge}
            </span>
          </div>
          <p className="text-outline text-[11px] font-semibold uppercase tracking-wider">{s.label}</p>
          <h3 className="text-3xl font-bold text-on-surface mt-1 leading-none">{s.value}</h3>
        </div>
      ))}
    </div>
  );
}
