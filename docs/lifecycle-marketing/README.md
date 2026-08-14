# Lifecycle marketing

The Go lifecycle module is designed for controlled behavior-triggered messaging.

Example: a known customer visits repeatedly, has explicitly opted into WhatsApp marketing, has not purchased recently, and is outside the promotion cooldown. The Go service can create a bounded coupon and send an approved WhatsApp marketing template.

Guardrails include explicit channel/purpose consent, message suppression/cooldowns, purchase checks, coupon caps, inventory checks, and message history. Cookie consent is not WhatsApp marketing consent.
