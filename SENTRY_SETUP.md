# Sentry setup

Create three Sentry projects: **Next.js**, **Go**, and **Python/FastAPI**. Keep each DSN in the deployment platform's encrypted environment settings; never commit a DSN or expose server DSNs as `NEXT_PUBLIC_*` values.

Set `SENTRY_DSN`, `APP_ENV=production`, and `RELEASE_VERSION` on the Railway Go API and private Python service. Set `NEXT_PUBLIC_SENTRY_DSN` on Vercel for browser errors and `SENTRY_DSN` there only when server-side Next.js error reporting is desired. The applications initialize Sentry only when the relevant DSN is present, so local development remains quiet by default.

In Sentry, create alerts for:

- A release error rate above 1% for 10 minutes.
- Any new unhandled exception in production.
- A sustained API availability or latency issue, using Railway/Vercel uptime metrics alongside Sentry.

Use `RELEASE_VERSION` from the deployment commit SHA. Before enabling broader tracing, review performance sampling and privacy settings. This project disables default PII collection and session replay; do not attach selfie files, raw quiz answers, cookies, payment details, or access tokens to Sentry events.

For an incident, use the Sentry event's request ID to locate the matching structured Railway log line, then export only the minimum event and log data required for review.
