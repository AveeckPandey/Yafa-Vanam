# Frontend deployment (Vercel)

Import the repository in Vercel with:

- **Root Directory:** `apps/web`
- **Include source files outside Root Directory:** ON — `lib/catalog.ts` imports `data/processed/Product.json` from the repo root, so the catalogue must ship into the build
- Framework preset Next.js (auto-detected); Node 22 default

The root `vercel.json` was removed: it was inert once the root directory moved to `apps/web`. The proxy layer is the route handlers under `apps/web/app/api/*`, which run inside Vercel functions and forward to the Go API and the advisor service.

Set the production domain to `yafavanam.com`; redirect `www.yafavanam.com` if it is added.

## Environment variables

### Runtime (server-side; changeable without a rebuild)

| Variable | Value / notes |
| --- | --- |
| `COMMERCE_API_URL` | `https://api.yafavanam.com`. Base for every server-side call to the Go API (cart, checkout, auth bridge). There is deliberately **no localhost fallback** — an unset value makes commerce routes fail loudly with 503 instead of silently pointing at `localhost:4000`. |
| `ADVISOR_URL` | Base of the Python recommendation service (e.g. its Railway/public URL), consumed by `/api/advisor/*` and `/api/yafa/*` proxies. Leave blank to keep those routes returning a clean 503 until the service is reachable. |
| `YAFA_INTERNAL_SERVICE_TOKEN` | Shared bearer token the `/api/yafa/*` proxy presents to the advisor service. Must equal the token configured on the service side. Required once the Yafa selfie flow is enabled. |
| `COGNITO_REGION` | e.g. `ap-south-1`. |
| `COGNITO_USER_POOL_ID` | Pool ID (`ap-south-1_…`). |
| `COGNITO_CLIENT_ID` | Confidential app client ID (`generate-secret`). |
| `COGNITO_CLIENT_SECRET` | Client secret. Used only server-side to compute SecretHash; never shipped to the browser. |

All four `COGNITO_*` values must be set together: `GET /api/auth/capability` reports `"cognito"` only when every one of them is present, otherwise the storefront falls back to native (Go-managed) accounts.

### Build-time (baked into the client bundle; set before deploying)

| Variable | Value / notes |
| --- | --- |
| `NEXT_PUBLIC_SITE_URL` | `https://yafavanam.com` — feeds `metadataBase` so OG/canonical URLs resolve on Vercel. |
| `NEXT_PUBLIC_AUTH_PROVIDER` | Leave **blank**. The provider is decided at runtime by `/api/auth/capability`; forcing this value reintroduces the dead-buttons trap. |
| `NEXT_PUBLIC_COGNITO_GOOGLE_ENABLED` | `false` until Google federation is actually enabled in Cognito. |
| `NEXT_PUBLIC_SENTRY_DSN` | Browser error monitoring; loaded via `instrumentation-client.ts` → `sentry.client.config.ts`. |
| `SENTRY_DSN` | Optional server-side Sentry reporting. |
| `NEXT_PUBLIC_POSTHOG_KEY` / `NEXT_PUBLIC_POSTHOG_HOST` | Only if analytics has consent. Host defaults to `https://us.i.posthog.com`. |
| `NEXT_PUBLIC_GA_MEASUREMENT_ID` | Only if GA is enabled after consent. |

NextAuth variables (`NEXTAUTH_URL`, `NEXTAUTH_SECRET`) are not used by this app and should not be set.

## Post-deploy smoke checks

1. Homepage renders with all campaign imagery (`/images/home/campaign/` is committed).
2. Cart round-trip works against the production Go API.
3. Sign-up with a real email address exercises the Cognito verification email end-to-end.
4. Gated routes (`/account`) require sign-in; sign-out revokes the session.
5. Yafa selfie flow, Razorpay test order, and friendly error states when the backend is unreachable.
