"use client";

import { useEffect, useRef, useState } from "react";
import { X } from "lucide-react";

interface Props {
  defaultValue: string;
  onChange:     (q: string) => void;
}

export function SearchBar({ defaultValue, onChange }: Props) {
  const [value, setValue] = useState(defaultValue);
  const timer   = useRef<ReturnType<typeof setTimeout>>(undefined);
  const mounted = useRef(false);

  // Sync when URL param changes externally (back button, clear-all).
  useEffect(() => {
    if (mounted.current) setValue(defaultValue);
    mounted.current = true;
  }, [defaultValue]);

  // Flush on unmount so debounce never fires after navigation.
  useEffect(() => () => clearTimeout(timer.current), []);

  const commit = (v: string) => {
    clearTimeout(timer.current);
    timer.current = setTimeout(() => onChange(v), 300);
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setValue(e.target.value);
    commit(e.target.value);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") { clearTimeout(timer.current); onChange(value); }
    if (e.key === "Escape") { clearTimeout(timer.current); setValue(""); onChange(""); }
  };

  const clear = () => { clearTimeout(timer.current); setValue(""); onChange(""); };

  return (
    <div className="relative group">
      {/* Glow ring on focus */}
      <div className="absolute -inset-px rounded-xl bg-gradient-to-r from-im-primary to-im-secondary opacity-0 blur-sm transition-opacity duration-500 group-focus-within:opacity-30 pointer-events-none" />

      <div className="relative flex items-center bg-surface-container-high border border-outline-variant rounded-xl px-lg py-sm shadow-sm transition-colors group-focus-within:border-im-primary">
        <span className="material-symbols-outlined text-[20px] text-im-primary mr-md flex-shrink-0">
          search
        </span>
        <input
          type="search"
          placeholder="Search papers, techniques, abstracts…"
          className="w-full bg-transparent border-none focus:ring-0 focus:outline-none text-body-md text-on-surface placeholder:text-outline font-body-md"
          value={value}
          onChange={handleChange}
          onKeyDown={handleKeyDown}
          autoComplete="off"
          spellCheck={false}
        />
        {value && (
          <button
            type="button"
            onClick={clear}
            className="ml-md text-on-surface-variant hover:text-on-surface transition-colors flex-shrink-0"
            aria-label="Clear search"
          >
            <X className="h-4 w-4" />
          </button>
        )}
      </div>
    </div>
  );
}
