"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import { FEATURES } from "@/lib/features";

const ALL_LINKS = [
  { href: "/",       label: "Dashboard",          shortLabel: "Dash",      feature: null          },
  { href: "/papers", label: "Papers",              shortLabel: "Papers",    feature: null          },
  { href: "/graph",  label: "Graph",               shortLabel: "Graph",     feature: "GRAPH"       },
  { href: "/chat",   label: "Research Assistant",  shortLabel: "Assistant", feature: null          },
] as const;

// Filter out any link whose feature flag is disabled.
const links = ALL_LINKS.filter(
  (l) => l.feature === null || FEATURES[l.feature as keyof typeof FEATURES]
);

export function NavLinks() {
  const pathname = usePathname();
  return (
    <nav className="flex items-center gap-4 text-sm">
      {links.map((l) => (
        <Link
          key={l.href}
          href={l.href}
          className={cn(
            "transition-colors hover:text-foreground/80 whitespace-nowrap",
            pathname === l.href || (l.href !== "/" && pathname.startsWith(l.href))
              ? "text-foreground font-medium"
              : "text-foreground/60"
          )}
        >
          <span className="hidden sm:inline">{l.label}</span>
          <span className="sm:hidden">{l.shortLabel}</span>
        </Link>
      ))}
    </nav>
  );
}
