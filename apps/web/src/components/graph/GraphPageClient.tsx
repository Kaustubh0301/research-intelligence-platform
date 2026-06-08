"use client";

import dynamic from "next/dynamic";
import { GraphProvider } from "./GraphContext";
import { GraphControls } from "./GraphControls";
import { Skeleton } from "@/components/ui/skeleton";

const GraphCanvas = dynamic(
  () => import("./GraphCanvas").then((m) => ({ default: m.GraphCanvas })),
  {
    ssr: false,
    loading: () => (
      <div className="flex-1 bg-gray-950">
        <Skeleton className="w-full h-full rounded-none" />
      </div>
    ),
  }
);

export function GraphPageClient() {
  return (
    <GraphProvider>
      <div className="flex h-[calc(100vh-3.5rem)] -mx-4 -my-6 overflow-hidden">
        <GraphControls />
        <GraphCanvas />
      </div>
    </GraphProvider>
  );
}
