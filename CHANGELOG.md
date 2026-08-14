# YAFA VANAM — Architecture Update

## Updated in this ZIP

- Replaced the Fastify/TypeScript commerce backend scaffold with a Go backend.
- Removed Prisma-oriented database packaging and moved database ownership into the Go service.
- Added PostgreSQL migration scaffolding plus `sqlc` query definitions.
- Added Product -> Shade -> Variant/SKU, orders, payments, refunds/returns, reviews, customer profiles, consent, metrics, badges, promotions, coupons, carts, wishlists, ingredients, concerns, and skin-profile schema foundations.
- Added Go module boundaries for CRM, analytics, merchandising, lifecycle marketing, recommendations, payments, refunds, and integrations.
- Added PostHog + GA4 consent-aware frontend analytics scaffolding.
- Added HubSpot CRM, WhatsApp Business, Razorpay, Sentry, and recommendation integration locations.
- Added Retool admin/query scaffolding.
- Added lifecycle marketing design for repeat visitors, explicit WhatsApp opt-in, cooldowns, and discount eligibility.
- Kept the Python/FastAPI recommendation engine and added a minimal runnable health/recommendation scaffold.
- Added a future AI Companion service with the YAFA VANAM quiz/skin-analysis/kit-recommendation system prompt.
- Added a future RAG assistant scaffold for product, ingredient, policy, and FAQ grounding, with product-image metadata support and multimodal RAG reserved for later.
- Updated the monorepo naming from the old Yafaisaan scaffold references to YAFA VANAM.
- Removed package-manager caches and `node_modules` from the deliverable and expanded `.gitignore`.
- Switched the JavaScript workspace from pnpm to npm workspaces. Run `npm install` to generate `package-lock.json` in your environment.

## Makeup Advisor V1 — 2026-08-13
- Added typed adaptive advisor sessions and Beauty Profile.
- Added catalogue-backed 24-shade complexion matching and supporting shade suitability selection.
- Added deterministic Lips/Eyes/Cheeks/Complexion ranking with explainable score reasons.
- Added neighbouring-shade brightening concealer logic and explicit corrector concern gating.
- Added vision and RAG provider interfaces without fake provider output.
- Added global Next.js Makeup Advisor launcher, quick replies, uploads, recommendation cards and follow-up modification actions.
- Added advisor analytics event vocabulary and deterministic tests.
- Added current 78-product catalogue snapshot under `data/processed/products.json`.
