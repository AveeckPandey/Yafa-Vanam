import { createHash } from "node:crypto";
import { NextResponse, type NextRequest } from "next/server";
import { z } from "zod";
import { getOrCreateCart } from "@/lib/cart-server";
import { commerceApi, CommerceApiError } from "@/lib/commerce-api";

const requestSchema = z.object({
  shippingMethod: z.enum(["standard", "express"]),
  discountCode: z.string().max(32).optional().default(""),
  customer: z.object({
    email: z.string().email(), firstName: z.string().min(1), lastName: z.string().min(1), address: z.string().min(1), city: z.string().min(1), state: z.string().min(1), pin: z.string().regex(/^[1-9][0-9]{5}$/), phone: z.string().regex(/^[6-9][0-9]{9}$/), apartment: z.string().optional(), giftMessage: z.string().max(250).optional(),
  }),
});

export async function POST(request: NextRequest) {
  const parsed = requestSchema.safeParse(await request.json().catch(() => null));
  if (!parsed.success) return NextResponse.json({ error: "Please complete your delivery details before paying." }, { status: 400 });
  try {
    const { cart } = await getOrCreateCart(request);
    if (!cart.items.length) return NextResponse.json({ error: "Your bag is empty." }, { status: 400 });
    const { customer, shippingMethod, discountCode } = parsed.data;
    const idempotencyKey = createHash("sha256").update(JSON.stringify({ cart: cart.id, email: customer.email, address: customer.address, pin: customer.pin, shippingMethod, discountCode })).digest("hex");
    const order = await commerceApi.createRazorpayOrder({
      cart_id: cart.id, customer_email: customer.email, shipping_method: shippingMethod, discount_code: discountCode,
      shipping_address: { recipient_name: `${customer.firstName} ${customer.lastName}`.trim(), phone: customer.phone, line1: customer.address, line2: customer.apartment || undefined, city: customer.city, state_region: customer.state, postal_code: customer.pin, country_code: "IN" },
    }, idempotencyKey, request.headers.get("cookie") || undefined, request.headers.get("x-csrf-token") || undefined);
    return NextResponse.json({ orderId: order.razorpay_order_id, amount: order.amount, currency: order.currency, keyId: order.key_id, orderNumber: order.order_number });
  } catch (error) {
    if (error instanceof CommerceApiError) return NextResponse.json({ error: error.message }, { status: error.status });
    return NextResponse.json({ error: "We could not prepare your payment." }, { status: 502 });
  }
}
