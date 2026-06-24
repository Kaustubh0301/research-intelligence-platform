import type { FeatureMapRecommendation } from "@/lib/types";
import { cn } from "@/lib/utils";

const TYPE_META: Record<
  FeatureMapRecommendation["rec_type"],
  { label: string; icon: string; cls: string }
> = {
  missing_technique: {
    label: "Missing technique",
    icon: "extension",
    cls: "bg-violet-500/10 text-violet-400 border-violet-500/30",
  },
  evaluation_suggestion: {
    label: "Evaluation",
    icon: "analytics",
    cls: "bg-cyan-500/10 text-cyan-400 border-cyan-500/30",
  },
};

function RecItem({ rec }: { rec: FeatureMapRecommendation }) {
  const meta = TYPE_META[rec.rec_type] ?? TYPE_META.missing_technique;
  return (
    <li className="rounded-lg border border-outline-variant bg-surface-container px-md py-sm">
      <div className="flex items-start justify-between gap-md">
        <p className="text-body-sm font-medium text-on-surface leading-snug">
          {rec.title}
        </p>
        <span
          className={cn(
            "inline-flex items-center gap-1 rounded-full border px-sm py-0.5 text-[10px] font-label-md whitespace-nowrap",
            meta.cls
          )}
        >
          <span className="material-symbols-outlined text-[13px]">{meta.icon}</span>
          {meta.label}
        </span>
      </div>

      <p className="mt-1 text-body-sm text-on-surface-variant leading-relaxed">
        {rec.body}
      </p>

      {rec.evidence_count > 0 && (
        <p className="mt-1.5 text-[11px] text-on-surface-variant opacity-70">
          <span className="material-symbols-outlined text-[12px] align-middle">
            menu_book
          </span>{" "}
          {rec.evidence_count} supporting paper{rec.evidence_count === 1 ? "" : "s"}
          {rec.supporting_paper_titles.length > 0 &&
            `: ${rec.supporting_paper_titles.slice(0, 2).join("; ")}${
              rec.supporting_paper_titles.length > 2 ? "…" : ""
            }`}
        </p>
      )}
    </li>
  );
}

export function RecommendationList({
  recommendations,
}: {
  recommendations: FeatureMapRecommendation[];
}) {
  if (!recommendations || recommendations.length === 0) return null;

  return (
    <div>
      <p className="mb-2 text-[11px] font-label-md uppercase tracking-wide text-on-surface-variant opacity-70">
        Recommendations
      </p>
      <ul className="space-y-2">
        {recommendations.map((r, i) => (
          <RecItem key={`${r.rec_type}-${r.rank}-${i}`} rec={r} />
        ))}
      </ul>
    </div>
  );
}
