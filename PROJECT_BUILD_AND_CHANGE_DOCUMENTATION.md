# YAFA VANAM Project Build and Change Documentation

**Document date:** 18 August 2026  
**Published repository:** `BuildWithAveeck/Yafavanam`  
**Published production branch:** `main`  
**Application commit documented:** `2d0005d` (`Add production web start script`)  
**Railway project:** `prolific-patience` (`c75e742f-0322-4636-865e-882194c67ccf`)  
**Railway environment:** `production`

## 1. Purpose and status terminology

This document records the implementation and deployment work completed so far. It distinguishes application code that exists in the repository from infrastructure that has actually been configured and verified.

- **Created** means the file, component, module, migration, or service did not previously exist and was added.
- **Edited** means an existing file or component was changed.
- **Configured** means infrastructure or service settings were changed without the change itself being application source code.
- **Implemented** means the code exists and passes the stated local checks. It does not necessarily mean the feature has been verified against the production Railway environment.
- **Verified in production** means the relevant Railway service or externally reachable behavior was directly observed and confirmed.

## 2. Current architecture

The repository is a monorepo with these principal parts:

| Layer | Location | Technology | Responsibility | Current state |
|---|---|---|---|---|
| Customer web application | `apps/web` | Next.js, React, TypeScript | Catalogue browsing, product pages, advisor UI, cart UI, authentication modal, account and utility pages | Builds successfully; Railway service reports `SUCCESS`; no public domain recorded |
| Commerce and authentication API | `apps/api` | Go 1.23, `net/http` | Catalogue, carts, orders, authentication, JWT validation, Google OAuth, PostgreSQL and Redis connections | Implemented and locally tested; not yet deployed as a separate Railway service |
| Recommendation engine | `services/recommendation-engine` | Python, FastAPI | Advisor sessions, ranking, shade matching, and product recommendations | Existing service edited; Railway production deployment not started or verified |
| Primary relational database | `apps/api/db/migrations` and Railway Postgres | PostgreSQL | Users, credentials, products, variants, orders, customer data, inventory and operational records | Railway service online; migrations have not been verified as applied |
| Authentication session store | Railway Redis | Redis | Refresh-token allow-list, rotation, expiry and revocation | Railway service online; API integration not production-verified |
| Local orchestration | `docker-compose.yml` | Docker Compose | Local PostgreSQL, Redis, Go API, and recommendation engine | Available for local development only; not the production deployment mechanism |
| Internal operations starter | `retool` | SQL and documentation | Query templates for a future private Retool operations dashboard | Starter assets only; no Retool application has been built or connected |

### Runtime request flow

1. The browser loads the Next.js application.
2. Public catalogue, product and advisor browsing remains available without authentication.
3. Purchase actions call `useRequireAuth`.
4. If no authenticated user exists, the action is stored temporarily and the authentication modal opens.
5. Authentication calls the Go API directly using credentialed browser requests.
6. The Go API writes users and credentials to PostgreSQL, creates signed JWT cookies, and stores refresh-session state in Redis.
7. After successful authentication, the deferred purchase action runs automatically.
8. Next.js cart route handlers act as a browser-facing adapter and forward the authentication cookie to the Go commerce API.
9. The Go API validates the authenticated user and cart ownership before returning or changing cart state.

## 3. Frontend and Next.js changes

### 3.1 Authentication provider and hooks

| Field | Detail |
|---|---|
| What | Global authentication state, session loading, login/register/logout methods, modal control, and deferred purchase actions |
| Location | `apps/web/components/auth/AuthProvider.tsx` |
| Change type | **Created** |
| Change | Added `AuthProvider`, `useAuth()`, and `useRequireAuth(action)`. Added calls to `/auth/csrf`, `/auth/me`, `/auth/login`, `/auth/register`, `/auth/logout`, and Google OAuth. Requests use `credentials: "include"`. |
| Why | Browsing must remain public while purchase actions require authentication without redirecting the user away from the current page. |
| How | `useRequireAuth` immediately executes an action for an authenticated user. Otherwise, it stores the callback in a ref and opens the modal. Successful authentication updates the user and invokes the stored callback. Closing the modal clears the deferred action. |
| Dependencies | React context/hooks, Go authentication API, browser cookies, `NEXT_PUBLIC_API_URL` |
| Status | Implemented; TypeScript and production build pass |
| Remaining | Production API URL and public API domain must be configured; refresh-on-access-expiry is not automatically attempted by the provider; Google OAuth return flow needs production verification. |

### 3.2 Authentication modal

| Field | Detail |
|---|---|
| What | In-place Sign In / Sign Up modal |
| Location | `apps/web/components/auth/AuthModal.tsx` |
| Change type | **Created** |
| Change | Added tab-switchable sign-in and sign-up forms, full-name/email/password/confirmation fields, Remember Me, Google sign-in, error display, busy state, click-outside dismissal, and Escape-key dismissal. |
| Why | Purchase authentication must be non-blocking and preserve the current page and interrupted action. |
| How | Form submission calls methods supplied by `AuthProvider`. The modal is rendered globally and locks document scrolling while open. |
| Dependencies | `AuthProvider`, Go auth endpoints, Google OAuth configuration |
| Status | Implemented |
| Remaining | Forgot Password is currently a visual button only; focus trapping and focus restoration should receive a dedicated accessibility test; Google OAuth production test remains. |

### 3.3 Global layout integration

| Field | Detail |
|---|---|
| What | Authentication context made available to the entire storefront |
| Location | `apps/web/app/layout.tsx` |
| Change type | **Edited** |
| Change | Wrapped the existing navigation, pages, footer, cart drawer and advisor in `AuthProvider`. |
| Why | Navbar, product components and cart components all need one consistent session and modal state. |
| How | The client provider is mounted inside the root body while the root layout remains the global shell. |
| Dependencies | `AuthProvider` |
| Status | Implemented and included in successful Next.js build |
| Remaining | Production session behavior must be tested with the deployed API. |

### 3.4 Protected Add to Bag

| Field | Detail |
|---|---|
| What | Purchase gate for product add-to-cart actions |
| Location | `apps/web/components/product/AddToBag.tsx` |
| Change type | **Edited** |
| Change | Wrapped the existing asynchronous add operation with `useRequireAuth`. |
| Why | The requirement permits public browsing but requires authentication at purchase intent. |
| How | An unauthenticated click opens the modal. After sign-in or registration, the original add operation resumes and opens the cart drawer. |
| Dependencies | `AuthProvider`, cart client, Next.js `/api/cart`, Go API |
| Status | Implemented locally |
| Remaining | Must be verified against the production web/API domains after the API is deployed. |

### 3.5 Protected checkout action

| Field | Detail |
|---|---|
| What | Authentication gate for checkout navigation |
| Location | `apps/web/components/cart/CartDrawer.tsx` |
| Change type | **Edited** |
| Change | Replaced direct checkout navigation with a `useRequireAuth` callback that closes the cart and navigates to `/checkout`. |
| Why | Checkout must not proceed for an anonymous user while browsing and cart inspection remain non-blocking. |
| How | The router action is deferred until authentication succeeds. |
| Dependencies | `AuthProvider`, Next.js router |
| Status | Implemented |
| Remaining | The checkout page itself is still a scaffold and payments are not implemented. Direct URL access to `/checkout` should be backed by a server-enforced checkout API before launch. |

### 3.6 Navbar account control

| Field | Detail |
|---|---|
| What | Session-aware account icon |
| Location | `apps/web/components/layout/Navbar.tsx` |
| Change type | **Edited** |
| Change | Changed the account link into a button that opens authentication when signed out and logs out when signed in. Existing bag-count behavior remains. |
| Why | Users need an explicit way to open authentication without requiring a purchase click. |
| How | Reads `isAuthenticated`, `openAuth`, and `logout` from the global auth context. |
| Dependencies | `AuthProvider` |
| Status | Implemented |
| Remaining | A signed-in account menu/profile link should replace the current one-click logout behavior. |

### 3.7 Authentication styling

| Field | Detail |
|---|---|
| What | Authentication modal presentation and responsive styling |
| Location | `apps/web/app/globals.css` |
| Change type | **Edited** |
| Change | Added modal backdrop, dialog, tabs, form controls, messages, Google button, mobile spacing, and related states. Other global storefront styles were also expanded as part of the larger UI implementation. |
| Why | The new authentication flow required a usable, on-brand modal across desktop and mobile. |
| How | Global class selectors style the modal emitted by `AuthModal`. |
| Dependencies | Existing design tokens and global CSS |
| Status | Implemented; visual production review still recommended |

### 3.8 Browser-facing cart API adapter

| Field | Detail |
|---|---|
| What | Next.js server-side adapter between the browser cart and Go API |
| Locations | `apps/web/app/api/cart/route.ts`, `apps/web/app/api/cart/items/[key]/route.ts`, `apps/web/lib/cart-server.ts`, `apps/web/lib/commerce-api.ts` |
| Change type | **Edited** for existing cart routes/server utilities; **Created** for `commerce-api.ts` |
| Change | Removed the old full-cart payload stored in a cookie. The browser now stores only an opaque cart ID. Added typed Go API requests, structured error handling, server-calculated cart conversion, and forwarding of the authenticated cookie to the Go API. |
| Why | Prices, product validity, stock rules and cart ownership must be enforced by the server rather than trusted from browser cookies. |
| How | Next route handlers validate request shapes with Zod, call the Go API, then map API cart lines into the frontend response. `yafa-cart-id` is `httpOnly`, secure in production, and contains only the cart identifier. |
| Dependencies | Next.js route handlers, Zod, Go commerce API, `COMMERCE_API_URL` or `NEXT_PUBLIC_API_URL` |
| Status | Implemented and production build passes |
| Remaining | Will return service-unavailable errors until the production Go API exists and the web variables point to it. Durable cart state is not yet backed by PostgreSQL. |

### 3.9 Product and catalogue UI changes

| File/location | Type | What changed and why | Status / remaining work |
|---|---|---|---|
| `apps/web/components/product/ProductPageClient.tsx` | **Edited** | Improved selected-variant and purchase behavior so product pages pass valid variant information into purchase controls. | Implemented; visually re-test representative products. |
| `apps/web/components/product/QuickShop.tsx` | **Edited** | Improved variant display/fallback behavior used by quick shop. | Implemented. |
| `apps/web/lib/catalog-types.ts` | **Edited** | Expanded shade data with code and undertone fields. | Implemented. |
| `apps/web/lib/catalog.ts` | **Edited** | Added shade label and preview fallbacks for incomplete normalized catalogue rows and mapped the expanded shade fields. | Implemented; fallback palette should eventually be replaced by authoritative catalogue color data. |
| `apps/web/app/makeup/MakeupCatalog.tsx` | **Edited** | Added URL-aware product-type filtering and filter state handling. | Implemented. |
| `apps/web/app/skincare/SkinCareCatalog.tsx` | **Edited** | Added URL-aware type filtering and reset behavior. | Implemented. |
| `apps/web/app/body-care/BodyCareCatalog.tsx` | **Edited** | Added URL-aware type filtering and filter status messaging. | Implemented. |
| `apps/web/app/fragrance/FragranceCatalog.tsx` | **Edited** | Added URL-aware type filtering and filter state behavior. | Implemented. |
| `apps/web/app/{makeup,skincare,body-care,fragrance}/page.tsx` | **Edited** | Wrapped URL-search-dependent catalogues in Suspense boundaries for Next.js rendering compatibility. | Implemented; production build confirms compatibility. |
| `apps/web/app/shop/ShopCatalog.tsx` | **Created** | Added the interactive shop catalogue experience. | Implemented. |
| `apps/web/app/shop/page.tsx` | **Edited** | Replaced scaffold output with the shop catalogue. | Implemented. |
| `apps/web/app/search/SearchExperience.tsx` | **Created** | Added an interactive product search experience. | Implemented. |
| `apps/web/app/search/page.tsx` | **Edited** | Connected the search route to the new search experience. | Implemented. |

### 3.10 Account, utility, and merchandising pages

| File/location | Type | What changed and why | Status / remaining work |
|---|---|---|---|
| `apps/web/app/account/page.tsx` | **Edited** | Replaced a scaffold with styled returning/new-customer account choices. | UI implemented; links lead to legacy standalone forms rather than the global modal. |
| `apps/web/app/auth/AuthForm.tsx` | **Created** | Added standalone sign-in/sign-up page presentation. | It intentionally does not submit credentials; should be connected to `useAuth` or replaced with modal invocation. |
| `apps/web/app/auth/sign-in/page.tsx` | **Edited** | Replaced scaffold route with `AuthForm`. | Presentation only; functional integration remains. |
| `apps/web/app/auth/sign-up/page.tsx` | **Edited** | Replaced scaffold route with `AuthForm`. | Presentation only; functional integration remains. |
| `apps/web/app/build-my-kit/BuildMyKit.tsx` | **Created** | Added a multi-step kit-building interaction and recommendation presentation. | Implemented; persistence/checkout integration remains. |
| `apps/web/app/build-my-kit/page.tsx` | **Edited** | Connected the route to the kit builder. | Implemented. |
| `apps/web/app/contact/ContactForm.tsx` | **Created** | Added a client-side contact form experience. | UI only unless a delivery endpoint is subsequently added. |
| `apps/web/app/contact/page.tsx` | **Edited** | Connected the contact route to the new form. | Implemented UI. |
| `apps/web/components/layout/Footer.tsx` | **Edited** | Expanded footer navigation/content. | Implemented. |
| `apps/web/components/layout/MegaMenu.tsx` | **Edited** | Updated merchandising/navigation links and structure. | Implemented. |
| `apps/web/components/advisor/MakeupAdvisor.module.css` | **Edited** | Minor advisor presentation adjustment. | Implemented. |
| `apps/web/app/icon.png` | **Created** | Added application icon asset. | Implemented. |
| `apps/web/public/images/brand/yv-mark.png` | **Created** | Added the YAFA VANAM brand mark. | Implemented. |
| `apps/web/public/images/hero/yafa-vanam-cheek-collection.png` | **Edited** | Updated hero/collection artwork. | Implemented. |
| `apps/web/public/images/hero/yafa-vanam-fragrance-collection.png` | **Deleted** | Removed a redundant/incorrect hero asset during asset cleanup. | Verify no external campaign depends on the removed path. |
| `apps/web/AGENTS.md`, `apps/web/CLAUDE.md` | **Created** | Added local development/agent guidance files. | Repository guidance only; no runtime effect. |

## 4. Go API and commerce changes

### 4.1 Runnable API server

| Field | Detail |
|---|---|
| What | Production-oriented `net/http` API server |
| Locations | `apps/api/platform/httpserver/server.go`, `apps/api/platform/httpserver/server_test.go` |
| Change type | **Created** |
| Change | Added health/readiness, catalogue, cart, order and auth route registration; JSON decoding/errors; request logging; CORS; recovery; security headers; and ownership-aware route handlers. |
| Why | The previous package was a scaffold and could not serve the storefront commerce/authentication requirements. |
| How | Go 1.23 method-aware `http.ServeMux` patterns dispatch handlers. Middleware adds logs, configured CORS, panic recovery and security response headers. Auth middleware wraps cart/order endpoints when auth is enabled. |
| Dependencies | Go standard library, auth service, commerce store |
| Status | Implemented; `go test ./...` passed |
| Remaining | When authentication configuration is absent, the server currently registers anonymous fallback cart/order routes. Production must fail closed instead of allowing this fallback. Add a production health check that verifies database/Redis connectivity rather than only process/catalogue health. |

### 4.2 API process startup and infrastructure clients

| Field | Detail |
|---|---|
| What | Go API bootstrap with PostgreSQL, Redis and authentication configuration |
| Location | `apps/api/cmd/api/main.go` |
| Change type | **Edited** |
| Change | Added catalogue loading, environment configuration, PostgreSQL pool creation, Redis client creation, connectivity checks, auth service/handler construction, server timeouts, logging and graceful shutdown. |
| Why | Authentication requires durable user records and revocable refresh sessions; the API also needed predictable production startup/shutdown behavior. |
| How | Auth is enabled only when `DATABASE_URL`, `REDIS_URL`, and a 32+ character `JWT_SECRET` are present. `APP_ENV=production` enables secure cookies. |
| Dependencies | `pgxpool`, `go-redis`, auth module, Railway variables |
| Status | Implemented and locally tested |
| Remaining | API Railway service does not exist yet. Startup retry/backoff should be added because Railway service ordering is not guaranteed. Missing auth configuration should terminate production startup rather than log a warning and continue. |

### 4.3 Catalogue service

| Field | Detail |
|---|---|
| What | Go catalogue loader, filter and sellability layer |
| Location | `apps/api/internal/commerce/catalog.go` |
| Change type | **Created** |
| Change | Loads `data/processed/Product.json`, builds product/variant indexes, lists categories/products, resolves products by slug and validates sellable variants. |
| Why | Cart pricing and product selection cannot safely depend on browser-supplied product details. |
| How | The catalogue snapshot is read at startup and exposed through typed Go models and indexed lookups. |
| Dependencies | Normalized catalogue JSON |
| Status | Implemented and tested |
| Remaining | Replace snapshot-only catalogue authority with durable PostgreSQL repositories or a defined catalogue synchronization strategy. |

### 4.4 Cart and order store

| Field | Detail |
|---|---|
| What | Server-owned cart and pending-order logic with ownership controls |
| Locations | `apps/api/internal/commerce/store.go`, `apps/api/internal/commerce/commerce_test.go` |
| Change type | **Created** |
| Change | Added cart creation/read/update/remove, quantity and stock validation, server-side totals, user ownership checks, order creation, shipping calculation, idempotency, and authenticated order lookup. |
| Why | Browser-side carts can be manipulated. The server must control product validity, prices, quantities and record ownership. |
| How | Carts and orders are held in synchronized in-memory maps. Authenticated handler methods attach/check JWT user IDs. IDs are cryptographically random. |
| Dependencies | Catalogue service, auth context |
| Status | Implemented and unit-tested |
| Remaining | **Major blocker:** cart and order data is process-local and will be lost on restart or redeploy. Move it to the existing PostgreSQL `carts`, `cart_items`, `orders`, and `order_items` tables before accepting production orders. Razorpay/payment capture is not implemented. |

### 4.5 OpenAPI and API documentation

| File/location | Type | Change and reason | Status |
|---|---|---|---|
| `apps/api/openapi/openapi.yaml` | **Edited** | Expanded the contract for implemented catalogue, cart and order endpoints. | Needs another update for the final authenticated ownership behavior and auth endpoints. |
| `docs/api.md` | **Edited** | Documented runnable commerce endpoints, local operation and the in-memory persistence boundary. | Partially stale: references anonymous carts/private order access tokens from an earlier slice and must be revised to match authenticated routes. |
| `README.md` | **Edited** | Added commerce API discovery information. | Implemented; production instructions can be expanded. |
| `IMPLEMENTATION_SUMMARY.md` | **Edited** | Updated catalogue path and marked the commerce slice as implemented. | Partially stale regarding anonymous carts after the later ownership changes. |

## 5. Authentication and security implementation

### 5.1 Authentication service and password hashing

| Field | Detail |
|---|---|
| What | Registration, credential validation, Google-user upsert, JWT issuance, refresh rotation, revocation and access validation |
| Location | `apps/api/internal/auth/service.go` |
| Change type | **Created** |
| Change | Added bcrypt password hashing, parameterized PostgreSQL queries, HS256 JWT access/refresh tokens, random refresh IDs, Redis TTL sessions, Remember Me lifetime selection, refresh rotation and logout revocation. |
| Why | Passwords must never be stored in plaintext, and session tokens must be revocable even when JWTs are used. |
| How | Registration hashes with `bcrypt.GenerateFromPassword` at the default cost. Login uses `bcrypt.CompareHashAndPassword`. Access tokens last 15 minutes. Refresh tokens normally last one day or 30 days for Remember Me. Redis stores the refresh ID and user/remember state; rotation deletes the old key before issuing a replacement. |
| Dependencies | `golang.org/x/crypto/bcrypt`, `github.com/golang-jwt/jwt/v5`, `pgx`, Redis |
| Status | Implemented and compiles/tests locally |
| Remaining | Registration user/credential inserts are not in a single database transaction, so a credential insert failure can leave a user without credentials. Add transaction handling. Add password policy, email verification, password reset and credential-change flows. Documentation currently says Argon2id but the implementation is bcrypt; align the docs. |

### 5.2 Authentication HTTP handlers

| Field | Detail |
|---|---|
| What | Authentication REST and OAuth endpoints |
| Location | `apps/api/internal/auth/handler.go` |
| Change type | **Created** |
| Change | Added `GET /auth/csrf`, `GET /auth/me`, login/register/refresh/logout, Google authorization and callback handlers, cookie creation/clearing, CSRF validation, and basic login/register rate limiters. |
| Why | The frontend needs secure server endpoints for first-party credentials and Google sign-in. |
| How | State-changing calls require the CSRF cookie to match `X-CSRF-Token`. JWTs are set in `HttpOnly`, `SameSite=Strict` cookies, with `Secure` in production. OAuth uses a random state cookie and validated relative return path. |
| Dependencies | Auth service, `golang.org/x/oauth2`, Google OAuth, `golang.org/x/time/rate` |
| Status | Implemented locally |
| Remaining | Rate limiters are global and process-local, not per-IP/per-email and not Redis-backed. Request bodies need strict size/unknown-field enforcement. Google response handling should require an explicitly verified email claim. OAuth state cookies should be cleared after use. Production callback and cookie behavior remain unverified. Forgot-password and email-verification endpoints are not implemented. |

### 5.3 Auth middleware and ownership

| Field | Detail |
|---|---|
| What | JWT validation middleware and authenticated-user request context |
| Location | `apps/api/internal/auth/middleware.go` |
| Change type | **Created** |
| Change | Added middleware that validates the access cookie, rejects unauthorized calls, and stores the verified user in request context. |
| Why | Cart/order authorization must be enforced by the backend, not only by the React modal. |
| How | Protected handlers retrieve the JWT-derived user using `UserFromContext`; commerce ownership methods compare that ID to the cart/order owner. |
| Dependencies | Auth service, Go context |
| Status | Implemented and attached to cart/order routes when auth is configured |
| Remaining | Enforce a fail-closed production mode and add integration tests proving one user cannot access another user's records. |

### 5.4 Security headers and request controls

| Field | Detail |
|---|---|
| What | API response hardening and CORS control |
| Location | `apps/api/platform/httpserver/server.go` |
| Change type | **Created/edited during implementation** |
| Change | Added `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, `Permissions-Policy`, API-oriented Content Security Policy, HSTS for TLS requests, configured-origin CORS, panic recovery and body limits for the general JSON decoder. |
| Why | Reduce browser attack surface, prevent unauthorized cross-origin credential use and avoid unhandled process crashes. |
| How | Middleware applies headers and only reflects origins present in `CORS_ALLOWED_ORIGINS`. Credentialed CORS is enabled for allowed origins. |
| Dependencies | Correct production domain values and Railway HTTPS proxy behavior |
| Status | Implemented locally |
| Remaining | Verify whether Railway forwards TLS state in a way that activates HSTS; otherwise honor a trusted forwarded-proto header. Add a web-app CSP suitable for Next.js assets. Add Cloudflare/Turnstile or equivalent bot control, dependency scanning, audit event writes and monitoring. |

## 6. Database and migrations

### 6.1 Core schema

| Field | Detail |
|---|---|
| What | Core PostgreSQL commerce/customer schema |
| Location | `apps/api/db/migrations/000001_core_schema.sql` |
| Change type | Existing migration used as the foundation |
| Contents | Categories, products, shades, ingredients, variants, images, users, addresses, profiles, carts, orders, payments, refunds, returns, reviews, metrics, badges, promotions, coupons and lifecycle messaging. |
| Why | Provides the durable relational target for commerce and customer operations. |
| Status | File exists; application against Railway Postgres not verified |

### 6.2 Production hardening schema

| Field | Detail |
|---|---|
| What | Authentication, inventory, audit and production data extensions |
| Location | `apps/api/db/migrations/000002_production_hardening.sql` |
| Change type | **Created** |
| Change | Added user status/verification fields, credentials, sessions/tokens/events, inventory batches/movements, order snapshots, coupon redemptions, shipments, AI consultation/upload/recommendation records, audit logs and supporting indexes. |
| Why | The initial schema did not cover credential storage, token lifecycle, expiring inventory, auditability or AI-data retention boundaries. |
| How | Uses PostgreSQL constraints, foreign keys, partial indexes and immutable snapshot fields to preserve operational integrity. |
| Dependencies | Migration `000001`; PostgreSQL `pgcrypto` extension |
| Status | Created and published; Railway application not verified |
| Remaining | Comments/docs say Argon2id while code stores bcrypt hashes. `auth_sessions`/`auth_tokens` tables are not used by the current Redis JWT implementation. Decide whether to retain them for audit/recovery or remove the unused model. |

### 6.3 Google OAuth identity schema

| Field | Detail |
|---|---|
| What | Google identity and avatar columns |
| Location | `apps/api/db/migrations/000003_auth_oauth.sql` |
| Change type | **Created** |
| Change | Adds unique `google_subject` and optional `avatar_url` to users. |
| Why | Google sign-in needs a stable provider identity independent of mutable email/display values. |
| Dependencies | Migrations `000001` and `000002` |
| Status | Created and published; Railway application not verified |

### 6.4 Required migration order

Apply exactly in this order:

1. `apps/api/db/migrations/000001_core_schema.sql`
2. `apps/api/db/migrations/000002_production_hardening.sql`
3. `apps/api/db/migrations/000003_auth_oauth.sql`

No automatic migration runner is currently included in the Go startup path or Railway configuration. Applying these scripts manually or adding an idempotent migration tool/pre-deploy command is required before the API can authenticate users.

## 7. Environment variables and secrets

### 7.1 Environment templates

| Field | Detail |
|---|---|
| What | Local and example environment configuration |
| Locations | `.env` (local, ignored), `.env.example` (published) |
| Change type | `.env` **Created locally**; `.env.example` **Edited** |
| Change | Added PostgreSQL, Redis, JWT, app URL, CORS and Google OAuth variables, plus existing analytics, AI, payment, CRM and messaging placeholders. |
| Why | Each service needs explicit configuration without committing live credentials. |
| How | `.env` supplies local defaults; `.env.example` documents required keys. Railway values must be entered as service variables rather than committed files. |
| Status | Local file exists and is ignored by Git; example is published |
| Remaining | Replace all production placeholders with Railway secrets/reference variables. Never use `change-me` or the local Docker JWT secret in production. |

### 7.2 Required API production variables

| Variable | Purpose | Expected production value/status |
|---|---|---|
| `DATABASE_URL` | PostgreSQL connection | Railway reference `${{Postgres.DATABASE_URL}}`; not verified on an API service |
| `REDIS_URL` | Refresh-session connection | Railway reference `${{Redis.REDIS_URL}}`; not verified on an API service |
| `JWT_SECRET` | HS256 signing secret | New high-entropy secret of at least 32 characters; not configured/verified |
| `APP_ENV` | Enables production cookie behavior | Must be `production`; not configured/verified |
| `API_PORT` | API listener | `4000` is supported; Railway may also expose `PORT`, which the code does not currently read |
| `APP_URL` | OAuth redirect target/front-end base | Must be the final web public domain; blocked until domain generation |
| `CORS_ALLOWED_ORIGINS` | Credentialed browser origin allow-list | Must be the exact HTTPS web domain; blocked until domain generation |
| `GOOGLE_CLIENT_ID` | Google OAuth client | Not configured |
| `GOOGLE_CLIENT_SECRET` | Google OAuth secret | Not configured |
| `GOOGLE_CALLBACK_URL` | OAuth callback | Must be `https://<api-domain>/auth/google/callback`; blocked until API domain generation |
| `YAFA_CATALOGUE_PATH` | Catalogue snapshot path | Docker image sets `/app/data/processed/Product.json` |

### 7.3 Required web production variables

| Variable | Purpose | Status |
|---|---|---|
| `NEXT_PUBLIC_API_URL` | Browser-visible Go API base for auth | Must be the public HTTPS API domain; not configured/verified |
| `COMMERCE_API_URL` | Server-side Next.js-to-Go commerce base | Can use the API public URL initially or Railway private URL; not configured/verified |
| `NEXT_PUBLIC_ADVISOR_URL` | Recommendation service endpoint | Not production-configured |
| `NEXT_PUBLIC_POSTHOG_KEY` / `NEXT_PUBLIC_POSTHOG_HOST` | Optional PostHog analytics | Not configured |
| `NEXT_PUBLIC_GA_MEASUREMENT_ID` | Optional GA4 analytics and UTM attribution | Not configured |

## 8. Docker and local development

### 8.1 Go API Dockerfile

| Field | Detail |
|---|---|
| What | Multi-stage Go API image |
| Location | `apps/api/Dockerfile` |
| Change type | **Edited** |
| Change | Builds the Go API from the monorepo, copies the normalized catalogue into the runtime image, runs as a non-root user and exposes port 4000. |
| Why | Railway needs a reproducible API image with the catalogue available at runtime and without unnecessary build tooling in the final image. |
| How | A Go Alpine build stage creates a static binary; the runtime Alpine stage contains only the binary/catalogue and a non-root account. |
| Dependencies | Repository-root Docker build context, `apps/api/go.mod`, `go.sum`, catalogue JSON |
| Status | Dockerfile exists and Go code builds locally; Railway API image deployment not started |
| Remaining | Configure a separate Railway repo service with Dockerfile path `apps/api/Dockerfile`; consider adding a container health check. |

### 8.2 Docker Compose

| Field | Detail |
|---|---|
| What | Local development stack |
| Location | `docker-compose.yml` |
| Change type | **Edited** |
| Change | Added Redis and API auth connection variables/dependencies alongside local PostgreSQL and recommendation engine. |
| Why | Local authentication requires both PostgreSQL and Redis. |
| How | Services communicate over the Compose network using `postgres` and `redis` hostnames. |
| Status | Configuration exists; full local Compose startup was not verified in this work session |
| Production decision | **Do not deploy these raw Compose database containers to Railway production.** Railway managed Postgres and managed Redis intentionally replace the `postgres` and `redis` Compose services. The Compose API/recommendation services are local equivalents; production should use separate Railway application services. |

### 8.3 Recommendation engine container and catalogue fixes

| File/location | Type | Change and reason | Status |
|---|---|---|---|
| `services/recommendation-engine/Dockerfile` | **Edited** | Corrected catalogue filename from `products.json` to `Product.json`. | Implemented; production not deployed. |
| `services/recommendation-engine/README.md` | **Edited** | Corrected documented catalogue path. | Complete. |
| `services/recommendation-engine/app/advisor/catalogue.py` | **Edited** | Corrected default catalogue path/case. | Implemented. |
| `services/recommendation-engine/app/advisor/recommender.py` | **Edited** | Centralized shade-result construction. | Implemented. |
| `services/recommendation-engine/app/advisor/shade_matcher.py` | **Edited** | Added canonical fallback shade naming and reused it across matching paths. | Implemented; expand master shade metadata as catalogue quality improves. |

## 9. Railway deployment record

### 9.1 Railway project setup

| Field | Detail |
|---|---|
| What | Existing Railway project linked to the local repository |
| Location | Railway project `prolific-patience` |
| Change type | **Configured** |
| Change | Railway CLI authenticated and linked to project ID `c75e742f-0322-4636-865e-882194c67ccf`, production environment. |
| Why | Enables deployment/status operations against the correct infrastructure. |
| Status | Configured and verified |

### 9.2 Managed PostgreSQL

| Field | Detail |
|---|---|
| What | Railway managed PostgreSQL service |
| Location | Railway service `Postgres` |
| Change type | **Configured** (created through Railway UI before final documentation) |
| Change | PostgreSQL service and persistent volume provisioned. |
| Why | Provides durable user, credential and future commerce storage without running a self-managed production container. |
| Status | `SUCCESS` / online; volume present |
| Remaining | Apply migrations in order; attach `DATABASE_URL` to the future API service as a Railway reference variable; verify tables and credential insert. No public TCP exposure is required for normal service-to-service use. |

### 9.3 Managed Redis

| Field | Detail |
|---|---|
| What | Railway managed Redis service |
| Location | Railway service `Redis` |
| Change type | **Configured** |
| Change | Redis service and persistent volume provisioned. |
| Why | Stores refresh-session state and supports rotation/revocation. |
| Status | `SUCCESS` / online |
| Remaining | Attach `REDIS_URL` to the future API service as a Railway reference variable and verify login/refresh/logout keys and TTLs. |

### 9.4 Next.js web service

| Field | Detail |
|---|---|
| What | GitHub-connected Next.js production service |
| Location | Railway service `Yafavanam` |
| Change type | **Configured** plus repository **Edited** |
| Change | Connected `BuildWithAveeck/Yafavanam` branch `main`. Initial build failed because Railpack could not find a production start command. Added root script `npm run start --workspace=@yafa/web` in `package.json`, pushed commit `2d0005d`, and redeployed from source. |
| Why | Railway Railpack detects the root npm workspace and requires a production start command. |
| How | Root `npm run build` builds the web workspace; root `npm start` delegates to Next.js production start. |
| Dependencies | GitHub repository, Node/npm, `apps/web` workspace |
| Status | Railway reports `SUCCESS` at commit `2d0005d`; local `npm run build` also passed |
| Remaining | No Railway service domain is recorded. Generate a public domain, configure web/API variables, then redeploy. Verify the site over HTTPS. |

### 9.5 Go API Railway service

| Field | Detail |
|---|---|
| What | Separate Railway service for Go API |
| Intended location | New Railway service, recommended name `Yafavanam API` or `yafa-api` |
| Change type | **Not started** |
| Required configuration | Connect the same GitHub repo/branch, keep repository root as build context, select Dockerfile `apps/api/Dockerfile`, reference Postgres/Redis variables, add production auth/OAuth variables, and generate a public domain. |
| Why | The web app cannot perform production authentication/cart/order requests without a reachable API. |
| Status | Not present in current Railway service list |
| Blocker | Requires service creation and production variables. |

### 9.6 Public domains, CORS and Google OAuth

| Item | Current status | Required completion |
|---|---|---|
| Web public domain | Not generated/recorded | Generate under `Yafavanam` Networking. |
| API public domain | API service does not exist | Create API service, deploy successfully, generate domain. |
| CORS | Code implemented; production value absent | Set API `CORS_ALLOWED_ORIGINS=https://<web-domain>` exactly. |
| App URL | Production value absent | Set API `APP_URL=https://<web-domain>`. |
| Google OAuth | Code implemented; provider config absent | Create Google Web OAuth client; add web origin and `https://<api-domain>/auth/google/callback`; set three Google variables on API. |
| Web API variables | Production values unverified | Set `NEXT_PUBLIC_API_URL` and `COMMERCE_API_URL`, then rebuild the web service. |

### 9.7 Health and authentication verification checklist

These checks are **not yet completed in production**:

1. `GET https://<api-domain>/health` returns HTTP 200 and `status: ok`.
2. API logs do not contain `authentication disabled`.
3. Database contains tables from all three migrations.
4. `POST /auth/register` creates one `users` row and one `user_credentials` row.
5. `user_credentials.password_hash` begins with a bcrypt identifier and never contains plaintext.
6. Successful login sets `yafa_access` and `yafa_refresh` as `Secure`, `HttpOnly`, `SameSite=Strict` cookies.
7. Redis contains a refresh-session key with the correct TTL.
8. Refresh deletes the old Redis key and creates a new one.
9. Logout deletes the active refresh key and clears cookies.
10. Anonymous product browsing works.
11. Anonymous Add to Bag opens the modal and does not change the cart.
12. Successful authentication resumes Add to Bag automatically.
13. A second user cannot read or modify the first user's cart/order.
14. Google login returns to the correct storefront path.

## 10. Source control and publishing

| Field | Detail |
|---|---|
| What | Published project history to the requested GitHub repository |
| Location | `https://github.com/BuildWithAveeck/Yafavanam` |
| Change type | **Configured/published** |
| Change | Created `agent/publish-yafa-platform`, committed the complete 71-file workspace change as `326bd47`, then replaced the unrelated target `main` history after explicit approval. Added and published the Railway start fix as `2d0005d`. |
| Why | Railway needed the completed code on the repository's default branch. |
| Status | Target `main` points to `2d0005d` |
| Remaining | Local feature branch is ahead of its similarly named remote branch by one commit, although target `main` contains that commit. Remote naming remains split between old `origin` (`AveeckPandey/Yafa-Vanam`) and `publish-target` (`BuildWithAveeck/Yafavanam`); make the intended repository the canonical `origin` to prevent accidental pushes. |

## 11. Dependency changes

### Go dependencies

`apps/api/go.mod` was **edited** and `apps/api/go.sum` was **created** to add:

- `github.com/golang-jwt/jwt/v5` for signed JWTs.
- `github.com/jackc/pgx/v5` for PostgreSQL pooling and parameterized queries.
- `github.com/redis/go-redis/v9` for Redis refresh-session storage.
- `golang.org/x/crypto` for bcrypt.
- `golang.org/x/oauth2` for Google OAuth authorization and exchange.
- `golang.org/x/time` for basic request rate limiting.

These dependencies were downloaded successfully, and `go test ./...` passed.

### Web dependencies

No new npm package was required for the authentication modal. Existing React/Next.js capabilities and existing Zod validation were used. `npm run typecheck` and `npm run build` passed.

## 12. Retool folder status

The `retool` directory was not converted into a working dashboard during this work. It contains SQL query templates and setup documentation for a future private operations dashboard covering orders, customers, inventory, trending items and bestsellers.

- **Change type:** Existing starter; not materially implemented in this change set.
- **Current status:** Not connected to Railway and not deployed.
- **Security requirement:** Retool must use a restricted database role or protected admin API. It must not expose raw production database credentials to the public web application.
- **Remaining work:** Create the Retool app in the business account, configure restricted resources, import/adapt queries, add role-based staff access and audit operations.

## 13. Validation performed

| Check | Result |
|---|---|
| `npm run typecheck` | Passed |
| `npm run build` | Passed; Next.js generated 116 routes/pages including dynamic and static routes |
| `go test ./...` | Passed, including commerce and HTTP server tests |
| GitHub publication | Verified on `BuildWithAveeck/Yafavanam` `main` |
| Railway web build | `SUCCESS` on commit `2d0005d` |
| Railway Postgres | `SUCCESS` / online |
| Railway Redis | `SUCCESS` / online |
| Railway public web request | Not tested because no domain is recorded |
| Railway Go API | Not deployed |
| Railway migrations | Not verified/applied |
| Production authentication | Not tested |

## 14. Project Status

### Completed

- Next.js storefront production build and Railway-compatible root start script.
- GitHub publication to the requested repository and default branch.
- Go catalogue/cart/order vertical slice with tests.
- Modal Sign In / Sign Up UI and global auth context.
- Deferred Add to Bag and checkout actions.
- bcrypt password hashing and parameterized PostgreSQL credential queries.
- JWT access/refresh cookies, Redis refresh rotation/revocation logic and Remember Me TTL behavior.
- CSRF protection on state-changing authentication endpoints.
- Google OAuth route and callback implementation.
- Backend authentication middleware and user-aware cart/order ownership checks.
- PostgreSQL core, production-hardening and OAuth migrations authored.
- Local Docker Compose updated with PostgreSQL, Redis, API and recommendation services.
- Railway web service build corrected and successfully deployed.
- Railway managed PostgreSQL and Redis services provisioned and online.
- Local TypeScript, Next.js production build and Go test validation.

### In Progress

- Railway deployment of the overall system: the web build is successful, but the Go API service, domains and production variables remain.
- Transition from local/process-memory commerce storage to durable PostgreSQL repositories.
- Production analytics/UTM setup through GA4 or PostHog variables.

### Not Started

- Go API Railway service creation and Docker deployment.
- Automated Railway migration runner/pre-deploy command.
- Production Google OAuth client configuration.
- Password reset, email verification and account recovery.
- Razorpay order/payment/webhook integration.
- Durable PostgreSQL cart/order repository implementation.
- Recommendation-engine Railway service deployment.
- Retool operations dashboard construction.
- Bot protection, security monitoring, dependency scanning and alerting.
- A functional production checkout page.

### Blocked / Needs Verification

- Public website verification is blocked until a web domain is generated.
- Authentication and protected Add to Bag are blocked until the Go API is deployed and web variables point to it.
- API startup is blocked until migrations and production PostgreSQL/Redis reference variables are configured.
- Google sign-in is blocked until the API domain and Google provider credentials exist.
- Order durability and real checkout are blocked by the current in-memory commerce store and missing payment integration.
- Production cookie, CORS, CSRF, rotation and cross-user ownership behavior require end-to-end verification.

### Recommended Next Steps

1. Generate the Railway public domain for `Yafavanam` and verify the home/shop/product routes over HTTPS.
2. Create a separate Railway Go API service from the same repository using `apps/api/Dockerfile` with repository root build context.
3. Add Railway reference variables `DATABASE_URL=${{Postgres.DATABASE_URL}}` and `REDIS_URL=${{Redis.REDIS_URL}}` to the API service.
4. Set `APP_ENV=production`, a high-entropy `JWT_SECRET`, `APP_URL`, and exact `CORS_ALLOWED_ORIGINS`.
5. Apply migrations `000001`, `000002`, and `000003` in numeric order; preferably add an automated migration tool and Railway pre-deploy command.
6. Generate the API public domain; set the web service's `NEXT_PUBLIC_API_URL` and `COMMERCE_API_URL`; redeploy the web app.
7. Run the complete health/authentication checklist in section 9.7.
8. Make production authentication fail closed if its required environment variables are missing.
9. Move cart/order state from memory to PostgreSQL before enabling real checkout.
10. Add Google provider credentials and verify the OAuth callback/return flow.
11. Implement password reset/email verification and Redis-backed per-IP/per-email rate limiting.
12. Add payment integration, webhook verification, monitoring and dependency/security scanning before accepting customer payments.

