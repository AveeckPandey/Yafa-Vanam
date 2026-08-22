import { NextResponse, type NextRequest } from "next/server";
import { z } from "zod";
import { CART_COOKIE, emptyCartResponse, getOrCreateCart, toCartResponse } from "@/lib/cart-server";
import { commerceApi, CommerceApiError } from "@/lib/commerce-api";

const addSchema = z.object({
  product_id: z.string().min(1),
  variant_id: z.string().min(1),
  quantity: z.number().int().min(1).max(20),
});

function withCartCookie(response: NextResponse, cartId: string) {
  response.cookies.set(CART_COOKIE, cartId, {
    httpOnly: true,
    sameSite: "lax",
    secure: process.env.NODE_ENV === "production",
    path: "/",
    maxAge: 60 * 60 * 24 * 30,
  });
  return response;
}

function apiError(error: unknown) {
  if (error instanceof CommerceApiError) {
    return NextResponse.json({ error: error.message }, { status: error.status });
  }
  return NextResponse.json({ error: "An unexpected cart error occurred." }, { status: 500 });
}

export async function GET(request: NextRequest) {
  // A GET request must not create a cart. Authenticated cart creation is a
  // state-changing operation and therefore requires the CSRF token supplied
  // by the browser on POST.
  if (!request.cookies.get(CART_COOKIE)?.value) {
    return NextResponse.json(emptyCartResponse);
  }
  const cartId = request.cookies.get(CART_COOKIE)?.value;
  try {
    const cart = await commerceApi.getCart(cartId!, request.headers.get("cookie") || undefined);
    return NextResponse.json(toCartResponse(cart));
  } catch (error) {
    if (error instanceof CommerceApiError && (error.status === 404 || error.status === 403)) {
      const response = NextResponse.json(emptyCartResponse);
      response.cookies.delete(CART_COOKIE);
      return response;
    }
    return apiError(error);
  }
}

export async function POST(request: NextRequest) {
  const parsed = addSchema.safeParse(await request.json().catch(() => null));
  if (!parsed.success) {
    return NextResponse.json({ error: "Invalid cart item." }, { status: 400 });
  }
  try {
    const { cart, created } = await getOrCreateCart(request);
    const updated = await commerceApi.addItem(cart.id, parsed.data, request.headers.get("cookie") || undefined, request.headers.get("x-csrf-token") || undefined);
    const response = NextResponse.json(toCartResponse(updated));
    return created ? withCartCookie(response, cart.id) : response;
  } catch (error) {
    return apiError(error);
  }
}
