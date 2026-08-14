"use client";

import type { AnalyticsEventName, AnalyticsProperties } from "./events";

declare global {
  interface Window {
    dataLayer?: unknown[];
    gtag?: (...args: unknown[]) => void;
  }
}

let initialized = false;

export function initGA4() {
  if (initialized || typeof window === "undefined") return;
  const id = process.env.NEXT_PUBLIC_GA_MEASUREMENT_ID;
  if (!id) return;

  window.dataLayer = window.dataLayer || [];
  window.gtag = (...args: unknown[]) => window.dataLayer?.push(args);
  window.gtag("consent", "default", {
    analytics_storage: "denied",
    ad_storage: "denied",
    ad_user_data: "denied",
    ad_personalization: "denied",
  });

  const script = document.createElement("script");
  script.async = true;
  script.src = `https://www.googletagmanager.com/gtag/js?id=${id}`;
  document.head.appendChild(script);

  window.gtag("js", new Date());
  window.gtag("config", id, { send_page_view: false });
  initialized = true;
}

export function updateGA4Consent(analytics: boolean, marketing: boolean) {
  window.gtag?.("consent", "update", {
    analytics_storage: analytics ? "granted" : "denied",
    ad_storage: marketing ? "granted" : "denied",
    ad_user_data: marketing ? "granted" : "denied",
    ad_personalization: marketing ? "granted" : "denied",
  });
}

const ga4Map: Partial<Record<AnalyticsEventName, string>> = {
  collection_viewed: "view_item_list",
  product_clicked: "select_item",
  product_viewed: "view_item",
  wishlist_added: "add_to_wishlist",
  product_added_to_cart: "add_to_cart",
  product_removed_from_cart: "remove_from_cart",
  cart_viewed: "view_cart",
  checkout_started: "begin_checkout",
  shipping_added: "add_shipping_info",
  payment_info_added: "add_payment_info",
  purchase_completed: "purchase",
  refund_processed: "refund",
};

export function captureGA4(event: AnalyticsEventName, properties?: AnalyticsProperties) {
  const mapped = ga4Map[event] || event;
  window.gtag?.("event", mapped, properties || {});
}
