import { api } from "@/lib/api";
import { FEATURES } from "@/lib/features";
import { StatCards } from "@/components/dashboard/StatCards";
import { TechniquesChart } from "@/components/dashboard/TechniquesChart";
import { ConferenceDonut } from "@/components/dashboard/ConferenceDonut";
import { TopPapersTable } from "@/components/dashboard/TopPapersTable";
import { ClusterOverview } from "@/components/dashboard/ClusterOverview";

export const revalidate = 60;

export default async function DashboardPage() {
  let stats;
  try {
    stats = await api.stats();
  } catch {
    return (
      <div className="flex flex-col items-center justify-center min-h-[400px] gap-3 text-center px-gutter">
        <span className="material-symbols-outlined text-[48px] text-outline">cloud_off</span>
        <h2 className="text-headline-md font-headline-md text-on-surface">Backend unavailable</h2>
        <p className="text-body-sm text-on-surface-variant max-w-sm">
          The API server is not responding. Start it with:
        </p>
        <pre className="rounded-lg bg-surface-container px-lg py-md text-code font-code text-im-primary border border-outline-variant text-left">
          uvicorn api.main:app --reload --port 8000
        </pre>
      </div>
    );
  }

  return (
    <div className="max-w-[1400px] mx-auto px-gutter py-lg space-y-lg">
      {/* Page header */}
      <div>
        <h1 className="text-headline-lg font-headline-lg text-on-surface">Dashboard</h1>
        <p className="text-body-sm text-on-surface-variant mt-1">
          {stats.total_papers} papers indexed
          {FEATURES.GRAPH && ` · ${stats.total_edges.toLocaleString()} graph edges`}
        </p>
      </div>

      {/* Stat cards */}
      <StatCards
        total_papers={stats.total_papers}
        total_edges={stats.total_edges}
        total_techniques={stats.total_techniques}
        total_clusters={stats.total_clusters}
      />

      {/* Charts row */}
      <div className="grid gap-lg md:grid-cols-2">
        <TechniquesChart techniques={stats.top_techniques} />
        <ConferenceDonut conferences={stats.conferences} />
      </div>

      {/* Top papers table */}
      <TopPapersTable papers={stats.top_papers} />

      {/* Cluster overview (graph feature) */}
      {FEATURES.GRAPH && <ClusterOverview clusters={stats.clusters} />}
    </div>
  );
}
