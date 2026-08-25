/**
 * Pure, dependency-free Cognito sign-up contract shared by the browser form,
 * the /api/auth/cognito/signup route, and the tests. No "server-only" import:
 * the client bundles this file for pre-flight validation while the server
 * re-runs every check as the authority.
 */

export const GENDER_OPTIONS = ["female", "male", "non_binary", "prefer_not_to_say"] as const;
export type GenderValue = (typeof GENDER_OPTIONS)[number];

export type SignUpProfileInput = {
  givenName?: unknown;
  email?: unknown;
  gender?: unknown;
  birthDate?: unknown;
};

export type NormalizedSignUpProfile = {
  givenName: string;
  email: string;
  gender: GenderValue;
  /** Strict calendar date, always YYYY-MM-DD as Cognito requires. */
  birthDate: string;
};

export type ValidationResult =
  | { ok: true; profile: NormalizedSignUpProfile }
  | { ok: false; error: string };

const BIRTHDATE_PATTERN = /^\d{4}-\d{2}-\d{2}$/;
const MIN_BIRTH_YEAR = 1900;

function asTrimmedString(value: unknown): string {
  return typeof value === "string" ? value.trim() : "";
}

/**
 * Accepts only strict YYYY-MM-DD strings that name a real calendar date in
 * the past. `new Date("2024-02-31")` silently rolls over to March 2nd, so the
 * parts are checked against a UTC round-trip instead of trusting the parser.
 */
export function normalizeBirthDate(value: unknown): { ok: true; value: string } | { ok: false } {
  const raw = asTrimmedString(value);
  if (!BIRTHDATE_PATTERN.test(raw)) return { ok: false };
  const [yearText, monthText, dayText] = raw.split("-");
  const year = Number(yearText);
  const month = Number(monthText);
  const day = Number(dayText);
  if (!Number.isInteger(year) || !Number.isInteger(month) || !Number.isInteger(day)) return { ok: false };
  if (year < MIN_BIRTH_YEAR || month < 1 || month > 12 || day < 1 || day > 31) return { ok: false };
  // Round-trip through UTC: an impossible date (e.g. 2024-02-31) normalizes
  // into a different day and fails the exact-format comparison.
  const parsed = new Date(`${raw}T00:00:00Z`);
  if (Number.isNaN(parsed.getTime())) return { ok: false };
  if (parsed.toISOString().slice(0, 10) !== raw) return { ok: false };
  // Birthdays are never in the future; comparing UTC days keeps the rule
  // identical no matter which timezone the server runs in.
  if (parsed.getTime() > Date.now()) return { ok: false };
  return { ok: true, value: raw };
}

/** Visitor-safe validation of the four required Cognito standard attributes. */
export function validateSignUpProfile(input: SignUpProfileInput | null | undefined): ValidationResult {
  const givenName = asTrimmedString(input?.givenName);
  if (!givenName) return { ok: false, error: "Please enter your given name." };

  const email = asTrimmedString(input?.email).toLowerCase();
  if (!email.includes("@")) return { ok: false, error: "Please enter a valid email address." };

  const gender = asTrimmedString(input?.gender);
  if (!(GENDER_OPTIONS as readonly string[]).includes(gender)) {
    return { ok: false, error: "Please choose an option for gender." };
  }

  const birthDate = normalizeBirthDate(input?.birthDate);
  if (!birthDate.ok) {
    return { ok: false, error: "Please enter a valid birthday that is not in the future." };
  }

  return {
    ok: true,
    profile: {
      givenName,
      email,
      gender: gender as GenderValue,
      birthDate: birthDate.value,
    },
  };
}

/**
 * The remember-me companion cookie stores "1"/"0". Anything else — including
 * a missing cookie from sessions created before this flag existed — resolves
 * to non-persistent, so refreshes can never silently extend a session the
 * visitor did not ask to keep.
 */
export function parseRememberFlag(value: string | null | undefined): boolean {
  return value === "1";
}
