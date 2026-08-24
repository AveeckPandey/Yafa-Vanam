import { NextRequest, NextResponse } from "next/server";
import { cognitoConfig, cookieNames, exchangeCode, safeReturnTo } from "@/lib/cognito-server";

const sessionCookie = { httpOnly: true, secure: process.env.NODE_ENV === "production", sameSite: "lax" as const, path: "/", maxAge: 60 * 60 };

export async function GET(request: NextRequest) {
  const config = cognitoConfig();
  const code = request.nextUrl.searchParams.get("code");
  const state = request.nextUrl.searchParams.get("state");
  const savedState = request.cookies.get(cookieNames.state)?.value;
  const verifier = request.cookies.get(cookieNames.verifier)?.value;
  const returnTo = safeReturnTo(request.cookies.get(cookieNames.returnTo)?.value);
  if (!config || process.env.NEXT_PUBLIC_AUTH_PROVIDER !== "cognito" || !code || !state || !verifier || state !== savedState) return NextResponse.redirect(new URL("/auth/sign-in?error=cognito", request.url));
  try {
    const tokens = await exchangeCode(config, code, verifier);
    const response = NextResponse.redirect(new URL(returnTo, request.url));
    response.cookies.set(cookieNames.id, tokens.id_token, sessionCookie);
    response.cookies.set(cookieNames.access, tokens.access_token, sessionCookie);
    if (tokens.refresh_token) response.cookies.set(cookieNames.refresh, tokens.refresh_token, { ...sessionCookie, maxAge: 60 * 60 * 24 * 30 });
    response.cookies.set(cookieNames.state, "", { path: "/api/auth/cognito", maxAge: 0 });
    response.cookies.set(cookieNames.verifier, "", { path: "/api/auth/cognito", maxAge: 0 });
    response.cookies.set(cookieNames.returnTo, "", { path: "/api/auth/cognito", maxAge: 0 });
    return response;
  } catch {
    return NextResponse.redirect(new URL("/auth/sign-in?error=cognito", request.url));
  }
}
