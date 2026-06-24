"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import type { FeatureMapResponse } from "@/lib/types";
import { FeatureCard } from "./FeatureCard";

const MIN_WORDS = 50;

const PLACEHOLDER = `Paste a project README, PRD, or architecture document here.

Example:

# Hybrid Retrieval System

## Dense Retrieval
We use a bi-encoder (DPR) with FAISS for approximate nearest-neighbor search.

## Re-ranking
Top candidates are re-ranked with a cross-encoder fine-tuned on MS MARCO.`;

function wordCount(text: string): number {
  const t = text.trim();
  return t ? t.split(/\s+/).length : 0;
}

export function FeatureMapClient() {
  const [text, setText] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<FeatureMapResponse | null>(null);

  const words = wordCount(text);
  const tooShort = words < MIN_WORDS;

  async function handleAnalyze() {
    if (tooShort || loading) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const res = await api.featureMapAnalyze({ text });
      setResult(res);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Analysis failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="max-w-[1100px] mx-auto px-gutter py-lg space-y-lg">
      {/* Header */}
      <div>
        <h1 className="font-headline-lg text-headline-md font-bold text-on-surface flex items-center gap-2">
          <span className="material-symbols-outlined text-im-primary">schema</span>
          Feature Mapper
        </h1>
        <p className="mt-1 text-body-sm text-on-surface-variant opacity-80">
          Paste a project document. Each feature is extracted and mapped to the
          most relevant research papers in the corpus.
        </p>
      </div>

      {/* Input */}
      <div className="rounded-xl border border-outline-variant bg-surface-container-low p-lg space-y-sm">
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder={PLACEHOLDER}
          rows={12}
          disabled={loading}
          className="w-full resize-y rounded-lg border border-outline-variant bg-surface-container px-md py-sm text-body-sm text-on-surface placeholder:text-on-surface-variant/40 focus:border-im-primary focus:outline-none disabled:opacity-60 font-mono leading-relaxed"
        />
        <div className="flex items-center justify-between">
          <span
            className={
              "text-[11px] " +
              (tooShort ? "text-amber-400" : "text-on-surface-variant opacity-70")
            }
          >
            {words} words
            {tooShort && ` · need at least ${MIN_WORDS}`}
          </span>
          <button
            onClick={handleAnalyze}
            disabled={tooShort || loading}
            className="inline-flex items-center gap-2 rounded-lg bg-im-primary px-lg py-sm text-label-md font-bold text-surface transition-opacity hover:opacity-90 disabled:opacity-40 disabled:cursor-not-allowed"
          >
            {loading ? (
              <>
                <span className="material-symbols-outlined text-[18px] animate-spin">
                  progress_activity
                </span>
                Analyzing…
              </>
            ) : (
              <>
                <span className="material-symbols-outlined text-[18px]">bolt</span>
                Analyze
              </>
            )}
          </button>
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="rounded-lg border border-red-500/30 bg-red-500/10 px-md py-sm text-body-sm text-red-400">
          {error}
        </div>
      )}

      {/* Loading hint */}
      {loading && (
        <p className="text-center text-body-sm text-on-surface-variant opacity-70">
          Extracting features and searching the corpus — this usually takes
          10–20 seconds.
        </p>
      )}

      {/* Results */}
      {result && (
        <div className="space-y-lg">
          <div className="flex flex-wrap items-center gap-x-lg gap-y-1 text-body-sm text-on-surface-variant">
            {result.title && (
              <span className="font-medium text-on-surface">{result.title}</span>
            )}
            <span>{result.feature_count} features</span>
            <span className="opacity-70">
              {(result.total_duration_ms / 1000).toFixed(1)}s
            </span>
          </div>

          {result.features.map((fr) => (
            <FeatureCard key={fr.feature.id} result={fr} />
          ))}
        </div>
      )}
    </div>
  );
}
