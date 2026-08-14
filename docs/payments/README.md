# Payments

Razorpay is the planned India-first payment provider. The browser never decides that an order is paid. The Go backend creates payment/order state, verifies provider callbacks/webhooks, stores provider IDs, and only then marks the payment/order as captured.

Payment secrets remain server-side. Retool should call Go admin endpoints for sensitive payment/refund actions instead of directly mutating payment tables.
