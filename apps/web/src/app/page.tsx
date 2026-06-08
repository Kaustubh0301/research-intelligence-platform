import { api } from "@/lib/api";
import { StatCards } from "@/components/dashboard/StatCards";
import { TechniquesChart } from "@/components/dashboard/TechniquesChart";
import { ConferenceDonut } from "@/components/dashboard/ConferenceDonut";
import { TopPapersTable } from "@/components/dashboard/TopPapersTable";
import { ClusterOverview } from "@/components/dashboard/ClusterOverview";

export const revalidate = 60;

export default async function DashboardPage() {
  const stats = await api.stats();

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
