"use client";

import { useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { X, ChevronDown, ChevronUp } from "lucide-react";
import { api, queryKeys } from "@/lib/api";
import { CLUSTER_COLOURS, CLUSTER_LABELS } from "@/lib/constants";
import { Input } from "@/components/ui/input";
import { Separator } from "@/components/ui/separator";
import { cn } from "@/lib/utils";

interface Props {
  conference: string;
  cluster: string;
  technique: string;
  onConferenceChange: (v: string) => void;
  onClusterChange: (v: string) => void;
  onTechniqueChange: (v: string) => void;
}

function Section({
  title,
  children,
  active,
}: {
  title: string;
  children: React.ReactNode;
  active?: boolean;
}) {
  const [open, setOpen] = useState(true);
  return (
    <div>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center justify-between py-1 text-xs font-semibold uppercase tracking-wider text-muted-foreground hover:text-foreground transition-colors"
      >
        <span className="flex items-center gap-1.5">
          {title}
          {active && (
            <span className="inline-flex h-1.5 w-1.5 rounded-full bg-primary" />
          )}
        </span>
        {open ? (
          <ChevronUp className="h-3.5 w-3.5" />
        ) : (
          <ChevronDown className="h-3.5 w-3.5" />
        )}
      </button>
      {open && <div className="mt-2">{children}</div>}
    </div>
  );
}

const CONFERENCES = ["NeurIPS", "ICLR", "ICML"];

const CLUSTERS = [0, 1, 2].map((n) => ({
  value: String(n),
  label: `Cluster ${n}`,
  description: CLUSTER_LABELS[n] ?? "",
}));

export function FilterPanel({
  conference,
  cluster,
  technique,
  onConferenceChange,
  onClusterChange,
  onTechniqueChange,
}: Props) {
  const [techInput, setTechInput] = useState(technique);
  const [techOpen, setTechOpen] = useState(false);
  const techTimer = useRef<ReturnType<typeof setTimeout>>(undefined);
  const [debouncedTechInput, setDebouncedTechInput] = useState(technique);
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Sync technique display text when the active technique changes from outside
  // (e.g. user clicks a technique chip on a PaperCard, or clears all filters).
  useEffect(() => {
    setTechInput(technique);
    setDebouncedTechInput(technique);
  }, [technique]);

  // Debounce the API call, not the display value.
  const handleTechInputChange = (v: string) => {
    setTechInput(v);
    setTechOpen(true);
    clearTimeout(techTimer.current);
    techTimer.current = setTimeout(() => setDebouncedTechInput(v), 250);
  };

  // Close dropdown on outside click.
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setTechOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  const { data: techniquesData, isFetching: techFetching } = useQuery({
    queryKey: queryKeys.techniques(debouncedTechInput),
    queryFn: () => api.techniques(debouncedTechInput || undefined),
    enabled: techOpen && debouncedTechInput.length >= 1,
    staleTime: 5 * 60 * 1000,
  });

  const selectTechnique = (name: string) => {
    onTechniqueChange(name);
    setTechInput(name);
    setTechOpen(false);
  };

  const clearTechnique = () => {
    onTechniqueChange("");
    setTechInput("");
    setDebouncedTechInput("");
    setTechOpen(false);
  };

  return (
    <div className="space-y-4 text-sm">
      <Section title="Conference" active={!!conference}>
        <div className="space-y-1.5">
          {CONFERENCES.map((conf) => (
            <label
              key={conf}
              className="flex items-center gap-2.5 cursor-pointer group"
            >
              <input
                type="checkbox"
                className="h-4 w-4 rounded border-muted-foreground/30 accent-primary cursor-pointer"
                checked={conference === conf}
                onChange={(e) => onConferenceChange(e.target.checked ? conf : "")}
              />
              <span className="group-hover:text-foreground transition-colors text-muted-foreground data-[checked]:text-foreground">
                {conf}
              </span>
            </label>
          ))}
        </div>
      </Section>

      <Separator />

      <Section title="Cluster" active={!!cluster}>
        <div className="space-y-1.5">
          <label className="flex items-center gap-2.5 cursor-pointer group">
            <input
              type="radio"
              name="cluster"
              value=""
              checked={cluster === ""}
              onChange={() => onClusterChange("")}
              className="h-4 w-4 accent-primary cursor-pointer"
            />
            <span className="text-muted-foreground group-hover:text-foreground transition-colors">
              All clusters
            </span>
          </label>
          {CLUSTERS.map((opt) => (
            <label
              key={opt.value}
              className="flex items-center gap-2.5 cursor-pointer group"
            >
              <input
                type="radio"
                name="cluster"
                value={opt.value}
                checked={cluster === opt.value}
                onChange={() => onClusterChange(opt.value)}
                className="h-4 w-4 accent-primary cursor-pointer"
              />
              <span className="flex items-center gap-1.5 text-muted-foreground group-hover:text-foreground transition-colors">
                <span
                  className="inline-block h-2.5 w-2.5 rounded-full flex-shrink-0"
                  style={{ backgroundColor: CLUSTER_COLOURS[Number(opt.value)] }}
                />
                <span className={cn(cluster === opt.value && "text-foreground font-medium")}>
                  {opt.label}
                </span>
              </span>
            </label>
          ))}
        </div>
      </Section>

      <Separator />

      <Section title="Technique" active={!!technique}>
        <div className="relative" ref={dropdownRef}>
          <div className="relative">
            <Input
              placeholder="Search techniques…"
              value={techInput}
              onChange={(e) => handleTechInputChange(e.target.value)}
              onFocus={() => techInput && setTechOpen(true)}
              className={cn("pr-7", technique && "border-primary/50")}
            />
            {(techInput || technique) && (
              <button
                type="button"
                onClick={clearTechnique}
                className="absolute right-2.5 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors"
                aria-label="Clear technique"
              >
                <X className="h-3.5 w-3.5" />
              </button>
            )}
          </div>

          {techOpen && debouncedTechInput.length >= 1 && (
            <div className="absolute top-full left-0 right-0 z-20 mt-1 rounded-md border bg-popover shadow-md overflow-hidden">
              {techFetching && (
                <div className="px-3 py-2 text-xs text-muted-foreground">
                  Loading…
                </div>
              )}
              {!techFetching &&
                techniquesData?.techniques.length === 0 && (
                  <div className="px-3 py-2 text-xs text-muted-foreground">
                    No techniques found
                  </div>
                )}
              <div className="max-h-52 overflow-y-auto">
                {techniquesData?.techniques.slice(0, 12).map((t) => (
                  <button
                    key={t.canonical_name}
                    type="button"
                    onMouseDown={(e) => {
                      // prevent blur before click registers
                      e.preventDefault();
                      selectTechnique(t.canonical_name);
                    }}
                    className={cn(
                      "flex w-full items-center justify-between px-3 py-2 text-xs hover:bg-accent transition-colors text-left",
                      technique === t.canonical_name && "bg-accent font-medium"
                    )}
                  >
                    <span className="truncate">{t.canonical_name}</span>
                    <span className="ml-2 flex-shrink-0 text-muted-foreground">
                      {t.usage_count}
                    </span>
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>

        {technique && (
          <div className="mt-2 flex items-center gap-1.5">
            <span className="text-xs text-muted-foreground">Active:</span>
            <span className="inline-flex items-center gap-1 rounded-full bg-primary/10 px-2 py-0.5 text-xs font-medium text-primary">
              {technique}
              <button
                type="button"
                onClick={clearTechnique}
                className="ml-0.5 hover:text-primary/70"
                aria-label="Remove technique filter"
              >
                <X className="h-3 w-3" />
              </button>
            </span>
          </div>
        )}
      </Section>
    </div>
  );
}
