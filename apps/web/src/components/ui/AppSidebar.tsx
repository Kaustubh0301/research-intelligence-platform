"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import { FEATURES } from "@/lib/features";

const NAV_ITEMS = [
  { href: "/",            icon: "dashboard",           label: "Dashboard",      feature: null    },
  { href: "/chat",        icon: "forum",               label: "AI Assistant",   feature: null    },
  { href: "/papers",      icon: "travel_explore",      label: "Paper Explorer", feature: null    },
  { href: "/feature-map", icon: "auto_awesome_motion", label: "Project Mapper", feature: null    },
  { href: "/graph",       icon: "hub",                 label: "Graph",          feature: "GRAPH" },
] as const;

function NavItem({ href, icon, label, active }: { href: string; icon: string; label: string; active: boolean }) {
  return (
    <Link
      href={href}
      className={cn(
        "flex items-center gap-3 px-4 py-2.5 rounded-lg transition-colors",
        active
          ? "bg-primary-container text-on-primary-container font-semibold"
          : "text-on-surface-variant hover:bg-surface-container-high hover:text-on-surface"
      )}
    >
      <span className="material-symbols-outlined text-[20px]">{icon}</span>
      <span className="text-sm">{label}</span>
    </Link>
  );
}

export function AppSidebar({ onToggle }: { onToggle?: () => void }) {
  const pathname = usePathname();

  const visibleItems = NAV_ITEMS.filter(
    (item) => item.feature === null || FEATURES[item.feature as keyof typeof FEATURES]
  );

  const isActive = (href: string) =>
    href === "/" ? pathname === "/" : pathname.startsWith(href);

  return (
    <aside className="w-64 h-screen bg-surface-container-lowest border-r border-outline-variant/30 flex flex-col py-3 px-3">
      {/* Brand */}
      <div className="flex items-center gap-3 px-2 py-4 mb-2">
        <div className="w-8 h-8 bg-im-primary rounded-lg flex items-center justify-center flex-shrink-0">
          <span className="material-symbols-outlined text-on-primary text-[18px]">auto_awesome</span>
        </div>
        <div>
          <h2 className="font-semibold text-im-primary text-sm leading-tight">InsightEngine</h2>
          <p className="text-[10px] uppercase tracking-widest text-outline mt-0.5">AI Research Hub</p>
        </div>
        {onToggle && (
          <button
            onClick={onToggle}
            className="ml-auto p-1 rounded-lg text-on-surface-variant hover:bg-surface-container-high transition-colors"
          >
            <span className="material-symbols-outlined text-[18px]">chevron_left</span>
          </button>
        )}
      </div>

      {/* Nav */}
      <nav className="flex-1 space-y-0.5">
        {visibleItems.map((item) => (
          <NavItem
            key={item.href}
            href={item.href}
            icon={item.icon}
            label={item.label}
            active={isActive(item.href)}
          />
        ))}
      </nav>
    </aside>
  );
}
