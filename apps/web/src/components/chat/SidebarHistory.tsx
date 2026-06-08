"use client";

import { Separator } from "@/components/ui/separator";
import type { ChatMessage, ChatSource } from "@/lib/types";
import { Clock, MessageSquare, Sparkles } from "lucide-react";
import Link from "next/link";
import { cn } from "@/lib/utils";

const EXAMPLE_PROMPTS = [
  "What techniques are used for LLM alignment in this corpus?",
  "Which papers introduce novel transformer architectures?",
  "Summarise the diffusion model research represented here",
  "What are the most central papers in cluster 0?",
  "What papers work on reinforcement learning from human feedback?",
];

interface Props {
  messages: ChatMessage[];
  savedPapers: ChatSource[];
  onPromptClick: (prompt: string) => void;
}

export function SidebarHistory({ messages, savedPapers, onPromptClick }: Props) {
  const userMessages = messages.filter((m) => m.role === "user");

  return (
    <aside className="w-60 shrink-0 border-r bg-background flex flex-col overflow-hidden">
      {/* Header */}
      <div className="p-3 border-b">
        <div className="flex items-center gap-2">
          <MessageSquare className="h-4 w-4 text-muted-foreground" />
          <span className="text-sm font-semibold">Research Assistant</span>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto">
        {/* Example prompts */}
        <div className="p-3">
          <div className="flex items-center gap-1.5 mb-2">
            <Sparkles className="h-3.5 w-3.5 text-muted-foreground" />
            <span className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
              Try asking
            </span>
          </div>
          <div className="space-y-1">
            {EXAMPLE_PROMPTS.map((prompt) => (
              <button
                key={prompt}
                onClick={() => onPromptClick(prompt)}
                className={cn(
                  "w-full text-left text-xs text-muted-foreground hover:text-foreground",
                  "hover:bg-muted rounded px-2 py-1.5 transition-colors line-clamp-2",
                  "leading-snug"
                )}
              >
                {prompt}
              </button>
            ))}
          </div>
        </div>

        {/* Recent questions */}
        {userMessages.length > 0 && (
          <>
            <Separator />
            <div className="p-3">
              <div className="flex items-center gap-1.5 mb-2">
                <Clock className="h-3.5 w-3.5 text-muted-foreground" />
                <span className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                  This session
                </span>
              </div>
              <div className="space-y-1">
                {[...userMessages].reverse().slice(0, 8).map((m) => (
                  <button
                    key={m.id}
                    onClick={() => onPromptClick(m.content)}
                    className={cn(
                      "w-full text-left text-xs text-muted-foreground hover:text-foreground",
                      "hover:bg-muted rounded px-2 py-1.5 transition-colors line-clamp-2",
                      "leading-snug"
                    )}
                  >
                    {m.content}
                  </button>
                ))}
              </div>
            </div>
          </>
        )}

        {/* Saved papers */}
        {savedPapers.length > 0 && (
          <>
            <Separator />
            <div className="p-3">
              <div className="flex items-center gap-1.5 mb-2">
                <span className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                  Cited papers
                </span>
              </div>
              <div className="space-y-1">
                {savedPapers.slice(0, 5).map((p) => (
                  <Link
                    key={p.id}
                    href={`/papers/${p.id}`}
                    className={cn(
                      "block text-xs text-muted-foreground hover:text-foreground",
                      "hover:bg-muted rounded px-2 py-1.5 transition-colors line-clamp-2",
                      "leading-snug"
                    )}
                  >
                    {p.title}
                  </Link>
                ))}
              </div>
            </div>
          </>
        )}
      </div>
    </aside>
  );
}
