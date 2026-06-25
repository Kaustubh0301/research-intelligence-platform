"use client";

import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";

interface Props {
  sidebarOpen: boolean;
  onToggle:    () => void;
}

const PAGE_TITLES: Record<string, string> = {
  "/":            "Dashboard",
  "/papers":      "Paper Explorer",
  "/chat":        "AI Assistant",
  "/feature-map": "Project Mapper",
  "/graph":       "Graph",
};

export function TopBar({ sidebarOpen, onToggle }: Props) {
  const pathname = usePathname();
  const [dark, setDark] = useState(false);

  useEffect(() => {
    const saved = localStorage.getItem("theme");
    if (saved === "dark") {
      document.documentElement.classList.add("dark");
      setDark(true);
    }
  }, []);

  function toggleDark() {
    const next = !dark;
    setDark(next);
    document.documentElement.classList.toggle("dark", next);
    localStorage.setItem("theme", next ? "dark" : "light");
  }

  const title = Object.entries(PAGE_TITLES).find(([k]) =>
    k === "/" ? pathname === "/" : pathname.startsWith(k)
  )?.[1] ?? "InsightEngine";

  return (
    <header className="h-14 bg-surface-bright border-b border-outline-variant/30 flex items-center px-5 gap-4 flex-shrink-0">
      <button
        onClick={onToggle}
        className="p-1.5 rounded-lg text-on-surface-variant hover:bg-surface-container-high transition-colors flex-shrink-0"
      >
        <span className="material-symbols-outlined text-[22px]">
          {sidebarOpen ? "menu_open" : "menu"}
        </span>
      </button>

      <span className="text-sm font-semibold text-on-surface-variant">{title}</span>

      <div className="flex items-center gap-2 ml-auto flex-shrink-0">
        <button
          onClick={toggleDark}
          className="p-1.5 text-on-surface-variant hover:text-im-primary hover:bg-surface-container-high rounded-lg transition-colors"
          title="Toggle dark mode"
        >
          <span className="material-symbols-outlined text-[20px]">
            {dark ? "light_mode" : "dark_mode"}
          </span>
        </button>
      </div>
    </header>
  );
}
