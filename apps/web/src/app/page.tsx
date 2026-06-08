import { api } from "@/lib/api";
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
      <div className="flex flex-col items-center justify-center min-h-[400px] gap-3 text-center">
        <div className="text-4xl">⚠️</div>
        <h2 className="text-lg font-semibold">Backend unavailable</h2>
        <p className="text-sm text-muted-foreground max-w-sm">
          The API server is not responding. Start it with:
        </p>
        <pre className="rounded-md bg-muted px-4 py-2 text-xs text-left">
          uvicorn api.main:app --reload --port 8000
        </pre>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Dashboard</h1>
        <p className="text-muted-foreground text-sm mt-1">
          NeurIPS 2024 · {stats.total_papers} papers · {stats.total_edges.toLocaleString()} graph edges
        </p>
      </div>

      <StatCards
        total_papers={stats.total_papers}
        total_edges={stats.total_edges}
        total_techniques={stats.total_techniques}
        total_clusters={stats.total_clusters}
      />

      <div className="grid gap-6 md:grid-cols-2">
        <TechniquesChart techniques={stats.top_techniques} />
        <ConferenceDonut conferences={stats.conferences} />
      </div>

      <TopPapersTable papers={stats.top_papers} />

      <ClusterOverview clusters={stats.clusters} />
    </div>
  );
}
