"use client";

import { useEffect, useRef, useState } from "react";
import { useSession } from "./SessionContext";

export function SessionTopBar() {
  const { activeSession, activeMessages, renameSession, deleteSession } =
    useSession();

  const [editing, setEditing] = useState(false);
  const [value, setValue] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  // Sync local value when active session changes.
  useEffect(() => {
    setValue(activeSession?.title ?? "");
    setEditing(false);
  }, [activeSession?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  function startEdit() {
    setValue(activeSession?.title ?? "");
    setEditing(true);
  }

  function commitEdit() {
    if (activeSession && value.trim()) {
      renameSession(activeSession.id, value.trim());
    }
    setEditing(false);
  }

  function handleKey(e: React.KeyboardEvent) {
    if (e.key === "Enter") commitEdit();
    if (e.key === "Escape") setEditing(false);
  }

  useEffect(() => {
    if (editing) inputRef.current?.select();
  }, [editing]);

  function handleDelete() {
    if (!activeSession) return;
    if (!confirm(`Delete "${activeSession.title}"? This cannot be undone.`)) return;
    deleteSession(activeSession.id);
  }

  if (!activeSession) return null;

  const msgCount = activeMessages.filter((m) => m.role === "user").length;
  const paperCount = activeSession.savedPapers.length;

  return (
    <div className="flex items-center gap-3 px-4 py-2.5 border-b border-border bg-background shrink-0">
      {/* Inline-editable title */}
      {editing ? (
        <input
          ref={inputRef}
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onBlur={commitEdit}
          onKeyDown={handleKey}
          className="flex-1 min-w-0 text-sm font-semibold bg-background border border-primary rounded px-2 py-0.5 outline-none text-foreground"
        />
      ) : (
        <button
          onClick={startEdit}
          title="Click to rename"
          className="flex-1 min-w-0 text-left text-sm font-semibold text-foreground hover:underline hover:underline-offset-2 truncate"
        >
          {activeSession.title}
        </button>
      )}

      {/* Metadata */}
      <span className="text-[10px] text-muted-foreground shrink-0 whitespace-nowrap">
        {msgCount > 0 && `${msgCount} turn${msgCount !== 1 ? "s" : ""}`}
        {msgCount > 0 && paperCount > 0 && " · "}
        {paperCount > 0 && `${paperCount} saved`}
      </span>

      {/* Delete */}
      <button
        onClick={handleDelete}
        title="Delete session"
        className="shrink-0 p-1.5 rounded text-muted-foreground hover:text-destructive hover:bg-destructive/10 transition-colors"
      >
        <svg className="h-3.5 w-3.5" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
          <path d="M3 4h10M6 4V2h4v2M5 4v9h6V4H5z" />
        </svg>
      </button>
    </div>
  );
}
