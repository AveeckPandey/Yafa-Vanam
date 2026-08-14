# Retool resource connections

Recommended resources:

1. PostgreSQL — read-only or narrowly scoped role for dashboards.
2. YAFA Go Admin API — sensitive mutations and workflows.
3. HubSpot — optional CRM views/actions.
4. Google Analytics 4 — acquisition/marketing views.
5. PostHog API — optional behavior insight queries.

Never expose database, Razorpay, WhatsApp, HubSpot, or Sentry secrets to the public Next.js client.
