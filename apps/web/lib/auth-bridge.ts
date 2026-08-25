import "server-only";

import { NextResponse, type NextRequest } from "next/server";
import { userFromIdToken, type CognitoConfig, type TokenSet } from "./cognito-server";
import { setCognitoSessionCookies } from "./cognito-session";

/**
 * Bridges a verified Cognito identity into the Go commerce API's first-party
 * session system. The browser never talks to the Go API about Cognito — these
 * server-side handlers do, forwarding the visitor's own CSRF pair so the Go
 * endpoint's double-submit check sees exactly what a native login would.
 */

const apiBase = () =>
  (process.env.COMMERCE_API_URL || process.env.NEXT_PUBLIC_API_URL || "").replace(/\/$/, "");

export type BridgeOutcome = "issued" | "degraded";

/**
 * POST /auth/cognito/exchange with the fresh id_token. On success the Go
 * response's Set-Cookie headers are relayed onto `headers` verbatim.
 *
 * A failure NEVER fails the sign-in: the visitor keeps their valid Cognito
 * session and the next page load heals the commerce session lazily
 * (see app/api/auth/cognito/session/route.ts). Returns how it went.
 */
export async function exchangeGoSession(
  headers: Headers,
  request: Request,
  idToken: string,
  remember: boolean,
): Promise<BridgeOutcome> {
  const base = apiBase();
  if (!base) return "degraded";
  try {
    const upstream = await fetch(`${base}/auth/cognito/exchange`, {
      method: "POST",
      cache: "no-store",
      redirect: "manual",
      headers: {
        "Content-Type": "application/json",
        ...(request.headers.get("cookie") ? { cookie: request.headers.get("cookie")! } : {}),
        ...(request.headers.get("x-csrf-token") ? { "x-csrf-token": request.headers.get("x-csrf-token")! } : {}),
      },
      body: JSON.stringify({ id_token: idToken, remember }),
    });
    if (!upstream.ok) {
      console.error(`cognito bridge exchange failed with ${upstream.status}`);
      return "degraded";
    }
    // Headers.get() merges repeated Set-Cookie values into one string that
    // browsers cannot reliably split — relay each header independently.
    for (const cookie of upstream.headers.getSetCookie()) {
      headers.append("set-cookie", cookie);
    }
    return "issued";
  } catch {
    console.error("cognito bridge exchange unreachable");
    return "degraded";
  }
}

/** Forwards a logout to the Go API so both cookie families die together. */
export async function relayGoLogout(request: Request) {
  const base = apiBase();
  if (!base) return;
  try {
    await fetch(`${base}/auth/logout`, {
      method: "POST",
      cache: "no-store",
      headers: {
        ...(request.headers.get("cookie") ? { cookie: request.headers.get("cookie")! } : {}),
        ...(request.headers.get("x-csrf-token") ? { "x-csrf-token": request.headers.get("x-csrf-token")! } : {}),
      },
      body: "",
    });
  } catch {
    // Commerce logout is best-effort here; the caller clears cookies locally.
  }
}

/** Double-submit CSRF check mirroring what the Go API enforces for native auth mutations. */
export function hasValidCsrfPair(request: Request) {
  const cookieHeader = request.headers.get("cookie") || "";
  const match = /(?:^|;\s*)yafa_csrf=([^;]+)/.exec(cookieHeader);
  const provided = request.headers.get("x-csrf-token");
  return Boolean(match?.[1]) && match![1] === provided && provided !== "";
}

/**
 * Builds the JSON response carrying a Headers object that may hold several
 * Set-Cookie values (Cognito tokens + relayed Go session). Iterating a Headers
 * object directly would merge them into one comma-joined value browsers cannot
 * parse — getSetCookie() preserves each independently.
 */
export function jsonWithCookies(body: unknown, headers: Headers, status = 200) {
  const response = NextResponse.json(body, { status });
  for (const cookie of headers.getSetCookie()) {
    response.headers.append("set-cookie", cookie);
  }
  return response;
}

/**
 * Shared tail of login and signup-confirm: verify the fresh id_token, write
 * the Cognito cookie family onto `headers`, then bridge to Go for its session
 * cookies. Route modules may only export HTTP handlers, so this lives here.
 */
export async function finishCognitoSignIn(
  request: NextRequest,
  headers: Headers,
  config: CognitoConfig,
  tokens: TokenSet,
  username: string,
  remember: boolean,
) {
  const user = await userFromIdToken(config, tokens.IdToken!); // signIn/refreshTokens guarantee IdToken
  setCognitoSessionCookies(headers, tokens, username, remember);
  await exchangeGoSession(headers, request, tokens.IdToken!, remember);
  return { user };
}
