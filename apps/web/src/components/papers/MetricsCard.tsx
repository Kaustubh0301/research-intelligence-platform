import type { PaperDetail } from "@/lib/types";
import { CLUSTER_COLOURS } from "@/lib/constants";
import { FEATURES } from "@/lib/features";

interface Props { paper: PaperDetail; }

function StatRow({
  icon,
  label,
  value,
  sub,
  accent,
}: {
  icon:    string;
  label:   string;
  value:   string | number;
  sub?:    string;
  accent?: string;
}) {
  return (
    <div className="flex items-center justify-between py-sm">
      <span className="flex items-center gap-sm text-body-sm text-on-surface-variant">
        <span className={`material-symbols-outlined text-[18px] ${accent ?? "text-outline"}`}>
          {icon}
        </span>
        {label}
      </span>
      <span className="text-body-sm font-medium text-on-surface tabular-nums">
        {typeof value === "number" ? value.toLocaleString() : value}
        {sub && <span className="ml-xs text-[11px] font-normal text-on-surface-variant">{sub}</span>}
      </span>
    </div>
  );
}

function CentralityBar({ value }: { value: number }) {
  const pct = Math.round(value * 100);
  return (
    <div className="space-y-xs py-xs">
      <div className="flex items-center justify-between text-body-sm">
        <span className="flex items-center gap-sm text-on-surface-variant">
          <span className="material-symbols-outlined text-[18px] text-outline">show_chart</span>
          Degree centrality
        </span>
        <span className="font-medium text-on-surface tabular-nums">{value.toFixed(4)}</span>
      </div>
      <div className="relative h-1.5 w-full overflow-hidden rounded-full bg-surface-container-highest">
        <div
          className="h-full rounded-full bg-im-primary transition-all"
          style={{ width: `${pct}%` }}
        />
      </div>
      <p className="text-right text-[11px] text-on-surface-variant">top {100 - pct}%</p>
    </div>
  );
}

export function MetricsCard({ paper }: Props) {
  const gm           = paper.graph_metrics;
  const clusterColour =
    gm?.cluster_id != null ? (CLUSTER_COLOURS[gm.cluster_id] ?? "#6b7280") : null;

  return (
    <section className="rounded-xl border border-outline-variant bg-surface-container-low p-lg space-y-xs">
      <h2 className="text-label-md uppercase tracking-widest text-on-surface-variant mb-sm">
        Metrics
      </h2>

      <div className="divide-y divide-outline-variant/40">
        <StatRow
          icon="trending_up"
          label="Citations"
          value={paper.citation_count}
          accent="text-im-primary"
        />
        {paper.influential_citation_count > 0 && (
          <StatRow
            icon="star"
            label="Influential"
            value={paper.influential_citation_count}
            accent="text-im-tertiary"
          />
        )}
        {paper.authors.length > 0 && (
          <StatRow icon="group" label="Authors" value={paper.authors.length} />
        )}

        {/* Graph metrics: cluster badge + neighbour count */}
        {FEATURES.GRAPH && gm && (
          <>
            {clusterColour !== null && (
              <div className="flex items-center justify-between py-sm">
                <span className="flex items-center gap-sm text-body-sm text-on-surface-variant">
                  <span className="material-symbols-outlined text-[18px] text-outline">account_tree</span>
                  Cluster
                </span>
                <span
                  className="inline-flex items-center rounded-full px-sm py-0.5 text-[11px] font-bold text-white"
                  style={{ backgroundColor: clusterColour }}
                >
                  Cluster {gm.cluster_id}
                </span>
              </div>
            )}
            <StatRow
              icon="hub"
              label="Neighbours"
              value={gm.neighbors_count}
              sub="in graph"
            />
          </>
        )}
      </div>

      {/* Graph centrality metrics */}
      {FEATURES.GRAPH && gm && (
        <div className="pt-sm border-t border-outline-variant/40">
          <CentralityBar value={gm.degree_centrality} />
          <div className="flex items-center justify-between pt-xs">
            <span className="text-[11px] text-on-surface-variant">Betweenness</span>
            <span className="text-[11px] font-medium text-on-surface tabular-nums">
              {gm.betweenness_centrality.toFixed(6)}
            </span>
          </div>
        </div>
      )}
    </section>
  );
}
