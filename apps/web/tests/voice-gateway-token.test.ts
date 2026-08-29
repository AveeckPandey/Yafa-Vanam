import { strict as assert } from "node:assert";
import { createHmac } from "node:crypto";
import { afterEach, describe, it } from "node:test";

import { createVoiceGatewayToken, voiceGatewayPublicUrl } from "../lib/voice-gateway-token.ts";

const originalEnv = { ...process.env };
afterEach(() => {
  process.env = { ...originalEnv };
});

describe("voice gateway token", () => {
  it("mints a two-minute server-signed token without exposing the secret", () => {
    process.env.YAFA_VOICE_GATEWAY_SIGNING_SECRET = "v".repeat(32);
    process.env.YAFA_VOICE_GATEWAY_TOKEN_AUDIENCE = "yafa-voice";
    const result = createVoiceGatewayToken("customer-1", 1000);
    const [encoded, supplied] = result.token.split(".");
    const claims = JSON.parse(Buffer.from(encoded, "base64url").toString("utf8"));
    const expected = createHmac("sha256", "v".repeat(32)).update(encoded).digest("base64url");
    assert.equal(supplied, expected);
    assert.equal(claims.sub, "customer-1");
    assert.equal(claims.aud, "yafa-voice");
    assert.equal(result.expiresAt, 1120);
    assert.equal(result.token.includes("v".repeat(32)), false);
  });

  it("fails closed with a weak signing secret", () => {
    process.env.YAFA_VOICE_GATEWAY_SIGNING_SECRET = "short";
    assert.throws(() => createVoiceGatewayToken("customer-1"), /signing_not_configured/);
  });

  it("requires HTTPS for the production gateway", () => {
    Object.defineProperty(process.env, "NODE_ENV", { value: "production", configurable: true, writable: true });
    process.env.YAFA_VOICE_GATEWAY_PUBLIC_URL = "http://voice.example.test";
    assert.throws(() => voiceGatewayPublicUrl(), /requires_https/);
    process.env.YAFA_VOICE_GATEWAY_PUBLIC_URL = "https://voice.example.test/";
    assert.equal(voiceGatewayPublicUrl(), "https://voice.example.test");
  });
});
