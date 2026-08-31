# YAFA VANAM RAG Service

This private FastAPI service provides grounded, agentic retrieval for YAFA
VANAM product and brand knowledge. The optional Bedrock agent can make only a
read-only verified-search tool call and an answer is discarded unless it cites
the returned chunk IDs. It does not contain product-ranking, shade-matching,
quiz, image-analysis, voice-transcription, or recommendation endpoints.

## Run

```powershell
pip install -r requirements.txt
pytest -q
uvicorn app.main:app --reload --port 8000
```

Use `GET /health` for process health. The protected RAG endpoints require the
`X-Yafa-Service-Token` header:

- `POST /internal/rag/search` retrieves eligible product and brand facts.
- `GET /internal/rag/health` reports vector-database and embedding-space
  status without exposing credentials.
- `POST /internal/yafa/chat` uses the optional Amazon Bedrock agent only after
  verified retrieval. Uncited, timed-out, or unavailable agent responses fall
  back to deterministic source composition. Current stock, price, orders,
  cart, and shipping questions are deferred to the commerce service.

The storefront reaches Yafa only through its server-side `/api/yafa/chat`
bridge. Set `YAFA_RAG_URL` and `YAFA_INTERNAL_SERVICE_TOKEN` there; never
expose either to the browser.

## Configuration

`VECTOR_DATABASE_URL` points to the dedicated pgvector database. It must not
be the commerce database. `EMBEDDING_PROVIDER`, `EMBEDDING_MODEL`, and
`EMBEDDING_DIMENSION` must match the existing embedding space; startup stops
when they do not. The catalogue and owner-approved brand knowledge are ingested
with `python scripts/ingest_products.py`.

For AWS production use Titan V2 embeddings (`1024` dimensions) and set
`YAFA_AGENTIC_RAG_ENABLED=true` with `YAFA_AGENT_MODEL=amazon.nova-lite-v1:0`.
The task role needs only `bedrock:InvokeModel` for those two model ARNs. Keep
`RAG_RERANK_ENABLED=false`, limit agent tool calls to two, and change
`RAG_CACHE_NAMESPACE` whenever a new knowledge corpus is promoted.

Production safeguards include shared corpus-revision cache invalidation,
complete-snapshot deletion reconciliation, forced tenant RLS on documents,
chunks, and aliases, extractive final answers, injection quarantine, conflict
keys, correlated retrieval/model telemetry, database circuit breaking, and a
blue/green shadow-database embedding migration. Operational commands and
required AWS settings are in `docs/deployment/rag-production-controls.md`.
