"use client";

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from "recharts";
import type { TechniqueStat } from "@/lib/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

interface Props {
  techniques: TechniqueStat[];
}

export function TechniquesChart({ techniques }: Props) {
  const data = techniques.slice(0, 12).map((t) => ({
    name:
      t.canonical_name.length > 30
        ? t.canonical_name.slice(0, 28) + "…"
        : t.canonical_name,
    papers: t.paper_count,
  }));

  return (
    <Card>
      <CardHeader>
        <CardTitle>Top Techniques by Paper Count</CardTitle>
      </CardHeader>
      <CardContent>
        <ResponsiveContainer width="100%" height={320}>
          <BarChart
            data={data}
            layout="vertical"
            margin={{ left: 16, right: 16, top: 4, bottom: 4 }}
          >
            <XAxis type="number" tick={{ fontSize: 11 }} />
            <YAxis
              type="category"
              dataKey="name"
              width={180}
              tick={{ fontSize: 11 }}
            />
            <Tooltip
              formatter={(v: number) => [v, "papers"]}
              contentStyle={{ fontSize: 12 }}
            />
            <Bar dataKey="papers" radius={[0, 4, 4, 0]}>
              {data.map((_, i) => (
                <Cell key={i} fill="#4648d4" fillOpacity={1 - i * 0.06} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}
