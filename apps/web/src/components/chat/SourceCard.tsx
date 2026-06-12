"use client";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { CategoryBadge } from "@/components/ui/CategoryBadge";
import { useSession } from "@/components/sessions/SessionContext";
import { CLUSTER_COLOURS } from "@/lib/constants";
import type { ChatSource } from "@/lib/types";
import { nowIso } from "@/lib/sessions";
import { ArrowUpRight, Bookmark, BookmarkCheck, TrendingUp } from "lucide-react";

interface Props {
  source: ChatSource;
  index: number;
}

export function SourceCard({ source, index }: Props) {
  const { activeSession, savePaper } = useSession();

  const isSaved =
    activeSession?.savedPapers.some((p) => p.id === source.id) ?? false;

  function handleSave() {
    savePaper({
      id: source.id,
      title: source.title,
      conference: source.conference,
      year: source.year ?? null,
      savedAt: nowIso(),
      tags: [],
    });
  }

  return (
    <Card className="shadow-none border border-border/60 hover:border-border transition-colors">
      <CardHeader className="pb-2 pt-3 px-3">
        <div className="flex items-start gap-2">
          <span className="text-xs font-mono text-muted-foreground mt-0.5 shrink-0">
            [{index}]
          </span>
          <div className="flex-1 min-w-0 space-y-1">
            <p className="text-sm font-medium leading-snug line-clamp-2">
              {source.title}
            </p>
            <CategoryBadge
              category={source.categories[0] ?? null}
              clusterId={source.cluster_id}
            />
          </div>
        </div>
      </CardHeader>

      <CardContent className="px-3 pb-3 space-y-2">
        {/* Venue + citations */}
        <div className="flex items-center justify-between gap-2 flex-wrap">
          <div className="flex items-center gap-1 flex-wrap">
            {source.conference && (
              <Badge variant="outline" className="text-xs h-5">
                {source.conference} {source.year}
              </Badge>
            )}
            {source.cluster_id !== null && (
              <Badge
                className="text-xs h-5"
                style={{
                  backgroundColor: CLUSTER_COLOURS[source.cluster_id ?? 0],
                  color: "#fff",
                }}
              >
                C{source.cluster_id}
              </Badge>
            )}
          </div>
          <div className="flex items-center gap-1 text-xs text-muted-foreground">
            <TrendingUp className="h-3 w-3" />
            <span>{source.citation_count.toLocaleString()}</span>
          </div>
        </div>

        {/* Techniques */}
        {source.top_techniques.length > 0 && (
          <div className="flex flex-wrap gap-1">
            {source.top_techniques.map((t) => (
              <span
                key={t}
                className="text-xs bg-blue-500/10 text-blue-700 dark:text-blue-300 rounded px-1.5 py-0.5"
              >
                {t}
              </span>
            ))}
          </div>
        )}

        {/* Categories */}
        {source.categories.length > 0 && (
          <div className="flex flex-wrap gap-1">
            {source.categories.map((c) => (
              <span
                key={c}
                className="text-xs bg-violet-500/10 text-violet-700 dark:text-violet-300 rounded px-1.5 py-0.5"
              >
                {c}
              </span>
            ))}
          </div>
        )}

        {/* Actions row */}
        <div className="flex items-center justify-between pt-1 gap-2">
          <span className="text-xs text-muted-foreground">
            relevance {source.match_score.toFixed(0)}
          </span>

          <div className="flex items-center gap-1">
            {/* Save / Saved */}
            {isSaved ? (
              <span className="inline-flex items-center gap-1 text-xs text-emerald-600 px-2 py-1">
                <BookmarkCheck className="h-3 w-3" />
                Saved
              </span>
            ) : (
              <button
                onClick={handleSave}
                className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-emerald-600 transition-colors px-2 py-1 rounded hover:bg-muted"
              >
                <Bookmark className="h-3 w-3" />
                Save
              </button>
            )}

            {/* Open in new tab */}
            <a
              href={`/papers/${source.id}`}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors px-2 py-1 rounded hover:bg-muted"
            >
              Open <ArrowUpRight className="h-3 w-3" />
            </a>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
