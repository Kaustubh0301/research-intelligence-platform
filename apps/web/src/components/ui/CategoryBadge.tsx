import { CLUSTER_LABELS } from "@/lib/constants";
import { cn } from "@/lib/utils";

/**
 * Shows the paper's primary research category as a small badge.
 * Falls back to the cluster label when category is null.
 * Returns null if neither is available.
 */
interface Props {
  category: string | null | undefined;
  clusterId?: number | null;
  className?: string;
}

export function CategoryBadge({ category, clusterId, className }: Props) {
  const label = category ?? (clusterId != null ? CLUSTER_LABELS[clusterId] : null);
  if (!label) return null;

  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border border-violet-200 bg-violet-50 px-2 py-0.5 text-xs font-medium text-violet-700 dark:border-violet-800 dark:bg-violet-950/40 dark:text-violet-300",
        className
      )}
    >
      {label}
    </span>
  );
}
