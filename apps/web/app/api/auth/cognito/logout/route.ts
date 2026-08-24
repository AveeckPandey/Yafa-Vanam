import { NextRequest, NextResponse } from "next/server";
import { cognitoConfig, cookieNames } from "@/lib/cognito-server";

export async function POST(request: NextRequest) {
  const config = cognitoConfig();
  const response = NextResponse.json({ logoutUrl: config ? `${config.domain}/logout?${new URLSearchParams({ client_id: config.clientId, logout_uri: config.logoutUri })}` : "/" });
  for (const name of [cookieNames.access, cookieNames.id, cookieNames.refresh]) response.cookies.set(name, "", { path: "/", maxAge: 0 });
  for (const name of [cookieNames.state, cookieNames.verifier, cookieNames.returnTo]) response.cookies.set(name, "", { path: "/api/auth/cognito", maxAge: 0 });
  return response;
}
