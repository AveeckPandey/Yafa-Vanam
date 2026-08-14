"use client";

import type { AnalyticsEventName, AnalyticsProperties } from "./events";
import { getConsent } from "./consent";
import { capturePostHog, initPostHog } from "./posthog";
import { captureGA4, initGA4, updateGA4Consent } from "./ga4";

export function initializeAnalytics() {
  const consent = getConsent();
  if (!consent?.analytics) return;
  initPostHog();
  initGA4();
  updateGA4Consent(consent.analytics, consent.marketing);
}

export function trackEvent(event: AnalyticsEventName, properties?: AnalyticsProperties) {
  const consent = getConsent();
  if (!consent?.analytics) return;
  capturePostHog(event, properties);
  captureGA4(event, properties);
}
