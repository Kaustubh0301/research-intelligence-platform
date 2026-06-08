import type { PaperDetail } from "@/lib/types";
import { CLUSTER_COLOURS } from "@/lib/constants";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { ExternalLink, TrendingUp, Lock, Unlock } from "lucide-react";

function presentationVariant(type: string | null) {
  if (type === "oral") return "green";
  if (type === "spotlight") return "blue";
  return "secondary";
}

interface Props {
  paper: PaperDetail;
}

export function PaperMeta({ paper }: Props) {
  const authors = paper.authors.slice(0, 4);
  const hasMore = paper.authors.length > 4;

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-bold leading-snug">{paper.title}</h1>

      <div className="text-sm text-muted-foreground">
        {authors.map((a, i) => (
          <span key={a.id}>
            {i > 0 && " · "}
            <span className={a.position === 1 ? "font-medium text-foreground" : ""}>
              {a.full_name}
            </span>
          </span>
        ))}
        {hasMore && <span> · et al.</span>}
      </div>

      <div className="flex flex-wrap gap-1.5">
        {paper.conference && paper.year && (
          <Badge variant="outline">
            {paper.conference} {paper.year}
          </Badge>
        )}
        {paper.presentation_type && (
          <Badge variant={presentationVariant(paper.presentation_type)}>
            {paper.presentation_type}
          </Badge>
        )}
        {paper.graph_metrics?.cluster_id !== undefined &&
          paper.graph_metrics.cluster_id !== null && (
            <span
              className="inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium text-white"
              style={{
                backgroundColor:
                  CLUSTER_COLOURS[paper.graph_metrics.cluster_id] ?? "#6b7280",
              }}
            >
              Cluster {paper.graph_metrics.cluster_id}
            </span>
          )}
        <Badge variant={paper.is_open_access ? "green" : "secondary"}>
          {paper.is_open_access ? (
            <><Unlock className="h-3 w-3 mr-1" />Open Access</>
          ) : (
            <><Lock className="h-3 w-3 mr-1" />Closed</>
          )}
        </Badge>
      </div>

      <div className="flex items-center gap-4 text-sm">
        <span className="flex items-center gap-1">
          <TrendingUp className="h-3.5 w-3.5 text-muted-foreground" />
          <span className="font-medium">{paper.citation_count.toLocaleString()}</span>
          <span className="text-muted-foreground">citations</span>
        </span>
        {paper.influential_citation_count > 0 && (
          <span className="text-muted-foreground">
            {paper.influential_citation_count} influential
          </span>
        )}
      </div>

      <div className="flex flex-wrap gap-2">
        {paper.pdf_url && (
          <Button variant="outline" size="sm" asChild>
            <a href={paper.pdf_url} target="_blank" rel="noopener noreferrer">
              <ExternalLink className="h-3.5 w-3.5 mr-1.5" />
              PDF
            </a>
          </Button>
        )}
        {paper.openreview_id && (
          <Button variant="outline" size="sm" asChild>
            <a
              href={`https://openreview.net/forum?id=${paper.openreview_id}`}
              target="_blank"
              rel="noopener noreferrer"
            >
              <ExternalLink className="h-3.5 w-3.5 mr-1.5" />
              OpenReview
            </a>
          </Button>
        )}
        {paper.semantic_scholar_id && (
          <Button variant="outline" size="sm" asChild>
            <a
              href={`https://www.semanticscholar.org/paper/${paper.semantic_scholar_id}`}
              target="_blank"
              rel="noopener noreferrer"
            >
              <ExternalLink className="h-3.5 w-3.5 mr-1.5" />
              Semantic Scholar
            </a>
          </Button>
        )}
        {paper.arxiv_id && (
          <Button variant="outline" size="sm" asChild>
            <a
              href={`https://arxiv.org/abs/${paper.arxiv_id}`}
              target="_blank"
              rel="noopener noreferrer"
            >
              <ExternalLink className="h-3.5 w-3.5 mr-1.5" />
              arXiv
            </a>
          </Button>
        )}
      </div>

      {paper.graph_metrics && (
        <div className="rounded-md border p-3 space-y-2 text-sm">
          <p className="font-medium text-xs text-muted-foreground uppercase tracking-wide">
            Graph Metrics
          </p>
          <div className="space-y-1.5">
            <div className="flex justify-between text-xs">
              <span>Degree centrality</span>
              <span className="font-mono">
                {paper.graph_metrics.degree_centrality.toFixed(4)}
              </span>
            </div>
            <Progress value={paper.graph_metrics.degree_centrality * 100} />
          </div>
          <div className="flex justify-between text-xs text-muted-foreground">
            <span>
              Betweenness:{" "}
              {paper.graph_metrics.betweenness_centrality.toFixed(6)}
            </span>
            <span>{paper.graph_metrics.neighbors_count} neighbours</span>
          </div>
        </div>
      )}
    </div>
  );
}
