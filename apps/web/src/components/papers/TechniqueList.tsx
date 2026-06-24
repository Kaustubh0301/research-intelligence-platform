import Link from "next/link";
import type { PaperTechnique } from "@/lib/types";

const ROLE_CONFIG = {
  introduces: {
    label: "Introduces",
    chipClass: "bg-emerald-50 text-emerald-800 border border-emerald-200 hover:bg-emerald-100",
    dotClass: "bg-emerald-500",
  },
  uses: {
    label: "Uses",
    chipClass: "bg-blue-50 text-blue-800 border border-blue-200 hover:bg-blue-100",
    dotClass: "bg-blue-500",
  },
  compares: {
    label: "Compares",
    chipClass: "bg-amber-50 text-amber-800 border border-amber-200 hover:bg-amber-100",
    dotClass: "bg-amber-500",
  },
  critiques: {
    label: "Critiques",
    chipClass: "bg-red-50 text-red-800 border border-red-200 hover:bg-red-100",
    dotClass: "bg-red-500",
  },
} as const;

const ROLE_ORDER = ["introduces", "uses", "compares", "critiques"] as const;

interface Props {
  techniques: PaperTechnique[];
}

export function TechniqueList({ techniques }: Props) {
  if (!techniques.length) return null;

  const grouped = techniques.reduce(
    (acc, t) => {
      (acc[t.role] ??= []).push(t);
      return acc;
    },
    {} as Record<string, PaperTechnique[]>
  );

  const hasAny = ROLE_ORDER.some((r) => (grouped[r]?.length ?? 0) > 0);
  if (!hasAny) return null;

  return (
    <section className="rounded-xl border bg-card p-5 space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          Techniques
        </h2>
        <span className="text-xs text-muted-foreground">
          {techniques.length} total
        </span>
      </div>

      {ROLE_ORDER.map((role) => {
        const items = grouped[role];
        if (!items?.length) return null;
        const cfg = ROLE_CONFIG[role];

        return (
          <div key={role}>
            <div className="flex items-center gap-1.5 mb-2">
              <span className={`h-2 w-2 rounded-full flex-shrink-0 ${cfg.dotClass}`} />
              <span className="text-xs font-medium text-muted-foreground">
                {cfg.label}
                <span className="ml-1 text-muted-foreground/60">({items.length})</span>
              </span>
            </div>
            <div className="flex flex-wrap gap-1.5">
              {items.map((t) => (
                <Link
                  key={t.name}
                  href={`/papers?technique=${encodeURIComponent(t.canonical_name ?? t.name)}`}
                  className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium transition-colors ${cfg.chipClass}`}
                  title={t.canonical_name !== t.name ? `Canonical: ${t.canonical_name}` : undefined}
                >
                  {t.name}
                </Link>
              ))}
            </div>
          </div>
        );
      })}
    </section>
  );
}
