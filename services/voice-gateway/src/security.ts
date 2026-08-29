import { createHmac, timingSafeEqual } from "node:crypto";

export type GatewayClaims = {
  aud: string;
  exp: number;
  iat: number;
  jti: string;
  sub: string;
};

export class GatewayAuthError extends Error {
  constructor(message = "unauthorized") {
    super(message);
    this.name = "GatewayAuthError";
  }
}

function signature(payload: string, secret: string): Buffer {
  return createHmac("sha256", secret).update(payload).digest();
}

export function verifyGatewayToken(
  token: unknown,
  secret: string,
  audience: string,
  nowSeconds = Math.floor(Date.now() / 1000),
): GatewayClaims {
  if (typeof token !== "string" || token.length > 4096 || secret.length < 32) {
    throw new GatewayAuthError();
  }
  const parts = token.split(".");
  if (parts.length !== 2 || !parts[0] || !parts[1]) throw new GatewayAuthError();

  let supplied: Buffer;
  let claims: GatewayClaims;
  try {
    supplied = Buffer.from(parts[1], "base64url");
    claims = JSON.parse(Buffer.from(parts[0], "base64url").toString("utf8")) as GatewayClaims;
  } catch {
    throw new GatewayAuthError();
  }
  const expected = signature(parts[0], secret);
  if (supplied.length !== expected.length || !timingSafeEqual(supplied, expected)) {
    throw new GatewayAuthError();
  }
  if (
    !claims || claims.aud !== audience || typeof claims.sub !== "string" ||
    !claims.sub.trim() || claims.sub.length > 128 || typeof claims.jti !== "string" ||
    claims.jti.length < 8 || claims.jti.length > 128 ||
    !Number.isInteger(claims.iat) || !Number.isInteger(claims.exp) ||
    claims.iat > nowSeconds + 30 || claims.exp <= nowSeconds ||
    claims.exp - claims.iat > 5 * 60
  ) {
    throw new GatewayAuthError();
  }
  return claims;
}

type Counter = { count: number; resetAt: number };

/** In-memory limiter for a single gateway process. ALB/WAF remains the outer limit. */
export class FixedWindowRateLimiter {
  private readonly counters = new Map<string, Counter>();

  constructor(private readonly limit: number, private readonly windowMs: number) {}

  allow(key: string, now = Date.now()): boolean {
    const existing = this.counters.get(key);
    if (!existing || existing.resetAt <= now) {
      this.counters.set(key, { count: 1, resetAt: now + this.windowMs });
      this.prune(now);
      return true;
    }
    if (existing.count >= this.limit) return false;
    existing.count += 1;
    return true;
  }

  private prune(now: number): void {
    if (this.counters.size < 10_000) return;
    for (const [key, value] of this.counters) {
      if (value.resetAt <= now) this.counters.delete(key);
    }
  }
}

const PROMPT_INJECTION_PATTERNS = [
  /\bignore (all |any )?(previous|prior|system|developer)( (system|developer))? (instructions?|prompts?|rules?)\b/i,
  /\b(reveal|repeat|print|show|leak|expose) (the |your )?(system|developer|hidden) (prompt|instructions?)\b/i,
  /\b(disable|bypass|override|remove) (the |your )?(safety|guardrails?|restrictions?)\b/i,
  /\bact as (dan|an unrestricted|a system administrator)\b/i,
  /\b(exfiltrate|dump) (credentials?|secrets?|tokens?|environment variables?)\b/i,
];

export function validateCustomerText(value: unknown, maxLength: number): string | null {
  if (typeof value !== "string") return null;
  const text = value.trim();
  if (!text || text.length > maxLength) return null;
  if (PROMPT_INJECTION_PATTERNS.some((pattern) => pattern.test(text))) return null;
  return text;
}

export function clientAddress(handshakeAddress: unknown, forwardedFor: unknown): string {
  const forwarded = typeof forwardedFor === "string" ? forwardedFor.split(",")[0]?.trim() : "";
  const candidate = forwarded || (typeof handshakeAddress === "string" ? handshakeAddress.trim() : "");
  return candidate.slice(0, 128) || "unknown";
}
