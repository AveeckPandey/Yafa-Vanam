# YAFA VANAM

Monorepo scaffold for the YAFA VANAM beauty commerce platform.

## Architecture snapshot

| Concern | Technology |
| --- | --- |
| Customer storefront | Next.js + TypeScript |
| Main commerce backend | Go |
| Database | PostgreSQL |
| Go DB access | pgx + sqlc |
| Recommendation / ML | Python + FastAPI |
| Behavior analytics | PostHog |
| Marketing analytics | Google Analytics 4 |
| CRM | HubSpot Free (initial phase) |
| Admin | Retool |
| Payments | Razorpay |
| Lifecycle messaging | WhatsApp Business |
| Monitoring | Sentry |
| Future knowledge assistant | RAG service |
| Future beauty companion | Quiz + skin analysis + kit recommendation orchestration |

## Main directories

```text
apps/web                     Next.js storefront
apps/api                     Go commerce/business API
services/recommendation-engine  Python/FastAPI ranking engine
services/ai-companion        future conversational companion + system prompt
services/rag-assistant       future grounded knowledge retrieval
retool                       internal admin query/docs scaffold
data                         catalogue import/normalization work
docs                         architecture and feature notes
```

## Local development

### PostgreSQL

```bash
docker compose up postgres
```

### Go API

```bash
cd apps/api
go run ./cmd/api
```

Health check: `http://localhost:4000/health`.

Commerce endpoints: `http://localhost:4000/api/v1`. The current vertical slice includes products, categories, anonymous carts, and pending-payment orders. See `docs/api.md` for the contract and persistence boundary.

### Next.js

Install Node.js/npm if needed, then:

```bash
npm install
npm run dev:web
```

The JavaScript workspace now uses npm workspaces. Run `npm install` once to install dependencies and generate `package-lock.json`.

### Recommendation engine

```bash
cd services/recommendation-engine
python -m venv .venv
# activate the environment, install requirements, then:
uvicorn app.main:app --reload --port 8000
```

## Important boundaries

- PostgreSQL + verified payment data is business truth.
- PostHog/GA4 are analytics, not accounting databases.
- Retool uses the Go Admin API for sensitive writes.
- The recommendation engine ranks; Go validates sellability.
- Future RAG explains knowledge; it does not decide stock, refunds, payments, or coupons.
- WhatsApp marketing requires a separate explicit opt-in and lifecycle suppression rules.
