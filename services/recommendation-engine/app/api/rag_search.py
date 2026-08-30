"""Internal RAG endpoints (Phase 1: retrieval only + infrastructure health).

The Go backend / Yafa orchestrator calls these with the shared service token.
No LLM generation: raw retrieved chunks come back so the caller decides
presentation and can honour requires_live_data by asking commerce instead.

Both endpoints are token-protected and never return embedding vectors,
credentials, connection strings or raw internal errors.
"""

from __future__ import annotations

import hmac
import os

from fastapi import APIRouter, Header, HTTPException

from app.rag.config import EmbeddingSpaceMismatchError, RagSettings, validate_dimensions
from app.rag.providers import provider_identity
from app.rag.providers.base import EmbeddingProviderError
from app.rag.repository import RagRepository
from app.rag.schemas import RagHealthResponse, RagSearchRequest, RagSearchResponse

router = APIRouter(prefix="/internal/rag", tags=["internal-rag"])


def _require_service_token(token: str | None) -> None:
    expected = os.getenv("YAFA_INTERNAL_SERVICE_TOKEN", "")
    if len(expected) < 32 or token is None or not hmac.compare_digest(token, expected):
        raise HTTPException(status_code=401, detail="unauthorized")


@router.post("/search", response_model=RagSearchResponse)
async def rag_search(
    request: RagSearchRequest,
    x_yafa_service_token: str | None = Header(default=None),
) -> RagSearchResponse:
    _require_service_token(x_yafa_service_token)
    retriever = _get_retriever()
    try:
        return await retriever.search(request)
    except EmbeddingProviderError as error:
        raise HTTPException(
            status_code=503,
            detail="RAG embedding service is temporarily unavailable. Please try again shortly.",
        ) from error


@router.get("/health", response_model=RagHealthResponse)
async def rag_health(
    x_yafa_service_token: str | None = Header(default=None),
) -> RagHealthResponse:
    """Database connectivity + pgvector presence + embedding-space identity.

    Reports status flags only; failures collapse to booleans so no database
    error text, DSN or credential can ever leak into the response.
    """
    _require_service_token(x_yafa_service_token)
    settings = RagSettings.from_env()
    if not settings.vector_database_url:
        return RagHealthResponse(
            status="unconfigured",
            database_connected=False,
            pgvector_enabled=False,
            embedding_provider=settings.embedding_provider,
            embedding_model=settings.embedding_model or None,
            embedding_dimension=settings.embedding_dimension,
        )

    connected = False
    pgvector_enabled = False
    stored_dimension: int | None = None
    metadata: dict | None = None
    try:
        repo = RagRepository(settings.vector_database_url)
        try:
            conn = repo.connection()
            with conn.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.execute(
                    """
                    SELECT EXISTS (
                        SELECT 1 FROM pg_extension WHERE extname = 'vector'
                    ) AS enabled
                    """
                )
                pgvector_enabled = bool(cursor.fetchone()["enabled"])
            stored_dimension = repo.stored_dimension()
            metadata = repo.get_embedding_metadata()
            connected = True
        finally:
            repo.close()
    except Exception:  # noqa: BLE001 - diagnostics must not leak error internals
        connected = False

    dimension_ok = (
        stored_dimension is None or settings.embedding_dimension is None
        or stored_dimension == settings.embedding_dimension
    )
    if metadata is None:
        space_consistent: bool | None = None
    else:
        # Compared against the configured space identity, not a constructed
        # provider: health must stay diagnosable even when build_provider
        # would refuse (missing key, dimension mismatch).
        identity = provider_identity(settings)
        space_consistent = identity is not None and metadata == {
            "embedding_provider": identity[0],
            "embedding_model": identity[1],
            "embedding_dimension": identity[2],
        }

    if not connected:
        status = "error"
    elif not pgvector_enabled or not dimension_ok or space_consistent is False:
        status = "degraded"
    else:
        status = "ok"

    return RagHealthResponse(
        status=status,
        database_connected=connected,
        pgvector_enabled=pgvector_enabled,
        embedding_provider=settings.embedding_provider,
        embedding_model=settings.embedding_model or None,
        embedding_dimension=settings.embedding_dimension,
        stored_dimension=stored_dimension,
        embedding_space_consistent=space_consistent,
    )


_retriever = None


def _get_retriever():
    """Lazily built singleton; raises a clean 503 when RAG is not configured."""
    global _retriever
    if _retriever is None:
        from app.rag.retriever import build_retriever

        try:
            _retriever = build_retriever()
        except RuntimeError as error:
            raise HTTPException(status_code=503, detail=str(error)) from error
    return _retriever


def validate_startup_dimensions() -> dict[str, object]:
    """Startup guard: config == provider output == stored column dimension ==
    recorded embedding space. Called from the FastAPI lifespan (off the event
    loop); skipped when no vector database is configured, raising otherwise."""
    settings = RagSettings.from_env()
    if not settings.vector_database_url:
        return {"rag_enabled": False}
    from app.rag.providers import build_provider

    provider = build_provider(settings)
    repo = RagRepository(settings.vector_database_url)
    try:
        # A new isolated RAG database starts empty. Apply tracked migrations
        # before reading vector metadata so first production boot is safe.
        repo.ensure_schema(provider.dimension)
        stored_dimension = repo.stored_dimension()
        validate_dimensions(settings.embedding_dimension, provider.dimension, stored_dimension)
        metadata = repo.get_embedding_metadata()
        if metadata is not None and (
            metadata["embedding_provider"] != provider.provider_name
            or metadata["embedding_model"] != provider.model_name
            or metadata["embedding_dimension"] != provider.dimension
        ):
            raise EmbeddingSpaceMismatchError(
                "stored embeddings were produced by "
                f"({metadata['embedding_provider']}, {metadata['embedding_model']}, "
                f"{metadata['embedding_dimension']}) but the service is configured for "
                f"({provider.provider_name}, {provider.model_name}, {provider.dimension}); "
                "run scripts/rebuild_embeddings.py"
            )
    finally:
        repo.close()
    return {
        "rag_enabled": True,
        "embedding_provider": provider.provider_name,
        "embedding_model": provider.model_name,
        "embedding_dimension": provider.dimension,
        "stored_dimension": stored_dimension,
    }
