import { NextRequest, NextResponse } from "next/server";
import { cognitoConfig, cookieNames, refreshTokens, userFromIdToken } from "@/lib/cognito-server";
import { clearCognitoCookies, setCognitoSessionCookies } from "@/lib/cognito-session";
import { exchangeGoSession, hasValidCsrfPair, jsonWithCookies } from "@/lib/auth-bridge";
import { parseRememberFlag } from "@/lib/cognito-shared";

/**
 * Explicit client-driven refresh (used when a commerce call comes back 401).
 * Mirrors the session route's healing: while we hold fresh tokens, an absent
 * yafa_access cookie is repaired in the same round trip.
 */
export async function POST(request: NextRequest) {
  if (!hasValidCsrfPair(request)) {
    return NextResponse.json({ error: "Invalid security token." }, { status: 403 });
  }
  const config = cognitoConfig();
  if (!config) {
    return NextResponse.json({ error: "Secure sign-in is not configured." }, { status: 503 });
  }
  const refreshToken = request.cookies.get(cookieNames.refresh)?.value ?? "";
  const username = decodeURIComponent(request.cookies.get(cookieNames.username)?.value ?? "");
  // The username may be an email alias or a pool-native id; any non-empty
  // value persisted from a verified token is acceptable.
  if (!refreshToken || !username) {
    return NextResponse.json({ error: "Your session has expired." }, { status: 401 });
  }
  try {
    const tokens = await refreshTokens(config, username, refreshToken);
    const user = await userFromIdToken(config, tokens.IdToken!);
    const headers = new Headers();
    // Preserve the visitor's original remember-me choice instead of silently
    // turning a non-persistent session into a 30-day one.
    setCognitoSessionCookies(headers, tokens, username, parseRememberFlag(request.cookies.get(cookieNames.remember)?.value));
    // Heal only when the Go access cookie is truly absent — an absent value
    // means "stale", while any present value means Go owns its state.
    if (!request.cookies.get("yafa_access")) {
      await exchangeGoSession(headers, request, tokens.IdToken!, false);
    }
    return jsonWithCookies({ user }, headers);
  } catch {
    const response = NextResponse.json({ error: "Your session has expired." }, { status: 401 });
    clearCognitoCookies(response.headers);
    return response;
  }
}
