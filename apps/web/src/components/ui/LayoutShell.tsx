"use client";

import { useState } from "react";
import { AppSidebar } from "./AppSidebar";
import { TopBar } from "./TopBar";
import { cn } from "@/lib/utils";

export function LayoutShell({ children }: { children: React.ReactNode }) {
  const [open, setOpen] = useState(true);

  return (
    <>
      {/* Sidebar — slides out when closed */}
      <div
        className={cn(
          "fixed left-0 top-0 h-screen z-[60] transition-transform duration-300 ease-in-out",
          open ? "translate-x-0" : "-translate-x-full"
        )}
      >
        <AppSidebar onToggle={() => setOpen(false)} />
      </div>

      {/* Content wrapper — expands when sidebar closes */}
      <div
        className={cn(
          "transition-[margin] duration-300 ease-in-out h-screen flex flex-col overflow-hidden",
          open ? "ml-64" : "ml-0"
        )}
      >
        <TopBar sidebarOpen={open} onToggle={() => setOpen((o) => !o)} />
        <main className="pt-16 flex-1 min-h-0 overflow-y-auto bg-surface">
          {children}
        </main>
      </div>
    </>
  );
}
