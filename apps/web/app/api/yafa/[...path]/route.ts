import { NextRequest, NextResponse } from "next/server";

/**
 * Server-only bridge to the recommendation-engine's internal Yafa endpoints
 * (Phase 2 section 35 / Phase 3 section 41). The service token never reaches
 * the browser: it lives in this route's environment alone.
 */
const advisorBase = () => (process.env.ADVISOR_URL || "").replace(/\/$/, "");
const serviceToken = () => process.env.YAFA_INTERNAL_SERVICE_TOKEN || "";

async function forward(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  const base = advisorBase();
  if (!base) {
    return NextResponse.json({ error: "Yafa service is not configured." }, { status: 503 });
  }
  const token = serviceToken();
  if (!token) {
    return NextResponse.json({ error: "Yafa service authentication is not configured." }, { status: 503 });
  }

  const { path } = await context.params;
  const contentType = request.headers.get("content-type");
  try {
    const upstream = await fetch(`${base}/internal/yafa/${path.map(encodeURIComponent).join("/")}`, {
      method: request.method,
      headers: {
        "x-yafa-service-token": token,
        ...(contentType ? { "content-type": contentType } : {}),
      },
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
    return NextResponse.json({ error: "Yafa service is temporarily unavailable." }, { status: 502 });
  }
}

export const GET = forward;
export const POST = forward;
