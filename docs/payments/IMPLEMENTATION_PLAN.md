# Checkout and payments

## Decision

Use Razorpay Standard Checkout as the primary India payment gateway. The browser will receive only a Razorpay key ID and a server-created Razorpay order ID. It must never receive the key secret or decide that an order is paid. Razorpay requires server-side signature verification and recommends webhooks as the authoritative asynchronous confirmation path. [Razorpay Standard Checkout](https://razorpay.com/docs/payments/payment-gateway/web-integration/standard/integration-steps/)

Stripe and PayPal remain future options for international expansion; they are not part of the first India checkout.

## Required credentials before live activation

- `RAZORPAY_KEY_ID`
- `RAZORPAY_KEY_SECRET` (server only)
- `RAZORPAY_WEBHOOK_SECRET` (server only)
- production webhook URL and Razorpay account/KYC approval

## Build order

1. Server prices the cart and creates a pending YAFA order.
2. Go API creates a Razorpay order using the amount/currency from that order.
3. Browser opens Razorpay Checkout with key ID and Razorpay order ID.
4. Browser sends payment ID/order ID/signature to Go for verification.
5. Razorpay webhook independently confirms payment; only then mark the order captured.
6. Success page reads the verified order, not a browser callback alone.

No real payment should be enabled until test-mode checkout, signature verification, webhook replay protection, refund flow, and failed-payment handling have passed end-to-end tests.
