# YAFA VANAM RAG Service

This private FastAPI service provides grounded retrieval for YAFA VANAM product
and brand knowledge. It does not contain product-ranking, shade-matching,
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
- `POST /internal/yafa/chat` composes a short answer only from retrieved,
  eligible chunks. It defers current stock, price, orders, cart, and shipping
  questions to the commerce service.

The storefront reaches Yafa only through its server-side `/api/yafa/chat`
bridge. Set `YAFA_RAG_URL` and `YAFA_INTERNAL_SERVICE_TOKEN` there; never
expose either to the browser.

## Configuration

`VECTOR_DATABASE_URL` points to the dedicated pgvector database. It must not
be the commerce database. `EMBEDDING_PROVIDER`, `EMBEDDING_MODEL`, and
`EMBEDDING_DIMENSION` must match the existing embedding space; startup stops
when they do not. The catalogue and owner-approved brand knowledge are ingested
with `python scripts/ingest_products.py`.
