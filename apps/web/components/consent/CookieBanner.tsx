"use client";

import { useEffect, useState } from "react";
import { getConsent, setConsent } from "../../lib/analytics/consent";
import { initializeAnalytics } from "../../lib/analytics";

export function CookieBanner() {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    setVisible(getConsent() === null);
  }, []);

  if (!visible) return null;

  return (
    <div role="dialog" aria-label="Cookie preferences">
      <p>
        Essential storage keeps the store working. With your permission, analytics helps YAFA VANAM understand how people use the site and improve the shopping experience.
      </p>
      <button
        type="button"
        onClick={() => {
          setConsent({ analytics: false, marketing: false });
          setVisible(false);
        }}
      >
        Reject optional
      </button>
      <button
        type="button"
        onClick={() => {
          setConsent({ analytics: true, marketing: false });
          initializeAnalytics();
          setVisible(false);
        }}
      >
        Accept analytics
      </button>
      <button
        type="button"
        onClick={() => {
          setConsent({ analytics: true, marketing: true });
          initializeAnalytics();
          setVisible(false);
        }}
      >
        Accept all
      </button>
    </div>
  );
}
