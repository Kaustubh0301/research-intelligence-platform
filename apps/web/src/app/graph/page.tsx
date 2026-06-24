import type { Metadata } from "next";
import { GraphPageClient } from "@/components/graph/GraphPageClient";

export const metadata: Metadata = {
  title: "Knowledge Graph — Research Intelligence Platform",
};

export default function GraphPage() {
  return <GraphPageClient />;
}
