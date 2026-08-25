import { NextRequest, NextResponse } from "next/server";
import { cognitoConfig, cookieNames, revokeSession } from "@/lib/cognito-server";
import { clearCognitoCookies } from "@/lib/cognito-session";
import { relayGoLogout } from "@/lib/auth-bridge";

const GO_COOKIE_BASE = "; Path=/; HttpOnly; SameSite=Strict; Max-Age=-1";

/**
 * Signs the visitor out of both systems in one call: revokes the Cognito
 * tokens (GlobalSignOut, falling back to RevokeToken), ends the Go commerce
 * session, and expires every cookie from either family. Best-effort by
 * design — a backend hiccup must not leave the visitor unable to log out.
 */
export async function POST(request: NextRequest) {
  const config = cognitoConfig();
  if (config) {
    await revokeSession(
      config,
      request.cookies.get(cookieNames.access)?.value,
      request.cookies.get(cookieNames.refresh)?.value,
    );
  }
  await relayGoLogout(request);
  const response = new NextResponse(null, { status: 204 });
  const headers = response.headers;
  clearCognitoCookies(headers);
  // Mirror of the Go API's own cookie attributes so the browser reliably
  // drops them even when the commerce service is unreachable.
  for (const name of ["yafa_access", "yafa_refresh"]) {
    headers.append("set-cookie", `${name}=${GO_COOKIE_BASE}`);
  }
  return response;
}
