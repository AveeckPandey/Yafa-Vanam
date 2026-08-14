"use client";

export type ConsentState = {
  analytics: boolean;
  marketing: boolean;
};

const KEY = "yafa-consent-v1";

export function getConsent(): ConsentState | null {
  if (typeof window === "undefined") return null;
  const raw = window.localStorage.getItem(KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as ConsentState;
  } catch {
    return null;
  }
}

export function setConsent(next: ConsentState) {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(KEY, JSON.stringify(next));
  window.dispatchEvent(new CustomEvent("yafa:consent-changed", { detail: next }));
}
