"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import { FEATURES } from "@/lib/features";

// ── Navigation items ──────────────────────────────────────────────────────

const NAV_ITEMS = [
  { href: "/",       icon: "dashboard",   label: "Dashboard",  feature: null    },
  { href: "/papers", icon: "menu_book",   label: "Library",    feature: null    },
  { href: "/graph",  icon: "hub",         label: "Graph",      feature: "GRAPH" },
  { href: "/chat",   icon: "smart_toy",   label: "Chatbot",    feature: null    },
  { href: "/feature-map", icon: "schema", label: "Feature Mapper", feature: null },
] as const;

function NavItem({
  href,
  icon,
  label,
  active,
}: {
  href: string;
  icon: string;
  label: string;
  active: boolean;
}) {
  return (
    <Link
      href={href}
      className={cn(
        "flex items-center gap-3 px-md py-sm rounded-lg transition-colors duration-200 group",
        active
          ? "bg-surface-container-highest text-im-primary font-bold"
          : "text-on-surface-variant hover:bg-surface-container-highest hover:text-on-surface"
      )}
    >
      <span className="material-symbols-outlined text-[20px]">{icon}</span>
      <span className="text-label-md">{label}</span>
    </Link>
  );
}

// ── Sidebar ───────────────────────────────────────────────────────────────

export function AppSidebar({ onToggle }: { onToggle?: () => void }) {
  const pathname = usePathname();

  const visibleItems = NAV_ITEMS.filter(
    (item) => item.feature === null || FEATURES[item.feature as keyof typeof FEATURES]
  );

  const isActive = (href: string) =>
    href === "/" ? pathname === "/" : pathname.startsWith(href);

  return (
    <aside className="w-64 h-screen bg-surface-container-low border-r border-outline-variant flex flex-col py-md px-sm">
      {/* Brand row + collapse button */}
      <div className="px-md mb-xl flex items-start justify-between">
        <Link href="/" className="block">
          <span className="font-headline-md text-headline-md font-bold text-im-primary">
            InsightEngine
          </span>
          <p className="text-[11px] text-on-surface-variant font-label-md tracking-wider mt-1 opacity-70 uppercase">
            AI Research Hub
          </p>
        </Link>
        {onToggle && (
          <button
            onClick={onToggle}
            title="Collapse sidebar"
            className="mt-1 p-xs rounded-lg text-on-surface-variant hover:bg-surface-container-highest hover:text-on-surface transition-colors flex-shrink-0"
          >
            <span className="material-symbols-outlined text-[20px]">chevron_left</span>
          </button>
        )}
      </div>

      {/* Primary nav */}
      <nav className="flex-1 space-y-1">
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
