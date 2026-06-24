"use client";

import { useState } from "react";
import { ChevronDown, ChevronUp } from "lucide-react";

const CHAR_LIMIT = 600;

interface Props {
  abstract: string;
}

export function AbstractCard({ abstract }: Props) {
  const long = abstract.length > CHAR_LIMIT;
  const [expanded, setExpanded] = useState(false);

  const displayed = long && !expanded
    ? abstract.slice(0, CHAR_LIMIT).trimEnd() + "…"
    : abstract;

  return (
    <section className="rounded-xl border bg-card p-6">
      <h2 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-3">
        Abstract
      </h2>
      <p className="text-sm leading-relaxed text-foreground/90">{displayed}</p>
      {long && (
        <button
          type="button"
          onClick={() => setExpanded((e) => !e)}
          className="mt-3 flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors"
        >
          {expanded ? (
            <>
              <ChevronUp className="h-3.5 w-3.5" />
              Show less
            </>
          ) : (
            <>
              <ChevronDown className="h-3.5 w-3.5" />
              Show full abstract
            </>
          )}
        </button>
      )}
    </section>
  );
}
