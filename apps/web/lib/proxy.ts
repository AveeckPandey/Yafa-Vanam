import { NextRequest, NextResponse } from "next/server";

/**
 * Shared relay for the /api/* catch-all proxies: no-store fetch to `upstream`,
 * forwarding `headers`, relaying only content-type/cache-control back, and a
 * 502 when the upstream is unreachable. Routes keep their own base-URL
 * resolution, header allow-lists, and 503 config checks.
 */
export async function relay(
  request: NextRequest,
  upstreamUrl: string,
  headers: HeadersInit = {},
  unavailableMessage = "The service is temporarily unavailable.",
): Promise<Response> {
  try {
    const upstream = await fetch(upstreamUrl, {
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
    return NextResponse.json({ error: unavailableMessage }, { status: 502 });
  }
}
