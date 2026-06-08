import Link from "next/link";
import type { TopPaper } from "@/lib/types";
import { CLUSTER_COLOURS } from "@/lib/constants";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

interface Props {
  papers: TopPaper[];
}

export function TopPapersTable({ papers }: Props) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Top Papers by Citation</CardTitle>
      </CardHeader>
      <CardContent className="p-0">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b bg-muted/50">
                <th className="px-4 py-3 text-left font-medium text-muted-foreground w-10">#</th>
                <th className="px-4 py-3 text-left font-medium text-muted-foreground">Title</th>
                <th className="px-4 py-3 text-left font-medium text-muted-foreground">Venue</th>
                <th className="px-4 py-3 text-right font-medium text-muted-foreground">Citations</th>
                <th className="px-4 py-3 text-left font-medium text-muted-foreground">Cluster</th>
              </tr>
            </thead>
            <tbody>
              {papers.map((p, i) => (
                <tr key={p.id} className="border-b last:border-0 hover:bg-muted/30">
                  <td className="px-4 py-3 text-muted-foreground">{i + 1}</td>
                  <td className="px-4 py-3 max-w-xs">
                    <Link
                      href={`/papers/${p.id}`}
                      className="hover:underline font-medium line-clamp-2"
                    >
                      {p.title}
                    </Link>
                  </td>
                  <td className="px-4 py-3 whitespace-nowrap text-muted-foreground">
                    {p.conference && p.year ? `${p.conference} ${p.year}` : "—"}
                  </td>
                  <td className="px-4 py-3 text-right font-mono">
                    {p.citation_count.toLocaleString()}
                  </td>
                  <td className="px-4 py-3">
                    {p.cluster_id !== null ? (
                      <span
                        className="inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium text-white"
                        style={{
                          backgroundColor:
                            CLUSTER_COLOURS[p.cluster_id] ?? "#6b7280",
                        }}
                      >
                        {p.cluster_id}
                      </span>
                    ) : (
                      <Badge variant="secondary">—</Badge>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </CardContent>
    </Card>
  );
}
