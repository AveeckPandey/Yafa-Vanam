import { NextRequest, NextResponse } from "next/server";
import { cognitoConfig, cookieNames, refreshTokens, userFromIdToken } from "@/lib/cognito-server";
import { clearCognitoCookies, setCognitoSessionCookies } from "@/lib/cognito-session";
import { exchangeGoSession, jsonWithCookies } from "@/lib/auth-bridge";

function readCookie(request: NextRequest, name: string) {
  return request.cookies.get(name)?.value ?? "";
}

/**
 * Restores the session on page load, and lazily heals the commerce half of
 * it. Healing rule: the Go API sets its access cookie's MaxAge equal to the
 * token TTL, so a MISSING yafa_access cookie means "stale" (expired or lost
 * during a backend outage), never "signed out". Whenever we hold a valid
 * Cognito id_token and that cookie is absent, re-run the bridge exchange so
 * checkout works again — at most one round trip per page load.
 *
 * The client must send its X-CSRF-Token header here too: the Go exchange
 * endpoint enforces the same double-submit check as native login.
 */
export async function GET(request: NextRequest) {
  const config = cognitoConfig();
  if (!config) {
    return NextResponse.json({ error: "Secure sign-in is not configured." }, { status: 503 });
  }

  const goAccessPresent = readCookie(request, "yafa_access") !== "";

  const idToken = readCookie(request, cookieNames.id);
  if (idToken) {
    try {
      const user = await userFromIdToken(config, idToken);
      const response = NextResponse.json({ user });
      if (!goAccessPresent) {
        await exchangeGoSession(response.headers, request, idToken, false);
      }
      return response;
    } catch {
      // Expired or malformed id cookie — fall through to the refresh path.
    }
  }

  const refreshToken = readCookie(request, cookieNames.refresh);
  const username = decodeURIComponent(readCookie(request, cookieNames.username));
  if (!refreshToken || !username.includes("@")) {
    return NextResponse.json({ error: "Not signed in." }, { status: 401 });
  }
  try {
    const tokens = await refreshTokens(config, username, refreshToken);
    // Refreshed tokens carry the same identity; verifying keeps that promise explicit.
    const user = await userFromIdToken(config, tokens.IdToken!);
    const headers = new Headers();
    // Whether "remember me" was chosen is unknowable here; keep the longer
    // horizon so an idle visitor is not logged out by this call itself.
    setCognitoSessionCookies(headers, tokens, username, true);
    if (!goAccessPresent) {
      await exchangeGoSession(headers, request, tokens.IdToken!, false);
    }
    return jsonWithCookies({ user }, headers);
  } catch {
    const response = NextResponse.json({ error: "Your session has expired." }, { status: 401 });
    clearCognitoCookies(response.headers);
    return response;
  }
}
