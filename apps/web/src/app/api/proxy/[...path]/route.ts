import { NextRequest, NextResponse } from "next/server";

const BACKEND = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

async function handler(req: NextRequest, { params }: { params: Promise<{ path: string[] }> }) {
  const { path } = await params;
  const url = `${BACKEND}/${path.join("/")}`;

  const headers: Record<string, string> = {
    "ngrok-skip-browser-warning": "1",
    "content-type": req.headers.get("content-type") ?? "application/json",
  };

  const body = req.method !== "GET" && req.method !== "HEAD"
    ? await req.text()
    : undefined;

  try {
    const res = await fetch(url, {
      method: req.method,
      headers,
      body,
      signal: AbortSignal.timeout(120_000), // 2 min for long-running analysis
    });

    const data = await res.text();
    return new NextResponse(data, {
      status: res.status,
      headers: { "content-type": res.headers.get("content-type") ?? "application/json" },
    });
  } catch (err) {
    return NextResponse.json({ detail: String(err) }, { status: 502 });
  }
}

export const GET = handler;
export const POST = handler;
export const PUT = handler;
export const DELETE = handler;
