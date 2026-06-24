import { cn } from "@/lib/utils";
import type { FeatureMapResult } from "@/lib/types";

type Tier = FeatureMapResult["coverage_tier"];

const TIER_STYLES: Record<Tier, { label: string; cls: string; icon: string }> = {
  strong: {
    label: "Strong",
    icon: "verified",
    cls: "bg-emerald-500/10 text-emerald-400 border-emerald-500/30",
  },
  moderate: {
    label: "Moderate",
    icon: "check_circle",
    cls: "bg-sky-500/10 text-sky-400 border-sky-500/30",
  },
  weak: {
    label: "Weak",
    icon: "error",
    cls: "bg-amber-500/10 text-amber-400 border-amber-500/30",
  },
  novel: {
    label: "Novel",
    icon: "auto_awesome",
    cls: "bg-fuchsia-500/10 text-fuchsia-400 border-fuchsia-500/30",
  },
};

export function CoverageBadge({
  tier,
  score,
}: {
  tier: Tier;
  score: number;
}) {
  const s = TIER_STYLES[tier] ?? TIER_STYLES.novel;
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border px-sm py-0.5 text-[11px] font-label-md whitespace-nowrap",
        s.cls
      )}
      title={`Coverage score: ${score.toFixed(3)}`}
    >
      <span className="material-symbols-outlined text-[14px]">{s.icon}</span>
      {s.label}
      <span className="opacity-70">· {score.toFixed(2)}</span>
    </span>
  );
}
