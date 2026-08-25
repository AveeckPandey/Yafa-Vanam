import "server-only";

import { cookieNames, type TokenSet } from "./cognito-server";

/**
 * Cookie lifecycle shared by every /api/auth/cognito route.
 *
 * MaxAge equals token validity so an expired cookie simply disappears from
 * the browser: the Go API relies on that property for lazy healing of the
 * commerce session (an absent yafa_access cookie means "stale", never
 * "signed out"), and this side mirrors it.
 */
const HOUR = 60 * 60;
const DAY = 24 * HOUR;

function baseAttributes(maxAge: number) {
  // Secure mirrors the native auth service's production-only flag.
  const secure = process.env.NODE_ENV === "production";
  return ` Path=/; HttpOnly;${secure ? " Secure;" : ""} SameSite=Lax; Max-Age=${maxAge}`;
}

/**
 * Appends the Cognito cookie family onto a Headers object (route handlers
 * may only export HTTP verbs, so responses are assembled at the very end).
 * JWT values are base64url+dots and emails are pre-encoded — both are safe
 * raw Set-Cookie values.
 */
export function setCognitoSessionCookies(headers: Headers, tokens: TokenSet, username: string, remember: boolean) {
  const refreshMaxAge = remember ? 30 * DAY : DAY;
  headers.append("set-cookie", `${cookieNames.id}=${tokens.IdToken ?? ""};${baseAttributes(HOUR)}`);
  headers.append("set-cookie", `${cookieNames.access}=${tokens.AccessToken ?? ""};${baseAttributes(HOUR)}`);
  if (tokens.RefreshToken) {
    headers.append("set-cookie", `${cookieNames.refresh}=${tokens.RefreshToken};${baseAttributes(refreshMaxAge)}`);
  }
  // Non-sensitive (the pool already knows it) but kept HttpOnly anyway; feeds
  // the SecretHash on refresh after the id_token cookie is long gone.
  headers.append("set-cookie", `${cookieNames.username}=${encodeURIComponent(username)};${baseAttributes(refreshMaxAge)}`);
  // "1"/"0" companion with the same lifetime as the refresh cookie so the
  // original remember-me choice survives token refreshes verbatim instead of
  // being silently upgraded to the 30-day horizon.
  headers.append("set-cookie", `${cookieNames.remember}=${remember ? "1" : "0"};${baseAttributes(refreshMaxAge)}`);
}

export function clearCognitoCookies(headers: Headers) {
  for (const name of Object.values(cookieNames)) {
    headers.append("set-cookie", `${name}=;${baseAttributes(-1)}`);
  }
}
