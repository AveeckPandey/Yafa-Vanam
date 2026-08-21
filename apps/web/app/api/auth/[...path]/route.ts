import { NextRequest, NextResponse } from "next/server";

const apiBase = () => (process.env.COMMERCE_API_URL || process.env.NEXT_PUBLIC_API_URL || (process.env.NODE_ENV === "production" ? "" : "http://localhost:4000")).replace(/\/$/, "");

async function forward(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  const API = apiBase();
  if (!API) return NextResponse.json({ error: "Secure sign-in is unavailable because the commerce connection is not configured." }, { status: 503 });
  const { path } = await context.params;
  let upstream: Response;
  try {
    upstream = await fetch(`${API}/auth/${path.map(encodeURIComponent).join("/")}${request.nextUrl.search}`, {
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
  } catch {
    return NextResponse.json({ error: "Secure sign-in is temporarily unavailable. Please try again shortly." }, { status: 502 });
  }

  const headers = new Headers(upstream.headers);
  // A login response sets both access and refresh cookies. Headers.get()
  // combines them into one string, which browsers cannot reliably store as
  // two cookies. Preserve each Set-Cookie header independently.
  const setCookies = upstream.headers.getSetCookie();
  headers.delete("set-cookie");
  const response = new NextResponse(upstream.body, { status: upstream.status, headers });
  for (const cookie of setCookies) {
    // OAuth is exposed to the browser under /api/auth, while the private Go
    // service mounts it at /auth. Keep its state cookies available on the
    // public callback path so Google OAuth state validation succeeds.
    response.headers.append("set-cookie", cookie.replaceAll("Path=/auth/google", "Path=/api/auth/google"));
  }
  response.headers.delete("content-encoding");
  response.headers.delete("content-length");
  return response;
}

export const GET = forward;
export const POST = forward;
export const OPTIONS = forward;
