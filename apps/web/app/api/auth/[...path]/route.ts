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

  const headers = new Headers(upstream.headers);
  const setCookie = headers.get("set-cookie");
  if (setCookie) {
    // OAuth is exposed to the browser under /api/auth, while the private Go
    // service mounts it at /auth. Keep its state cookies available on the
    // public callback path so Google OAuth state validation succeeds.
    headers.set("set-cookie", setCookie.replaceAll("Path=/auth/google", "Path=/api/auth/google"));
  }

  const response = new NextResponse(upstream.body, { status: upstream.status, headers });
  response.headers.delete("content-encoding");
  response.headers.delete("content-length");
  return response;
}

export const GET = forward;
export const POST = forward;
export const OPTIONS = forward;
