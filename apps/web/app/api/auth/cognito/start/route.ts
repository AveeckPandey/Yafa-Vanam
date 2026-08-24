import { NextRequest, NextResponse } from "next/server";
import { authorizeUrl, cognitoConfig, cookieNames, randomUrlSafe, safeReturnTo } from "@/lib/cognito-server";

export async function GET(request: NextRequest) {
  const config = cognitoConfig();
  if (!config || process.env.NEXT_PUBLIC_AUTH_PROVIDER !== "cognito") return NextResponse.json({ error: "Cognito authentication is not configured." }, { status: 503 });
  const requestedMode = request.nextUrl.searchParams.get("mode");
  const mode = requestedMode === "signup" || requestedMode === "forgot" ? requestedMode : "signin";
  const state = randomUrlSafe();
  const verifier = randomUrlSafe(48);
  const response = NextResponse.redirect(authorizeUrl(config, mode, state, verifier, request.nextUrl.searchParams.get("identity_provider")));
  const cookieOptions = { httpOnly: true, secure: process.env.NODE_ENV === "production", sameSite: "lax" as const, path: "/api/auth/cognito", maxAge: 60 * 10 };
  response.cookies.set(cookieNames.state, state, cookieOptions);
  response.cookies.set(cookieNames.verifier, verifier, cookieOptions);
  response.cookies.set(cookieNames.returnTo, safeReturnTo(request.nextUrl.searchParams.get("return_to")), cookieOptions);
  return response;
}
