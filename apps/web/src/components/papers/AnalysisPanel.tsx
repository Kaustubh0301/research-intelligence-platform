"use client";

import { useState, useRef, useCallback } from "react";
import {
  Sparkles,
  FlaskConical,
  Zap,
  AlertTriangle,
  Rocket,
  Compass,
  Clock,
  Lock,
} from "lucide-react";
import type { PaperAnalysis, ExperimentalFinding } from "@/lib/types";
import { cn } from "@/lib/utils";

// ── Reading time ──────────────────────────────────────────────────────────────

function wordCount(text: string | null | undefined): number {
  if (!text) return 0;
  return text.split(/\s+/).filter(Boolean).length;
}

function readingMinutes(analysis: PaperAnalysis): number {
  const words = wordCount(analysis.summary) + wordCount(analysis.methodology);
  return Math.max(1, Math.round(words / 200));
}

// ── Bullet list ───────────────────────────────────────────────────────────────

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

// ── Prose block ───────────────────────────────────────────────────────────────

function ProseBlock({ text }: { text: string }) {
  const sentences = text
    .split(/(?<=\.) (?=[A-Z])/)
    .map((s) => s.trim())
    .filter(Boolean);

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

// ── Unavailable section placeholder ──────────────────────────────────────────

function UnavailableSection({
  title,
  icon,
}: {
  title: string;
  icon?: React.ReactNode;
}) {
  return (
    <div className="border-t py-3 flex items-center gap-2 opacity-50">
      {icon && <span className="text-muted-foreground">{icon}</span>}
      <span className="text-sm text-muted-foreground">{title}</span>
      <span className="ml-auto flex items-center gap-1 text-xs text-muted-foreground/70">
        <Lock className="h-3 w-3" />
        V2 only
      </span>
    </div>
  );
}

// ── Analysis section (always-visible, scrollable target) ─────────────────────

interface SectionProps {
  id: string;
  title: string;
  icon?: React.ReactNode;
  count?: number;
  children: React.ReactNode;
  open: boolean;
  onToggle: () => void;
}

function AnalysisSection({ id, title, icon, count, children, open, onToggle }: SectionProps) {
  return (
    // scroll-mt accounts for sticky header (h-14 = 56px) + analysis nav (~48px) + small gap
    <div id={id} className="border-t first:border-t-0 scroll-mt-28">
      <button
        type="button"
        onClick={onToggle}
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
        <svg
          className={cn(
            "h-4 w-4 flex-shrink-0 text-muted-foreground transition-transform",
            open && "rotate-180"
          )}
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={2}
        >
          <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      <div className={cn("overflow-hidden", open ? "pb-4" : "hidden")}>
        {children}
      </div>
    </div>
  );
}

// ── Analysis nav bar ──────────────────────────────────────────────────────────

interface NavItem {
  id: string;
  label: string;
  available: boolean;
}

function AnalysisNav({
  items,
  onNavigate,
}: {
  items: NavItem[];
  onNavigate: (id: string) => void;
}) {
  return (
    // sticky top-14 = below the app header (h-14 = 56px)
    <div className="sticky top-14 z-10 -mx-5 px-5 bg-card border-b border-border/60 overflow-x-auto">
      <nav className="flex gap-0.5 py-1.5 min-w-max">
        {items.map((item) => (
          <button
            key={item.id}
            type="button"
            disabled={!item.available}
            onClick={() => item.available && onNavigate(item.id)}
            className={cn(
              "px-3 py-1.5 rounded-md text-xs font-medium transition-colors whitespace-nowrap",
              item.available
                ? "text-muted-foreground hover:text-foreground hover:bg-muted/60 cursor-pointer"
                : "text-muted-foreground/30 cursor-not-allowed"
            )}
          >
            {item.label}
          </button>
        ))}
      </nav>
    </div>
  );
}

// ── Main panel ────────────────────────────────────────────────────────────────

interface Props {
  analysis: PaperAnalysis | null;
}

const SECTION_IDS = {
  summary: "analysis-summary",
  methodology: "analysis-methodology",
  findings: "analysis-findings",
  strengths: "analysis-strengths",
  limitations: "analysis-limitations",
  applications: "analysis-applications",
  future: "analysis-future",
} as const;

export function AnalysisPanel({ analysis }: Props) {
  // Section open states (all default open for easy nav)
  const [open, setOpen] = useState({
    methodology: true,
    findings: true,
    strengths: true,
    limitations: true,
    applications: true,
    future: true,
  });

  const toggle = useCallback((key: keyof typeof open) => {
    setOpen((s) => ({ ...s, [key]: !s[key] }));
  }, []);

  const scrollToSection = useCallback(
    (id: string, key?: keyof typeof open) => {
      // Open the section if it's closed
      if (key) {
        setOpen((s) => ({ ...s, [key]: true }));
      }
      // Defer scroll until after state update re-renders the section
      setTimeout(() => {
        document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" });
      }, 50);
    },
    []
  );

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

  const isV2 = !!(
    analysis.methodology ||
    analysis.experimental_findings.length > 0 ||
    analysis.strengths.length > 0 ||
    analysis.practical_applications.length > 0 ||
    analysis.future_research_directions.length > 0
  );

  // Resolve display fields (V2 preferred, V1 fallback)
  const strengthsItems = analysis.strengths.length > 0 ? analysis.strengths : analysis.advantages;
  const applicationsItems =
    analysis.practical_applications.length > 0
      ? analysis.practical_applications
      : analysis.use_cases;
  const futureItems =
    analysis.future_research_directions.length > 0
      ? analysis.future_research_directions
      : analysis.future_work;
  const limitationsItems = analysis.limitations;

  // Reading time (summary + methodology prose)
  const mins = readingMinutes(analysis);

  // Nav items — available only if there's content
  const navItems: NavItem[] = [
    { id: SECTION_IDS.summary, label: "Summary", available: !!analysis.summary },
    { id: SECTION_IDS.methodology, label: "Methodology", available: !!analysis.methodology },
    {
      id: SECTION_IDS.findings,
      label: "Findings",
      available: analysis.experimental_findings.length > 0,
    },
    { id: SECTION_IDS.strengths, label: "Strengths", available: strengthsItems.length > 0 },
    { id: SECTION_IDS.limitations, label: "Limitations", available: limitationsItems.length > 0 },
    {
      id: SECTION_IDS.applications,
      label: "Applications",
      available: applicationsItems.length > 0,
    },
    { id: SECTION_IDS.future, label: "Future Directions", available: futureItems.length > 0 },
  ];

  return (
    <section className="rounded-xl border bg-card overflow-hidden">
      {/* ── Panel header ── */}
      <div className="flex items-center gap-2 px-5 pt-5 pb-3">
        <Sparkles className="h-4 w-4 text-muted-foreground" />
        <h2 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          AI Analysis
        </h2>
        {isV2 && (
          <span className="rounded-full bg-primary/10 px-2 py-0.5 text-xs font-medium text-primary">
            V2
          </span>
        )}
        <span className="flex items-center gap-1 ml-auto text-xs text-muted-foreground/60">
          <Clock className="h-3 w-3" />
          ~{mins} min read
        </span>
        {analysis.model && (
          <span className="text-xs text-muted-foreground/40">{analysis.model}</span>
        )}
      </div>

      {/* ── Sticky section nav ── */}
      <AnalysisNav
        items={navItems}
        onNavigate={(id) => {
          const keyMap: Record<string, keyof typeof open> = {
            [SECTION_IDS.methodology]: "methodology",
            [SECTION_IDS.findings]: "findings",
            [SECTION_IDS.strengths]: "strengths",
            [SECTION_IDS.limitations]: "limitations",
            [SECTION_IDS.applications]: "applications",
            [SECTION_IDS.future]: "future",
          };
          scrollToSection(id, keyMap[id]);
        }}
      />

      {/* ── Sections ── */}
      <div className="px-5">
        {/* 1. Executive Summary — always rendered as prose, no toggle */}
        {analysis.summary ? (
          <div id={SECTION_IDS.summary} className="py-4 border-b scroll-mt-28">
            <ProseBlock text={analysis.summary} />
          </div>
        ) : (
          <div id={SECTION_IDS.summary} className="scroll-mt-28">
            <UnavailableSection title="Summary" />
          </div>
        )}

        {/* 2. Methodology */}
        {analysis.methodology ? (
          <AnalysisSection
            id={SECTION_IDS.methodology}
            title="Methodology"
            icon={<FlaskConical className="h-3.5 w-3.5" />}
            open={open.methodology}
            onToggle={() => toggle("methodology")}
          >
            <ProseBlock text={analysis.methodology} />
          </AnalysisSection>
        ) : (
          <div id={SECTION_IDS.methodology} className="scroll-mt-28">
            <UnavailableSection
              title="Methodology"
              icon={<FlaskConical className="h-3.5 w-3.5" />}
            />
          </div>
        )}

        {/* 3. Experimental Findings */}
        {analysis.experimental_findings.length > 0 ? (
          <AnalysisSection
            id={SECTION_IDS.findings}
            title="Experimental Findings"
            icon={<Zap className="h-3.5 w-3.5" />}
            count={analysis.experimental_findings.length}
            open={open.findings}
            onToggle={() => toggle("findings")}
          >
            <FindingsTable findings={analysis.experimental_findings} />
          </AnalysisSection>
        ) : (
          <div id={SECTION_IDS.findings} className="scroll-mt-28">
            <UnavailableSection
              title="Experimental Findings"
              icon={<Zap className="h-3.5 w-3.5" />}
            />
          </div>
        )}

        {/* 4. Strengths */}
        {strengthsItems.length > 0 ? (
          <AnalysisSection
            id={SECTION_IDS.strengths}
            title={analysis.strengths.length > 0 ? "Strengths" : "Advantages"}
            open={open.strengths}
            onToggle={() => toggle("strengths")}
            count={strengthsItems.length}
          >
            <BulletList items={strengthsItems} />
          </AnalysisSection>
        ) : (
          <div id={SECTION_IDS.strengths} className="scroll-mt-28">
            <UnavailableSection title="Strengths" />
          </div>
        )}

        {/* 5. Limitations */}
        {limitationsItems.length > 0 ? (
          <AnalysisSection
            id={SECTION_IDS.limitations}
            title="Limitations"
            icon={<AlertTriangle className="h-3.5 w-3.5" />}
            count={limitationsItems.length}
            open={open.limitations}
            onToggle={() => toggle("limitations")}
          >
            <BulletList items={limitationsItems} />
          </AnalysisSection>
        ) : (
          <div id={SECTION_IDS.limitations} className="scroll-mt-28">
            <UnavailableSection
              title="Limitations"
              icon={<AlertTriangle className="h-3.5 w-3.5" />}
            />
          </div>
        )}

        {/* 6. Practical Applications */}
        {applicationsItems.length > 0 ? (
          <AnalysisSection
            id={SECTION_IDS.applications}
            title={analysis.practical_applications.length > 0 ? "Practical Applications" : "Use Cases"}
            icon={<Rocket className="h-3.5 w-3.5" />}
            count={applicationsItems.length}
            open={open.applications}
            onToggle={() => toggle("applications")}
          >
            <BulletList items={applicationsItems} />
          </AnalysisSection>
        ) : (
          <div id={SECTION_IDS.applications} className="scroll-mt-28">
            <UnavailableSection
              title="Practical Applications"
              icon={<Rocket className="h-3.5 w-3.5" />}
            />
          </div>
        )}

        {/* 7. Future Research Directions */}
        {futureItems.length > 0 ? (
          <AnalysisSection
            id={SECTION_IDS.future}
            title={
              analysis.future_research_directions.length > 0
                ? "Future Research Directions"
                : "Future Work"
            }
            icon={<Compass className="h-3.5 w-3.5" />}
            count={futureItems.length}
            open={open.future}
            onToggle={() => toggle("future")}
          >
            <BulletList items={futureItems} />
          </AnalysisSection>
        ) : (
          <div id={SECTION_IDS.future} className="scroll-mt-28">
            <UnavailableSection
              title="Future Research Directions"
              icon={<Compass className="h-3.5 w-3.5" />}
            />
          </div>
        )}
      </div>
    </section>
  );
}
