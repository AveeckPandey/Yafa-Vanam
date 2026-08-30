"""Private YAFA VANAM product-knowledge RAG service."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.rag_search import router as rag_search_router, validate_startup_dimensions
from app.api.yafa_chat import router as yafa_chat_router

try:
    import sentry_sdk
    from sentry_sdk.integrations.asgi import SentryAsgiMiddleware
except ImportError:  # Keeps local development usable before optional monitoring is installed.
    sentry_sdk = None
    SentryAsgiMiddleware = None


if sentry_sdk is not None and os.getenv("SENTRY_DSN"):
    sentry_sdk.init(
        dsn=os.environ["SENTRY_DSN"],
        environment=os.getenv("ENVIRONMENT", os.getenv("APP_ENV", "development")),
        release=os.getenv("RELEASE_VERSION") or None,
        traces_sample_rate=0.1,
        send_default_pii=False,
    )


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Validate the vector store before serving any RAG traffic."""
    import asyncio

    status = await asyncio.to_thread(validate_startup_dimensions)
    if status.get("rag_enabled"):
        print(f"[rag] embeddings validated: {status}")
    yield


app = FastAPI(title="YAFA VANAM RAG Service", version="1.0.0", lifespan=lifespan)
if sentry_sdk is not None and SentryAsgiMiddleware is not None and os.getenv("SENTRY_DSN"):
    app.add_middleware(SentryAsgiMiddleware)

# The browser reaches this private service only through the server-side Yafa
# bridge, which supplies the internal service token.
app.include_router(rag_search_router)
app.include_router(yafa_chat_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"service": "yafa-rag", "status": "ok"}
