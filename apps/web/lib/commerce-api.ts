import "server-only";

// Response models come from the generated API contract (@yafa/frontend-types,
// built from apps/api/openapi/openapi.yaml) so the storefront can never drift
// from what the Go API actually returns. Regenerate after contract changes:
//   npm run generate:api-types
import type { ApiCart, RazorpayCheckoutOrder } from "@yafa/frontend-types";

const BASE = (process.env.COMMERCE_API_URL || process.env.NEXT_PUBLIC_API_URL || "http://localhost:4000").replace(/\/$/, "");

export type { ApiCart, RazorpayCheckoutOrder };

// Request shape kept local: it is stricter than the schema requires (enum +
// mandatory discount_code) because the checkout form always supplies both.
export type RazorpayCheckoutInput = {
  cart_id: string;
  customer_email: string;
  shipping_method: "standard" | "express";
  discount_code: string;
  shipping_address: {
    recipient_name: string;
    phone: string;
    line1: string;
    line2?: string;
    city: string;
    state_region: string;
    postal_code: string;
    country_code: "IN";
  };
};

export class CommerceApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
  ) {
    super(message);
    this.name = "CommerceApiError";
  }
}

async function request<T>(path: string, init?: RequestInit, cookie?: string, csrf?: string): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${BASE}${path}`, {
      ...init,
      cache: "no-store",
      headers: { "Content-Type": "application/json", ...(cookie ? { Cookie: cookie } : {}), ...(csrf ? { "X-CSRF-Token": csrf } : {}), ...(init?.headers || {}) },
    });
  } catch {
    throw new CommerceApiError(503, "The commerce service is temporarily unavailable.");
  }

  if (!response.ok) {
    const body = await response.json().catch(() => null) as { error?: string | { message?: string } } | null;
    const message = typeof body?.error === "string" ? body.error : body?.error?.message;
    throw new CommerceApiError(
      response.status,
      message || `Commerce request failed (${response.status}).`,
    );
  }
  return response.json() as Promise<T>;
}

export const commerceApi = {
  createCart: (cookie?: string, csrf?: string) => request<ApiCart>("/api/v1/carts", { method: "POST", body: "{}" }, cookie, csrf),
  getCart: (cartId: string, cookie?: string) => request<ApiCart>(`/api/v1/carts/${encodeURIComponent(cartId)}`, undefined, cookie),
  addItem: (cartId: string, input: { product_id: string; variant_id: string; quantity: number }, cookie?: string, csrf?: string) =>
    request<ApiCart>(`/api/v1/carts/${encodeURIComponent(cartId)}/items`, {
      method: "POST",
      body: JSON.stringify(input),
    }, cookie, csrf),
  setItem: (cartId: string, variantId: string, quantity: number, cookie?: string, csrf?: string) =>
    request<ApiCart>(`/api/v1/carts/${encodeURIComponent(cartId)}/items/${encodeURIComponent(variantId)}`, {
      method: "PATCH",
      body: JSON.stringify({ quantity }),
    }, cookie, csrf),
  removeItem: (cartId: string, variantId: string, cookie?: string, csrf?: string) =>
    request<ApiCart>(`/api/v1/carts/${encodeURIComponent(cartId)}/items/${encodeURIComponent(variantId)}`, {
      method: "DELETE",
    }, cookie, csrf),
  createRazorpayOrder: (input: RazorpayCheckoutInput, idempotencyKey: string, cookie?: string, csrf?: string) =>
    request<RazorpayCheckoutOrder>("/api/v1/payments/razorpay/orders", {
      method: "POST",
      headers: { "Idempotency-Key": idempotencyKey },
      body: JSON.stringify(input),
    }, cookie, csrf),
  verifyRazorpayPayment: (input: { razorpay_payment_id: string; razorpay_order_id: string; razorpay_signature: string }, cookie?: string, csrf?: string) =>
    request<{ verified: boolean; order_number: string; payment_status: string }>("/api/v1/payments/razorpay/verify", {
      method: "POST", body: JSON.stringify(input),
    }, cookie, csrf),
};
