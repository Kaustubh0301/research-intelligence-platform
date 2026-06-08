import type { PaperDetail } from "@/lib/types";
import { CLUSTER_COLOURS } from "@/lib/constants";
import { buttonVariants } from "@/components/ui/button";
import { ExternalLink, BookOpen, Lock } from "lucide-react";
import { cn } from "@/lib/utils";

function PresentationPill({ type }: { type: string }) {
  const styles: Record<string, string> = {
    oral: "bg-emerald-50 text-emerald-700 border-emerald-200",
    spotlight: "bg-blue-50 text-blue-700 border-blue-200",
    poster: "bg-zinc-50 text-zinc-600 border-zinc-200",
  };
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium capitalize",
        styles[type] ?? styles.poster
      )}
    >
      {type}
    </span>
  );
}

interface Props {
  paper: PaperDetail;
}

export function PaperHero({ paper }: Props) {
  const allAuthors = paper.authors;
  const displayAuthors = allAuthors.slice(0, 5);
  const extra = allAuthors.length - displayAuthors.length;

  const clusterColour =
    paper.graph_metrics?.cluster_id != null
      ? (CLUSTER_COLOURS[paper.graph_metrics.cluster_id] ?? "#6b7280")
      : null;

  return (
    <div className="rounded-xl border bg-card p-6 space-y-4">
      {/* Title */}
      <h1 className="text-2xl font-bold leading-tight tracking-tight">
        {paper.title}
      </h1>

      {/* Authors */}
      <p className="text-sm text-muted-foreground leading-relaxed">
        {displayAuthors.map((a, i) => (
          <span key={a.id}>
            {i > 0 && <span className="mx-1 text-border">·</span>}
            <span
              className={cn(
                a.position === 1 && "font-medium text-foreground"
              )}
            >
              {a.full_name}
              {a.affiliation && (
                <span className="text-xs text-muted-foreground/60 ml-0.5">
                  {" "}({a.affiliation})
                </span>
              )}
            </span>
          </span>
        ))}
        {extra > 0 && (
          <span className="ml-1 text-muted-foreground/60">
            +{extra} more
          </span>
        )}
      </p>

      {/* Badges row */}
      <div className="flex flex-wrap gap-2">
        {paper.conference && paper.year && (
          <span className="inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium text-muted-foreground">
            {paper.conference} {paper.year}
          </span>
        )}
        {paper.presentation_type && (
          <PresentationPill type={paper.presentation_type} />
        )}
        {clusterColour !== null && (
          <span
            className="inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold text-white"
            style={{ backgroundColor: clusterColour }}
          >
            Cluster {paper.graph_metrics!.cluster_id}
          </span>
        )}
        {paper.is_open_access ? (
          <span className="inline-flex items-center gap-1 rounded-full border border-amber-200 bg-amber-50 px-2.5 py-0.5 text-xs font-medium text-amber-700">
            <BookOpen className="h-3 w-3" />
            Open Access
          </span>
        ) : (
          <span className="inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-xs font-medium text-muted-foreground">
            <Lock className="h-3 w-3" />
            Closed
          </span>
        )}
      </div>

      {/* External links */}
      {(paper.pdf_url || paper.openreview_id || paper.arxiv_id || paper.semantic_scholar_id) && (
        <div className="flex flex-wrap gap-2 pt-1">
          {paper.pdf_url && (
            <a
              href={paper.pdf_url}
              target="_blank"
              rel="noopener noreferrer"
              className={buttonVariants({ variant: "outline", size: "sm" })}
            >
              <ExternalLink className="mr-1.5 h-3.5 w-3.5" />
              PDF
            </a>
          )}
          {paper.openreview_id && (
            <a
              href={`https://openreview.net/forum?id=${paper.openreview_id}`}
              target="_blank"
              rel="noopener noreferrer"
              className={buttonVariants({ variant: "outline", size: "sm" })}
            >
              <ExternalLink className="mr-1.5 h-3.5 w-3.5" />
              OpenReview
            </a>
          )}
          {paper.arxiv_id && (
            <a
              href={`https://arxiv.org/abs/${paper.arxiv_id}`}
              target="_blank"
              rel="noopener noreferrer"
              className={buttonVariants({ variant: "outline", size: "sm" })}
            >
              <ExternalLink className="mr-1.5 h-3.5 w-3.5" />
              arXiv
            </a>
          )}
          {paper.semantic_scholar_id && (
            <a
              href={`https://www.semanticscholar.org/paper/${paper.semantic_scholar_id}`}
              target="_blank"
              rel="noopener noreferrer"
              className={buttonVariants({ variant: "outline", size: "sm" })}
            >
              <ExternalLink className="mr-1.5 h-3.5 w-3.5" />
              Semantic Scholar
            </a>
          )}
        </div>
      )}
    </div>
  );
}
