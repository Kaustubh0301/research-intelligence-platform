import { Skeleton } from "@/components/ui/skeleton";

export default function Loading() {
  return (
    <div className="space-y-6 pb-12">
      {/* Back nav */}
      <Skeleton className="h-5 w-24" />

      {/* Hero card */}
      <div className="rounded-xl border bg-card p-6 space-y-4">
        <Skeleton className="h-8 w-full" />
        <Skeleton className="h-8 w-4/5" />
        <Skeleton className="h-4 w-2/3" />
        <div className="flex gap-2">
          <Skeleton className="h-6 w-24 rounded-full" />
          <Skeleton className="h-6 w-16 rounded-full" />
          <Skeleton className="h-6 w-20 rounded-full" />
        </div>
        <div className="flex gap-2 pt-1">
          <Skeleton className="h-8 w-16 rounded-md" />
          <Skeleton className="h-8 w-24 rounded-md" />
          <Skeleton className="h-8 w-20 rounded-md" />
        </div>
      </div>

      {/* Abstract card */}
      <div className="rounded-xl border bg-card p-6 space-y-2">
        <Skeleton className="h-3 w-16" />
        <Skeleton className="h-4 w-full" />
        <Skeleton className="h-4 w-full" />
        <Skeleton className="h-4 w-5/6" />
        <Skeleton className="h-4 w-4/5" />
      </div>

      {/* Two-column body */}
      <div className="grid gap-6 lg:grid-cols-[360px_1fr]">
        {/* Left column */}
        <div className="space-y-5">
          {/* Metrics card */}
          <div className="rounded-xl border bg-card p-5 space-y-3">
            <Skeleton className="h-3 w-16" />
            {[...Array(4)].map((_, i) => (
              <div key={i} className="flex justify-between py-1">
                <Skeleton className="h-4 w-28" />
                <Skeleton className="h-4 w-16" />
              </div>
            ))}
            <Skeleton className="h-2 w-full rounded-full mt-2" />
          </div>

          {/* Techniques card */}
          <div className="rounded-xl border bg-card p-5 space-y-3">
            <Skeleton className="h-3 w-20" />
            <div className="flex flex-wrap gap-1.5">
              {[...Array(5)].map((_, i) => (
                <Skeleton key={i} className="h-6 w-20 rounded-full" />
              ))}
            </div>
            <div className="flex flex-wrap gap-1.5">
              {[...Array(7)].map((_, i) => (
                <Skeleton key={i} className="h-6 w-16 rounded-full" />
              ))}
            </div>
          </div>
        </div>

        {/* Right column */}
        <div className="space-y-6">
          {/* Analysis card */}
          <div className="rounded-xl border bg-card p-5 space-y-3">
            <Skeleton className="h-3 w-24" />
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-4/5" />
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-3/5" />
            <div className="space-y-1 pt-2">
              {[...Array(3)].map((_, i) => (
                <Skeleton key={i} className="h-10 w-full rounded-md" />
              ))}
            </div>
          </div>

          {/* Related papers card */}
          <div className="rounded-xl border bg-card p-5 space-y-3">
            <Skeleton className="h-3 w-28" />
            {[...Array(5)].map((_, i) => (
              <div key={i} className="rounded-lg border p-3 space-y-2">
                <div className="flex gap-2">
                  <Skeleton className="h-4 flex-1" />
                  <Skeleton className="h-4 w-16 flex-shrink-0" />
                </div>
                <div className="flex gap-2">
                  <Skeleton className="h-5 w-16 rounded-full" />
                  <Skeleton className="h-5 w-12 rounded-full" />
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
