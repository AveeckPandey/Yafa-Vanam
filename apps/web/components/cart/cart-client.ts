import type { CartResponse } from "@/lib/cart-types";
import { csrfToken } from "@/lib/csrf-client";
import { trackEvent } from "@/lib/analytics";

export async function getCart() {
  const response = await fetch("/api/cart", { cache: "no-store" });
  if (!response.ok) throw new Error("Unable to load the bag.");
  return response.json() as Promise<CartResponse>;
}

export async function addCartItem(productId: string, variantId: string, quantity: number) {
  const token = await csrfToken();
  const response = await fetch("/api/cart", {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-CSRF-Token": token },
    body: JSON.stringify({ product_id: productId, variant_id: variantId, quantity }),
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => null) as { error?: string } | null;
    throw new Error(payload?.error || "This item could not be added to your bag.");
  }
  const cart = await response.json() as CartResponse;
  window.dispatchEvent(new CustomEvent("yafa-cart-updated", { detail: cart }));
  window.dispatchEvent(new CustomEvent("yafa-cart-open", { detail: cart }));
  return cart;
}

export async function updateCartItem(key: string, quantity: number) {
  const token = await csrfToken();
  const response = await fetch(`/api/cart/items/${encodeURIComponent(key)}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json", "X-CSRF-Token": token },
    body: JSON.stringify({ quantity }),
  });
  if (!response.ok) throw new Error("The quantity could not be updated.");
  const cart = await response.json() as CartResponse;
  window.dispatchEvent(new CustomEvent("yafa-cart-updated", { detail: cart }));
  return cart;
}

export async function removeCartItem(key: string) {
  const token = await csrfToken();
  const response = await fetch(`/api/cart/items/${encodeURIComponent(key)}`, { method: "DELETE", headers: { "X-CSRF-Token": token } });
  if (!response.ok) throw new Error("The item could not be removed.");
  const cart = await response.json() as CartResponse;
  trackEvent("product_removed_from_cart", { line_item: key });
  window.dispatchEvent(new CustomEvent("yafa-cart-updated", { detail: cart }));
  return cart;
}
