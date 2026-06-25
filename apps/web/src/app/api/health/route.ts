import { NextResponse } from "next/server";

const BACKEND = process.env.NEXT_PUBLIC_API_URL?.replace(/\/api\/v1\/?$/, "") ?? "http://localhost:8000";

export async function GET() {
  try {
    const r = await fetch(`${BACKEND}/health`, {
      cache: "no-store",
      headers: { "ngrok-skip-browser-warning": "1" },
      signal: AbortSignal.timeout(4000),
    });
    const data = await r.json();
    return NextResponse.json(data, { status: r.status });
  } catch {
    return NextResponse.json({ status: "down" }, { status: 503 });
  }
}
