import { strict as assert } from "node:assert";
import { describe, it } from "node:test";
import { paymentOrderIdempotencyKey } from "../lib/payment-order-idempotency.ts";

const customer = {
  email: "shopper@example.com",
  firstName: "Aveeck",
  lastName: "Pandey",
  address: "1 Beauty Lane",
  apartment: "",
  city: "Pune",
  state: "Maharashtra",
  pin: "411001",
  phone: "9876543210",
};

const base = {
  customer,
  shippingMethod: "standard" as const,
  discountCode: "",
  cart: {
    id: "same-cart",
    currency: "INR",
    subtotal: 8400,
    items: [{ key: "mascara:black", productId: "mascara", variantId: "black", unitPrice: 8400, quantity: 1 }],
  },
};

describe("paymentOrderIdempotencyKey", () => {
  it("keeps an identical payment retry idempotent", () => {
    assert.equal(paymentOrderIdempotencyKey(base), paymentOrderIdempotencyKey(structuredClone(base)));
  });

  it("creates a new payment order when the same cart changes amount", () => {
    const previousCheckout = {
      ...base,
      cart: {
        ...base.cart,
        subtotal: 19620,
        items: [{ ...base.cart.items[0], unitPrice: 9810, quantity: 2 }],
      },
    };
    assert.notEqual(paymentOrderIdempotencyKey(base), paymentOrderIdempotencyKey(previousCheckout));
  });

  it("is stable when the API returns identical items in a different order", () => {
    const first = { ...base, cart: { ...base.cart, items: [base.cart.items[0], { key: "lip:rose", productId: "lip", variantId: "rose", unitPrice: 1200, quantity: 1 }] } };
    const reversed = { ...first, cart: { ...first.cart, items: [...first.cart.items].reverse() } };
    assert.equal(paymentOrderIdempotencyKey(first), paymentOrderIdempotencyKey(reversed));
  });

  it("creates a new order when delivery or promotion terms change", () => {
    assert.notEqual(paymentOrderIdempotencyKey(base), paymentOrderIdempotencyKey({ ...base, shippingMethod: "express" }));
    assert.notEqual(paymentOrderIdempotencyKey(base), paymentOrderIdempotencyKey({ ...base, discountCode: "YV20-NEW" }));
    assert.notEqual(paymentOrderIdempotencyKey(base), paymentOrderIdempotencyKey({ ...base, customer: { ...customer, pin: "560001" } }));
  });
});
