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
    <div className="cookie-banner" role="dialog" aria-label="Cookie preferences" aria-describedby="cookie-banner-copy">
      <p id="cookie-banner-copy">
        Essential storage keeps the store working. With your permission, analytics helps YAFA VANAM understand how people use the site and improve the shopping experience.
      </p>
      <div className="cookie-banner__actions"><button
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
      <button className="cookie-banner__primary"
        type="button"
        onClick={() => {
          setConsent({ analytics: true, marketing: true });
          initializeAnalytics();
          setVisible(false);
        }}
      >
        Accept all
      </button></div>
    </div>
  );
}
