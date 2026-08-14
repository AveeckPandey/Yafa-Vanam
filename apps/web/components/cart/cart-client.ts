import type { CartResponse } from "@/lib/cart-types";

export async function getCart() {
  const response = await fetch("/api/cart", { cache: "no-store" });
  if (!response.ok) throw new Error("Unable to load the bag.");
  return response.json() as Promise<CartResponse>;
}

export async function addCartItem(productId: string, variantId: string, quantity: number) {
  const response = await fetch("/api/cart", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ product_id: productId, variant_id: variantId, quantity }),
  });
  if (!response.ok) throw new Error("This item could not be added to your bag.");
  const cart = await response.json() as CartResponse;
  window.dispatchEvent(new CustomEvent("yafa-cart-updated", { detail: cart }));
  window.dispatchEvent(new CustomEvent("yafa-cart-open", { detail: cart }));
  return cart;
}

export async function updateCartItem(key: string, quantity: number) {
  const response = await fetch(`/api/cart/items/${encodeURIComponent(key)}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ quantity }),
  });
  if (!response.ok) throw new Error("The quantity could not be updated.");
  const cart = await response.json() as CartResponse;
  window.dispatchEvent(new CustomEvent("yafa-cart-updated", { detail: cart }));
  return cart;
}

export async function removeCartItem(key: string) {
  const response = await fetch(`/api/cart/items/${encodeURIComponent(key)}`, { method: "DELETE" });
  if (!response.ok) throw new Error("The item could not be removed.");
  const cart = await response.json() as CartResponse;
  window.dispatchEvent(new CustomEvent("yafa-cart-updated", { detail: cart }));
  return cart;
}
