"use client";

import { useState } from "react";
import type { FeatureMapPaper } from "@/lib/types";

export function PaperRow({ paper }: { paper: FeatureMapPaper }) {
  const [open, setOpen] = useState(false);

  const similarities = paper.similarity_points ?? [];
  const differences = paper.difference_points ?? [];
  const hasExplanation =
    !!paper.relevance_explanation ||
    similarities.length > 0 ||
    differences.length > 0;

  return (
    <li className="rounded-lg border border-outline-variant bg-surface-container">
      <div className="flex gap-md px-md py-sm">
        <span className="mt-0.5 flex h-6 w-6 flex-shrink-0 items-center justify-center rounded-full bg-surface-container-highest text-[12px] font-bold text-on-surface-variant">
          {paper.rank}
        </span>

        <div className="min-w-0 flex-1">
          <p className="text-body-sm font-medium text-on-surface leading-snug">
            {paper.title}
          </p>

          <div className="mt-1 flex flex-wrap items-center gap-x-md gap-y-1 text-[11px] text-on-surface-variant">
            {paper.venue && (
              <span className="inline-flex items-center gap-1">
                <span className="material-symbols-outlined text-[13px]">article</span>
                {paper.venue}
                {paper.year ? ` ${paper.year}` : ""}
              </span>
            )}
            <span className="opacity-70">RRF {paper.rrf_score.toFixed(4)}</span>
            {paper.semantic_score != null && (
              <span className="opacity-70">sem {paper.semantic_score.toFixed(2)}</span>
            )}
            {paper.technique_score != null && (
              <span className="opacity-70">tech {paper.technique_score.toFixed(2)}</span>
            )}
          </div>

          {paper.top_techniques.length > 0 && (
            <div className="mt-1.5 flex flex-wrap gap-1">
              {paper.top_techniques.slice(0, 4).map((t) => (
                <span
                  key={t}
                  className="inline-flex rounded-full bg-primary-container/10 border border-primary-container/20 px-2 py-0.5 text-[10px] text-im-primary"
                >
                  {t}
                </span>
              ))}
            </div>
          )}

          {/* Collapsible relevance explanation — collapsed by default */}
          {hasExplanation && (
            <div className="mt-2">
              <button
                onClick={() => setOpen((o) => !o)}
                className="inline-flex items-center gap-1 text-[11px] font-label-md text-im-primary hover:opacity-80 transition-opacity"
                aria-expanded={open}
              >
                <span className="material-symbols-outlined text-[16px]">
                  {open ? "expand_less" : "expand_more"}
                </span>
                Why relevant
              </button>

              {open && (
                <div className="mt-2 space-y-2 border-l-2 border-outline-variant pl-md">
                  {paper.relevance_explanation && (
                    <p className="text-body-sm text-on-surface-variant leading-relaxed">
                      {paper.relevance_explanation}
                    </p>
                  )}

                  {similarities.length > 0 && (
                    <div>
                      <p className="text-[11px] font-label-md uppercase tracking-wide text-emerald-400 opacity-90">
                        Similarities
                      </p>
                      <ul className="mt-1 space-y-0.5">
                        {similarities.map((s, i) => (
                          <li
                            key={i}
                            className="flex gap-1.5 text-body-sm text-on-surface-variant"
                          >
                            <span className="text-emerald-400">•</span>
                            <span>{s}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {differences.length > 0 && (
                    <div>
                      <p className="text-[11px] font-label-md uppercase tracking-wide text-amber-400 opacity-90">
                        Differences
                      </p>
                      <ul className="mt-1 space-y-0.5">
                        {differences.map((d, i) => (
                          <li
                            key={i}
                            className="flex gap-1.5 text-body-sm text-on-surface-variant"
                          >
                            <span className="text-amber-400">•</span>
                            <span>{d}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </li>
  );
}
