import { NextRequest, NextResponse } from "next/server";
import { CognitoError, cognitoConfig, forgotPassword } from "@/lib/cognito-server";
import { hasValidCsrfPair } from "@/lib/auth-bridge";

// Identical response regardless of account state, so the endpoint cannot
// probe which emails are registered — mirroring the native reset request.
const ACCEPTED_MESSAGE = "If an account matches that email, a verification code will arrive shortly.";

export async function POST(request: NextRequest) {
  if (!hasValidCsrfPair(request)) {
    return NextResponse.json({ error: "Invalid security token." }, { status: 403 });
  }
  const config = cognitoConfig();
  if (!config) {
    return NextResponse.json({ error: "Password reset is not configured." }, { status: 503 });
  }
  const body = await request.json().catch(() => null) as { email?: string } | null;
  const email = body?.email?.trim().toLowerCase() || "";
  if (!email.includes("@")) {
    return NextResponse.json({ error: "Enter your email address." }, { status: 400 });
  }
  try {
    await forgotPassword(config, email);
    return NextResponse.json({ message: ACCEPTED_MESSAGE });
  } catch (reason) {
    if (reason instanceof CognitoError && (reason.code === "LimitExceededException" || reason.code === "TooManyRequestsException")) {
      return NextResponse.json({ error: reason.message }, { status: 429 });
    }
    // NotAuthorizedException for unconfirmed accounts still means "code sent
    // to a real address", but revealing that distinction buys nothing here.
    return NextResponse.json({ message: ACCEPTED_MESSAGE });
  }
}
