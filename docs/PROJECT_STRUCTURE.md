# YAFA VANAM Monorepo Structure

This is the active project structure after removal of the legacy recommendation,
image, voice, companion, and old RAG scaffold code. Generated dependency folders,
caches, logs, and product image files are intentionally not expanded below.

```text
YAFA VANAM/
├── apps/
│   ├── web/                              Next.js customer storefront
│   │   ├── app/                          App Router pages and route handlers
│   │   │   ├── api/
│   │   │   │   ├── auth/                 Cognito session and sign-in routes
│   │   │   │   ├── cart/                 Cart proxy routes
│   │   │   │   ├── payments/razorpay/    Razorpay order and verification routes
│   │   │   │   ├── search/               Product search route
│   │   │   │   ├── v1/                   Go commerce API proxy
│   │   │   │   └── yafa/                 RAG chat API proxy
│   │   │   ├── account/, auth/           Account and authentication screens
│   │   │   ├── cart/, checkout/, order/  Commerce journey screens
│   │   │   ├── products/, shop/          Product details and catalogue screens
│   │   │   ├── makeup/, skincare/,
│   │   │   │   fragrance/, body-care/    Product category screens
│   │   │   ├── yafa/                     Dedicated YAFA chat screen
│   │   │   └── layout.tsx, globals.css   Application shell and global styling
│   │   ├── components/
│   │   │   ├── yafa/                     Chat drawer, messages, input, cards
│   │   │   ├── product/, cart/, checkout/ Commerce UI
│   │   │   ├── account/, auth/           Customer identity and account UI
│   │   │   ├── layout/, home/, search/   Site navigation and discovery UI
│   │   │   └── analytics/, consent/      Analytics and cookie-consent UI
│   │   ├── lib/                          API clients, catalogue, auth, cart,
│   │   │                                   payments, analytics, and chat types
│   │   ├── public/                       Product, brand, campaign, and email assets
│   │   ├── tests/                        Unit and integration tests
│   │   ├── e2e/                          Playwright storefront and accessibility tests
│   │   ├── scripts/                      Catalogue validation
│   │   ├── Dockerfile                    Production storefront image
│   │   └── package.json                  Web workspace commands and dependencies
│   │
│   └── api/                              Go commerce and business API
│       ├── cmd/api/                      Service entry point
│       ├── internal/
│       │   ├── auth/                     Cognito authentication and email flows
│       │   ├── commerce/                 Catalogue, orders, coupons, promotions
│       │   └── database/                 Migration runner
│       ├── platform/httpserver/          HTTP routes, Razorpay, order confirmation
│       ├── db/
│       │   ├── migrations/               PostgreSQL schema migrations
│       │   ├── queries/                  sqlc source queries
│       │   └── generated/                Generated database access code/docs
│       ├── openapi/openapi.yaml          API contract
│       └── Dockerfile, go.mod            API build configuration
│
├── services/
│   └── recommendation-engine/            Active FastAPI grounded RAG service
│       ├── app/
│       │   ├── main.py                   FastAPI application entry point
│       │   ├── api/                      RAG search and YAFA chat endpoints
│       │   ├── rag/                      Ingestion, chunking, retrieval, filters,
│       │   │   │                         ranking, verified-source policy, repository
│       │   │   └── providers/            OpenRouter and Amazon Bedrock embeddings
│       │   └── yafa/                     Intent handling, conversation, prompts,
│       │                                 context, orchestration, response schemas
│       ├── migrations/                   RAG schema and embedding-space migrations
│       ├── scripts/                      Ingest, evaluate, rebuild, probe, smoke test
│       ├── tests/                        RAG, provider, API, safety, and chat tests
│       ├── Dockerfile                    RAG service image
│       ├── requirements.txt              Python dependencies
│       └── README.md                     RAG service guide
│
├── packages/
│   └── frontend-types/                   Shared generated API TypeScript types
│
├── data/
│   ├── processed/                        Normalised product and brand knowledge data
│   └── scripts/                          Catalogue import, normalisation, validation,
│                                       and database seeding tools
│
├── infra/
│   └── aws/
│       ├── cloudformation/               Network and data infrastructure templates
│       ├── lambda/                       Email Lambda source, policies, test payloads
│       └── *.json, *.sh                  IAM, CloudFront, Cognito, WAF, budget,
│                                       storage, GitHub Actions, and EC2 configuration
│
├── lambda/
│   └── welcome-coupon/                   Standalone welcome-coupon Lambda source
│
├── scripts/
│   └── security/                         Secret scanning
│
├── docs/
│   ├── PROJECT_STRUCTURE.md              This file
│   ├── api.md, database-schema.md        API and data documentation
│   ├── rag/                              Active RAG workflow documentation
│   ├── deployment/                       AWS ECS and production architecture guidance
│   ├── ai/, analytics/, brand/, crm/     Supporting product documentation
│   ├── lifecycle-marketing/, merchandising/
│   ├── payments/, returns/               Commerce operational documentation
│   └── design-system.md                  UI design guidance
│
├── docker-compose.yml                    Local backend and data stack
├── package.json                          npm workspace root
├── package-lock.json                     Locked JavaScript dependencies
├── README.md                             Project overview and local startup
├── run-local.ps1                         Local development helper
├── vercel.json                           Frontend deployment configuration
├── Jenkinsfile*                          CI pipelines
└── SECURITY_CHECKLIST.md                 Security verification checklist
```

## Runtime relationships

```text
Customer browser
  └── Next.js storefront (apps/web)
        ├── Go commerce API (apps/api) ──► PostgreSQL
        └── YAFA RAG API proxy ──────────► FastAPI RAG service
                                             ├── pgvector PostgreSQL
                                             └── embedding provider
                                                 (OpenRouter or Amazon Bedrock)
```

## Local containers

`docker-compose.yml` starts the following backend/data services:

- `postgres` — commerce PostgreSQL database
- `rag-postgres` — pgvector database for verified RAG knowledge
- `redis` — API caching/support service
- `api` — Go commerce API
- `yafa-rag` — FastAPI RAG service

The Next.js storefront runs separately through the `apps/web` npm workspace.

## Deliberately absent

The repository no longer contains an active recommendation engine, image upload
or analysis flow, voice gateway, AI companion service, standalone legacy RAG
scaffold, or Retool administration scaffold. YAFA is a verified-product RAG
chat experience only.
