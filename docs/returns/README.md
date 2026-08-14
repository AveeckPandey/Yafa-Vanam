# Returns and refunds

Returns and refunds are modeled separately. A return request can cover one or more order items; refunds can be full or partial and can map back to specific order items.

The Go backend owns eligibility, evidence handling, inventory consequences, Razorpay refund calls, status transitions, and audit history. Cosmetics/hygiene rules and statutory consumer rights should be reflected in the final customer-facing policy before launch.
