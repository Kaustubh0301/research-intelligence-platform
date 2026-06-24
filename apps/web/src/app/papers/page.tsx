import { Suspense } from "react";
import { PaperSearchClient } from "@/components/papers/PaperSearchClient";

export default function PapersPage() {
  return (
    <div>
      {/* ── Hero search header ─────────────────────────────────────────── */}
      <div className="relative w-full flex items-center justify-center overflow-hidden bg-gradient-to-b from-surface-container-low to-surface py-xl">
        {/* Decorative radial glow */}
        <div
          aria-hidden
          className="pointer-events-none absolute inset-0 flex items-center justify-center"
        >
          <div className="h-64 w-64 rounded-full bg-primary-container/10 blur-3xl" />
        </div>

        <div className="relative z-10 w-full max-w-3xl px-gutter text-center">
          <h1 className="font-headline-lg text-headline-lg text-on-surface mb-md">
            Explore Machine Learning Intelligence
          </h1>
          <p className="text-body-sm text-on-surface-variant mb-lg opacity-70">
            Try: "transformer distillation" · "scaling laws" · "long-context retrieval"
          </p>
          {/* Search bar rendered by PaperSearchClient — just a placeholder here */}
        </div>
      </div>

      {/* ── Main content ───────────────────────────────────────────────── */}
      <div className="max-w-[1400px] mx-auto px-gutter py-lg">
        <Suspense fallback={<PapersShell />}>
          <PaperSearchClient />
        </Suspense>
      </div>
    </div>
  );
}

function PapersShell() {
  return (
    <div className="flex gap-lg">
      {/* Filter sidebar skeleton */}
      <div className="w-64 flex-shrink-0 space-y-lg">
        {[80, 60, 90, 70, 85].map((w, i) => (
          <div
            key={i}
            className="h-4 rounded-full animate-pulse bg-surface-container-high"
            style={{ width: `${w}%` }}
          />
        ))}
      </div>
      {/* Results skeleton */}
      <div className="flex-1 space-y-md">
        <div className="h-9 rounded-lg animate-pulse bg-surface-container-high" />
        {[...Array(5)].map((_, i) => (
          <div key={i} className="h-36 rounded-xl animate-pulse bg-surface-container-low border border-outline-variant" />
        ))}
      </div>
    </div>
  );
}
