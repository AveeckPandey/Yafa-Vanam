import { NextRequest, NextResponse } from "next/server";
import { CognitoError, cognitoConfig, signUp } from "@/lib/cognito-server";
import { hasValidCsrfPair } from "@/lib/auth-bridge";

export async function POST(request: NextRequest) {
  if (!hasValidCsrfPair(request)) {
    return NextResponse.json({ error: "Invalid security token." }, { status: 403 });
  }
  const config = cognitoConfig();
  if (!config) {
    return NextResponse.json({ error: "Secure sign-up is not configured." }, { status: 503 });
  }
  const body = await request.json().catch(() => null) as { name?: string; email?: string; password?: string } | null;
  const name = body?.name?.trim() || "";
  const email = body?.email?.trim().toLowerCase() || "";
  if (!name || !email.includes("@") || !body?.password || body.password.length < 8) {
    return NextResponse.json({ error: "Provide a name, valid email, and password of at least 8 characters." }, { status: 400 });
  }
  try {
    await signUp(config, name, email, body.password);
    // No session yet: the visitor must confirm the emailed code first. The
    // welcome coupon is issued by the pool's PostConfirmation trigger at that
    // moment, never here.
    return NextResponse.json({ confirmationRequired: true, email });
  } catch (reason) {
    if (reason instanceof CognitoError) {
      return NextResponse.json({ error: reason.message }, { status: reason.code === "UsernameExistsException" ? 409 : 422 });
    }
    throw reason;
  }
}
