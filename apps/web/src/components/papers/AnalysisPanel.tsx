"use client";

import { useState } from "react";
import { ChevronDown, ChevronUp, Sparkles } from "lucide-react";
import type { PaperAnalysis } from "@/lib/types";
import { cn } from "@/lib/utils";

interface SectionProps {
  title: string;
  count?: number;
  children: React.ReactNode;
  defaultOpen?: boolean;
}

function CollapsibleSection({ title, count, children, defaultOpen = false }: SectionProps) {
  const [open, setOpen] = useState(defaultOpen);

  return (
    <div className="border-t first:border-t-0">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center justify-between py-3 text-left transition-colors hover:text-foreground"
      >
        <span className="flex items-center gap-2 text-sm font-medium">
          {title}
          {count !== undefined && count > 0 && (
            <span className="rounded-full bg-secondary px-1.5 py-0.5 text-xs font-normal text-muted-foreground">
              {count}
            </span>
          )}
        </span>
        {open ? (
          <ChevronUp className="h-4 w-4 flex-shrink-0 text-muted-foreground" />
        ) : (
          <ChevronDown className="h-4 w-4 flex-shrink-0 text-muted-foreground" />
        )}
      </button>

      <div className={cn("overflow-hidden", open ? "pb-4" : "hidden")}>
        {children}
      </div>
    </div>
  );
}

function BulletList({ items }: { items: string[] }) {
  return (
    <ul className="space-y-1.5">
      {items.map((item, i) => (
        <li key={i} className="flex gap-2 text-sm text-muted-foreground leading-relaxed">
          <span className="mt-1.5 h-1.5 w-1.5 flex-shrink-0 rounded-full bg-muted-foreground/40" />
          <span>{item}</span>
        </li>
      ))}
    </ul>
  );
}

interface Props {
  analysis: PaperAnalysis | null;
}

export function AnalysisPanel({ analysis }: Props) {
  if (!analysis) {
    return (
      <section className="rounded-xl border bg-card p-5">
        <div className="flex items-center gap-2 mb-3">
          <Sparkles className="h-4 w-4 text-muted-foreground" />
          <h2 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            AI Analysis
          </h2>
        </div>
        <p className="text-sm text-muted-foreground">
          Analysis not available for this paper.
        </p>
      </section>
    );
  }

  return (
    <section className="rounded-xl border bg-card p-5">
      <div className="flex items-center gap-2 mb-1">
        <Sparkles className="h-4 w-4 text-muted-foreground" />
        <h2 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          AI Analysis
        </h2>
        {analysis.model && (
          <span className="ml-auto text-xs text-muted-foreground/50">
            {analysis.model}
          </span>
        )}
      </div>

      <div>
        {/* Summary is always open and styled differently */}
        {analysis.summary && (
          <div className="py-4 border-b">
            <p className="text-sm leading-relaxed text-foreground/80">
              {analysis.summary}
            </p>
          </div>
        )}

        {analysis.advantages.length > 0 && (
          <CollapsibleSection title="Advantages" count={analysis.advantages.length}>
            <BulletList items={analysis.advantages} />
          </CollapsibleSection>
        )}

        {analysis.limitations.length > 0 && (
          <CollapsibleSection title="Limitations" count={analysis.limitations.length}>
            <BulletList items={analysis.limitations} />
          </CollapsibleSection>
        )}

        {analysis.future_work.length > 0 && (
          <CollapsibleSection title="Future Work" count={analysis.future_work.length}>
            <BulletList items={analysis.future_work} />
          </CollapsibleSection>
        )}

        {analysis.use_cases.length > 0 && (
          <CollapsibleSection title="Use Cases" count={analysis.use_cases.length}>
            <BulletList items={analysis.use_cases} />
          </CollapsibleSection>
        )}
      </div>
    </section>
  );
}
