import type { PaperDetail } from "@/lib/types";
import { CLUSTER_COLOURS } from "@/lib/constants";
import { TrendingUp, Star, Users, Zap, GitBranch, Activity } from "lucide-react";
import { cn } from "@/lib/utils";

interface Props {
  paper: PaperDetail;
}

function StatRow({
  icon: Icon,
  label,
  value,
  sub,
  className,
}: {
  icon: React.ElementType;
  label: string;
  value: string | number;
  sub?: string;
  className?: string;
}) {
  return (
    <div className="flex items-center justify-between py-2">
      <span className="flex items-center gap-2 text-sm text-muted-foreground">
        <Icon className={cn("h-4 w-4 flex-shrink-0", className)} />
        {label}
      </span>
      <span className="text-sm font-medium tabular-nums">
        {typeof value === "number" ? value.toLocaleString() : value}
        {sub && (
          <span className="ml-1 text-xs font-normal text-muted-foreground">
            {sub}
          </span>
        )}
      </span>
    </div>
  );
}

function CentralityBar({ value }: { value: number }) {
  const pct = Math.round(value * 100);
  return (
    <div className="space-y-1 py-1">
      <div className="flex items-center justify-between text-sm">
        <span className="flex items-center gap-2 text-muted-foreground">
          <Activity className="h-4 w-4 flex-shrink-0" />
          Degree centrality
        </span>
        <span className="font-medium tabular-nums">{value.toFixed(4)}</span>
      </div>
      <div className="relative h-1.5 w-full overflow-hidden rounded-full bg-secondary">
        <div
          className="h-full rounded-full bg-primary transition-all"
          style={{ width: `${pct}%` }}
        />
      </div>
      <p className="text-right text-[11px] text-muted-foreground">
        top {100 - pct}%
      </p>
    </div>
  );
}

export function MetricsCard({ paper }: Props) {
  const gm = paper.graph_metrics;
  const clusterColour =
    gm?.cluster_id != null
      ? (CLUSTER_COLOURS[gm.cluster_id] ?? "#6b7280")
      : null;

  return (
    <section className="rounded-xl border bg-card p-5 space-y-1">
      <h2 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-2">
        Metrics
      </h2>

      <div className="divide-y">
        <StatRow
          icon={TrendingUp}
          label="Citations"
          value={paper.citation_count}
          className="text-blue-500"
        />
        {paper.influential_citation_count > 0 && (
          <StatRow
            icon={Star}
            label="Influential"
            value={paper.influential_citation_count}
            className="text-amber-500"
          />
        )}
        {paper.authors.length > 0 && (
          <StatRow
            icon={Users}
            label="Authors"
            value={paper.authors.length}
          />
        )}

        {gm && (
          <>
            {clusterColour !== null && (
              <div className="flex items-center justify-between py-2">
                <span className="flex items-center gap-2 text-sm text-muted-foreground">
                  <GitBranch className="h-4 w-4 flex-shrink-0" />
                  Cluster
                </span>
                <span
                  className="inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold text-white"
                  style={{ backgroundColor: clusterColour }}
                >
                  Cluster {gm.cluster_id}
                </span>
              </div>
            )}
            <StatRow
              icon={Zap}
              label="Neighbours"
              value={gm.neighbors_count}
              sub="in graph"
            />
          </>
        )}
      </div>

      {gm && (
        <div className="pt-2 border-t">
          <CentralityBar value={gm.degree_centrality} />
          <div className="flex items-center justify-between pt-1">
            <span className="text-xs text-muted-foreground">Betweenness</span>
            <span className="text-xs font-medium tabular-nums">
              {gm.betweenness_centrality.toFixed(6)}
            </span>
          </div>
        </div>
      )}
    </section>
  );
}
