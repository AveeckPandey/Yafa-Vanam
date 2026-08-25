import { strict as assert } from "node:assert";
import { describe, it } from "node:test";
import { clearCognitoCookies, setCognitoSessionCookies } from "../lib/cognito-session.ts";

const HOUR = 60 * 60;
const DAY = 24 * HOUR;

const tokens = {
  IdToken: "id-token-value",
  AccessToken: "access-token-value",
  RefreshToken: "refresh-token-value",
  ExpiresIn: 3600,
};

function cookiesFor(remember: boolean) {
  const headers = new Headers();
  setCognitoSessionCookies(headers, tokens, "pool-username-or-alias", remember);
  return headers.getSetCookie().map((cookie) => {
    const [pair, ...attributes] = cookie.split(";");
    const maxAge = /Max-Age=(\d+)/.exec(attributes.join(";"))?.[1] ?? "";
    const name = pair.slice(0, pair.indexOf("="));
    return { name, value: pair.slice(pair.indexOf("=") + 1), maxAge: Number(maxAge) };
  });
}

describe("setCognitoSessionCookies", () => {
  it("persists the visitor's remember-me choice in a companion cookie", () => {
    const persistent = cookiesFor(true).find((cookie) => cookie.name === "yafa_cognito_remember");
    const ephemeral = cookiesFor(false).find((cookie) => cookie.name === "yafa_cognito_remember");
    assert.equal(persistent?.value, "1");
    assert.equal(persistent?.maxAge, 30 * DAY);
    assert.equal(ephemeral?.value, "0");
    assert.equal(ephemeral?.maxAge, DAY);
  });

  it("never extends a non-persistent session to the 30-day horizon", () => {
    for (const cookie of cookiesFor(false)) {
      if (["yafa_cognito_refresh", "yafa_cognito_username", "yafa_cognito_remember"].includes(cookie.name)) {
        assert.equal(cookie.maxAge, DAY, `${cookie.name} must stay non-persistent`);
      }
    }
  });

  it("keeps the refresh and username cookies alive alongside the remembered choice", () => {
    const family = cookiesFor(true);
    for (const name of ["yafa_cognito_refresh", "yafa_cognito_username"]) {
      const cookie = family.find((candidate) => candidate.name === name);
      assert.equal(cookie?.maxAge, 30 * DAY);
    }
  });

  it("expires token cookies after one hour regardless of persistence", () => {
    for (const remember of [true, false]) {
      for (const name of ["yafa_cognito_id", "yafa_cognito_access"]) {
        const cookie = cookiesFor(remember).find((candidate) => candidate.name === name);
        assert.equal(cookie?.maxAge, HOUR);
      }
    }
  });
});

describe("clearCognitoCookies", () => {
  it("clears the whole family including the remember flag", () => {
    const headers = new Headers();
    clearCognitoCookies(headers);
    const names = headers.getSetCookie().map((cookie) => cookie.split("=")[0]);
    for (const expected of ["yafa_cognito_id", "yafa_cognito_access", "yafa_cognito_refresh", "yafa_cognito_username", "yafa_cognito_remember"]) {
      assert.ok(names.includes(expected), `${expected} must be cleared`);
    }
  });
});
