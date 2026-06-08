"use client";

import { useState } from "react";
import { ChevronDown, ChevronUp, Sparkles, FlaskConical, Zap, AlertTriangle, Rocket, Compass } from "lucide-react";
import type { PaperAnalysis, ExperimentalFinding } from "@/lib/types";
import { cn } from "@/lib/utils";

// ── Collapsible section wrapper ───────────────────────────────────────────────

interface SectionProps {
  title: string;
  icon?: React.ReactNode;
  count?: number;
  children: React.ReactNode;
  defaultOpen?: boolean;
}

function CollapsibleSection({ title, icon, count, children, defaultOpen = false }: SectionProps) {
  const [open, setOpen] = useState(defaultOpen);

  return (
    <div className="border-t first:border-t-0">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center justify-between py-3 text-left transition-colors hover:text-foreground"
      >
        <span className="flex items-center gap-2 text-sm font-medium">
          {icon && <span className="text-muted-foreground">{icon}</span>}
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

// ── Bullet list (strengths, limitations, applications, directions) ────────────

function BulletList({ items }: { items: string[] }) {
  return (
    <ul className="space-y-2.5">
      {items.map((item, i) => (
        <li key={i} className="flex gap-2.5 text-sm text-muted-foreground leading-relaxed">
          <span className="mt-2 h-1.5 w-1.5 flex-shrink-0 rounded-full bg-muted-foreground/40" />
          <span>{item}</span>
        </li>
      ))}
    </ul>
  );
}

// ── Multi-paragraph prose block (summary, methodology) ───────────────────────

function ProseBlock({ text }: { text: string }) {
  // The text arrives as space-joined paragraphs from the parser.
  // Re-split on sentence-boundary heuristic: ". " followed by a capital
  // letter, when the run is long enough to warrant a break. We group
  // every ~3–4 sentences into a visual paragraph.
  const sentences = text
    .split(/(?<=\.) (?=[A-Z])/)
    .map((s) => s.trim())
    .filter(Boolean);

  // Group into paragraphs of ~3 sentences
  const paras: string[] = [];
  const PER = 3;
  for (let i = 0; i < sentences.length; i += PER) {
    paras.push(sentences.slice(i, i + PER).join(" "));
  }

  if (paras.length <= 1) {
    return <p className="text-sm leading-relaxed text-foreground/80">{text}</p>;
  }

  return (
    <div className="space-y-3">
      {paras.map((p, i) => (
        <p key={i} className="text-sm leading-relaxed text-foreground/80">
          {p}
        </p>
      ))}
    </div>
  );
}

// ── Experimental findings table ───────────────────────────────────────────────

function FindingsTable({ findings }: { findings: ExperimentalFinding[] }) {
  if (findings.length === 0) return null;

  return (
    <div className="overflow-x-auto rounded-lg border border-border/60">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border/60 bg-muted/40">
            <th className="px-3 py-2 text-left font-medium text-muted-foreground text-xs uppercase tracking-wide">
              Benchmark
            </th>
            <th className="px-3 py-2 text-left font-medium text-muted-foreground text-xs uppercase tracking-wide">
              Metric
            </th>
            <th className="px-3 py-2 text-left font-medium text-muted-foreground text-xs uppercase tracking-wide">
              Result
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border/40">
          {findings.map((f, i) => (
            <tr key={i} className="hover:bg-muted/20 transition-colors">
              <td className="px-3 py-2 font-medium text-foreground/90 whitespace-nowrap">
                {f.benchmark}
              </td>
              <td className="px-3 py-2 text-muted-foreground whitespace-nowrap">
                {f.metric}
              </td>
              <td className="px-3 py-2 text-muted-foreground">
                {f.scores}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ── Prose section (methodology) ───────────────────────────────────────────────

function ProseSection({
  title,
  icon,
  text,
  defaultOpen = false,
}: {
  title: string;
  icon?: React.ReactNode;
  text: string;
  defaultOpen?: boolean;
}) {
  return (
    <CollapsibleSection title={title} icon={icon} defaultOpen={defaultOpen}>
      <ProseBlock text={text} />
    </CollapsibleSection>
  );
}

// ── Main panel ────────────────────────────────────────────────────────────────

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

  // Determine if this is a V2 analysis (has at least one populated V2 field)
  const isV2 = !!(
    analysis.methodology ||
    analysis.experimental_findings.length > 0 ||
    analysis.strengths.length > 0 ||
    analysis.practical_applications.length > 0 ||
    analysis.future_research_directions.length > 0
  );

  // For V1-only papers, fall back to legacy fields if V2 are empty
  const limitations = analysis.limitations.length > 0
    ? analysis.limitations
    : [];

  return (
    <section className="rounded-xl border bg-card p-5">
      <div className="flex items-center gap-2 mb-1">
        <Sparkles className="h-4 w-4 text-muted-foreground" />
        <h2 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          AI Analysis
        </h2>
        {isV2 && (
          <span className="rounded-full bg-primary/10 px-2 py-0.5 text-xs font-medium text-primary">
            V2
          </span>
        )}
        {analysis.model && (
          <span className="ml-auto text-xs text-muted-foreground/50">
            {analysis.model}
          </span>
        )}
      </div>

      <div>
        {/* ── 1. Executive Summary — always open, always rendered as prose ── */}
        {analysis.summary && (
          <div className="py-4 border-b">
            <ProseBlock text={analysis.summary} />
          </div>
        )}

        {/* ── 2. Methodology ── */}
        {analysis.methodology && (
          <ProseSection
            title="Methodology"
            icon={<FlaskConical className="h-3.5 w-3.5" />}
            text={analysis.methodology}
            defaultOpen={false}
          />
        )}

        {/* ── 3. Experimental Findings ── */}
        {analysis.experimental_findings.length > 0 && (
          <CollapsibleSection
            title="Experimental Findings"
            icon={<Zap className="h-3.5 w-3.5" />}
            count={analysis.experimental_findings.length}
          >
            <FindingsTable findings={analysis.experimental_findings} />
          </CollapsibleSection>
        )}

        {/* ── 4. Strengths (V2) or Advantages (V1 fallback) ── */}
        {analysis.strengths.length > 0 && (
          <CollapsibleSection
            title="Strengths"
            count={analysis.strengths.length}
          >
            <BulletList items={analysis.strengths} />
          </CollapsibleSection>
        )}
        {analysis.strengths.length === 0 && analysis.advantages.length > 0 && (
          <CollapsibleSection
            title="Advantages"
            count={analysis.advantages.length}
          >
            <BulletList items={analysis.advantages} />
          </CollapsibleSection>
        )}

        {/* ── 5. Limitations ── */}
        {limitations.length > 0 && (
          <CollapsibleSection
            title="Limitations"
            icon={<AlertTriangle className="h-3.5 w-3.5" />}
            count={limitations.length}
          >
            <BulletList items={limitations} />
          </CollapsibleSection>
        )}

        {/* ── 6. Practical Applications (V2) or Use Cases (V1 fallback) ── */}
        {analysis.practical_applications.length > 0 && (
          <CollapsibleSection
            title="Practical Applications"
            icon={<Rocket className="h-3.5 w-3.5" />}
            count={analysis.practical_applications.length}
          >
            <BulletList items={analysis.practical_applications} />
          </CollapsibleSection>
        )}
        {analysis.practical_applications.length === 0 && analysis.use_cases.length > 0 && (
          <CollapsibleSection
            title="Use Cases"
            count={analysis.use_cases.length}
          >
            <BulletList items={analysis.use_cases} />
          </CollapsibleSection>
        )}

        {/* ── 7. Future Research Directions (V2) or Future Work (V1 fallback) ── */}
        {analysis.future_research_directions.length > 0 && (
          <CollapsibleSection
            title="Future Research Directions"
            icon={<Compass className="h-3.5 w-3.5" />}
            count={analysis.future_research_directions.length}
          >
            <BulletList items={analysis.future_research_directions} />
          </CollapsibleSection>
        )}
        {analysis.future_research_directions.length === 0 && analysis.future_work.length > 0 && (
          <CollapsibleSection
            title="Future Work"
            count={analysis.future_work.length}
          >
            <BulletList items={analysis.future_work} />
          </CollapsibleSection>
        )}
      </div>
    </section>
  );
}
