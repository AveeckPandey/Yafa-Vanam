# Go Commerce API

The backend in `apps/api` now provides a runnable commerce slice for the storefront.

## Implemented

- Active product catalogue, category discovery, search, filtering, and pagination.
- Anonymous server-owned carts with product/variant validation and server-calculated prices.
- Quantity updates, removal, stock-aware sellability checks, and a 20-unit line limit.
- Pending-payment order creation with shipping calculation and idempotency keys.
- Private order lookup using an order access token.
- Strict JSON decoding, structured errors, CORS, security headers, panic recovery, timeouts, JSON logs, and graceful shutdown.
- OpenAPI contract at `apps/api/openapi/openapi.yaml`.

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

Catalogue data is loaded from the normalized 78-product JSON snapshot at startup. Cart and pending-order state is process-local in this first vertical slice, so it resets when the API restarts. The existing PostgreSQL schema remains the target for the durable repository implementation. Razorpay order/payment creation must be added before accepting real checkout payments.
