# Payments

Razorpay is the planned India-first payment provider. The browser never decides that an order is paid. The Go backend creates payment/order state, verifies provider callbacks/webhooks, stores provider IDs, and only then marks the payment/order as captured.

Payment secrets remain server-side. Retool should call Go admin endpoints for sensitive payment/refund actions instead of directly mutating payment tables.

Refunds use `POST /api/internal/refunds` with the internal bearer credential.
Each request requires an idempotency key; the service derives a stable Razorpay
receipt from it, reserves the remaining refundable amount transactionally, and
reconciles `refund.created`, `refund.processed`, and `refund.failed` webhooks.
Never retry a timed-out refund with a new idempotency key.
