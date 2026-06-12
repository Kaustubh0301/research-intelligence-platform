import type { ChatSource } from "./types";

// ── Serialisation-safe message ────────────────────────────────────────────────
// Stored in localStorage. timestamp is ISO string; isLoading is never persisted.
export interface StoredMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  sources?: ChatSource[];
  timestamp: string;
}

export interface Note {
  id: string;
  content: string;
  createdAt: string;
  updatedAt: string;
}

export interface SavedPaper {
  id: string;
  title: string;
  conference: string | null;
  year: number | null;
  savedAt: string;
  tags: string[];
}

export interface ResearchSession {
  id: string;
  title: string;
  createdAt: string;
  updatedAt: string;
  conversationId: string | null;
  messages: StoredMessage[];
  savedPapers: SavedPaper[];
  notes: Note[];
  lastViewedPaperId: string | null;
}

// ── localStorage keys ─────────────────────────────────────────────────────────
export const LS_INDEX = "rip:session:index";
export const LS_ACTIVE = "rip:active_session_id";
export const sessionKey = (id: string) => `rip:session:${id}`;

// ── Helpers ───────────────────────────────────────────────────────────────────
function genId(): string {
  return typeof crypto !== "undefined" && crypto.randomUUID
    ? crypto.randomUUID()
    : Math.random().toString(36).slice(2) + Date.now().toString(36);
}

export function nowIso(): string {
  return new Date().toISOString();
}

export function createEmptySession(): ResearchSession {
  const id = genId();
  const ts = nowIso();
  return {
    id,
    title: "Untitled Session",
    createdAt: ts,
    updatedAt: ts,
    conversationId: null,
    messages: [],
    savedPapers: [],
    // Note[] pre-created so Phase 2 notes UI has a record to write into immediately.
    notes: [{ id: genId(), content: "", createdAt: ts, updatedAt: ts }],
    lastViewedPaperId: null,
  };
}

// ── Read ──────────────────────────────────────────────────────────────────────
export function loadIndex(): string[] {
  try {
    const raw = localStorage.getItem(LS_INDEX);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? (parsed as string[]) : [];
  } catch {
    return [];
  }
}

export function loadSession(id: string): ResearchSession | null {
  try {
    const raw = localStorage.getItem(sessionKey(id));
    if (!raw) return null;
    return JSON.parse(raw) as ResearchSession;
  } catch {
    return null;
  }
}

export function loadActiveId(): string | null {
  try {
    return localStorage.getItem(LS_ACTIVE);
  } catch {
    return null;
  }
}

// ── Write ─────────────────────────────────────────────────────────────────────
export function saveSession(session: ResearchSession): void {
  try {
    localStorage.setItem(sessionKey(session.id), JSON.stringify(session));
  } catch {
    // Silently ignore quota errors — data is still in memory.
  }
}

export function writeIndex(ids: string[]): void {
  try {
    localStorage.setItem(LS_INDEX, JSON.stringify(ids));
  } catch {}
}

export function writeActiveId(id: string): void {
  try {
    localStorage.setItem(LS_ACTIVE, id);
  } catch {}
}

export function deleteSessionFromStorage(id: string): void {
  try {
    localStorage.removeItem(sessionKey(id));
  } catch {}
}
