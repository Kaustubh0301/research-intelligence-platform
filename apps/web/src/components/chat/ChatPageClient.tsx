"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { api } from "@/lib/api";
import type { ChatMessage, ChatSource, ConversationMessage } from "@/lib/types";
import { useSession } from "@/components/sessions/SessionContext";
import { ChatSidebar } from "@/components/sessions/ChatSidebar";
import { SessionTopBar } from "@/components/sessions/SessionTopBar";
import { ChatInput } from "./ChatInput";
import { MessageBubble } from "./MessageBubble";
import { SourcePanel } from "./SourcePanel";
import { BookOpen, Menu, X } from "lucide-react";

function uid() {
  return Math.random().toString(36).slice(2);
}

export function ChatPageClient() {
  const {
    activeSession,
    activeMessages,
    initialized,
    appendMessage,
    setConversationId,
    autoNameIfUntitled,
  } = useSession();

  // ── Ephemeral UI state (never persisted) ────────────────────────────────────
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [loadingMsgId, setLoadingMsgId] = useState<string | null>(null);
  const [activeSources, setActiveSources] = useState<ChatSource[]>([]);
  const [leftOpen, setLeftOpen] = useState(false);
  const [rightOpen, setRightOpen] = useState(false);

  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const wasLoadingRef = useRef(false);

  // ── Reset ephemeral state on session switch ──────────────────────────────────
  useEffect(() => {
    setInput("");
    setIsLoading(false);
    setLoadingMsgId(null);
    // Restore last assistant message's sources into the right panel.
    const last = [...activeMessages].reverse().find((m) => m.role === "assistant");
    setActiveSources(last?.sources ?? []);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeSession?.id]);

  // ── Auto-scroll ──────────────────────────────────────────────────────────────
  const displayMessages = useMemo((): ChatMessage[] => {
    if (!loadingMsgId) return activeMessages;
    return [
      ...activeMessages,
      {
        id: loadingMsgId,
        role: "assistant",
        content: "",
        isLoading: true,
        timestamp: new Date(),
      },
    ];
  }, [activeMessages, loadingMsgId]);

  useEffect(() => {
    const el = scrollContainerRef.current;
    if (!el) return;
    const justFinished = wasLoadingRef.current && !isLoading;
    wasLoadingRef.current = isLoading;
    if (displayMessages.length > 0 && (justFinished || isLoading)) {
      el.scrollTop = el.scrollHeight;
    }
  }, [displayMessages.length, isLoading]);

  // ── Send ─────────────────────────────────────────────────────────────────────
  const sendMessage = async (text: string) => {
    const trimmed = text.trim();
    if (!trimmed || isLoading || !activeSession) return;

    // Build history from current messages before any state mutations.
    const history: ConversationMessage[] = activeMessages
      .filter((m) => !m.isLoading && m.content)
      .slice(-20)
      .map((m) => ({ role: m.role, content: m.content }));

    setInput("");
    setIsLoading(true);

    // Auto-name session from the first user message.
    if (activeMessages.length === 0) autoNameIfUntitled(trimmed);

    const userMsg: ChatMessage = {
      id: uid(),
      role: "user",
      content: trimmed,
      timestamp: new Date(),
    };
    appendMessage(userMsg);

    const loadingId = uid();
    setLoadingMsgId(loadingId);

    try {
      const res = await api.chat({
        message: trimmed,
        conversation_id: activeSession.conversationId ?? undefined,
        history,
      });

      setConversationId(res.conversation_id);
      setActiveSources(res.sources);
      if (res.sources.length > 0) setRightOpen(true);

      appendMessage({
        id: uid(),
        role: "assistant",
        content: res.answer,
        sources: res.sources,
        timestamp: new Date(),
      });
    } catch (err) {
      appendMessage({
        id: uid(),
        role: "assistant",
        content:
          err instanceof Error
            ? `Error: ${err.message}`
            : "An unexpected error occurred. Please try again.",
        timestamp: new Date(),
      });
    } finally {
      setLoadingMsgId(null);
      setIsLoading(false);
    }
  };

  // Clicking an assistant message restores its sources in the panel.
  const handleMessageClick = (msg: ChatMessage) => {
    if (msg.role === "assistant" && msg.sources) {
      setActiveSources(msg.sources);
    }
  };

  // ── Render ───────────────────────────────────────────────────────────────────
  if (!initialized) {
    // Sessions are loading from localStorage — show nothing to avoid flash.
    return <div className="flex h-[calc(100vh-4rem)]" />;
  }

  return (
    <div className="flex h-[calc(100vh-4rem)] overflow-hidden relative">
      {/* Mobile overlay */}
      {(leftOpen || rightOpen) && (
        <div
          className="fixed inset-0 z-30 bg-black/40 md:hidden"
          onClick={() => {
            setLeftOpen(false);
            setRightOpen(false);
          }}
        />
      )}

      {/* Left: session sidebar */}
      <div
        className={`
          absolute md:relative z-40 md:z-auto h-full flex
          transition-transform duration-200
          ${leftOpen ? "translate-x-0" : "-translate-x-full md:translate-x-0"}
        `}
      >
        <ChatSidebar />
      </div>

      {/* Centre: chat area */}
      <div className="flex flex-col flex-1 min-w-0 min-h-0">
        {/* Mobile toolbar */}
        <div className="flex items-center gap-2 px-3 py-2 border-b md:hidden">
          <button
            onClick={() => setLeftOpen((o) => !o)}
            className="flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground"
          >
            {leftOpen ? <X className="h-4 w-4" /> : <Menu className="h-4 w-4" />}
            <span className="text-xs">Sessions</span>
          </button>
          <span className="flex-1 text-center text-sm font-medium truncate">
            {activeSession?.title ?? "Research Assistant"}
          </span>
          <button
            onClick={() => setRightOpen((o) => !o)}
            className="flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground"
          >
            <span className="text-xs">
              Sources {activeSources.length > 0 ? `(${activeSources.length})` : ""}
            </span>
            <BookOpen className="h-4 w-4" />
          </button>
        </div>

        {/* Desktop: session title bar */}
        <div className="hidden md:block">
          <SessionTopBar />
        </div>

        {/* Message list */}
        <div
          ref={scrollContainerRef}
          className="flex-1 min-h-0 overflow-y-auto px-4 py-4 space-y-4"
        >
          {displayMessages.length === 0 && (
            <div className="flex flex-col items-center justify-center h-full text-center gap-3 pb-8">
              <div className="w-12 h-12 rounded-2xl bg-primary/10 flex items-center justify-center">
                <span className="text-2xl">🔬</span>
              </div>
              <h2 className="text-lg font-semibold">Research Assistant</h2>
              <p className="text-sm text-muted-foreground max-w-sm">
                Ask questions about the NeurIPS &amp; ICLR 2024 corpus. Answers are
                grounded in paper summaries, techniques, and analyses.
              </p>
              <div className="flex flex-col gap-1.5 w-full max-w-sm mt-2">
                {[
                  "What techniques are used for LLM alignment?",
                  "Which papers introduce novel transformer architectures?",
                  "Summarise the diffusion model research represented here",
                ].map((prompt) => (
                  <button
                    key={prompt}
                    onClick={() => sendMessage(prompt)}
                    className="text-xs text-left text-muted-foreground hover:text-foreground bg-muted/50 hover:bg-muted rounded-lg px-3 py-2 transition-colors"
                  >
                    {prompt}
                  </button>
                ))}
              </div>
            </div>
          )}

          {displayMessages.map((msg) => (
            <div
              key={msg.id}
              onClick={() => handleMessageClick(msg)}
              className={
                msg.role === "assistant" && msg.sources ? "cursor-pointer" : undefined
              }
            >
              <MessageBubble message={msg} />
            </div>
          ))}
        </div>

        {/* Input */}
        <ChatInput
          value={input}
          onChange={setInput}
          onSend={() => sendMessage(input)}
          disabled={isLoading}
        />
      </div>

      {/* Right: source panel */}
      <div
        className={`
          absolute right-0 md:relative z-40 md:z-auto h-full
          transition-transform duration-200
          ${rightOpen ? "translate-x-0" : "translate-x-full md:translate-x-0"}
        `}
      >
        <SourcePanel sources={activeSources} isLoading={isLoading} />
      </div>
    </div>
  );
}
