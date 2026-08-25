import { NextRequest, NextResponse } from "next/server";
import { CognitoError, cognitoConfig, resendConfirmationCode } from "@/lib/cognito-server";
import { hasValidCsrfPair } from "@/lib/auth-bridge";

// The response is deliberately identical whether or not the account exists,
// so the endpoint cannot be used to probe registrations.
const ACCEPTED_MESSAGE = "If that account still needs verifying, a new code is on its way.";

export async function POST(request: NextRequest) {
  if (!hasValidCsrfPair(request)) {
    return NextResponse.json({ error: "Invalid security token." }, { status: 403 });
  }
  const config = cognitoConfig();
  if (!config) {
    return NextResponse.json({ error: "Secure sign-up is not configured." }, { status: 503 });
  }
  const body = await request.json().catch(() => null) as { email?: string } | null;
  const email = body?.email?.trim().toLowerCase() || "";
  if (!email.includes("@")) {
    return NextResponse.json({ error: "Enter your email address." }, { status: 400 });
  }
  try {
    await resendConfirmationCode(config, email);
    return NextResponse.json({ message: ACCEPTED_MESSAGE });
  } catch (reason) {
    // Throttling surfaces a real problem; everything else keeps the generic
    // accepted response so retries reveal nothing about account state.
    if (reason instanceof CognitoError && (reason.code === "LimitExceededException" || reason.code === "TooManyRequestsException")) {
      return NextResponse.json({ error: reason.message }, { status: 429 });
    }
    return NextResponse.json({ message: ACCEPTED_MESSAGE });
  }
}
