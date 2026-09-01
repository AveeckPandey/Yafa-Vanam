# Returns and refunds

Returns and refunds are separate. The implemented administrator refund API can
issue full or partial refunds against captured Razorpay payments. It does not
automatically restock products: inventory should change only after a physical
return passes the hygiene and condition policy.

The Go backend owns Razorpay refund calls, idempotency, amount limits, status
transitions, and audit history. A customer-facing return-request/evidence flow
is still separate work. Cosmetics/hygiene rules and statutory consumer rights
must be reflected in the final customer-facing policy before launch.
