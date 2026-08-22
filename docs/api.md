# Go Commerce API

The backend in `apps/api` now provides a runnable commerce slice for the storefront.

## Implemented

- Active product catalogue, category discovery, search, filtering, and pagination.
- Anonymous server-owned carts with product/variant validation and server-calculated prices.
- Quantity updates, removal, stock-aware sellability checks, and a 20-unit line limit.
- Pending-payment order creation with shipping calculation and idempotency keys.
- Private order lookup using an order access token.
- Strict JSON decoding, structured errors, CORS, security headers, panic recovery, timeouts, JSON logs, and graceful shutdown.
- OpenAPI contract at `apps/api/openapi/openapi.yaml` covering every route: catalogue,
  carts, orders, Razorpay payments, session auth (`/auth/*`), and the YAFA beauty-profile
  flow.
- TypeScript types for the storefront are generated from that spec into
  `packages/frontend-types` (`@yafa/frontend-types`). After any contract change run
  `npm run generate:api-types` and commit the regenerated file.

The Next.js `/api/cart` routes are a browser-facing adapter. They keep only the opaque cart ID in an HTTP-only cookie; catalogue prices and totals come from Go.

## Run locally

From the repository root:

```bash
npm run dev:api
```

The API resolves `data/processed/Product.json` automatically. Override it with `YAFA_CATALOGUE_PATH` when needed.

Useful endpoints:

```text
GET  http://localhost:4000/health
GET  http://localhost:4000/api/v1/products?category=Makeup&q=tint
POST http://localhost:4000/api/v1/carts
POST http://localhost:4000/api/v1/orders
```

## Current persistence boundary

Catalogue data is loaded from the normalized 78-product JSON snapshot at startup. Carts, orders, and Razorpay payment records persist through PostgreSQL (`internal/commerce/postgres_store.go`, migration `000005_commerce_persistence.sql`) whenever `DATABASE_URL` is configured — they survive restarts and deploys, with transactional order creation, idempotency-key replay, and a `payments` audit row per Razorpay order. Without `DATABASE_URL` (local development only) the API falls back to the ephemeral in-memory store and logs an explicit warning at startup; never run production that way. Both backends implement the same `commerce.CommerceStore` interface and are covered by tests (`go test ./...`; set `TEST_DATABASE_URL` to include the PostgreSQL suite).
