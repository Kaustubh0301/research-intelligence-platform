"use client";

import { useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { X, ChevronDown, ChevronUp } from "lucide-react";
import { api, queryKeys } from "@/lib/api";
import { CLUSTER_COLOURS, CLUSTER_LABELS } from "@/lib/constants";
import { FEATURES } from "@/lib/features";
import { cn } from "@/lib/utils";

interface Props {
  conference: string;
  cluster:    string;
  technique:  string;
  onConferenceChange: (v: string) => void;
  onClusterChange:    (v: string) => void;
  onTechniqueChange:  (v: string) => void;
}

// ── Collapsible section ───────────────────────────────────────────────────

function Section({
  title,
  children,
  active,
}: {
  title:    string;
  children: React.ReactNode;
  active?:  boolean;
}) {
  const [open, setOpen] = useState(true);
  return (
    <div>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center justify-between py-1 text-label-md uppercase tracking-widest text-im-primary hover:opacity-80 transition-opacity"
      >
        <span className="flex items-center gap-xs">
          {title}
          {active && <span className="inline-flex h-1.5 w-1.5 rounded-full bg-im-primary" />}
        </span>
        {open
          ? <ChevronUp className="h-3.5 w-3.5" />
          : <ChevronDown className="h-3.5 w-3.5" />}
      </button>
      {open && <div className="mt-md">{children}</div>}
    </div>
  );
}

// ── Data ──────────────────────────────────────────────────────────────────

const CONFERENCES = ["NeurIPS", "ICLR", "ICML"];
const CLUSTERS    = [0, 1, 2].map((n) => ({
  value:       String(n),
  label:       CLUSTER_LABELS[n] ?? `Cluster ${n}`,
  description: "",
}));

// ── Main component ────────────────────────────────────────────────────────

export function FilterPanel({
  conference,
  cluster,
  technique,
  onConferenceChange,
  onClusterChange,
  onTechniqueChange,
}: Props) {
  const [techInput, setTechInput]           = useState(technique);
  const [techOpen, setTechOpen]             = useState(false);
  const [debouncedTechInput, setDebounced]  = useState(technique);
  const techTimer  = useRef<ReturnType<typeof setTimeout>>(undefined);
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Sync when technique changes externally.
  useEffect(() => {
    setTechInput(technique);
    setDebounced(technique);
  }, [technique]);

  const handleTechInputChange = (v: string) => {
    setTechInput(v);
    setTechOpen(true);
    clearTimeout(techTimer.current);
    techTimer.current = setTimeout(() => setDebounced(v), 250);
  };

  // Close dropdown on outside click.
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node))
        setTechOpen(false);
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  const { data: techniquesData, isFetching: techFetching } = useQuery({
    queryKey: queryKeys.techniques(debouncedTechInput),
    queryFn:  () => api.techniques(debouncedTechInput || undefined),
    enabled:  techOpen && debouncedTechInput.length >= 1,
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
    setDebounced("");
    setTechOpen(false);
  };

  return (
    <div className="space-y-lg text-body-sm">

      {/* Conference — pill buttons matching mockup */}
      <Section title="Venues" active={!!conference}>
        <div className="grid grid-cols-2 gap-sm">
          {CONFERENCES.map((conf) => (
            <button
              key={conf}
              type="button"
              onClick={() => onConferenceChange(conference === conf ? "" : conf)}
              className={cn(
                "border px-sm py-xs rounded text-label-md text-xs text-center transition-colors",
                conference === conf
                  ? "bg-surface-container-highest border-im-primary text-im-primary font-bold"
                  : "bg-surface-container border-outline-variant text-on-surface-variant hover:border-outline"
              )}
            >
              {conf}
            </button>
          ))}
        </div>
      </Section>

      {FEATURES.GRAPH && (
        <>
          <div className="border-t border-outline-variant" />

          {/* Cluster */}
          <Section title="Cluster" active={!!cluster}>
            <div className="space-y-sm">
              <label className="flex items-center gap-sm cursor-pointer group">
                <input
                  type="radio"
                  name="cluster"
                  value=""
                  checked={cluster === ""}
                  onChange={() => onClusterChange("")}
                  className="h-4 w-4 accent-[#adc6ff] cursor-pointer"
                />
                <span className="text-on-surface-variant group-hover:text-on-surface transition-colors">
                  All clusters
                </span>
              </label>
              {CLUSTERS.map((opt) => (
                <label key={opt.value} className="flex items-center gap-sm cursor-pointer group">
                  <input
                    type="radio"
                    name="cluster"
                    value={opt.value}
                    checked={cluster === opt.value}
                    onChange={() => onClusterChange(opt.value)}
                    className="h-4 w-4 accent-[#adc6ff] cursor-pointer"
                  />
                  <span className="flex items-center gap-xs text-on-surface-variant group-hover:text-on-surface transition-colors">
                    <span
                      className="inline-block h-2.5 w-2.5 rounded-full flex-shrink-0"
                      style={{ backgroundColor: CLUSTER_COLOURS[Number(opt.value)] }}
                    />
                    <span className={cn(cluster === opt.value && "text-on-surface font-medium")}>
                      {opt.label}
                    </span>
                  </span>
                </label>
              ))}
            </div>
          </Section>
        </>
      )}

      <div className="border-t border-outline-variant" />

      {/* Technique autocomplete */}
      <Section title="Technique" active={!!technique}>
        <div className="relative" ref={dropdownRef}>
          <div className="relative flex items-center bg-surface-container-high border border-outline-variant rounded-lg px-sm py-sm focus-within:border-im-primary transition-colors">
            <span className="material-symbols-outlined text-[16px] text-outline mr-xs">search</span>
            <input
              type="text"
              placeholder="Search techniques…"
              value={techInput}
              onChange={(e) => handleTechInputChange(e.target.value)}
              onFocus={() => techInput && setTechOpen(true)}
              className="flex-1 bg-transparent border-none focus:ring-0 focus:outline-none text-body-sm text-on-surface placeholder:text-outline"
            />
            {(techInput || technique) && (
              <button
                type="button"
                onClick={clearTechnique}
                className="text-on-surface-variant hover:text-on-surface transition-colors"
                aria-label="Clear technique"
              >
                <X className="h-3.5 w-3.5" />
              </button>
            )}
          </div>

          {techOpen && debouncedTechInput.length >= 1 && (
            <div className="absolute top-full left-0 right-0 z-20 mt-1 rounded-lg border border-outline-variant bg-surface-container shadow-xl overflow-hidden">
              {techFetching && (
                <div className="px-md py-sm text-body-sm text-on-surface-variant">Loading…</div>
              )}
              {!techFetching && techniquesData?.techniques.length === 0 && (
                <div className="px-md py-sm text-body-sm text-on-surface-variant">No techniques found</div>
              )}
              <div className="max-h-52 overflow-y-auto">
                {techniquesData?.techniques.slice(0, 12).map((t) => (
                  <button
                    key={t.canonical_name}
                    type="button"
                    onMouseDown={(e) => { e.preventDefault(); selectTechnique(t.canonical_name); }}
                    className={cn(
                      "flex w-full items-center justify-between px-md py-sm text-body-sm hover:bg-surface-container-high transition-colors text-left",
                      technique === t.canonical_name && "bg-surface-container-high text-on-surface font-medium"
                    )}
                  >
                    <span className="truncate text-on-surface-variant hover:text-on-surface">{t.canonical_name}</span>
                    <span className="ml-sm flex-shrink-0 text-outline text-[11px]">{t.usage_count}</span>
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>

        {technique && (
          <div className="mt-sm flex items-center gap-xs">
            <span className="text-body-sm text-on-surface-variant">Active:</span>
            <span className="inline-flex items-center gap-xs rounded-full bg-primary-container/10 px-sm py-0.5 text-[11px] font-label-md text-im-primary border border-primary-container/20">
              {technique}
              <button
                type="button"
                onClick={clearTechnique}
                className="hover:opacity-60"
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
