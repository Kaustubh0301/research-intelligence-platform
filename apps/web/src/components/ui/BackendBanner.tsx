"use client";

import { useEffect, useState } from "react";

type Status = "checking" | "ok" | "down";

export function BackendBanner() {
  const [status, setStatus] = useState<Status>("checking");

  const check = () => {
    fetch("/api/health", { cache: "no-store" })
      .then((r) => setStatus(r.ok ? "ok" : "down"))
      .catch(() => setStatus("down"));
  };

  useEffect(() => {
    check();
    const id = setInterval(check, 30_000);
    return () => clearInterval(id);
  }, []);

  if (status !== "down") return null;

  return (
    <div role="alert" className="flex items-center gap-2 bg-red-600 text-white px-4 py-1.5 text-xs font-medium w-full flex-shrink-0">
      <span className="material-symbols-outlined text-[16px] leading-none">cloud_off</span>
      Backend unavailable — search, chat, and analysis will not work until it is restored.
    </div>
  );
}
