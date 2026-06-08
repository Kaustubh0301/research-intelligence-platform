import { Suspense } from "react";
import { PaperSearchClient } from "@/components/papers/PaperSearchClient";

// The search client owns all interactive state via URL params;
// this page is just the static shell + SSR boundary.
export default function PapersPage() {
  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Papers</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Browse and search 100 NeurIPS 2024 papers
        </p>
      </div>

      {/*
        Suspense is required because PaperSearchClient calls useSearchParams()
        which suspends during SSR. The fallback is shown on first load only;
        subsequent navigations keep the existing UI via keepPreviousData.
      */}
      <Suspense fallback={<PapersShell />}>
        <PaperSearchClient />
      </Suspense>
    </div>
  );
}

function PapersShell() {
  return (
    <div className="grid grid-cols-1 gap-0 md:grid-cols-[240px_1fr]">
      <div className="hidden md:block pr-6 border-r space-y-4">
        {[80, 60, 90, 70, 85].map((w, i) => (
          <div
            key={i}
            className="h-4 rounded animate-pulse bg-muted"
            style={{ width: `${w}%` }}
          />
        ))}
      </div>
      <div className="md:pl-6 space-y-3">
        <div className="h-9 rounded-md animate-pulse bg-muted" />
        {[...Array(6)].map((_, i) => (
          <div key={i} className="h-32 rounded-lg animate-pulse bg-muted" />
        ))}
      </div>
    </div>
  );
}
