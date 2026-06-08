import type { Metadata } from "next";
import { notFound } from "next/navigation";
import Link from "next/link";
import { ChevronLeft } from "lucide-react";
import { api } from "@/lib/api";
import { PaperHero } from "@/components/papers/PaperHero";
import { AbstractCard } from "@/components/papers/AbstractCard";
import { MetricsCard } from "@/components/papers/MetricsCard";
import { TechniqueList } from "@/components/papers/TechniqueList";
import { AnalysisPanel } from "@/components/papers/AnalysisPanel";
import { RelatedPapers } from "@/components/papers/RelatedPapers";
import { TagSection } from "@/components/papers/TagSection";

interface Props {
  params: Promise<{ id: string }>;
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { id } = await params;
  try {
    const paper = await api.paper(id);
    return {
      title: `${paper.title} — Research Intelligence`,
      description: paper.abstract?.slice(0, 160) ?? undefined,
    };
  } catch {
    return { title: "Paper — Research Intelligence" };
  }
}

export default async function PaperPage({ params }: Props) {
  const { id } = await params;

  let paper, relatedData;
  try {
    [paper, relatedData] = await Promise.all([
      api.paper(id),
      api.paperRelated(id, 8),
    ]);
  } catch {
    notFound();
  }

  return (
    <div className="space-y-6 pb-12">
      {/* ── Breadcrumb ─────────────────────────────────────────────────── */}
      <Link
        href="/papers"
        className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground transition-colors"
      >
        <ChevronLeft className="h-4 w-4" />
        Papers
      </Link>

      {/* ── Hero: title · authors · badges · external links ───────────── */}
      <PaperHero paper={paper} />

      {/* ── Abstract ──────────────────────────────────────────────────── */}
      {paper.abstract && <AbstractCard abstract={paper.abstract} />}

      {/* ── Two-column body ───────────────────────────────────────────── */}
      <div className="grid gap-6 lg:grid-cols-[360px_1fr]">

        {/* Left column: metrics + techniques + tags */}
        <div className="space-y-5">
          <MetricsCard paper={paper} />

          <TechniqueList techniques={paper.techniques} />

          {paper.categories.length > 0 && (
            <TagSection
              title="Research Areas"
              tags={paper.categories.map((c) => c.name)}
            />
          )}

          {paper.datasets.length > 0 && (
            <TagSection
              title="Datasets"
              tags={paper.datasets.map((d) => d.name)}
            />
          )}

          {paper.methodologies.length > 0 && (
            <TagSection
              title="Methodologies"
              tags={paper.methodologies.map((m) => m.name)}
            />
          )}
        </div>

        {/* Right column: analysis + related */}
        <div className="space-y-6">
          <AnalysisPanel analysis={paper.analysis} />
          <RelatedPapers related={relatedData.related} />
        </div>
      </div>
    </div>
  );
}
