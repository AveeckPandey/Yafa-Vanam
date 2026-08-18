import "server-only";

const BASE = (process.env.COMMERCE_API_URL || process.env.NEXT_PUBLIC_API_URL || "http://localhost:4000").replace(/\/$/, "");

export type ApiCartLine = {
  key: string;
  product_id: string;
  variant_id: string;
  name: string;
  slug: string;
  product_type: string;
  currency: string;
  unit_price: number;
  quantity: number;
  size: string | null;
  shade: string | null;
  image: string | null;
};

export type ApiCart = {
  id: string;
  items: ApiCartLine[];
  item_count: number;
  subtotal: number;
  currency: string;
  updated_at: string;
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

async function request<T>(path: string, init?: RequestInit, cookie?: string): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${BASE}${path}`, {
      ...init,
      cache: "no-store",
      headers: { "Content-Type": "application/json", ...(cookie ? { Cookie: cookie } : {}), ...(init?.headers || {}) },
    });
  } catch {
    throw new CommerceApiError(503, "The commerce service is temporarily unavailable.");
  }

  if (!response.ok) {
    const body = await response.json().catch(() => null) as { error?: { message?: string } } | null;
    throw new CommerceApiError(
      response.status,
      body?.error?.message || `Commerce request failed (${response.status}).`,
    );
  }
  return response.json() as Promise<T>;
}

export const commerceApi = {
  createCart: (cookie?: string) => request<ApiCart>("/api/v1/carts", { method: "POST", body: "{}" }, cookie),
  getCart: (cartId: string, cookie?: string) => request<ApiCart>(`/api/v1/carts/${encodeURIComponent(cartId)}`, undefined, cookie),
  addItem: (cartId: string, input: { product_id: string; variant_id: string; quantity: number }, cookie?: string) =>
    request<ApiCart>(`/api/v1/carts/${encodeURIComponent(cartId)}/items`, {
      method: "POST",
      body: JSON.stringify(input),
    }, cookie),
  setItem: (cartId: string, variantId: string, quantity: number, cookie?: string) =>
    request<ApiCart>(`/api/v1/carts/${encodeURIComponent(cartId)}/items/${encodeURIComponent(variantId)}`, {
      method: "PATCH",
      body: JSON.stringify({ quantity }),
    }, cookie),
  removeItem: (cartId: string, variantId: string, cookie?: string) =>
    request<ApiCart>(`/api/v1/carts/${encodeURIComponent(cartId)}/items/${encodeURIComponent(variantId)}`, {
      method: "DELETE",
    }, cookie),
};
