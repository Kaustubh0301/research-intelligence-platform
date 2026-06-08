import Link from "next/link";
import { TrendingUp, BookOpen, Star } from "lucide-react";
import type { PaperSummary } from "@/lib/types";
import { CLUSTER_COLOURS } from "@/lib/constants";
import { CategoryBadge } from "@/components/ui/CategoryBadge";
import { cn } from "@/lib/utils";

interface Props {
  paper: PaperSummary;
  onTechniqueClick?: (name: string) => void;
}

function PresentationBadge({ type }: { type: string }) {
  const styles: Record<string, string> = {
    oral: "bg-emerald-50 text-emerald-700 border-emerald-200",
    spotlight: "bg-blue-50 text-blue-700 border-blue-200",
    poster: "bg-zinc-50 text-zinc-600 border-zinc-200",
  };
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium capitalize",
        styles[type] ?? styles.poster
      )}
    >
      {type}
    </span>
  );
}

export function PaperCard({ paper, onTechniqueClick }: Props) {
  const clusterColour = paper.cluster_id !== null
    ? (CLUSTER_COLOURS[paper.cluster_id] ?? "#6b7280")
    : null;

  return (
    // Stretched-link pattern: outer div is position:relative,
    // the Link covers the whole card at z-0, technique chips sit at z-10.
    <article className="group relative rounded-lg border bg-card transition-shadow hover:shadow-md hover:border-border/80">
      {/* Full-card link — sits behind everything */}
      <Link
        href={`/papers/${paper.id}`}
        className="absolute inset-0 z-0 rounded-lg"
        aria-label={paper.title}
      />

      <div className="relative z-10 pointer-events-none p-4">
        {/* Top metadata row */}
        <div className="flex flex-wrap items-center gap-1.5 mb-2">
          {paper.conference && paper.year && (
            <span className="inline-flex items-center rounded-full border px-2 py-0.5 text-xs text-muted-foreground">
              {paper.conference} {paper.year}
            </span>
          )}
          {paper.presentation_type && (
            <PresentationBadge type={paper.presentation_type} />
          )}
          {clusterColour !== null && (
            <span
              className="inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium text-white"
              style={{ backgroundColor: clusterColour }}
            >
              Cluster {paper.cluster_id}
            </span>
          )}
          {paper.is_open_access && (
            <span className="inline-flex items-center rounded-full bg-amber-50 border border-amber-200 px-2 py-0.5 text-xs font-medium text-amber-700">
              <BookOpen className="mr-1 h-3 w-3" />
              OA
            </span>
          )}
        </div>

        {/* Title + primary category */}
        <div className="flex items-start gap-2 mb-1.5">
          <h2 className="flex-1 text-sm font-semibold leading-snug group-hover:text-primary transition-colors line-clamp-2">
            {paper.title}
          </h2>
          <CategoryBadge
            category={paper.primary_category}
            clusterId={paper.cluster_id}
            className="flex-shrink-0 mt-0.5"
          />
        </div>

        {/* Abstract snippet */}
        {paper.abstract_snippet && (
          <p className="text-xs text-muted-foreground leading-relaxed line-clamp-2 mb-3">
            {paper.abstract_snippet}
          </p>
        )}

        {/* Bottom row: techniques + metrics */}
        <div className="flex items-end justify-between gap-2 mt-auto">
          {/* Technique chips — pointer-events restored so they're clickable above the link */}
          <div className="pointer-events-auto flex flex-wrap gap-1">
            {paper.top_techniques.slice(0, 3).map((t) => (
              <button
                key={t}
                type="button"
                onClick={(e) => {
                  e.preventDefault();
                  onTechniqueClick?.(t);
                }}
                className="inline-flex items-center rounded px-1.5 py-0.5 text-xs bg-secondary text-secondary-foreground hover:bg-muted transition-colors"
              >
                {t}
              </button>
            ))}
          </div>

          {/* Metrics */}
          <div className="flex items-center gap-3 flex-shrink-0 text-xs text-muted-foreground">
            {paper.influential_citation_count > 0 && (
              <span
                className="flex items-center gap-0.5"
                title="Influential citations"
              >
                <Star className="h-3 w-3 text-amber-400 fill-amber-400" />
                {paper.influential_citation_count}
              </span>
            )}
            <span
              className="flex items-center gap-1"
              title="Total citations"
            >
              <TrendingUp className="h-3 w-3" />
              {paper.citation_count.toLocaleString()}
            </span>
          </div>
        </div>
      </div>
    </article>
  );
}
