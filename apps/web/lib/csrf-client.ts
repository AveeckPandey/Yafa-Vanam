"use client";

export async function csrfToken(): Promise<string> {
  const response = await fetch("/api/auth/csrf", { credentials: "include", cache: "no-store" });
  const value = await response.json().catch(() => null) as { csrfToken?: string } | null;
  if (!response.ok || !value?.csrfToken) {
    throw new Error("Unable to prepare your secure session. Please try again.");
  }
  return value.csrfToken;
}
