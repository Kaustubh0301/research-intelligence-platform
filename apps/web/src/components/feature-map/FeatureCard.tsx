import type { FeatureMapResult } from "@/lib/types";
import { CoverageBadge } from "./CoverageBadge";
import { PaperRow } from "./PaperRow";
import { RecommendationList } from "./RecommendationList";

export function FeatureCard({ result }: { result: FeatureMapResult }) {
  const { feature, coverage_tier, coverage_score, papers, recommendations } = result;

  return (
    <section className="rounded-xl border border-outline-variant bg-surface-container-low p-lg space-y-md">
      {/* Header */}
      <div className="flex items-start justify-between gap-md">
        <div className="min-w-0">
          <h3 className="font-headline-md text-title-md font-bold text-on-surface leading-tight">
            {feature.name}
          </h3>
          <span className="mt-1 inline-flex items-center gap-1 text-[11px] uppercase tracking-wide text-on-surface-variant opacity-70">
            <span className="material-symbols-outlined text-[14px]">category</span>
            {feature.feature_type}
          </span>
        </div>
        <CoverageBadge tier={coverage_tier} score={coverage_score} />
      </div>

      {feature.description && (
        <p className="text-body-sm text-on-surface-variant leading-relaxed">
          {feature.description}
        </p>
      )}

      {/* Matched techniques */}
      {feature.matched_techniques.length > 0 && (
        <div>
          <p className="mb-1.5 text-[11px] font-label-md uppercase tracking-wide text-on-surface-variant opacity-70">
            Matched techniques
          </p>
          <div className="flex flex-wrap gap-1.5">
            {feature.matched_techniques.map((t) => (
              <span
                key={t}
                className="inline-flex rounded-full bg-surface-container-highest border border-outline-variant px-sm py-0.5 text-[11px] text-on-surface"
              >
                {t}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Top papers */}
      <div>
        <p className="mb-2 text-[11px] font-label-md uppercase tracking-wide text-on-surface-variant opacity-70">
          Top {papers.length} {papers.length === 1 ? "paper" : "papers"}
        </p>
        {papers.length === 0 ? (
          <p className="text-body-sm text-on-surface-variant opacity-60 italic">
            No matching papers found in the corpus.
          </p>
        ) : (
          <ul className="space-y-2">
            {papers.map((p) => (
              <PaperRow key={p.paper_id} paper={p} />
            ))}
          </ul>
        )}
      </div>

      {/* Recommendations (Phase 2C) */}
      <RecommendationList recommendations={recommendations} />
    </section>
  );
}
