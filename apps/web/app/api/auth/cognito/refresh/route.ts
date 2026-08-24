import { NextRequest, NextResponse } from "next/server";
import { cognitoConfig, cookieNames, refreshSession } from "@/lib/cognito-server";

export async function POST(request: NextRequest) {
  const config = cognitoConfig();
  const refreshToken = request.cookies.get(cookieNames.refresh)?.value;
  if (!config || !refreshToken) return NextResponse.json({ error: "Your session has expired." }, { status: 401 });
  try {
    const tokens = await refreshSession(config, refreshToken);
    const response = NextResponse.json({ refreshed: true });
    const options = { httpOnly: true, secure: process.env.NODE_ENV === "production", sameSite: "lax" as const, path: "/", maxAge: 60 * 60 };
    response.cookies.set(cookieNames.id, tokens.id_token, options);
    response.cookies.set(cookieNames.access, tokens.access_token, options);
    return response;
  } catch { return NextResponse.json({ error: "Your session has expired." }, { status: 401 }); }
}
