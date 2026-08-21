import { NextRequest, NextResponse } from "next/server";

const apiBase = () => (process.env.COMMERCE_API_URL || process.env.NEXT_PUBLIC_API_URL || "").replace(/\/$/, "");

async function forward(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  const base = apiBase();
  if (!base) return NextResponse.json({ error: "Commerce API is not configured." }, { status: 503 });

  const { path } = await context.params;
  const headers = new Headers();
  for (const name of ["content-type", "cookie", "x-csrf-token", "x-yafa-session-token", "authorization"]) {
    const value = request.headers.get(name);
    if (value) headers.set(name, value);
  }

  try {
    const upstream = await fetch(`${base}/api/v1/${path.map(encodeURIComponent).join("/")}${request.nextUrl.search}`, {
      method: request.method,
      headers,
      body: request.method === "GET" || request.method === "HEAD" ? undefined : await request.arrayBuffer(),
      cache: "no-store",
    });
    const responseHeaders = new Headers();
    for (const name of ["content-type", "cache-control"]) {
      const value = upstream.headers.get(name);
      if (value) responseHeaders.set(name, value);
    }
    return new Response(upstream.body, { status: upstream.status, headers: responseHeaders });
  } catch {
    return NextResponse.json({ error: "Commerce API is temporarily unavailable." }, { status: 502 });
  }
}

export const GET = forward;
export const POST = forward;
export const PATCH = forward;
export const PUT = forward;
export const DELETE = forward;
