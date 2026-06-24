"use client";

import { usePathname } from "next/navigation";
import Link from "next/link";
import { cn } from "@/lib/utils";

const SECTION_TABS: Record<string, Array<{ href: string; label: string }>> = {
  "/papers": [{ href: "/papers", label: "Papers" }],
  "/chat":   [{ href: "/chat",   label: "Research Assistant" }],
  "/":       [{ href: "/",       label: "Overview" }],
};

function resolveTabs(pathname: string) {
  if (pathname.startsWith("/papers")) return SECTION_TABS["/papers"];
  if (pathname.startsWith("/chat"))   return SECTION_TABS["/chat"];
  return SECTION_TABS["/"];
}

interface Props {
  sidebarOpen: boolean;
  onToggle:    () => void;
}

export function TopBar({ sidebarOpen, onToggle }: Props) {
  const pathname = usePathname();
  const tabs     = resolveTabs(pathname);

  return (
    <header className="fixed top-0 right-0 left-0 h-16 bg-surface border-b border-outline-variant flex items-center z-50 transition-[padding] duration-300 ease-in-out"
      style={{ paddingLeft: sidebarOpen ? "16rem" : "0" }}
    >
      <div className="flex items-center justify-between w-full px-gutter">
        {/* Left: toggle button + sub-tabs */}
        <div className="flex items-center h-full gap-sm">
          {/* Sidebar toggle */}
          <button
            onClick={onToggle}
            title={sidebarOpen ? "Collapse sidebar" : "Expand sidebar"}
            className="p-sm rounded-lg text-on-surface-variant hover:bg-surface-container-highest hover:text-on-surface transition-colors flex-shrink-0"
          >
            <span className="material-symbols-outlined text-[22px]">
              {sidebarOpen ? "menu_open" : "menu"}
            </span>
          </button>

          {/* Section sub-tabs */}
          <nav className="flex h-full">
            {tabs.map((tab) => {
              const active =
                tab.href === "/" ? pathname === "/" : pathname.startsWith(tab.href);
              return (
                <Link
                  key={tab.href}
                  href={tab.href}
                  className={cn(
                    "h-16 flex items-center px-sm text-label-md transition-colors border-b-2",
                    active
                      ? "text-im-primary border-im-primary font-bold"
                      : "text-on-surface-variant border-transparent hover:text-on-surface"
                  )}
                >
                  {tab.label}
                </Link>
              );
            })}
          </nav>
        </div>

      </div>
    </header>
  );
}
