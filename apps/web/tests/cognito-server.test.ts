import { strict as assert } from "node:assert";
import { createServer, type Server } from "node:http";
import { createSign, generateKeyPairSync } from "node:crypto";
import { after, describe, it } from "node:test";
import { signUp, userFromIdToken, secretHashUsername, cognitoConfig, type CognitoConfig, type TokenSet } from "../lib/cognito-server.ts";

const config: CognitoConfig = {
  region: "ap-south-1",
  userPoolId: "ap-south-1_TESTPOOL",
  clientId: "test-client-id",
  clientSecret: "test-client-secret",
  issuer: "placeholder",
  refreshUsernameSource: "username_claim",
};

const profile = {
  givenName: "Ada",
  email: "shopper@example.com",
  gender: "prefer_not_to_say",
  birthDate: "1994-06-15",
} as const;

describe("signUp", () => {
  it("sends exactly the four required standard attributes with Cognito's names", async () => {
    const captured: Array<{ url: string; init: RequestInit }> = [];
    const originalFetch = globalThis.fetch;
    globalThis.fetch = (async (url: string | URL | Request, init?: RequestInit) => {
      captured.push({ url: String(url), init: init ?? {} });
      return new Response(JSON.stringify({ UserSub: "new-sub" }), { status: 200 });
    }) as typeof fetch;
    try {
      await signUp(config, profile, "sup3r-Secret!pw");
    } finally {
      globalThis.fetch = originalFetch;
    }

    assert.equal(captured.length, 1);
    const body = JSON.parse(String(captured[0].init.body)) as {
      ClientId: string;
      Username: string;
      SecretHash: string;
      UserAttributes: Array<{ Name: string; Value: string }>;
    };
    assert.equal(captured[0].url, "https://cognito-idp.ap-south-1.amazonaws.com/");
    assert.equal(captured[0].init.headers && (captured[0].init.headers as Record<string, string>)["X-Amz-Target"], "AWSCognitoIdentityProviderService.SignUp");
    assert.equal(body.ClientId, config.clientId);
    assert.equal(body.Username, profile.email);
    assert.match(body.SecretHash, /^[A-Za-z0-9+/=]+$/);
    // Exact attribute contract: names and values, nothing legacy.
    assert.deepEqual(body.UserAttributes, [
      { Name: "email", Value: "shopper@example.com" },
      { Name: "given_name", Value: "Ada" },
      { Name: "gender", Value: "prefer_not_to_say" },
      { Name: "birthdate", Value: "1994-06-15" },
    ]);
    assert.ok(!body.UserAttributes.some((attribute) => attribute.Name === "name"));
  });
});

/** Minimal RS256 id_token builder mirroring what the pool signs. */
function makeJwksFixture() {
  const { privateKey, publicKey } = generateKeyPairSync("rsa", { modulusLength: 2048 });
  const jwk = publicKey.export({ format: "jwk" }) as { kty: string; n: string; e: string };
  const b64u = (input: string) => Buffer.from(input, "utf8").toString("base64url");
  return {
    privateKey,
    signIdToken(claims: Record<string, unknown>, kid = "test-kid") {
      const header = b64u(JSON.stringify({ alg: "RS256", typ: "JWT", kid }));
      const payload = b64u(JSON.stringify(claims));
      const signature = createSign("RSA-SHA256").update(`${header}.${payload}`).sign(privateKey);
      return `${header}.${payload}.${Buffer.from(signature).toString("base64url")}`;
    },
    serve(): Promise<{ server: Server; issuer: string }> {
      return new Promise((resolve) => {
        const server = createServer((_request, response) => {
          response.setHeader("content-type", "application/json");
          response.end(JSON.stringify({ keys: [{ kid: "test-kid", alg: "RS256", ...jwk }] }));
        });
        server.listen(0, "127.0.0.1", () => resolve({ server, issuer: `http://127.0.0.1:${(server.address() as { port: number }).port}` }));
      });
    },
  };
}

describe("userFromIdToken", () => {
  const fixture = makeJwksFixture();
  let localConfig: CognitoConfig;
  const baseClaims = (): Record<string, unknown> => ({
    iss: "",
    aud: config.clientId,
    token_use: "id",
    sub: "subject-1",
    email: "shopper@example.com",
    email_verified: true,
    iat: Math.floor(Date.now() / 1000),
    exp: Math.floor(Date.now() / 1000) + 300,
  });

  it("verifies a signed token against its JWKS keys", async () => {
    const { server, issuer } = await fixture.serve();
    localConfig = { ...config, issuer };
    after(() => server.close());
    const token = fixture.signIdToken({ ...baseClaims(), iss: issuer });
    const user = await userFromIdToken(localConfig, token);
    assert.equal(user.id, "subject-1");
    assert.equal(user.email, "shopper@example.com");
    assert.equal(user.username, "subject-1");
  });

  it("rejects ID tokens whose email is not verified — including a missing claim", async () => {
    for (const email_verified of [false, "false", undefined]) {
      const claims = baseClaims();
      if (email_verified === undefined) delete claims.email_verified;
      else claims.email_verified = email_verified;
      const token = fixture.signIdToken({ ...claims, iss: localConfig!.issuer });
      await assert.rejects(() => userFromIdToken(localConfig!, token), /not verified/);
    }
  });

  it("accepts Cognito's compatible string 'true' verification form", async () => {
    const token = fixture.signIdToken({ ...baseClaims(), iss: localConfig!.issuer, email_verified: "true" });
    await assert.doesNotReject(() => userFromIdToken(localConfig!, token));
  });

  it("maps given_name into the display name when no name claim exists", async () => {
    const withGivenName = fixture.signIdToken({
      ...baseClaims(), iss: localConfig!.issuer, name: undefined, given_name: "Ada", "cognito:username": "ada-1994",
    });
    assert.equal((await userFromIdToken(localConfig!, withGivenName)).name, "Ada");

    const usernameFallback = fixture.signIdToken({
      ...baseClaims(), iss: localConfig!.issuer, given_name: undefined, "cognito:username": "ada-1994",
    });
    assert.equal((await userFromIdToken(localConfig!, usernameFallback)).name, "ada-1994");

    const emailFallback = fixture.signIdToken({ ...baseClaims(), iss: localConfig!.issuer });
    assert.equal((await userFromIdToken(localConfig!, emailFallback)).name, "shopper@example.com");
  });

  it("prefers the pool username claim for refresh SECRET_HASH identity", async () => {
    const token = fixture.signIdToken({ ...baseClaims(), iss: localConfig!.issuer, "cognito:username": "pool-native-id" });
    const user = await userFromIdToken(localConfig!, token);
    assert.equal(user.username, "pool-native-id");
  });

  it("still rejects tampered or wrong-audience tokens", async () => {
    const valid = fixture.signIdToken({ ...baseClaims(), iss: localConfig!.issuer });
    const tampered = `${valid.slice(0, -3)}aaa`;
    await assert.rejects(() => userFromIdToken(localConfig!, tampered));
    const wrongAudience = fixture.signIdToken({ ...baseClaims(), iss: localConfig!.issuer, aud: "someone-else" });
    await assert.rejects(() => userFromIdToken(localConfig!, wrongAudience));
  });
});

// Type-level guard: TokenSet stays compatible with the session cookie writer.
const _tokens: TokenSet = {};
void _tokens;

describe("secretHashUsername", () => {
  const user = { id: "sub-uuid-1", username: "pool-native-or-alias" };
  const base = { ...config, issuer: "https://cognito-idp.ap-south-1.amazonaws.com/ap-south-1_P" };

  it("uses the username claim for username-sign-in pools", () => {
    assert.equal(secretHashUsername({ ...base, refreshUsernameSource: "username_claim" }, user), "pool-native-or-alias");
  });

  it("requires the sub for alias-based pools", () => {
    assert.equal(secretHashUsername({ ...base, refreshUsernameSource: "sub" }, user), "sub-uuid-1");
  });
});

describe("cognitoConfig refresh identity parsing", () => {
  const originalEnv = { ...process.env };
  const setBase = () => {
    process.env.COGNITO_REGION = "ap-south-1";
    process.env.COGNITO_USER_POOL_ID = "ap-south-1_POOL";
    process.env.COGNITO_CLIENT_ID = "client";
    process.env.COGNITO_CLIENT_SECRET = "secret";
  };

  it("defaults to the username claim when unset", () => {
    setBase();
    delete process.env.COGNITO_REFRESH_USERNAME_SOURCE;
    assert.equal(cognitoConfig()?.refreshUsernameSource, "username_claim");
  });

  it("accepts both documented values and rejects unknown ones by disabling Cognito mode", () => {
    setBase();
    process.env.COGNITO_REFRESH_USERNAME_SOURCE = "sub";
    assert.equal(cognitoConfig()?.refreshUsernameSource, "sub");
    process.env.COGNITO_REFRESH_USERNAME_SOURCE = "username_claim";
    assert.equal(cognitoConfig()?.refreshUsernameSource, "username_claim");
    process.env.COGNITO_REFRESH_USERNAME_SOURCE = "email";
    assert.equal(cognitoConfig(), null);
  });
});
