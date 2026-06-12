"use client";

import { useEffect, useRef, useState } from "react";
import { cn } from "@/lib/utils";
import { useSession } from "./SessionContext";

function formatRelativeDate(isoString: string): string {
  const date = new Date(isoString);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));
  if (diffDays === 0) return "today";
  if (diffDays === 1) return "yesterday";
  if (diffDays < 7) return `${diffDays}d ago`;
  return date.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

export function SessionList() {
  const { sessions, activeId, createSession, switchSession, renameSession, deleteSession } =
    useSession();

  const [renamingId, setRenamingId] = useState<string | null>(null);
  const [renameValue, setRenameValue] = useState("");
  const renameInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (renamingId && renameInputRef.current) {
      renameInputRef.current.focus();
      renameInputRef.current.select();
    }
  }, [renamingId]);

  function startRename(id: string, currentTitle: string) {
    setRenamingId(id);
    setRenameValue(currentTitle);
  }

  function commitRename() {
    if (renamingId && renameValue.trim()) {
      renameSession(renamingId, renameValue.trim());
    }
    setRenamingId(null);
  }

  function handleRenameKey(e: React.KeyboardEvent) {
    if (e.key === "Enter") commitRename();
    if (e.key === "Escape") setRenamingId(null);
  }

  function handleDelete(id: string, title: string) {
    if (!confirm(`Delete "${title}"? This cannot be undone.`)) return;
    deleteSession(id);
  }

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between px-3 py-2 border-b border-border shrink-0">
        <span className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
          Sessions
        </span>
        <button
          onClick={createSession}
          title="New session"
          className="flex items-center justify-center w-5 h-5 rounded text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
        >
          <span className="text-base leading-none">+</span>
        </button>
      </div>

      <div className="flex-1 overflow-y-auto py-1">
        {sessions.map((session) => {
          const isActive = session.id === activeId;
          const isRenaming = renamingId === session.id;

          return (
            <div
              key={session.id}
              className={cn(
                "group relative flex items-start gap-2 px-3 py-2 cursor-pointer",
                "border-l-2 transition-colors",
                isActive
                  ? "border-l-primary bg-primary/5 text-foreground"
                  : "border-l-transparent text-muted-foreground hover:bg-muted hover:text-foreground"
              )}
              onClick={() => {
                if (!isRenaming) switchSession(session.id);
              }}
            >
              {/* Dot */}
              <span
                className={cn(
                  "mt-1 h-1.5 w-1.5 rounded-full shrink-0",
                  isActive ? "bg-primary" : "bg-border"
                )}
              />

              {/* Title / rename input */}
              <div className="flex-1 min-w-0">
                {isRenaming ? (
                  <input
                    ref={renameInputRef}
                    value={renameValue}
                    onChange={(e) => setRenameValue(e.target.value)}
                    onBlur={commitRename}
                    onKeyDown={handleRenameKey}
                    onClick={(e) => e.stopPropagation()}
                    className="w-full text-xs bg-background border border-primary rounded px-1.5 py-0.5 outline-none text-foreground"
                  />
                ) : (
                  <p className="text-xs font-medium leading-snug truncate">
                    {session.title}
                  </p>
                )}
                <p className="text-[10px] text-muted-foreground/70 mt-0.5">
                  {formatRelativeDate(session.updatedAt)}
                </p>
              </div>

              {/* Hover actions */}
              {!isRenaming && (
                <div
                  className="absolute right-2 top-1/2 -translate-y-1/2 hidden group-hover:flex items-center gap-0.5"
                  onClick={(e) => e.stopPropagation()}
                >
                  <button
                    title="Rename"
                    onClick={() => startRename(session.id, session.title)}
                    className="p-1 rounded text-muted-foreground hover:text-foreground hover:bg-accent transition-colors"
                  >
                    <svg className="h-3 w-3" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
                      <path d="M11.5 2.5l2 2-9 9H2.5v-2l9-9z" />
                    </svg>
                  </button>
                  <button
                    title="Delete"
                    onClick={() => handleDelete(session.id, session.title)}
                    className="p-1 rounded text-muted-foreground hover:text-destructive hover:bg-destructive/10 transition-colors"
                  >
                    <svg className="h-3 w-3" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
                      <path d="M3 4h10M6 4V2h4v2M5 4v9h6V4H5z" />
                    </svg>
                  </button>
                </div>
              )}
            </div>
          );
        })}
      </div>

      <div className="px-2 py-2 border-t border-border shrink-0">
        <button
          onClick={createSession}
          className="w-full text-left text-[11px] text-muted-foreground hover:text-foreground border border-dashed border-border hover:border-primary/50 rounded-md px-2 py-1.5 transition-colors"
        >
          + New session
        </button>
      </div>
    </div>
  );
}
