import { NextResponse, type NextRequest } from "next/server";
import { z } from "zod";
import { CART_COOKIE, decodeCart, encodeCart, hydrateCart } from "@/lib/cart-server";

const quantitySchema = z.object({ quantity: z.number().int().min(1).max(20) });

function save(items: ReturnType<typeof decodeCart>) {
  const response = NextResponse.json(hydrateCart(items));
  response.cookies.set(CART_COOKIE, encodeCart(items), {
    httpOnly: true,
    sameSite: "lax",
    path: "/",
    maxAge: 60 * 60 * 24 * 30,
  });
  return response;
}

export async function PATCH(
  request: NextRequest,
  context: { params: Promise<{ key: string }> },
) {
  const { key } = await context.params;
  const parsed = quantitySchema.safeParse(await request.json().catch(() => null));
  if (!parsed.success) return NextResponse.json({ error: "Invalid quantity." }, { status: 400 });
  const [productId, variantId] = decodeURIComponent(key).split(":");
  const stored = decodeCart(request.cookies.get(CART_COOKIE)?.value);
  return save(stored.map((line) =>
    line.productId === productId && line.variantId === variantId
      ? { ...line, quantity: parsed.data.quantity }
      : line,
  ));
}

export async function DELETE(
  request: NextRequest,
  context: { params: Promise<{ key: string }> },
) {
  const { key } = await context.params;
  const [productId, variantId] = decodeURIComponent(key).split(":");
  const stored = decodeCart(request.cookies.get(CART_COOKIE)?.value);
  return save(stored.filter(
    (line) => line.productId !== productId || line.variantId !== variantId,
  ));
}
