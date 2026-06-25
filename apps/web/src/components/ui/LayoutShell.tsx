"use client";

import { useState } from "react";
import { AppSidebar } from "./AppSidebar";
import { TopBar } from "./TopBar";
import { BackendBanner } from "./BackendBanner";
import { cn } from "@/lib/utils";

export function LayoutShell({ children }: { children: React.ReactNode }) {
  const [open, setOpen] = useState(true);

  return (
    <>
      <div
        className={cn(
          "fixed left-0 top-0 h-screen z-[60]",
          open ? "translate-x-0" : "-translate-x-full"
        )}
        style={{ transition: "transform 200ms ease" }}
      >
        <AppSidebar onToggle={() => setOpen(false)} />
      </div>

      <div
        className={cn("h-screen flex flex-col overflow-hidden", open ? "ml-64" : "ml-0")}
        style={{ transition: "margin 200ms ease" }}
      >
        <div className="flex-shrink-0">
          <BackendBanner />
          <TopBar sidebarOpen={open} onToggle={() => setOpen((o) => !o)} />
        </div>
        <main className="flex-1 min-h-0 overflow-y-auto bg-surface">
          {children}
        </main>
      </div>
    </>
  );
}
