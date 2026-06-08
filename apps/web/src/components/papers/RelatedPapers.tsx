import Link from "next/link";
import { TrendingUp } from "lucide-react";
import type { RelatedPaperEntry } from "@/lib/types";
import { CLUSTER_COLOURS } from "@/lib/constants";
import { CategoryBadge } from "@/components/ui/CategoryBadge";

const MAX_WEIGHT = 10; // normalise weight bar against this ceiling

interface Props {
  related: RelatedPaperEntry[];
}

function WeightBar({ weight }: { weight: number }) {
  const pct = Math.min(100, (weight / MAX_WEIGHT) * 100);
  return (
    <div className="flex items-center gap-2 min-w-0">
      <div className="h-1 w-16 flex-shrink-0 overflow-hidden rounded-full bg-secondary">
        <div
          className="h-full rounded-full bg-primary/60 transition-all"
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="text-xs text-muted-foreground whitespace-nowrap">
        {weight.toFixed(1)}
      </span>
    </div>
  );
}

export function RelatedPapers({ related }: Props) {
  if (!related.length) {
    return (
      <section className="rounded-xl border bg-card p-5">
        <h2 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-3">
          Related Papers
        </h2>
        <p className="text-sm text-muted-foreground">No related papers found.</p>
      </section>
    );
  }

  return (
    <section className="rounded-xl border bg-card p-5">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          Related Papers
        </h2>
        <span className="text-xs text-muted-foreground">{related.length} papers</span>
      </div>

      <div className="space-y-3">
        {related.map(({ paper, weight, shared_techniques }) => {
          const clusterColour =
            paper.cluster_id != null
              ? (CLUSTER_COLOURS[paper.cluster_id] ?? "#6b7280")
              : null;

          return (
            <article
              key={paper.id}
              className="group relative rounded-lg border bg-background p-3 transition-colors hover:border-border/80 hover:bg-muted/20"
            >
              {/* Stretch link */}
              <Link
                href={`/papers/${paper.id}`}
                className="absolute inset-0 rounded-lg"
                aria-label={paper.title}
              />

              <div className="relative space-y-2">
                {/* Title + category + weight */}
                <div className="flex items-start gap-2">
                  <p className="flex-1 text-sm font-medium leading-snug group-hover:text-primary transition-colors line-clamp-2">
                    {paper.title}
                  </p>
                  <div className="flex-shrink-0 flex items-center gap-1.5 pt-0.5">
                    <CategoryBadge
                      category={paper.primary_category}
                      clusterId={paper.cluster_id}
                    />
                    <WeightBar weight={weight} />
                  </div>
                </div>

                {/* Meta row */}
                <div className="flex flex-wrap items-center gap-1.5">
                  {clusterColour !== null && (
                    <span
                      className="inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium text-white"
                      style={{ backgroundColor: clusterColour }}
                    >
                      Cluster {paper.cluster_id}
                    </span>
                  )}
                  {paper.citation_count > 0 && (
                    <span className="flex items-center gap-1 text-xs text-muted-foreground">
                      <TrendingUp className="h-3 w-3" />
                      {paper.citation_count.toLocaleString()}
                    </span>
                  )}
                  {/* Shared technique chips — z-10 so they're clickable above the stretch link */}
                  {shared_techniques.slice(0, 3).map((t) => (
                    <span
                      key={t}
                      className="relative z-10 inline-flex items-center rounded bg-secondary px-1.5 py-0.5 text-xs text-secondary-foreground"
                    >
                      {t}
                    </span>
                  ))}
                </div>
              </div>
            </article>
          );
        })}
      </div>
    </section>
  );
}
