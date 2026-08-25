"use client";

import type { AnalyticsEventName, AnalyticsProperties } from "./events";

type PostHogClient = (typeof import("posthog-js"))["default"];
type QueuedEvent = { event: AnalyticsEventName; properties?: AnalyticsProperties };

let initialized = false;
let client: PostHogClient | null = null;
let loading: Promise<void> | null = null;
const queuedEvents: QueuedEvent[] = [];

export function initPostHog() {
  if (initialized || loading || typeof window === "undefined") return;
  const key = process.env.NEXT_PUBLIC_POSTHOG_KEY;
  if (!key) return;

  // Keep the analytics SDK out of the critical storefront bundle. It is only
  // fetched after a visitor has explicitly granted analytics consent.
  loading = import("posthog-js").then(({ default: posthog }) => {
    posthog.init(key, {
      api_host: process.env.NEXT_PUBLIC_POSTHOG_HOST || "https://us.i.posthog.com",
      capture_pageview: false,
      persistence: "localStorage+cookie",
    });
    client = posthog;
    initialized = true;
    queuedEvents.splice(0).forEach(({ event, properties }) => posthog.capture(event, properties));
  }).catch(() => {
    // Analytics must never make the shopping experience fail.
  });
}

export function capturePostHog(event: AnalyticsEventName, properties?: AnalyticsProperties) {
  if (initialized) {
    client?.capture(event, properties);
  } else if (loading) {
    queuedEvents.push({ event, properties });
  }
}

export function identifyPostHog(userId: string, properties?: Record<string, unknown>) {
  if (initialized) client?.identify(userId, properties);
}
