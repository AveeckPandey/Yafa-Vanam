import { NextRequest, NextResponse } from "next/server";
import { CognitoError, cognitoConfig, confirmForgotPassword } from "@/lib/cognito-server";
import { hasValidCsrfPair } from "@/lib/auth-bridge";

/**
 * Completes a Cognito password reset with the emailed six-digit code.
 * Deliberately does NOT start a session — the visitor returns to sign-in and
 * proves the new password, exactly like the native token-based flow.
 */
export async function POST(request: NextRequest) {
  if (!hasValidCsrfPair(request)) {
    return NextResponse.json({ error: "Invalid security token." }, { status: 403 });
  }
  const config = cognitoConfig();
  if (!config) {
    return NextResponse.json({ error: "Password reset is not configured." }, { status: 503 });
  }
  const body = await request.json().catch(() => null) as { email?: string; code?: string; password?: string } | null;
  const email = body?.email?.trim().toLowerCase() || "";
  const code = body?.code?.trim() || "";
  if (!email.includes("@") || !code || !body?.password) {
    return NextResponse.json({ error: "Enter the code from your email and a new password." }, { status: 400 });
  }
  try {
    await confirmForgotPassword(config, email, code, body.password);
    return NextResponse.json({ message: "Your password has been updated. You can now sign in." });
  } catch (reason) {
    if (reason instanceof CognitoError) {
      const status = reason.code === "CodeMismatchException" || reason.code === "ExpiredCodeException" ? 422 : 400;
      return NextResponse.json({ error: reason.message }, { status });
    }
    throw reason;
  }
}
