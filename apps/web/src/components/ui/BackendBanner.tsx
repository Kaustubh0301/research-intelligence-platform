"use client";

import { useEffect, useState } from "react";

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";
// Health endpoint is at the root, not under /api/v1
const HEALTH_URL = BASE.replace(/\/api\/v1\/?$/, "") + "/health";
const POLL_INTERVAL_MS = 30_000;

type Status = "checking" | "ok" | "down";

export function BackendBanner() {
  const [status, setStatus] = useState<Status>("checking");

  const check = () => {
    fetch(HEALTH_URL, { method: "GET", cache: "no-store", headers: { "ngrok-skip-browser-warning": "1" } })
      .then((r) => setStatus(r.ok ? "ok" : "down"))
      .catch(() => setStatus("down"));
  };

  useEffect(() => {
    check();
    const id = setInterval(check, POLL_INTERVAL_MS);
    return () => clearInterval(id);
  }, []);

  if (status !== "down") return null;

  return (
    <div
      role="alert"
      className="fixed top-0 left-0 right-0 z-[100] flex items-center justify-center gap-2
                 bg-error text-on-error px-4 py-2 text-sm font-medium shadow-md"
    >
      <span className="material-symbols-outlined text-base leading-none">cloud_off</span>
      Backend unavailable — search, chat, and analysis will not work until it
      is restored.
    </div>
  );
}
