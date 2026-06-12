"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { ChatMessage } from "./types";
import {
  type ResearchSession,
  type SavedPaper,
  type StoredMessage,
  createEmptySession,
  deleteSessionFromStorage,
  loadActiveId,
  loadIndex,
  loadSession,
  nowIso,
  saveSession,
  writeActiveId,
  writeIndex,
} from "./sessions";

// ── Helpers ───────────────────────────────────────────────────────────────────

// First-message auto-name heuristic: trim to word boundary at ≤50 chars.
function autoNameFromMessage(msg: string): string {
  const cleaned = msg.trim();
  if (cleaned.length <= 50) return cleaned;
  const truncated = cleaned.slice(0, 50);
  const lastSpace = truncated.lastIndexOf(" ");
  return (lastSpace > 20 ? truncated.slice(0, lastSpace) : truncated) + "…";
}

function hydrateMessages(stored: StoredMessage[]): ChatMessage[] {
  return stored.map((m) => ({
    ...m,
    timestamp: new Date(m.timestamp),
    isLoading: false,
  }));
}

function dehydrateMessage(msg: ChatMessage): StoredMessage {
  return {
    id: msg.id,
    role: msg.role,
    content: msg.content,
    sources: msg.sources,
    timestamp:
      msg.timestamp instanceof Date
        ? msg.timestamp.toISOString()
        : String(msg.timestamp),
  };
}

function touch(session: ResearchSession): ResearchSession {
  return { ...session, updatedAt: nowIso() };
}

// ── Store hook ────────────────────────────────────────────────────────────────

export function useSessionStore() {
  const [sessions, setSessions] = useState<ResearchSession[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [initialized, setInitialized] = useState(false);

  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  // Always-current reference to sessions for use inside non-reactive callbacks.
  const sessionsRef = useRef<ResearchSession[]>(sessions);
  useEffect(() => {
    sessionsRef.current = sessions;
  }, [sessions]);

  // ── Init (runs once, client-only) ──────────────────────────────────────────
  useEffect(() => {
    const ids = loadIndex();
    let loaded: ResearchSession[] = ids
      .map(loadSession)
      .filter((s): s is ResearchSession => s !== null);

    if (loaded.length === 0) {
      const fresh = createEmptySession();
      saveSession(fresh);
      writeIndex([fresh.id]);
      loaded = [fresh];
    }

    const stored = loadActiveId();
    const resolvedId =
      stored && loaded.some((s) => s.id === stored) ? stored : loaded[0].id;

    setSessions(loaded);
    setActiveId(resolvedId);
    writeActiveId(resolvedId);
    setInitialized(true);
  }, []);

  // ── Debounced persistence ──────────────────────────────────────────────────
  useEffect(() => {
    if (!initialized) return;
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      sessions.forEach(saveSession);
      writeIndex(sessions.map((s) => s.id));
    }, 800);
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [sessions, initialized]);

  // ── Derived ────────────────────────────────────────────────────────────────
  const activeSession = useMemo(
    () => sessions.find((s) => s.id === activeId) ?? null,
    [sessions, activeId]
  );

  const activeMessages = useMemo(
    () => (activeSession ? hydrateMessages(activeSession.messages) : []),
    [activeSession]
  );

  // ── Session CRUD ───────────────────────────────────────────────────────────
  const createSession = useCallback(() => {
    const s = createEmptySession();
    saveSession(s);
    setSessions((prev) => {
      const next = [s, ...prev];
      writeIndex(next.map((x) => x.id));
      return next;
    });
    setActiveId(s.id);
    writeActiveId(s.id);
  }, []);

  const switchSession = useCallback((id: string) => {
    setActiveId(id);
    writeActiveId(id);
  }, []);

  const renameSession = useCallback((id: string, title: string) => {
    setSessions((prev) =>
      prev.map((s) => (s.id === id ? touch({ ...s, title }) : s))
    );
  }, []);

  const deleteSession = useCallback(
    (id: string) => {
      deleteSessionFromStorage(id);
      const prev = sessionsRef.current;
      const next = prev.filter((s) => s.id !== id);

      if (next.length === 0) {
        const fresh = createEmptySession();
        saveSession(fresh);
        setSessions([fresh]);
        setActiveId(fresh.id);
        writeIndex([fresh.id]);
        writeActiveId(fresh.id);
        return;
      }

      setSessions(next);
      writeIndex(next.map((s) => s.id));

      if (activeId === id) {
        const idx = prev.findIndex((s) => s.id === id);
        const nextSession = next[Math.min(idx, next.length - 1)];
        setActiveId(nextSession.id);
        writeActiveId(nextSession.id);
      }
    },
    [activeId]
  );

  // ── Chat ───────────────────────────────────────────────────────────────────
  const appendMessage = useCallback(
    (msg: ChatMessage) => {
      const stored = dehydrateMessage(msg);
      setSessions((prev) =>
        prev.map((s) =>
          s.id === activeId
            ? touch({ ...s, messages: [...s.messages, stored] })
            : s
        )
      );
    },
    [activeId]
  );

  const setConversationId = useCallback(
    (conversationId: string) => {
      setSessions((prev) =>
        prev.map((s) =>
          s.id === activeId ? touch({ ...s, conversationId }) : s
        )
      );
    },
    [activeId]
  );

  const autoNameIfUntitled = useCallback(
    (firstUserMessage: string) => {
      setSessions((prev) =>
        prev.map((s) => {
          if (s.id !== activeId || s.title !== "Untitled Session") return s;
          return touch({ ...s, title: autoNameFromMessage(firstUserMessage) });
        })
      );
    },
    [activeId]
  );

  // ── Saved papers ───────────────────────────────────────────────────────────
  const savePaper = useCallback(
    (paper: SavedPaper) => {
      setSessions((prev) =>
        prev.map((s) => {
          if (s.id !== activeId) return s;
          if (s.savedPapers.some((p) => p.id === paper.id)) return s;
          return touch({ ...s, savedPapers: [...s.savedPapers, paper] });
        })
      );
    },
    [activeId]
  );

  const removePaper = useCallback(
    (paperId: string) => {
      setSessions((prev) =>
        prev.map((s) =>
          s.id === activeId
            ? touch({
                ...s,
                savedPapers: s.savedPapers.filter((p) => p.id !== paperId),
              })
            : s
        )
      );
    },
    [activeId]
  );

  const setLastViewedPaper = useCallback(
    (paperId: string) => {
      setSessions((prev) =>
        prev.map((s) =>
          s.id === activeId ? { ...s, lastViewedPaperId: paperId } : s
        )
      );
    },
    [activeId]
  );

  return useMemo(
    () => ({
      sessions,
      activeId,
      activeSession,
      activeMessages,
      initialized,
      createSession,
      switchSession,
      renameSession,
      deleteSession,
      appendMessage,
      setConversationId,
      autoNameIfUntitled,
      savePaper,
      removePaper,
      setLastViewedPaper,
    }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [
      sessions,
      activeId,
      activeSession,
      activeMessages,
      initialized,
    ]
  );
}
