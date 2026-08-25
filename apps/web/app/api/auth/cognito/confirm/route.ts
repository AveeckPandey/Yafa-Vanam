import { NextRequest, NextResponse } from "next/server";
import { CognitoError, cognitoConfig, confirmSignUp, signIn } from "@/lib/cognito-server";
import { finishCognitoSignIn, hasValidCsrfPair, jsonWithCookies } from "@/lib/auth-bridge";

/**
 * Email-code confirmation completes the sign-up. Confirming fires the pool's
 * PostConfirmation welcome-coupon trigger exactly once; then the visitor is
 * signed in immediately with both cookie families — Cognito tokens here, Go
 * commerce session via the bridge.
 */
export async function POST(request: NextRequest) {
  if (!hasValidCsrfPair(request)) {
    return NextResponse.json({ error: "Invalid security token." }, { status: 403 });
  }
  const config = cognitoConfig();
  if (!config) {
    return NextResponse.json({ error: "Secure sign-up is not configured." }, { status: 503 });
  }
  const body = await request.json().catch(() => null) as { email?: string; code?: string; password?: string; remember?: boolean } | null;
  const email = body?.email?.trim().toLowerCase() || "";
  const code = body?.code?.trim() || "";
  if (!email.includes("@") || !code || !body?.password) {
    return NextResponse.json({ error: "Enter the verification code from your email." }, { status: 400 });
  }
  try {
    await confirmSignUp(config, email, code);
    // Re-signing in after confirmation proves the password still pairs with
    // the account instead of trusting whatever the browser forwarded.
    const tokens = await signIn(config, email, body.password);
    const headers = new Headers();
    const { user } = await finishCognitoSignIn(request, headers, config, tokens, body.remember === true);
    return jsonWithCookies({ user }, headers);
  } catch (reason) {
    if (reason instanceof CognitoError) {
      const status = reason.code === "CodeMismatchException" || reason.code === "ExpiredCodeException" ? 422 : reason.code === "UserNotConfirmedException" ? 409 : 401;
      return NextResponse.json({ error: reason.message }, { status });
    }
    throw reason;
  }
}
