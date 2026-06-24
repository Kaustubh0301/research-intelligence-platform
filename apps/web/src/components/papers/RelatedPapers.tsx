import Link from "next/link";
import type { RelatedPaperEntry } from "@/lib/types";
import { CLUSTER_COLOURS, CLUSTER_LABELS } from "@/lib/constants";

interface Props { related: RelatedPaperEntry[]; }

type MatchTier = { label: string; className: string };

function matchTier(weight: number): MatchTier {
  if (weight >= 12) return { label: "Strong Match",   className: "bg-emerald-500/15 text-emerald-700 dark:text-emerald-400 border-emerald-500/30" };
  if (weight >= 7)  return { label: "Good Match",     className: "bg-blue-500/15 text-blue-700 dark:text-blue-400 border-blue-500/30" };
  if (weight >= 4)  return { label: "Related",        className: "bg-surface-container-highest text-on-surface-variant border-outline-variant" };
  return              { label: "Loosely Related", className: "bg-surface-container-highest text-on-surface-variant/60 border-outline-variant" };
}

export function RelatedPapers({ related }: Props) {
  if (!related.length) {
    return (
      <section className="rounded-xl border border-outline-variant bg-surface-container-low p-lg">
        <h2 className="text-label-md uppercase tracking-widest text-on-surface-variant mb-md">
          Related Papers
        </h2>
        <p className="text-body-sm text-on-surface-variant">No related papers found.</p>
      </section>
    );
  }

  return (
    <section className="rounded-xl border border-outline-variant bg-surface-container-low p-lg">
      <div className="flex items-center justify-between mb-lg">
        <h2 className="text-label-md uppercase tracking-widest text-on-surface-variant">
          Related Papers
        </h2>
        <span className="text-[11px] text-on-surface-variant">{related.length} papers</span>
      </div>

      <div className="space-y-md">
        {related.map(({ paper, weight, shared_techniques, shared_datasets, shared_categories, shared_methodologies }) => {
          const clusterColour =
            paper.cluster_id != null ? (CLUSTER_COLOURS[paper.cluster_id] ?? "#6b7280") : null;
          const clusterLabel =
            paper.cluster_id != null ? (CLUSTER_LABELS[paper.cluster_id] ?? `Cluster ${paper.cluster_id}`) : null;
          const tier = matchTier(weight);

          // Build "Why related" bullets — techniques first, then datasets, then categories
          const whyItems: string[] = [
            ...shared_techniques.slice(0, 3),
            ...shared_datasets.slice(0, 2),
            ...shared_categories.slice(0, 2),
            ...shared_methodologies.slice(0, 1),
          ].filter((item, idx, arr) => arr.indexOf(item) === idx).slice(0, 5);

          return (
            <article
              key={paper.id}
              className="group relative rounded-lg border border-outline-variant bg-surface-container p-md transition-colors hover:border-im-primary hover:bg-surface-container-high"
            >
              <Link
                href={`/papers/${paper.id}`}
                className="absolute inset-0 z-0 rounded-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-im-primary"
                aria-label={paper.title}
              />
              <div className="relative z-10 pointer-events-none space-y-sm">
                {/* Title + match badge */}
                <div className="flex items-start gap-sm">
                  <p className="flex-1 text-body-sm font-medium text-on-surface group-hover:text-im-primary transition-colors line-clamp-2">
                    {paper.title}
                  </p>
                  <span className={`flex-shrink-0 mt-0.5 inline-flex items-center rounded-full border px-xs py-0.5 text-[10px] font-semibold whitespace-nowrap ${tier.className}`}>
                    {tier.label}
                  </span>
                </div>

                {/* Why related */}
                {whyItems.length > 0 && (
                  <div className="flex flex-wrap items-center gap-xs">
                    <span className="text-[10px] text-on-surface-variant/60 mr-0.5">Why related:</span>
                    {whyItems.map((item) => (
                      <span
                        key={item}
                        className="inline-flex items-center rounded bg-surface-container-highest px-xs py-0.5 text-[10px] text-on-surface-variant border border-outline-variant"
                      >
                        {item}
                      </span>
                    ))}
                  </div>
                )}

                {/* Meta row */}
                <div className="flex flex-wrap items-center gap-xs">
                  {clusterColour !== null && clusterLabel !== null && (
                    <span
                      className="inline-flex items-center rounded-full px-sm py-0.5 text-[10px] font-bold text-white"
                      style={{ backgroundColor: clusterColour }}
                    >
                      {clusterLabel}
                    </span>
                  )}
                  {paper.citation_count > 0 && (
                    <span className="flex items-center gap-xs text-[11px] text-on-surface-variant">
                      <span className="material-symbols-outlined text-[13px]">trending_up</span>
                      {paper.citation_count.toLocaleString()}
                    </span>
                  )}
                </div>
              </div>
            </article>
          );
        })}
      </div>
    </section>
  );
}
