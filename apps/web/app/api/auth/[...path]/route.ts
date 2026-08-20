import { NextRequest, NextResponse } from "next/server";

const API = (process.env.COMMERCE_API_URL || process.env.NEXT_PUBLIC_API_URL || "http://localhost:4000").replace(/\/$/, "");

async function forward(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  const { path } = await context.params;
  const upstream = await fetch(`${API}/auth/${path.map(encodeURIComponent).join("/")}${request.nextUrl.search}`, {
    method: request.method,
    headers: {
      ...(request.headers.get("content-type") ? { "content-type": request.headers.get("content-type")! } : {}),
      ...(request.headers.get("x-csrf-token") ? { "x-csrf-token": request.headers.get("x-csrf-token")! } : {}),
      ...(request.headers.get("cookie") ? { cookie: request.headers.get("cookie")! } : {}),
    },
    body: request.method === "GET" || request.method === "HEAD" ? undefined : await request.text(),
    redirect: "manual",
    cache: "no-store",
  });

  const response = new NextResponse(upstream.body, { status: upstream.status, headers: upstream.headers });
  response.headers.delete("content-encoding");
  response.headers.delete("content-length");
  return response;
}

export const GET = forward;
export const POST = forward;
export const OPTIONS = forward;
