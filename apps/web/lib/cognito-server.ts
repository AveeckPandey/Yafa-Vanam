import "server-only";

import { createHash, createPublicKey, randomBytes, verify } from "node:crypto";

export type CognitoUser = { id: string; name: string; email: string };

type CognitoConfig = {
  clientId: string;
  domain: string;
  issuer: string;
  redirectUri: string;
  logoutUri: string;
};

type TokenSet = { access_token?: string; id_token?: string; refresh_token?: string; error?: string; error_description?: string };
type JwtHeader = { alg?: string; kid?: string };
type JwtClaims = { sub?: string; email?: string; name?: string; "cognito:username"?: string; aud?: string; iss?: string; exp?: number; token_use?: string };

const cookieNames = {
  access: "yafa_cognito_access",
  id: "yafa_cognito_id",
  refresh: "yafa_cognito_refresh",
  state: "yafa_cognito_state",
  verifier: "yafa_cognito_verifier",
  returnTo: "yafa_cognito_return_to",
} as const;

const jwks = new Map<string, { expiresAt: number; keys: Map<string, JsonWebKey> }>();

function required(name: string) {
  return process.env[name]?.trim() || "";
}

export function cognitoConfig(): CognitoConfig | null {
  const region = required("COGNITO_REGION");
  const userPoolId = required("COGNITO_USER_POOL_ID");
  const clientId = required("COGNITO_CLIENT_ID");
  const domain = required("COGNITO_DOMAIN").replace(/\/$/, "");
  const redirectUri = required("COGNITO_REDIRECT_URI");
  const logoutUri = required("COGNITO_LOGOUT_URI");
  if (!region || !userPoolId || !clientId || !domain || !redirectUri || !logoutUri) return null;
  return {
    clientId,
    domain: domain.startsWith("https://") ? domain : `https://${domain}`,
    issuer: `https://cognito-idp.${region}.amazonaws.com/${userPoolId}`,
    redirectUri,
    logoutUri,
  };
}

export function isCognitoEnabled() {
  return process.env.NEXT_PUBLIC_AUTH_PROVIDER === "cognito" && cognitoConfig() !== null;
}

export function randomUrlSafe(bytes = 32) {
  return randomBytes(bytes).toString("base64url");
}

export function codeChallenge(verifier: string) {
  return createHash("sha256").update(verifier).digest("base64url");
}

export function safeReturnTo(value: string | null | undefined) {
  return value && value.startsWith("/") && !value.startsWith("//") ? value : "/account";
}

export function authorizeUrl(config: CognitoConfig, mode: "signin" | "signup" | "forgot", state: string, verifier: string, identityProvider?: string | null) {
  const path = mode === "signup" ? "/signup" : mode === "forgot" ? "/forgotPassword" : "/login";
  const params = new URLSearchParams({
    client_id: config.clientId,
    response_type: "code",
    scope: "openid email profile",
    redirect_uri: config.redirectUri,
    state,
    code_challenge: codeChallenge(verifier),
    code_challenge_method: "S256",
  });
  if (identityProvider && mode === "signin") params.set("identity_provider", identityProvider);
  return `${config.domain}${path}?${params}`;
}

export async function exchangeCode(config: CognitoConfig, code: string, verifier: string) {
  const response = await fetch(`${config.domain}/oauth2/token`, {
    method: "POST",
    cache: "no-store",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({ grant_type: "authorization_code", client_id: config.clientId, code, redirect_uri: config.redirectUri, code_verifier: verifier }),
  });
  const payload = await response.json().catch(() => ({})) as TokenSet;
  if (!response.ok || !payload.id_token || !payload.access_token) throw new Error(payload.error_description || "Cognito could not complete sign-in.");
  return payload as Required<Pick<TokenSet, "access_token" | "id_token">> & TokenSet;
}

export async function refreshSession(config: CognitoConfig, refreshToken: string) {
  const response = await fetch(`${config.domain}/oauth2/token`, {
    method: "POST",
    cache: "no-store",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({ grant_type: "refresh_token", client_id: config.clientId, refresh_token: refreshToken }),
  });
  const payload = await response.json().catch(() => ({})) as TokenSet;
  if (!response.ok || !payload.id_token || !payload.access_token) throw new Error(payload.error_description || "Your session has expired.");
  return payload as Required<Pick<TokenSet, "access_token" | "id_token">> & TokenSet;
}

function decodePart<T>(encoded: string): T | null {
  try { return JSON.parse(Buffer.from(encoded, "base64url").toString("utf8")) as T; } catch { return null; }
}

async function keyFor(config: CognitoConfig, kid: string) {
  const known = jwks.get(config.issuer);
  if (known && known.expiresAt > Date.now() && known.keys.has(kid)) return known.keys.get(kid)!;
  const response = await fetch(`${config.issuer}/.well-known/jwks.json`, { cache: "no-store" });
  const payload = await response.json().catch(() => null) as { keys?: Array<JsonWebKey & { kid?: string }> } | null;
  if (!response.ok || !payload?.keys) throw new Error("Cognito signing keys are unavailable.");
  const keys = new Map<string, JsonWebKey>(
    payload.keys
      .filter((key): key is JsonWebKey & { kid: string } => Boolean(key.kid))
      .map((key) => [key.kid, key]),
  );
  jwks.set(config.issuer, { keys, expiresAt: Date.now() + 60 * 60 * 1000 });
  return keys.get(kid);
}

export async function userFromIdToken(config: CognitoConfig, token: string): Promise<CognitoUser> {
  const [encodedHeader, encodedClaims, encodedSignature, ...extra] = token.split(".");
  const header = decodePart<JwtHeader>(encodedHeader || "");
  const claims = decodePart<JwtClaims>(encodedClaims || "");
  if (extra.length || !header?.kid || header.alg !== "RS256" || !claims?.sub || !claims.email || claims.iss !== config.issuer || claims.aud !== config.clientId || claims.token_use !== "id" || !claims.exp || claims.exp * 1000 <= Date.now()) throw new Error("Invalid Cognito session.");
  const jwk = await keyFor(config, header.kid);
  if (!jwk || !verify("RSA-SHA256", Buffer.from(`${encodedHeader}.${encodedClaims}`), createPublicKey({ key: jwk, format: "jwk" }), Buffer.from(encodedSignature || "", "base64url"))) throw new Error("Invalid Cognito session.");
  return { id: claims.sub, email: claims.email, name: claims.name || claims["cognito:username"] || claims.email };
}

export { cookieNames };
