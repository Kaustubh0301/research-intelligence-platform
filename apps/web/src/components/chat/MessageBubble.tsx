"use client";

import { useEffect, useState } from "react";
import { cn } from "@/lib/utils";
import type { ChatMessage } from "@/lib/types";

interface Props {
  message: ChatMessage;
}

// Simulated streaming: reveal characters progressively for assistant messages
function useStreamedText(
  content: string,
  isLoading: boolean,
  enabled: boolean
): { displayed: string; done: boolean } {
  const [displayed, setDisplayed] = useState("");
  const [done, setDone] = useState(false);

  useEffect(() => {
    if (!enabled || isLoading) {
      setDisplayed(content);
      setDone(true);
      return;
    }
    // Reset on new content
    setDisplayed("");
    setDone(false);
    let i = 0;
    // Chunk size grows over time for natural feel (slow start, faster middle)
    const tick = () => {
      if (i >= content.length) {
        setDone(true);
        return;
      }
      const chunk = Math.min(4 + Math.floor(i / 80), 12);
      i = Math.min(i + chunk, content.length);
      setDisplayed(content.slice(0, i));
      setTimeout(tick, 18);
    };
    const t = setTimeout(tick, 30);
    return () => clearTimeout(t);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [content]);

  return { displayed, done };
}

function escapeHtml(s: string): string {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function renderContent(text: string) {
  const lines = text.split("\n");
  return lines.map((line, i) => {
    const escaped = escapeHtml(line);
    const processed = escaped.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
    const isBullet = /^[-•*]\s/.test(line) || /^\d+\.\s/.test(line);
    return (
      <span key={i} className={cn("block", isBullet && "pl-3")}>
        <span dangerouslySetInnerHTML={{ __html: processed || " " }} />
      </span>
    );
  });
}

export function MessageBubble({ message }: Props) {
  const isUser = message.role === "user";
  const isNew = !message.isLoading && message.role === "assistant";

  const { displayed, done } = useStreamedText(
    message.content,
    message.isLoading ?? false,
    isNew
  );

  return (
    <div
      className={cn(
        "flex w-full",
        isUser ? "justify-end" : "justify-start"
      )}
    >
      <div
        className={cn(
          "max-w-[75%] rounded-2xl px-4 py-3 text-sm leading-relaxed",
          isUser
            ? "bg-primary text-primary-foreground rounded-br-sm"
            : "bg-muted rounded-bl-sm"
        )}
      >
        {message.isLoading ? (
          // Typing indicator — three animated dots
          <span className="flex items-center gap-1 h-5">
            <span className="w-2 h-2 rounded-full bg-current animate-bounce [animation-delay:0ms]" />
            <span className="w-2 h-2 rounded-full bg-current animate-bounce [animation-delay:150ms]" />
            <span className="w-2 h-2 rounded-full bg-current animate-bounce [animation-delay:300ms]" />
          </span>
        ) : isUser ? (
          <span>{message.content}</span>
        ) : (
          <span>
            {renderContent(displayed)}
            {!done && (
              <span className="inline-block w-0.5 h-4 bg-current ml-0.5 animate-pulse" />
            )}
          </span>
        )}
      </div>
    </div>
  );
}
