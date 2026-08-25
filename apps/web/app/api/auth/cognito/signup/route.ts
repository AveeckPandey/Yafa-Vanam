import { NextRequest, NextResponse } from "next/server";
import { CognitoError, cognitoConfig, signUp } from "@/lib/cognito-server";
import { hasValidCsrfPair } from "@/lib/auth-bridge";
import { validateSignUpProfile } from "@/lib/cognito-shared";

export async function POST(request: NextRequest) {
  if (!hasValidCsrfPair(request)) {
    return NextResponse.json({ error: "Invalid security token." }, { status: 403 });
  }
  const config = cognitoConfig();
  if (!config) {
    return NextResponse.json({ error: "Secure sign-up is not configured." }, { status: 503 });
  }
  const body = await request.json().catch(() => null) as Record<string, unknown> | null;
  const profile = validateSignUpProfile(body);
  if (!profile.ok) {
    return NextResponse.json({ error: profile.error }, { status: 400 });
  }
  const password = typeof body?.password === "string" ? body.password : "";
  if (password.length < 8) {
    return NextResponse.json({ error: "Provide a valid email and password of at least 8 characters." }, { status: 400 });
  }
  try {
    await signUp(config, profile.profile, password);
    // No session yet: the visitor must confirm the emailed code first. The
    // welcome coupon is issued by the pool's PostConfirmation trigger at that
    // moment, never here. Attribute values are never logged.
    return NextResponse.json({ confirmationRequired: true, email: profile.profile.email });
  } catch (reason) {
    if (reason instanceof CognitoError) {
      return NextResponse.json({ error: reason.message }, { status: reason.code === "UsernameExistsException" ? 409 : 422 });
    }
    throw reason;
  }
}
