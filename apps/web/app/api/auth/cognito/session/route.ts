import { NextRequest, NextResponse } from "next/server";
import { cognitoConfig, cookieNames, userFromIdToken } from "@/lib/cognito-server";

export async function GET(request: NextRequest) {
  const config = cognitoConfig();
  const token = request.cookies.get(cookieNames.id)?.value;
  if (!config || !token) return NextResponse.json({ error: "Not signed in." }, { status: 401 });
  try { return NextResponse.json({ user: await userFromIdToken(config, token) }); }
  catch { return NextResponse.json({ error: "Your session has expired." }, { status: 401 }); }
}
