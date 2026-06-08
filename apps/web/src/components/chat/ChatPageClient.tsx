"use client";

import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import type { ChatMessage, ChatSource } from "@/lib/types";
import { ChatInput } from "./ChatInput";
import { MessageBubble } from "./MessageBubble";
import { SidebarHistory } from "./SidebarHistory";
import { SourcePanel } from "./SourcePanel";
import { BookOpen, Menu, X } from "lucide-react";

function uid() {
  return Math.random().toString(36).slice(2);
}

export function ChatPageClient() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [activeSources, setActiveSources] = useState<ChatSource[]>([]);
  const [conversationId, setConversationId] = useState<string | undefined>();
  const [leftOpen, setLeftOpen] = useState(false);
  const [rightOpen, setRightOpen] = useState(false);

  // Accumulate all cited papers across the conversation for the sidebar
  const [citedPapers, setCitedPapers] = useState<ChatSource[]>([]);

  const bottomRef = useRef<HTMLDivElement>(null);

  // Auto-scroll on new message
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const sendMessage = async (text: string) => {
    const trimmed = text.trim();
    if (!trimmed || isLoading) return;

    setInput("");
    setIsLoading(true);

    const userMsg: ChatMessage = {
      id: uid(),
      role: "user",
      content: trimmed,
      timestamp: new Date(),
    };

    // Placeholder assistant message — shows typing indicator
    const assistantId = uid();
    const loadingMsg: ChatMessage = {
      id: assistantId,
      role: "assistant",
      content: "",
      isLoading: true,
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMsg, loadingMsg]);

    try {
      const res = await api.chat({
        message: trimmed,
        conversation_id: conversationId,
      });

      setConversationId(res.conversation_id);
      setActiveSources(res.sources);
      if (res.sources.length > 0) setRightOpen(true);

      // Merge new sources into cited papers (deduplicate by id)
      setCitedPapers((prev) => {
        const ids = new Set(prev.map((p) => p.id));
        const newOnes = res.sources.filter((s) => !ids.has(s.id));
        return [...prev, ...newOnes];
      });

      // Replace the loading placeholder with the real answer
      const assistantMsg: ChatMessage = {
        id: assistantId,
        role: "assistant",
        content: res.answer,
        sources: res.sources,
        isLoading: false,
        timestamp: new Date(),
      };

      setMessages((prev) =>
        prev.map((m) => (m.id === assistantId ? assistantMsg : m))
      );
    } catch (err) {
      const errMsg: ChatMessage = {
        id: assistantId,
        role: "assistant",
        content:
          err instanceof Error
            ? `Error: ${err.message}`
            : "An unexpected error occurred. Please try again.",
        isLoading: false,
        timestamp: new Date(),
      };
      setMessages((prev) =>
        prev.map((m) => (m.id === assistantId ? errMsg : m))
      );
    } finally {
      setIsLoading(false);
    }
  };

  // Clicking on a previous assistant message restores its sources
  const handleMessageClick = (msg: ChatMessage) => {
    if (msg.role === "assistant" && msg.sources) {
      setActiveSources(msg.sources);
    }
  };

  return (
    <div className="flex h-[calc(100vh-3.5rem)] -mx-4 -my-6 overflow-hidden relative">
      {/* Mobile overlays */}
      {(leftOpen || rightOpen) && (
        <div
          className="fixed inset-0 z-30 bg-black/40 md:hidden"
          onClick={() => { setLeftOpen(false); setRightOpen(false); }}
        />
      )}

      {/* Left sidebar */}
      <div className={`
        absolute md:relative z-40 md:z-auto h-full
        transition-transform duration-200
        ${leftOpen ? "translate-x-0" : "-translate-x-full md:translate-x-0"}
      `}>
        <SidebarHistory
          messages={messages}
          savedPapers={citedPapers}
          onPromptClick={(p) => {
            setInput(p);
            setLeftOpen(false);
          }}
        />
      </div>

      {/* Main chat area */}
      <div className="flex flex-col flex-1 min-w-0">
        {/* Mobile top toolbar */}
        <div className="flex items-center gap-2 px-3 py-2 border-b md:hidden">
          <button
            onClick={() => setLeftOpen((o) => !o)}
            className="flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground"
            aria-label="Toggle history"
          >
            {leftOpen ? <X className="h-4 w-4" /> : <Menu className="h-4 w-4" />}
            <span className="text-xs">Menu</span>
          </button>
          <span className="flex-1 text-center text-sm font-medium">Research Assistant</span>
          <button
            onClick={() => setRightOpen((o) => !o)}
            className="flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground"
            aria-label="Toggle sources"
          >
            <span className="text-xs">Sources {activeSources.length > 0 ? `(${activeSources.length})` : ""}</span>
            <BookOpen className="h-4 w-4" />
          </button>
        </div>

        {/* Message list */}
        <div className="flex-1 overflow-y-auto px-4 py-4 space-y-4">
          {messages.length === 0 && (
            <div className="flex flex-col items-center justify-center h-full text-center gap-3 pb-8">
              <div className="w-12 h-12 rounded-2xl bg-primary/10 flex items-center justify-center">
                <span className="text-2xl">🔬</span>
              </div>
              <h2 className="text-lg font-semibold">Research Assistant</h2>
              <p className="text-sm text-muted-foreground max-w-sm">
                Ask questions about the NeurIPS 2024 corpus. Answers are
                grounded in paper summaries, techniques, and analyses — no
                hallucination.
              </p>
              <p className="text-xs text-muted-foreground">
                Select an example prompt from the sidebar to get started.
              </p>
            </div>
          )}

          {messages.map((msg) => (
            <div
              key={msg.id}
              onClick={() => handleMessageClick(msg)}
              className={
                msg.role === "assistant" && msg.sources
                  ? "cursor-pointer"
                  : undefined
              }
            >
              <MessageBubble message={msg} />
            </div>
          ))}
          <div ref={bottomRef} />
        </div>

        {/* Input bar */}
        <ChatInput
          value={input}
          onChange={setInput}
          onSend={() => sendMessage(input)}
          disabled={isLoading}
        />
      </div>

      {/* Right source panel */}
      <div className={`
        absolute right-0 md:relative z-40 md:z-auto h-full
        transition-transform duration-200
        ${rightOpen ? "translate-x-0" : "translate-x-full md:translate-x-0"}
      `}>
        <SourcePanel sources={activeSources} isLoading={isLoading} />
      </div>
    </div>
  );
}
