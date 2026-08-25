import { strict as assert } from "node:assert";
import { describe, it } from "node:test";
import {
  GENDER_OPTIONS,
  normalizeBirthDate,
  parseRememberFlag,
  validateSignUpProfile,
} from "../lib/cognito-shared.ts";

describe("validateSignUpProfile", () => {
  const valid = { givenName: "  Ada ", email: "Shopper@Example.com", gender: "female", birthDate: "1994-06-15" };

  it("accepts the four required attributes and normalizes them", () => {
    const result = validateSignUpProfile(valid);
    assert.ok(result.ok);
    assert.deepEqual(result.profile, {
      givenName: "Ada",
      email: "shopper@example.com",
      gender: "female",
      birthDate: "1994-06-15",
    });
  });

  it("rejects each missing required attribute", () => {
    assert.equal(validateSignUpProfile(null).ok, false);
    for (const key of ["givenName", "email", "gender", "birthDate"] as const) {
      const partial: Record<string, string> = { ...valid };
      delete partial[key];
      assert.equal(validateSignUpProfile(partial).ok, false, `${key} must be required`);
    }
  });

  it("rejects unknown gender values and accepts every published option", () => {
    assert.equal(validateSignUpProfile({ ...valid, gender: "unset" }).ok, false);
    for (const option of GENDER_OPTIONS) {
      assert.equal(validateSignUpProfile({ ...valid, gender: option }).ok, true, `${option} must be accepted`);
    }
  });

  it("keeps the prefer-not-to-say choice available", () => {
    assert.ok((GENDER_OPTIONS as readonly string[]).includes("prefer_not_to_say"));
  });

  it("rejects non-string attribute values", () => {
    assert.equal(validateSignUpProfile({ ...valid, givenName: 42 as unknown as string }).ok, false);
    assert.equal(validateSignUpProfile({ ...valid, email: undefined }).ok, false);
  });
});

describe("normalizeBirthDate", () => {
  it("requires the strict YYYY-MM-DD shape Cognito expects", () => {
    assert.deepEqual(normalizeBirthDate("1990-01-02"), { ok: true, value: "1990-01-02" });
    for (const bad of ["02/01/1990", "1990-1-2", "19900102", "", "not-a-date", null, undefined]) {
      assert.equal(normalizeBirthDate(bad).ok, false, JSON.stringify(bad));
    }
  });

  it("rejects impossible calendar dates that JS would silently roll over", () => {
    assert.equal(normalizeBirthDate("2024-02-31").ok, false);
    assert.equal(normalizeBirthDate("2023-04-31").ok, false);
    assert.equal(normalizeBirthDate("2023-13-01").ok, false);
  });

  it("rejects future birthdays", () => {
    const tomorrow = new Date(Date.now() + 24 * 60 * 60 * 1000).toISOString().slice(0, 10);
    assert.equal(normalizeBirthDate(tomorrow).ok, false);
  });

  it("rejects implausibly old years", () => {
    assert.equal(normalizeBirthDate("1899-12-31").ok, false);
  });
});

describe("parseRememberFlag", () => {
  it("treats only the persisted '1' cookie value as persistent", () => {
    assert.equal(parseRememberFlag("1"), true);
    assert.equal(parseRememberFlag("0"), false);
    assert.equal(parseRememberFlag(""), false);
    assert.equal(parseRememberFlag(undefined), false);
    assert.equal(parseRememberFlag(null), false);
  });

  it("defaults legacy sessions (missing flag cookie) to non-persistent", () => {
    assert.equal(parseRememberFlag(undefined), false);
  });
});
