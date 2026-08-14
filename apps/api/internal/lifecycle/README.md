# Lifecycle marketing

This Go module will own behavior-triggered customer messaging. PostHog supplies behavior signals; PostgreSQL remains the source of truth for identity, orders, consent, eligibility, coupons, suppression, and message history.

Initial trigger example:

- known customer
- explicit WhatsApp marketing opt-in
- at least 3 visits in 14 days
- no purchase in the configured lookback
- not inside a promotion cooldown

If eligible, the service can create a bounded discount and request delivery through an approved WhatsApp Business template. Analytics-cookie consent alone is never treated as WhatsApp marketing consent.
