import { NextResponse } from "next/server";

// Companion to the removed hosted-UI start route (see ../start/route.ts):
// there is no authorization code to exchange any more, so report Gone.
export async function GET() {
  return NextResponse.json(
    { error: "Hosted Cognito sign-in was removed; use the built-in sign-in form." },
    { status: 410 },
  );
}
