# YAFA VANAM

RAG-only beauty commerce platform for YAFA VANAM. The customer chat answers
verified product and brand questions; it does not make personalised
recommendations or process images, voice, or medical advice.

## Current architecture

| Concern | Technology |
| --- | --- |
| Customer storefront | Next.js + TypeScript |
| Main commerce backend | Go |
| Commerce database | PostgreSQL |
| Product knowledge service | Python + FastAPI grounded RAG |
| RAG vector database | PostgreSQL with pgvector |
| Caching | Redis |
| Local runtime | Docker Compose |
| Production infrastructure | AWS |

## Project structure

```text
apps/
  web/                       Next.js storefront and YAFA chat interface
  api/                       Go commerce API, database migrations, OpenAPI contract
services/
  recommendation-engine/     FastAPI RAG service, verified knowledge retrieval,
                             embeddings, ingestion migrations, and RAG tests
data/                         Product catalogue import and normalisation data
packages/                     Shared workspace packages
infra/
  aws/                       AWS deployment infrastructure and Lambda functions
lambda/                       Standalone Lambda source
scripts/                      Repository automation and operational scripts
docs/
  rag/                       RAG setup, ingestion, and operational guidance
  deployment/                Docker and AWS deployment guidance
  ai/, analytics/, brand/, crm/, lifecycle-marketing/, merchandising/,
  payments/, returns/        Supporting product and operational documentation
docker-compose.yml            Local PostgreSQL, pgvector, Redis, Go API, and RAG stack
```

For the complete active monorepo map, see `docs/PROJECT_STRUCTURE.md`.

## Local development

### Full local stack

```bash
docker compose up --build
```

This starts PostgreSQL, pgvector, Redis, the Go API, and the RAG service. Run
the Next.js storefront separately with `npm run dev:web`.

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

### Product-knowledge RAG only

```bash
cd services/recommendation-engine
python -m venv .venv
# activate the environment, install requirements, then:
uvicorn app.main:app --reload --port 8000
```

## Important boundaries

- PostgreSQL + verified payment data is business truth.
- RAG explains verified product and brand knowledge; it does not decide stock,
  refunds, payments, coupons, or personalised product choices.
- The RAG service returns grounded product information and product links only.
  It does not use image, voice, shade-matching, or recommendation workflows.
- See `docs/deployment/aws-production-architecture.md` for the AWS target
  architecture and `docs/rag/README.md` for the active RAG workflow.
