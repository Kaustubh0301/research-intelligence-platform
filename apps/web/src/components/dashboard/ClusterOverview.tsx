import type { ClusterStat } from "@/lib/types";
import { CLUSTER_COLOURS } from "@/lib/constants";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";

interface Props {
  clusters: ClusterStat[];
}

export function ClusterOverview({ clusters }: Props) {
  const maxDegree = Math.max(...clusters.map((c) => c.avg_degree), 0.001);

  return (
    <Card>
      <CardHeader>
        <CardTitle>Cluster Overview</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {clusters.map((c) => (
          <div key={c.cluster_id} className="space-y-1.5">
            <div className="flex items-center justify-between text-sm">
              <div className="flex items-center gap-2">
                <span
                  className="inline-block h-3 w-3 rounded-full"
                  style={{
                    backgroundColor: CLUSTER_COLOURS[c.cluster_id] ?? "#6b7280",
                  }}
                />
                <span className="font-medium">Cluster {c.cluster_id}</span>
                <span className="text-muted-foreground">
                  {c.paper_count} papers
                </span>
              </div>
              <span className="text-muted-foreground text-xs">
                avg degree {c.avg_degree.toFixed(4)}
              </span>
            </div>
            <Progress value={(c.avg_degree / maxDegree) * 100} />
          </div>
        ))}
      </CardContent>
    </Card>
  );
}
