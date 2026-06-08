"use client";

import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { CLUSTER_COLOURS } from "@/lib/constants";
import type { ChatSource } from "@/lib/types";
import { ArrowUpRight, TrendingUp } from "lucide-react";

interface Props {
  source: ChatSource;
  index: number;
}

export function SourceCard({ source, index }: Props) {
  return (
    <Card className="shadow-none border border-border/60 hover:border-border transition-colors">
      <CardHeader className="pb-2 pt-3 px-3">
        <div className="flex items-start gap-2">
          <span className="text-xs font-mono text-muted-foreground mt-0.5 shrink-0">
            [{index}]
          </span>
          <p className="text-sm font-medium leading-snug line-clamp-2 flex-1">
            {source.title}
          </p>
        </div>
      </CardHeader>
      <CardContent className="px-3 pb-3 space-y-2">
        {/* Venue + citations row */}
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

        {/* Match score hint */}
        <div className="flex items-center justify-between pt-1">
          <span className="text-xs text-muted-foreground">
            relevance {source.match_score.toFixed(0)}
          </span>
          <Link
            href={`/papers/${source.id}`}
            className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors px-2 py-1 rounded hover:bg-muted"
          >
            Open <ArrowUpRight className="h-3 w-3" />
          </Link>
        </div>
      </CardContent>
    </Card>
  );
}
