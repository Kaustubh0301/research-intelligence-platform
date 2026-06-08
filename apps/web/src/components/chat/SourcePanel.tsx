"use client";

import { Skeleton } from "@/components/ui/skeleton";
import type { ChatSource } from "@/lib/types";
import { BookOpen } from "lucide-react";
import { SourceCard } from "./SourceCard";

interface Props {
  sources: ChatSource[];
  isLoading: boolean;
}

export function SourcePanel({ sources, isLoading }: Props) {
  return (
    <aside className="w-72 shrink-0 border-l bg-background flex flex-col overflow-hidden">
      <div className="p-3 border-b flex items-center gap-2">
        <BookOpen className="h-4 w-4 text-muted-foreground" />
        <span className="text-sm font-semibold">Supporting Papers</span>
        {sources.length > 0 && !isLoading && (
          <span className="ml-auto text-xs text-muted-foreground">
            {sources.length}
          </span>
        )}
      </div>

      <div className="flex-1 overflow-y-auto p-3 space-y-3">
        {isLoading ? (
          <>
            {[1, 2, 3].map((i) => (
              <div key={i} className="space-y-2 p-3 border rounded-lg">
                <Skeleton className="h-3 w-full" />
                <Skeleton className="h-3 w-4/5" />
                <div className="flex gap-1">
                  <Skeleton className="h-5 w-16 rounded-full" />
                  <Skeleton className="h-5 w-12 rounded-full" />
                </div>
                <div className="flex gap-1">
                  <Skeleton className="h-5 w-20 rounded" />
                  <Skeleton className="h-5 w-16 rounded" />
                </div>
              </div>
            ))}
          </>
        ) : sources.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-40 text-center">
            <BookOpen className="h-8 w-8 text-muted-foreground/30 mb-2" />
            <p className="text-sm text-muted-foreground">
              Supporting papers will appear here after you ask a question.
            </p>
          </div>
        ) : (
          sources.map((source, i) => (
            <SourceCard key={source.id} source={source} index={i + 1} />
          ))
        )}
      </div>
    </aside>
  );
}
