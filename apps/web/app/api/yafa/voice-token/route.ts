import { NextRequest, NextResponse } from "next/server";

import { hasValidCsrfPair } from "@/lib/auth-bridge";
import { cognitoConfig, cookieNames, userFromIdToken } from "@/lib/cognito-server";
import { createVoiceGatewayToken, voiceGatewayPublicUrl } from "@/lib/voice-gateway-token";

export const dynamic = "force-dynamic";

/**
 * Mint a two-minute gateway token for a verified signed-in customer.
 * Cognito and signing credentials remain server-only; this response is never
 * cached and cannot be minted cross-site because it requires the CSRF pair.
 */
export async function POST(request: NextRequest) {
  if (!hasValidCsrfPair(request)) {
    return NextResponse.json({ error: "Invalid security token." }, { status: 403 });
  }
  const config = cognitoConfig();
  const idToken = request.cookies.get(cookieNames.id)?.value || "";
  if (!config || !idToken) {
    return NextResponse.json({ error: "Sign in to use live voice." }, { status: 401 });
  }
  try {
    const user = await userFromIdToken(config, idToken);
    const { token, expiresAt } = createVoiceGatewayToken(user.id);
    return NextResponse.json(
      { gatewayUrl: voiceGatewayPublicUrl(), token, expiresAt },
      { headers: { "Cache-Control": "no-store, private", "Referrer-Policy": "no-referrer" } },
    );
  } catch (error) {
    const reason = error instanceof Error ? error.message : "";
    if (reason.startsWith("voice_gateway_")) {
      return NextResponse.json({ error: "Live voice is not configured." }, { status: 503 });
    }
    return NextResponse.json({ error: "Your session has expired. Sign in again." }, { status: 401 });
  }
}
