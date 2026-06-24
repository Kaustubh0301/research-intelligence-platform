"use client";

import { cn } from "@/lib/utils";
import { useSession } from "./SessionContext";

export function SavedPapersList() {
  const { activeSession, removePaper } = useSession();

  const papers = activeSession?.savedPapers ?? [];

  return (
    <div className="flex flex-col">
      <div className="flex items-center justify-between px-3 py-2 border-b border-border bg-muted/40 shrink-0">
        <span className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
          Saved papers
        </span>
        {papers.length > 0 && (
          <span className="text-[10px] bg-accent text-muted-foreground rounded-full px-1.5 py-0.5 leading-none">
            {papers.length}
          </span>
        )}
      </div>

      {papers.length === 0 ? (
        <p className="px-3 py-3 text-[11px] text-muted-foreground/60 italic">
          No papers saved yet. Click Save on any source.
        </p>
      ) : (
        <div className="py-1">
          {papers.map((paper) => (
            <div
              key={paper.id}
              className="group flex items-start gap-2 px-3 py-2 hover:bg-muted transition-colors"
            >
              {/* Paper icon */}
              <svg
                className="h-3.5 w-3.5 mt-0.5 text-primary/60 shrink-0"
                viewBox="0 0 16 16"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.5"
              >
                <rect x="3" y="1" width="10" height="14" rx="1" />
                <path d="M6 5h4M6 8h4M6 11h2" />
              </svg>

              <div className="flex-1 min-w-0">
                <a
                  href={`/papers/${paper.id}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="block text-[11px] font-medium text-foreground leading-snug line-clamp-2 hover:text-primary transition-colors"
                >
                  {paper.title}
                </a>
                {(paper.conference || paper.year) && (
                  <p className="text-[10px] text-muted-foreground mt-0.5">
                    {[paper.conference, paper.year].filter(Boolean).join(" ")}
                  </p>
                )}
              </div>

              {/* Remove */}
              <button
                onClick={() => removePaper(paper.id)}
                title="Remove"
                className={cn(
                  "shrink-0 p-0.5 rounded text-muted-foreground/40",
                  "opacity-0 group-hover:opacity-100 transition-opacity",
                  "hover:text-destructive hover:bg-destructive/10"
                )}
              >
                <svg className="h-3 w-3" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M3 3l10 10M13 3L3 13" />
                </svg>
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
