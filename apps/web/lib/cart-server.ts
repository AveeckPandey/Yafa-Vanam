import "server-only";
import type { NextRequest } from "next/server";
import type { CartResponse } from "./cart-types";
import { commerceApi, CommerceApiError, type ApiCart } from "./commerce-api";
import { getProductById } from "./catalog";

export const CART_COOKIE = "yafa-cart-id";

export const emptyCartResponse: CartResponse = {
  items: [],
  itemCount: 0,
  subtotal: 0,
  currency: "INR",
};

export function toCartResponse(cart: ApiCart): CartResponse {
  return {
    items: cart.items.map((line) => {
      const localProduct = getProductById(line.product_id);
      return {
        key: line.key,
        productId: line.product_id,
        variantId: line.variant_id,
        name: line.name,
        slug: line.slug,
        productType: line.product_type,
        currency: line.currency,
        unitPrice: line.unit_price,
        quantity: line.quantity,
        size: line.size,
        shade: line.shade,
        image: localProduct?.image || line.image || "/images/hero/yafa-vanam-soft-colour.png",
      };
    }),
    itemCount: cart.item_count,
    subtotal: cart.subtotal,
    currency: cart.currency,
  };
}

export async function getOrCreateCart(request: NextRequest) {
  const authCookie = request.headers.get("cookie") || undefined;
  const csrf = request.headers.get("x-csrf-token") || undefined;
  const existingId = request.cookies.get(CART_COOKIE)?.value;
  if (existingId) {
    try {
      return { cart: await commerceApi.getCart(existingId, authCookie), created: false };
    } catch (error) {
      if (!(error instanceof CommerceApiError) || error.status !== 404) throw error;
    }
  }
  return { cart: await commerceApi.createCart(authCookie, csrf), created: true };
}
