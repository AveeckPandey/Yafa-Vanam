# Railway deployment target

Planned Railway services:

- `yafa-api` — Go HTTP API
- `yafa-worker` — Go scheduled/background work
- `recommendation-engine` — Python/FastAPI
- `postgres` — PostgreSQL
- future `rag-assistant` — only when that phase begins

The Next.js web app can run on Railway or Vercel. Internal service-to-service calls should use Railway private networking when services live in the same project/environment.
