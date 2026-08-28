import { createHash } from "node:crypto";

type PaymentCart = {
  id: string;
  currency: string;
  subtotal: number;
  items: Array<{
    key: string;
    productId: string;
    variantId: string;
    unitPrice: number;
    quantity: number;
  }>;
};

type PaymentCustomer = {
  email: string;
  firstName: string;
  lastName: string;
  address: string;
  apartment?: string;
  city: string;
  state: string;
  pin: string;
  phone: string;
};

const clean = (value: string | undefined) => (value || "").trim();

// An idempotency key represents one exact checkout intent. The cart id alone
// is not enough because customers can change quantities while keeping the same
// cart. Including the priced snapshot prevents an old Razorpay order from
// being replayed with a stale amount, while identical retries remain safe.
export function paymentOrderIdempotencyKey(input: {
  cart: PaymentCart;
  customer: PaymentCustomer;
  shippingMethod: "standard" | "express";
  discountCode: string;
}) {
  const fingerprint = {
    cart: {
      id: input.cart.id,
      currency: input.cart.currency,
      subtotal: input.cart.subtotal,
      items: input.cart.items
        .map((item) => ({
          key: item.key,
          productId: item.productId,
          variantId: item.variantId,
          unitPrice: item.unitPrice,
          quantity: item.quantity,
        }))
        .sort((left, right) => left.key.localeCompare(right.key)),
    },
    customer: {
      email: clean(input.customer.email).toLowerCase(),
      recipientName: `${clean(input.customer.firstName)} ${clean(input.customer.lastName)}`.trim(),
      phone: clean(input.customer.phone),
      address: clean(input.customer.address),
      apartment: clean(input.customer.apartment),
      city: clean(input.customer.city),
      state: clean(input.customer.state),
      pin: clean(input.customer.pin),
    },
    shippingMethod: input.shippingMethod,
    discountCode: clean(input.discountCode).toUpperCase(),
  };

  return createHash("sha256").update(JSON.stringify(fingerprint)).digest("hex");
}
