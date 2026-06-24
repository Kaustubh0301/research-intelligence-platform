"use client";

import dynamic from "next/dynamic";
import { useState } from "react";
import { GraphProvider } from "./GraphContext";
import { GraphControls } from "./GraphControls";
import { Skeleton } from "@/components/ui/skeleton";
import { SlidersHorizontal, X } from "lucide-react";

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
  const [sidebarOpen, setSidebarOpen] = useState(false);

  return (
    <GraphProvider>
      <div className="flex h-[calc(100vh-3.5rem)] -mx-4 -my-6 overflow-hidden relative">
        {/* Mobile sidebar overlay */}
        {sidebarOpen && (
          <div
            className="fixed inset-0 z-30 bg-black/40 md:hidden"
            onClick={() => setSidebarOpen(false)}
          />
        )}

        {/* Sidebar — always visible on md+, drawer on mobile */}
        <div className={`
          absolute md:relative z-40 md:z-auto h-full
          transition-transform duration-200
          ${sidebarOpen ? "translate-x-0" : "-translate-x-full md:translate-x-0"}
        `}>
          <GraphControls onClose={() => setSidebarOpen(false)} />
        </div>

        {/* Canvas fills remaining space */}
        <GraphCanvas />

        {/* Mobile toggle button */}
        <button
          className="absolute bottom-4 left-4 z-20 md:hidden flex items-center gap-2 rounded-full bg-background border shadow-lg px-4 py-2 text-sm font-medium"
          onClick={() => setSidebarOpen((o) => !o)}
          aria-label="Toggle controls"
        >
          {sidebarOpen ? <X className="h-4 w-4" /> : <SlidersHorizontal className="h-4 w-4" />}
          {sidebarOpen ? "Close" : "Controls"}
        </button>
      </div>
    </GraphProvider>
  );
}
