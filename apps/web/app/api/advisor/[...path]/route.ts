import { NextRequest, NextResponse } from "next/server";

const advisorBase = () => (process.env.ADVISOR_URL || "").replace(/\/$/, "");

async function forward(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  const base = advisorBase();
  if (!base) return NextResponse.json({ error: "Recommendation service is not configured." }, { status: 503 });

  const { path } = await context.params;
  const contentType = request.headers.get("content-type");
  try {
    const upstream = await fetch(`${base}/${path.map(encodeURIComponent).join("/")}${request.nextUrl.search}`, {
      method: request.method,
      headers: contentType ? { "content-type": contentType } : undefined,
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
    return NextResponse.json({ error: "Recommendation service is temporarily unavailable." }, { status: 502 });
  }
}

export const GET = forward;
export const POST = forward;
