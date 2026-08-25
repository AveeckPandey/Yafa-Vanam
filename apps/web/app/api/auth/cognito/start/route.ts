import { NextResponse } from "next/server";

// The Cognito hosted-UI redirect flow was removed in favour of the custom
// sign-in/sign-up forms (app/auth/* + /api/auth/cognito/{login,signup,...}).
// This path used to start the authorization-code dance; keep a loud 410 so
// stale links fail clearly instead of 404ing mysteriously.
export async function GET() {
  return NextResponse.json(
    { error: "Hosted Cognito sign-in was removed; use the built-in sign-in form." },
    { status: 410 },
  );
}
