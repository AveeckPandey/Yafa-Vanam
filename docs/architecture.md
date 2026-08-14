# YAFA VANAM Architecture

## Core stack

- Customer storefront: Next.js + TypeScript
- Main commerce/business backend: Go
- Database: PostgreSQL
- Go database access: pgx + sqlc
- Recommendation/ML: Python + FastAPI
- Behavior analytics: PostHog
- Marketing/acquisition analytics: Google Analytics 4
- CRM: HubSpot Free (initially)
- Internal admin: Retool
- Payments/refunds: Razorpay
- Lifecycle messaging: WhatsApp Business API through the Go backend
- Error monitoring: Sentry
- Hosting target: Railway services; Vercel remains optional for the Next.js storefront
- Future AI companion: quiz + optional cosmetic photo analysis + kit reveal orchestration
- Future RAG: grounded product/ingredient/policy/FAQ assistant

## Service flow

```text
Customer
  |
  v
Next.js storefront
  |-- consent --> PostHog / GA4
  |
  v
Go Commerce API
  |-- PostgreSQL (business truth)
  |-- Razorpay
  |-- HubSpot
  |-- WhatsApp Business
  |-- Sentry
  |-- Python/FastAPI recommendation engine
  `-- future RAG/AI services

Retool --> PostgreSQL for safe reads
Retool --> Go Admin API for sensitive actions
```

## Principle

Analytics describes behavior; verified PostgreSQL/payment records define business truth. AI services may rank/explain products, but the Go layer owns sellability, current stock, price, orders, refunds, consent, discounts, and external side effects.
