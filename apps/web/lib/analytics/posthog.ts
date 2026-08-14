"use client";

import posthog from "posthog-js";
import type { AnalyticsEventName, AnalyticsProperties } from "./events";

let initialized = false;

export function initPostHog() {
  if (initialized || typeof window === "undefined") return;
  const key = process.env.NEXT_PUBLIC_POSTHOG_KEY;
  if (!key) return;
  posthog.init(key, {
    api_host: process.env.NEXT_PUBLIC_POSTHOG_HOST || "https://us.i.posthog.com",
    capture_pageview: false,
    persistence: "localStorage+cookie",
  });
  initialized = true;
}

export function capturePostHog(event: AnalyticsEventName, properties?: AnalyticsProperties) {
  if (!initialized) return;
  posthog.capture(event, properties);
}

export function identifyPostHog(userId: string, properties?: Record<string, unknown>) {
  if (!initialized) return;
  posthog.identify(userId, properties);
}
