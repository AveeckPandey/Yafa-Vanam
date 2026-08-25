import { NextRequest, NextResponse } from "next/server";
import { CognitoError, cognitoConfig, signIn } from "@/lib/cognito-server";
import { finishCognitoSignIn, hasValidCsrfPair, jsonWithCookies } from "@/lib/auth-bridge";

export async function POST(request: NextRequest) {
  if (!hasValidCsrfPair(request)) {
    return NextResponse.json({ error: "Invalid security token." }, { status: 403 });
  }
  const config = cognitoConfig();
  if (!config) {
    return NextResponse.json({ error: "Secure sign-in is not configured." }, { status: 503 });
  }
  const body = await request.json().catch(() => null) as { email?: string; password?: string; remember?: boolean } | null;
  const email = body?.email?.trim().toLowerCase() || "";
  if (!email.includes("@") || !body?.password) {
    return NextResponse.json({ error: "Enter your email and password." }, { status: 400 });
  }
  try {
    const tokens = await signIn(config, email, body.password);
    const headers = new Headers();
    const { user } = await finishCognitoSignIn(request, headers, config, tokens, email, body.remember === true);
    return jsonWithCookies({ user }, headers);
  } catch (reason) {
    if (reason instanceof CognitoError) {
      // UserNotConfirmedException is a routing signal, not a failure: the
      // client flips to the verification-code panel with this flag set.
      return NextResponse.json(
        { error: reason.message, ...(reason.code === "UserNotConfirmedException" ? { needsConfirmation: true } : {}) },
        { status: reason.code === "UserNotConfirmedException" ? 403 : 401 },
      );
    }
    throw reason;
  }
}
