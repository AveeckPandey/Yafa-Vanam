"use client";

import { getConsent, setConsent } from "../../lib/analytics/consent";

export function CookiePreferences() {
  const consent = getConsent();
  return (
    <button className="cookie-preferences"
      type="button"
      onClick={() => {
        const next = !(consent?.analytics ?? false);
        setConsent({ analytics: next, marketing: next ? (consent?.marketing ?? false) : false });
      }}
    >
      Manage cookie preferences
    </button>
  );
}
