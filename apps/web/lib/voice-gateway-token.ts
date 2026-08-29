import "server-only";

import { createHmac, randomUUID } from "node:crypto";

const audience = () => process.env.YAFA_VOICE_GATEWAY_TOKEN_AUDIENCE || "yafa-voice";
const signingSecret = () => process.env.YAFA_VOICE_GATEWAY_SIGNING_SECRET || "";

export function voiceGatewayPublicUrl(): string {
  const raw = (process.env.YAFA_VOICE_GATEWAY_PUBLIC_URL || "").trim();
  if (!raw) throw new Error("voice_gateway_not_configured");
  const url = new URL(raw);
  if (process.env.NODE_ENV === "production" && url.protocol !== "https:") {
    throw new Error("voice_gateway_requires_https");
  }
  if (url.protocol !== "https:" && url.protocol !== "http:") throw new Error("voice_gateway_url_invalid");
  return url.toString().replace(/\/$/, "");
}

export function createVoiceGatewayToken(subject: string, nowSeconds = Math.floor(Date.now() / 1000)) {
  const secret = signingSecret();
  if (secret.length < 32) throw new Error("voice_gateway_signing_not_configured");
  if (!subject || subject.length > 128) throw new Error("voice_gateway_subject_invalid");
  const expiresAt = nowSeconds + 120;
  const payload = Buffer.from(JSON.stringify({
    aud: audience(),
    exp: expiresAt,
    iat: nowSeconds,
    jti: randomUUID(),
    sub: subject,
  })).toString("base64url");
  const signature = createHmac("sha256", secret).update(payload).digest("base64url");
  return { token: `${payload}.${signature}`, expiresAt };
}
