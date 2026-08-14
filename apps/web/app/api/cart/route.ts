import { NextResponse, type NextRequest } from "next/server";
import { z } from "zod";
import { CART_COOKIE, decodeCart, encodeCart, hydrateCart } from "@/lib/cart-server";
import { getProductById } from "@/lib/catalog";

const addSchema = z.object({
  product_id: z.string().min(1),
  variant_id: z.string().min(1),
  quantity: z.number().int().min(1).max(20),
});

function cartResponse(request: NextRequest) {
  return hydrateCart(decodeCart(request.cookies.get(CART_COOKIE)?.value));
}

export async function GET(request: NextRequest) {
  return NextResponse.json(cartResponse(request));
}

export async function POST(request: NextRequest) {
  const parsed = addSchema.safeParse(await request.json().catch(() => null));
  if (!parsed.success) {
    return NextResponse.json({ error: "Invalid cart item." }, { status: 400 });
  }

  const product = getProductById(parsed.data.product_id);
  const variant = product?.variants.find(
    (candidate) => candidate.id === parsed.data.variant_id && candidate.isActive,
  );
  if (!product || !variant) {
    return NextResponse.json({ error: "This product option is unavailable." }, { status: 404 });
  }

  const stored = decodeCart(request.cookies.get(CART_COOKIE)?.value);
  const existing = stored.find(
    (line) => line.productId === product.id && line.variantId === variant.id,
  );
  const updated = existing
    ? stored.map((line) =>
        line === existing
          ? { ...line, quantity: Math.min(line.quantity + parsed.data.quantity, 20) }
          : line,
      )
    : [...stored, {
        productId: product.id,
        variantId: variant.id,
        quantity: parsed.data.quantity,
      }];
  const response = NextResponse.json(hydrateCart(updated));
  response.cookies.set(CART_COOKIE, encodeCart(updated), {
    httpOnly: true,
    sameSite: "lax",
    path: "/",
    maxAge: 60 * 60 * 24 * 30,
  });
  return response;
}
