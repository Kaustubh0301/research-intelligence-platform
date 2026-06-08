"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";

const links = [
  { href: "/", label: "Dashboard" },
  { href: "/papers", label: "Papers" },
];

export function NavLinks() {
  const pathname = usePathname();
  return (
    <nav className="flex items-center gap-4 text-sm">
      {links.map((l) => (
        <Link
          key={l.href}
          href={l.href}
          className={cn(
            "transition-colors hover:text-foreground/80",
            pathname === l.href || (l.href !== "/" && pathname.startsWith(l.href))
              ? "text-foreground font-medium"
              : "text-foreground/60"
          )}
        >
          {l.label}
        </Link>
      ))}
    </nav>
  );
}
