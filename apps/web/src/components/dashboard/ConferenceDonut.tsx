"use client";

import {
  PieChart,
  Pie,
  Cell,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import type { ConferenceStat } from "@/lib/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

const COLOURS = ["#4648d4", "#6063ee", "#c0c1ff", "#767586", "#bec6e0"];

interface Props {
  conferences: ConferenceStat[];
}

export function ConferenceDonut({ conferences }: Props) {
  const data = conferences.map((c) => ({
    name: `${c.short_name} ${c.year}`,
    value: c.count,
  }));

  return (
    <Card>
      <CardHeader>
        <CardTitle>Corpus by Conference</CardTitle>
      </CardHeader>
      <CardContent>
        <ResponsiveContainer width="100%" height={320}>
          <PieChart>
            <Pie
              data={data}
              cx="50%"
              cy="50%"
              innerRadius={70}
              outerRadius={110}
              dataKey="value"
              label={({ name, value }) => `${name}: ${value}`}
              labelLine={false}
            >
              {data.map((_, i) => (
                <Cell key={i} fill={COLOURS[i % COLOURS.length]} />
              ))}
            </Pie>
            <Tooltip formatter={(v: number) => [v, "papers"]} />
            <Legend />
          </PieChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}
