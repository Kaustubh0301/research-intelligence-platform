"use client";

import { SavedPapersList } from "./SavedPapersList";
import { SessionList } from "./SessionList";

export function ChatSidebar() {
  return (
    <aside className="w-52 h-full shrink-0 border-r border-border bg-background flex flex-col overflow-hidden">
      {/* Upper: session list — takes remaining space */}
      <div className="flex-1 min-h-0 overflow-hidden flex flex-col">
        <SessionList />
      </div>

      {/* Lower: saved papers — fixed height, scrolls internally */}
      <div className="border-t border-border shrink-0 max-h-64 overflow-y-auto">
        <SavedPapersList />
      </div>
    </aside>
  );
}
