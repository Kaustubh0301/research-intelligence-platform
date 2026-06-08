"use client";

import { FileText, Network, Layers, GitBranch } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

interface Props {
  total_papers: number;
  total_edges: number;
  total_techniques: number;
  total_clusters: number;
}

const stats = (p: Props) => [
  { label: "Papers", value: p.total_papers.toLocaleString(), icon: FileText },
  { label: "Graph Edges", value: p.total_edges.toLocaleString(), icon: Network },
  { label: "Techniques", value: p.total_techniques.toLocaleString(), icon: Layers },
  { label: "Clusters", value: p.total_clusters.toLocaleString(), icon: GitBranch },
];

export function StatCards(props: Props) {
  return (
    <div className="grid gap-4 grid-cols-2 sm:grid-cols-4">
      {stats(props).map((s) => (
        <Card key={s.label}>
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle>{s.label}</CardTitle>
              <s.icon className="h-4 w-4 text-muted-foreground" />
            </div>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold">{s.value}</p>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
