"use client";

import { useEffect, useRef, useState } from "react";
import { Search, X } from "lucide-react";
import { Input } from "@/components/ui/input";

interface Props {
  defaultValue: string;
  onChange: (q: string) => void;
}

export function SearchBar({ defaultValue, onChange }: Props) {
  const [value, setValue] = useState(defaultValue);
  const timer = useRef<ReturnType<typeof setTimeout>>(undefined);
  const mounted = useRef(false);

  // Sync when URL param changes externally (e.g. back button, clear-all).
  useEffect(() => {
    if (mounted.current) setValue(defaultValue);
    mounted.current = true;
  }, [defaultValue]);

  // Flush immediately on unmount so the debounce never fires after navigation.
  useEffect(() => {
    return () => clearTimeout(timer.current);
  }, []);

  const commit = (v: string) => {
    clearTimeout(timer.current);
    timer.current = setTimeout(() => onChange(v), 300);
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setValue(e.target.value);
    commit(e.target.value);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") {
      clearTimeout(timer.current);
      onChange(value);
    }
    if (e.key === "Escape") {
      clearTimeout(timer.current);
      setValue("");
      onChange("");
    }
  };

  const clear = () => {
    clearTimeout(timer.current);
    setValue("");
    onChange("");
  };

  return (
    <div className="relative">
      <Search className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
      <Input
        type="search"
        placeholder="Search papers, techniques, abstracts…"
        className="pl-9 pr-9"
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
          className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors"
          aria-label="Clear search"
        >
          <X className="h-4 w-4" />
        </button>
      )}
    </div>
  );
}
