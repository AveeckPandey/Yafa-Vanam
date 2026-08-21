# Production deployment

## 1. Provision Railway services

Create one Railway project with a managed PostgreSQL 15+ service, Redis 7+ service, the public Go API, and the private Python recommendation service. Keep the Python service without a public domain. Give the Go API `DATABASE_URL`, `REDIS_URL`, and the Python private-domain URL as Railway variables; do not commit values or paste them into frontend variables.

Deploy the Go API from `apps/api` and Python from `services/recommendation-engine`. Their `railway.json` files define health checks. Railway supplies `PORT`; the Go service also accepts `API_PORT` for local development.

## 2. Apply migrations once

The API applies pending SQL files in `apps/api/db/migrations` at startup, records them in `schema_migrations`, and holds a PostgreSQL advisory lock so concurrent Railway replicas cannot race. A migration failure stops the release before the API starts serving traffic. Use a Railway one-off service shell only to inspect or recover a failed migration; do not manually mark a migration as applied without reviewing the database state.

## 3. Configure the Go API

Copy `apps/api/.env.production.example` into Railway variables. Use a 32+ character random `JWT_SECRET` and a separate 32+ character `YAFA_INTERNAL_SERVICE_TOKEN`. Configure private S3/R2 storage only; do not make the selfie bucket public. Set `CORS_ALLOWED_ORIGINS` to the exact Vercel domains and configure Razorpay webhooks to call `https://api.yafavanam.com/api/v1/payments/razorpay/webhook`.

The service fails startup in production if database/Redis/JWT configuration is absent, CORS is unspecified, required Yafa storage/AI configuration is absent, or enabled Razorpay checkout lacks its server secrets.

## 4. Configure the Python service

Set `YAFA_INTERNAL_SERVICE_TOKEN` to exactly the same secret used by the Go API. Do not set a public domain. Its `/health` endpoint must return `200` before the Go API is released. Review the CV validation report before replacing the provisional `calibration_config.json` threshold.

## 5. Configure Vercel

Deploy the repository with `apps/web` as the frontend root. Set `COMMERCE_API_URL` only as a server-side Vercel variable and point it to `https://api.yafavanam.com`. Set `NEXT_PUBLIC_API_URL=https://api.yafavanam.com`; set only public analytics keys with the `NEXT_PUBLIC_` prefix. The root `vercel.json` proxies browser `/api/v1/*` requests to the Go API; Next.js `/api/*` route handlers remain local.

Set the production domain to `yafavanam.com` (and redirect `www` if used). Confirm the OAuth callback exactly matches `https://yafavanam.com/api/auth/google/callback`.

## 6. Release verification and rollback

After deployment, check `GET /health` and `GET /ready` on the Go API; each reports only `ok`, `degraded`, or dependency state without secrets. Check the private Python `/health` through Railway’s service health UI. Complete a Razorpay test-mode payment and confirm both signature verification and a signed webhook update.

If verification fails, roll back the API/frontend deployment first. Do not roll back a database migration by deleting data; use a reviewed forward-fix migration or restore the verified staging snapshot.
