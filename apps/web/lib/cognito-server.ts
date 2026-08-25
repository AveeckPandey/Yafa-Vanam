import "server-only";

import { createHmac, createPublicKey, verify } from "node:crypto";
import type { NormalizedSignUpProfile } from "./cognito-shared";

export type CognitoUser = {
  id: string;
  name: string;
  email: string;
  /**
   * The pool's actual username claim (cognito:username). This — not the
   * email alias — is the identity Cognito expects inside a refresh-token
   * SECRET_HASH for every sign-in configuration.
   */
  username: string;
};

export type CognitoConfig = {
  region: string;
  userPoolId: string;
  clientId: string;
  clientSecret: string;
  issuer: string;
  /**
   * Which identity Cognito expects inside the refresh-token SECRET_HASH for
   * this pool's sign-in configuration. "username_claim" fits pools where
   * users sign in with their username (including email-as-username);
   * "sub" is required for pools using email/phone aliases, where the
   * permanent username differs from the sign-in identifier.
   */
  refreshUsernameSource: "username_claim" | "sub";
};

const REFRESH_USERNAME_SOURCES = ["username_claim", "sub"] as const;

export type TokenSet = {
  IdToken?: string;
  AccessToken?: string;
  RefreshToken?: string;
  ExpiresIn?: number;
};

/** Error thrown by every Cognito call; message is always visitor-safe. */
export class CognitoError extends Error {
  constructor(
    public readonly code: string,
    message: string,
    public readonly meta?: Record<string, unknown>,
  ) {
    super(message);
    this.name = "CognitoError";
  }
}

type JwtHeader = { alg?: string; kid?: string };
type JwtClaims = {
  sub?: string;
  email?: string;
  name?: string;
  given_name?: string;
  email_verified?: boolean | string;
  "cognito:username"?: string;
  aud?: string;
  iss?: string;
  exp?: number;
  token_use?: string;
};

// The username cookie stores the pool username claim taken from the verified
// id_token (email alias or pool-native id), so the refresh flow can compute
// its SecretHash with Cognito's expected identity even after the id_token
// cookie has expired. The remember cookie preserves the visitor's original
// "remember me" choice so refreshes never extend a session they did not ask
// to keep. Cleared together at logout.
export const cookieNames = {
  access: "yafa_cognito_access",
  id: "yafa_cognito_id",
  refresh: "yafa_cognito_refresh",
  username: "yafa_cognito_username",
  remember: "yafa_cognito_remember",
} as const;

const jwks = new Map<string, { expiresAt: number; keys: Map<string, JsonWebKey> }>();

function required(name: string) {
  return process.env[name]?.trim() || "";
}

/**
 * Server-side truth about which auth system this deployment runs. Never trust
 * NEXT_PUBLIC_AUTH_PROVIDER alone — build-time env can drift from runtime
 * configuration, which is how dead buttons happen.
 */
export function cognitoProvider(): "cognito" | "native" {
  return cognitoConfig() ? "cognito" : "native";
}

export function cognitoConfig(): CognitoConfig | null {
  const region = required("COGNITO_REGION");
  const userPoolId = required("COGNITO_USER_POOL_ID");
  const clientId = required("COGNITO_CLIENT_ID");
  const clientSecret = required("COGNITO_CLIENT_SECRET");
  if (!region || !userPoolId || !clientId || !clientSecret) return null;
  // An unrecognized value must disable Cognito mode entirely (the capability
  // endpoint then reports "native") rather than guess and break refreshes.
  const sourceSetting = required("COGNITO_REFRESH_USERNAME_SOURCE") || "username_claim";
  if (!(REFRESH_USERNAME_SOURCES as readonly string[]).includes(sourceSetting)) return null;
  return {
    region,
    userPoolId,
    clientId,
    clientSecret,
    issuer: `https://cognito-idp.${region}.amazonaws.com/${userPoolId}`,
    refreshUsernameSource: sourceSetting as CognitoConfig["refreshUsernameSource"],
  };
}

export function safeReturnTo(value: string | null | undefined, fallback = "/account") {
  return value && value.startsWith("/") && !value.startsWith("//") ? value : fallback;
}

function secretHash(config: CognitoConfig, username: string) {
  return createHmac("sha256", config.clientSecret).update(`${username}${config.clientId}`).digest("base64");
}

/**
 * The identity Cognito expects inside a REFRESH_TOKEN_AUTH SECRET_HASH. Alias
 * pools require the immutable sub; username-sign-in pools expect the
 * cognito:username claim. Chosen per deployment via COGNITO_REFRESH_USERNAME_SOURCE.
 */
export function secretHashUsername(config: CognitoConfig, user: Pick<CognitoUser, "id" | "username">): string {
  return config.refreshUsernameSource === "sub" ? user.id : user.username;
}

const FRIENDLY_ERRORS: Record<string, string> = {
  NotAuthorizedException: "Incorrect email or password.",
  UserNotConfirmedException: "Please verify your email to finish signing in.",
  UserNotFoundException: "No account matches that email.",
  UsernameExistsException: "An account with this email already exists. Try signing in instead.",
  InvalidPasswordException: "Passwords need at least 8 characters, including numbers and symbols where required.",
  InvalidParameterException: "Some details look off. Please check them and try again.",
  CodeMismatchException: "That verification code is incorrect. Please check the latest email and try again.",
  ExpiredCodeException: "That code has expired. Request a new one and try again.",
  TooManyFailedAttemptsException: "Too many attempts. Please wait a moment before trying again.",
  LimitExceededException: "Too many attempts. Please wait a moment before trying again.",
  TooManyRequestsException: "Too many requests. Please wait a moment before trying again.",
  PasswordResetRequiredException: "For your security, please reset your password before signing in.",
  EnableSoftwareTokenMFAException: "Multi-factor sign-in is not supported here yet. Please contact support.",
};

async function cognitoInvoke<T>(config: CognitoConfig, operation: string, payload: Record<string, unknown>): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`https://cognito-idp.${config.region}.amazonaws.com/`, {
      method: "POST",
      cache: "no-store",
      headers: {
        "Content-Type": "application/x-amz-json-1.1",
        "X-Amz-Target": `AWSCognitoIdentityProviderService.${operation}`,
      },
      body: JSON.stringify(payload),
    });
  } catch {
    throw new CognitoError("NetworkError", "Sign-in is temporarily unavailable. Please try again shortly.");
  }
  const body = await response.json().catch(() => ({}) as Record<string, unknown>);
  if (!response.ok) {
    // Cognito reports failures as __type: "Namespace#ExceptionName".
    const rawType = String(body.__type || body.code || "");
    const code = rawType.split("#").pop() || "UnknownError";
    throw new CognitoError(code, FRIENDLY_ERRORS[code] || "We could not complete that request. Please try again.", { detail: body.message });
  }
  return body as T;
}

function authParams(config: CognitoConfig, username: string, password: string) {
  return { USERNAME: username, PASSWORD: password, SECRET_HASH: secretHash(config, username) };
}

/**
 * Creates the pool account with the exact standard attribute names the user
 * pool requires. Callers must pass a profile already normalized through
 * validateSignUpProfile(); this layer never logs attribute values.
 */
export async function signUp(config: CognitoConfig, profile: NormalizedSignUpProfile, password: string) {
  return cognitoInvoke<{ UserSub: string }>(config, "SignUp", {
    ClientId: config.clientId,
    Username: profile.email,
    Password: password,
    SecretHash: secretHash(config, profile.email),
    UserAttributes: [
      { Name: "email", Value: profile.email },
      { Name: "given_name", Value: profile.givenName },
      { Name: "gender", Value: profile.gender },
      { Name: "birthdate", Value: profile.birthDate },
    ],
  });
}

export async function confirmSignUp(config: CognitoConfig, email: string, code: string) {
  return cognitoInvoke<Record<string, never>>(config, "ConfirmSignUp", {
    ClientId: config.clientId,
    Username: email,
    ConfirmationCode: code,
    SecretHash: secretHash(config, email),
    ForceAliasCreation: false,
  });
}

export async function resendConfirmationCode(config: CognitoConfig, email: string) {
  return cognitoInvoke<Record<string, never>>(config, "ResendConfirmationCode", {
    ClientId: config.clientId,
    Username: email,
    SecretHash: secretHash(config, email),
  });
}

export async function signIn(config: CognitoConfig, email: string, password: string): Promise<TokenSet> {
  const result = await cognitoInvoke<{ AuthenticationResult?: TokenSet; ChallengeName?: string }>(config, "InitiateAuth", {
    AuthFlow: "USER_PASSWORD_AUTH",
    ClientId: config.clientId,
    AuthParameters: authParams(config, email, password),
  });
  if (!result.AuthenticationResult?.IdToken) {
    throw new CognitoError(
      "UnsupportedChallenge",
      result.ChallengeName === "NEW_PASSWORD_REQUIRED"
        ? "This account needs a password update before it can be used here. Please reset your password."
        : "We could not complete that request. Please try again.",
    );
  }
  return result.AuthenticationResult;
}

export async function forgotPassword(config: CognitoConfig, email: string) {
  return cognitoInvoke<Record<string, never>>(config, "ForgotPassword", {
    ClientId: config.clientId,
    Username: email,
    SecretHash: secretHash(config, email),
  });
}

export async function confirmForgotPassword(config: CognitoConfig, email: string, code: string, password: string) {
  return cognitoInvoke<Record<string, never>>(config, "ConfirmForgotPassword", {
    ClientId: config.clientId,
    Username: email,
    ConfirmationCode: code,
    Password: password,
    SecretHash: secretHash(config, email),
  });
}

export async function refreshTokens(config: CognitoConfig, username: string, refreshToken: string): Promise<TokenSet> {
  const result = await cognitoInvoke<{ AuthenticationResult?: TokenSet }>(config, "InitiateAuth", {
    AuthFlow: "REFRESH_TOKEN_AUTH",
    ClientId: config.clientId,
    AuthParameters: {
      REFRESH_TOKEN: refreshToken,
      // The username is the pool username claim persisted from the verified
      // id_token — Cognito's expected SECRET_HASH identity for every sign-in
      // configuration. Session identity always comes from verified tokens.
      SECRET_HASH: secretHash(config, username),
    },
  });
  if (!result.AuthenticationResult?.IdToken) throw new CognitoError("ExpiredSession", "Your session has expired.");
  return result.AuthenticationResult;
}

/** Best-effort revocation: GlobalSignOut via access token, falling back to RevokeToken via refresh token. */
export async function revokeSession(config: CognitoConfig, accessToken?: string, refreshToken?: string) {
  if (accessToken) {
    try {
      await cognitoInvoke<Record<string, never>>(config, "GlobalSignOut", { AccessToken: accessToken });
      return;
    } catch {
      // Fall through to RevokeToken below.
    }
  }
  if (refreshToken) {
    await cognitoInvoke<Record<string, never>>(config, "RevokeToken", {
      ClientId: config.clientId,
      ClientSecret: config.clientSecret,
      Token: refreshToken,
    }).catch(() => undefined);
  }
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
  // Mirrors the Go bridge: only an explicitly verified address may open a
  // session. Cognito issues booleans; some admin flows emit string forms.
  const emailVerified = claims.email_verified === true || claims.email_verified === "true";
  if (!emailVerified) throw new Error("Cognito account email is not verified.");
  const jwk = await keyFor(config, header.kid);
  if (!jwk || !verify("RSA-SHA256", Buffer.from(`${encodedHeader}.${encodedClaims}`), createPublicKey({ key: jwk, format: "jwk" }), Buffer.from(encodedSignature || "", "base64url"))) throw new Error("Invalid Cognito session.");
  // Display name prefers the full name claim, then falls back to given_name —
  // pools collecting only the new required attributes have no name claim.
  const name = claims.name || claims.given_name || claims["cognito:username"] || claims.email;
  return {
    id: claims.sub,
    email: claims.email,
    name,
    username: claims["cognito:username"] || claims.sub!,
  };
}
