import { NextResponse, type NextRequest } from "next/server";
import { z } from "zod";
import { CART_COOKIE, toCartResponse } from "@/lib/cart-server";
import { commerceApi, CommerceApiError } from "@/lib/commerce-api";

const quantitySchema = z.object({ quantity: z.number().int().min(1).max(20) });

function apiError(error: unknown) {
  if (error instanceof CommerceApiError) {
    return NextResponse.json({ error: error.message }, { status: error.status });
  }
  return NextResponse.json({ error: "An unexpected cart error occurred." }, { status: 500 });
}

function cartIdentity(request: NextRequest, key: string) {
  const cartId = request.cookies.get(CART_COOKIE)?.value;
  const [, variantId] = decodeURIComponent(key).split(":");
  return { cartId, variantId };
}

export async function PATCH(
  request: NextRequest,
  context: { params: Promise<{ key: string }> },
) {
  const { key } = await context.params;
  const parsed = quantitySchema.safeParse(await request.json().catch(() => null));
  if (!parsed.success) return NextResponse.json({ error: "Invalid quantity." }, { status: 400 });
  const { cartId, variantId } = cartIdentity(request, key);
  if (!cartId || !variantId) return NextResponse.json({ error: "Cart item not found." }, { status: 404 });
  try {
    return NextResponse.json(toCartResponse(await commerceApi.setItem(cartId, variantId, parsed.data.quantity, request.headers.get("cookie") || undefined)));
  } catch (error) {
    return apiError(error);
  }
}

export async function DELETE(
  request: NextRequest,
  context: { params: Promise<{ key: string }> },
) {
  const { key } = await context.params;
  const { cartId, variantId } = cartIdentity(request, key);
  if (!cartId || !variantId) return NextResponse.json({ error: "Cart item not found." }, { status: 404 });
  try {
    return NextResponse.json(toCartResponse(await commerceApi.removeItem(cartId, variantId, request.headers.get("cookie") || undefined)));
  } catch (error) {
    return apiError(error);
  }
}
