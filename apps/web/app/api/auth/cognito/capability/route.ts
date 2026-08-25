import { NextResponse } from "next/server";
import { cognitoProvider } from "@/lib/cognito-server";

/**
 * Server-side truth about which auth system this deployment runs. The client
 * must branch on THIS, never on NEXT_PUBLIC_AUTH_PROVIDER alone — build-time
 * env can drift from runtime configuration (a pool misconfigured on Vercel
 * would otherwise render sign-in buttons that go nowhere).
 */
export function GET() {
  return NextResponse.json({ provider: cognitoProvider() });
}
