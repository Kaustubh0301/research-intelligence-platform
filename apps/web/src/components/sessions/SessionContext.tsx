"use client";

import { createContext, useContext } from "react";
import { useSessionStore } from "@/lib/useSessionStore";

type SessionStore = ReturnType<typeof useSessionStore>;

const SessionCtx = createContext<SessionStore | null>(null);

export function SessionProvider({ children }: { children: React.ReactNode }) {
  const store = useSessionStore();
  return <SessionCtx.Provider value={store}>{children}</SessionCtx.Provider>;
}

export function useSession(): SessionStore {
  const ctx = useContext(SessionCtx);
  if (!ctx) throw new Error("useSession must be used within <SessionProvider>");
  return ctx;
}
