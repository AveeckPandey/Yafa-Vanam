import "server-only";
import type { CartResponse } from "./cart-types";
import { getProductById } from "./catalog";

export const CART_COOKIE = "yafa-cart-v1";

export type StoredCartLine = {
  productId: string;
  variantId: string;
  quantity: number;
};

export function decodeCart(value?: string): StoredCartLine[] {
  if (!value) return [];
  try {
    const parsed = JSON.parse(Buffer.from(value, "base64url").toString("utf8"));
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

export function encodeCart(items: StoredCartLine[]) {
  return Buffer.from(JSON.stringify(items), "utf8").toString("base64url");
}

export function hydrateCart(stored: StoredCartLine[]): CartResponse {
  const items = stored.flatMap((line) => {
    const product = getProductById(line.productId);
    const variant = product?.variants.find(
      (candidate) => candidate.id === line.variantId && candidate.isActive,
    );
    if (!product || !variant || !Number.isInteger(line.quantity) || line.quantity < 1) return [];

    return [{
      key: `${product.id}:${variant.id}`,
      productId: product.id,
      variantId: variant.id,
      name: product.name,
      slug: product.slug,
      productType: product.productType,
      currency: product.currency,
      unitPrice: variant.price,
      quantity: Math.min(line.quantity, 20),
      size: variant.size,
      shade: variant.shade?.name ?? null,
      image: product.image,
    }];
  });

  return {
    items,
    itemCount: items.reduce((total, item) => total + item.quantity, 0),
    subtotal: items.reduce((total, item) => total + item.unitPrice * item.quantity, 0),
    currency: items[0]?.currency ?? "INR",
  };
}
