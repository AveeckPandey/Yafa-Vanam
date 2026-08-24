"use client";

export async function csrfToken(): Promise<string> {
  const response = await fetch("/api/auth/csrf", { credentials: "include", cache: "no-store" });
  const value = await response.json().catch(() => null) as { csrfToken?: string } | null;
  // Local commerce can run without the optional account service. In that
  // configuration there are no account cookies to protect and the Go API
  // deliberately does not expose /auth/csrf. Keep anonymous carts working
  // while still requiring a real CSRF token whenever authentication exists.
  if (response.status === 404) {
    return "";
  }
  if (!response.ok || !value?.csrfToken) {
    throw new Error("Unable to prepare your secure session. Please try again.");
  }
  return value.csrfToken;
}
