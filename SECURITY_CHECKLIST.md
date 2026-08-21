# Production security checklist

Mark each item only after verifying it in the target production environment.

- [ ] Secrets are held only in encrypted deployment environment variables; no secret, DSN with credentials, or private key is committed.
- [ ] HTTPS is enforced at the public edge; the API serves HSTS when it receives TLS traffic.
- [ ] `CORS_ALLOWED_ORIGINS` is an exact production allowlist; localhost appears only in development.
- [ ] Cookie-authenticated mutations require an origin check and double-submit CSRF header.
- [ ] Every user-owned resource has an authorization and ownership test.
- [ ] Database queries use parameterised pgx calls and request DTOs reject unknown fields.
- [ ] No unsafe `dangerouslySetInnerHTML` rendering is present without a documented sanitisation review.
- [ ] Razorpay signatures and webhook signatures are verified before payment fulfilment.
- [ ] Selfie uploads enforce MIME/magic-byte validation, a five-megabyte limit, private storage, and signed access URLs.
- [ ] Password hashing uses bcrypt cost 12 or higher, and login failures do not disclose account existence.
- [ ] Redis-backed API limits are working: auth 10/minute, payments 20/minute, all other API routes 100/minute per client IP; health checks are exempt.
- [ ] Structured logs contain request ID, route, status, latency, and no credentials, cookies, payment data, raw selfies, full addresses, or raw quiz answers.
- [ ] Daily encrypted database backups and a weekly private `pg_dump` job are enabled; a staging restore test has passed within the last quarter.
- [ ] `govulncheck ./...`, `pip-audit`, and `npm audit` run in CI, container images are scanned, and dependency findings are reviewed.
- [ ] Staging has passed authentication, IDOR/BOLA, CSRF, upload, XSS, SSRF, rate-limit, and payment-webhook tests before production release.
- [ ] Sentry alerts, incident contacts, and credential-rotation ownership are configured.
