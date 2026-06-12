import Link from "next/link";
import type { PaperSummary } from "@/lib/types";
import { cn } from "@/lib/utils";

interface Props {
  paper: PaperSummary;
  onTechniqueClick?: (name: string) => void;
}

// ── Conference badge colour ───────────────────────────────────────────────

function conferenceBadgeClass(conf: string | null) {
  if (!conf) return "bg-surface-container border-outline-variant text-on-surface-variant";
  const c = conf.toUpperCase();
  if (c.includes("NEURIPS") || c.includes("NIPS"))
    return "bg-primary-container/10 border-primary-container/20 text-im-primary";
  if (c.includes("ICML"))
    return "bg-tertiary-container/10 border-tertiary-container/20 text-im-tertiary";
  if (c.includes("ICLR"))
    return "bg-secondary-container/10 border-secondary-container/20 text-im-secondary";
  return "bg-surface-container border-outline-variant text-on-surface-variant";
}

// ── Presentation type chip ────────────────────────────────────────────────

function PresentationChip({ type }: { type: string }) {
  const styles: Record<string, string> = {
    oral:      "bg-emerald-900/30 border-emerald-700/40 text-emerald-400",
    spotlight: "bg-blue-900/30 border-blue-700/40 text-blue-400",
    poster:    "bg-surface-container border-outline-variant text-on-surface-variant",
  };
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border px-2 py-0.5 text-[10px] font-bold font-label-md uppercase",
        styles[type] ?? styles.poster
      )}
    >
      {type}
    </span>
  );
}

// ── Card ──────────────────────────────────────────────────────────────────

export function PaperCard({ paper, onTechniqueClick }: Props) {
  const confBadge = conferenceBadgeClass(paper.conference);

  return (
    <article className="group relative bg-surface-container-low border border-outline-variant rounded-xl p-lg hover:border-im-primary transition-all duration-300 hover:shadow-[0_8px_30px_rgba(0,0,0,0.25)]">
      {/* Full-card link behind everything */}
      <Link
        href={`/papers/${paper.id}`}
        className="absolute inset-0 z-0 rounded-xl focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-im-primary focus-visible:ring-offset-2 focus-visible:ring-offset-background"
        aria-label={paper.title}
      />

      <div className="relative z-10 pointer-events-none">
        <div className="flex justify-between items-start gap-md">

          {/* Left: metadata + title + abstract + technique chips */}
          <div className="flex-1 min-w-0">
            {/* Badge row */}
            <div className="flex flex-wrap items-center gap-sm mb-xs">
              {paper.conference && paper.year && (
                <span
                  className={cn(
                    "inline-flex items-center border rounded px-sm py-0.5 text-[10px] font-bold font-label-md uppercase",
                    confBadge
                  )}
                >
                  {paper.conference} {paper.year}
                </span>
              )}
              {paper.presentation_type && (
                <PresentationChip type={paper.presentation_type} />
              )}
              {paper.is_open_access && (
                <span className="inline-flex items-center border border-amber-700/40 bg-amber-900/20 rounded px-sm py-0.5 text-[10px] font-bold font-label-md uppercase text-amber-400">
                  Open Access
                </span>
              )}
            </div>

            {/* Title */}
            <h2 className="text-body-lg font-headline-md text-on-surface group-hover:text-im-primary transition-colors line-clamp-2 mb-sm leading-snug">
              {paper.title}
            </h2>

            {/* Abstract snippet */}
            {paper.abstract_snippet && (
              <p className="text-body-sm text-on-surface-variant line-clamp-2 mb-md leading-relaxed">
                {paper.abstract_snippet}
              </p>
            )}

            {/* Technique chips */}
            {paper.top_techniques.length > 0 && (
              <div className="pointer-events-auto flex flex-wrap gap-xs">
                {paper.top_techniques.slice(0, 4).map((t) => (
                  <button
                    key={t}
                    type="button"
                    onClick={(e) => {
                      e.preventDefault();
                      onTechniqueClick?.(t);
                    }}
                    className="flex items-center gap-xs px-sm py-1 bg-surface-container-highest rounded border border-outline-variant text-[11px] font-label-md text-on-surface-variant uppercase hover:border-outline hover:text-on-surface transition-colors"
                  >
                    <span className="material-symbols-outlined text-[13px] text-im-primary">
                      psychology
                    </span>
                    {t}
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* Right: citation count + bookmark */}
          <div className="flex flex-col items-end gap-md flex-shrink-0">
            <div className="text-right">
              <div className="text-headline-md font-bold text-on-surface font-code">
                {paper.citation_count >= 1000
                  ? `${(paper.citation_count / 1000).toFixed(1)}k`
                  : paper.citation_count.toLocaleString()}
              </div>
              <div className="text-[10px] text-on-surface-variant font-label-md uppercase tracking-tighter mt-0.5">
                Citations
              </div>
            </div>

            {paper.influential_citation_count > 0 && (
              <div className="text-right">
                <div className="text-body-sm font-bold text-im-tertiary font-code">
                  {paper.influential_citation_count}
                </div>
                <div className="text-[10px] text-on-surface-variant font-label-md uppercase tracking-tighter">
                  Influential
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </article>
  );
}
