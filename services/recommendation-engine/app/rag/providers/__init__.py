"""Embedding providers: interface, offline hashing fallback, OpenRouter client."""

from __future__ import annotations

from app.rag.config import RagSettings, validate_dimensions
from app.rag.providers.base import (
    EmbeddingAuthError,
    EmbeddingProvider,
    EmbeddingProviderError,
    EmbeddingRateLimitError,
    HashingEmbeddingProvider,
    validate_vectors,
)
from app.rag.providers.openrouter import DEFAULT_BASE_URL, OpenRouterEmbeddingProvider

# Locked Phase 1 provider/model (update spec §2).
DEFAULT_OPENROUTER_MODEL = "nvidia/nemotron-3-embed-1b:free"

__all__ = [
    "DEFAULT_BASE_URL",
    "DEFAULT_OPENROUTER_MODEL",
    "EmbeddingAuthError",
    "EmbeddingProvider",
    "EmbeddingProviderError",
    "EmbeddingRateLimitError",
    "HashingEmbeddingProvider",
    "OpenRouterEmbeddingProvider",
    "build_provider",
    "provider_identity",
    "validate_vectors",
]


def provider_identity(settings: RagSettings) -> tuple[str, str, int] | None:
    """(provider_name, model_name, dimension) the configuration will run as,
    derived from settings alone — no provider is constructed.

    Health checks use this to judge whether stored embeddings belong to the
    configured space even when build_provider would refuse (missing API key,
    dimension mismatch): a mis-configured deployment must still report
    *which* space it claims to be in, so drift stays diagnosable.
    """
    kind = settings.embedding_provider
    if kind == "hashing":
        return (
            HashingEmbeddingProvider().provider_name,
            HashingEmbeddingProvider.MODEL_NAME,
            settings.embedding_dimension or HashingEmbeddingProvider.DEFAULT_DIMENSION,
        )
    if kind == "openrouter" and settings.embedding_dimension:
        return (
            "openrouter",
            settings.embedding_model or DEFAULT_OPENROUTER_MODEL,
            settings.embedding_dimension,
        )
    return None


def build_provider(settings: RagSettings) -> EmbeddingProvider:
    provider_kind = settings.embedding_provider
    if provider_kind == "hashing":
        # The hashing embedder has a fixed intrinsic output width; a configured
        # EMBEDDING_DIMENSION must match it exactly, as with any real model —
        # silently resizing the provider to the config would make validation
        # vacuous. Other widths (2048 in the opt-in integration tests)
        # construct HashingEmbeddingProvider directly instead.
        provider: EmbeddingProvider = HashingEmbeddingProvider()
    elif provider_kind == "openrouter":
        if not settings.openrouter_api_key:
            raise RuntimeError("EMBEDDING_PROVIDER=openrouter requires OPENROUTER_API_KEY")
        if not settings.embedding_dimension:
            raise RuntimeError("EMBEDDING_DIMENSION is required for openrouter (2048 for the locked model)")
        provider = OpenRouterEmbeddingProvider(
            model=settings.embedding_model or DEFAULT_OPENROUTER_MODEL,
            api_key=settings.openrouter_api_key,
            dimension=settings.embedding_dimension,
            base_url=settings.openrouter_base_url,
        )
    else:
        raise RuntimeError(f"unsupported EMBEDDING_PROVIDER {provider_kind!r}")

    validate_dimensions(settings.embedding_dimension, provider.dimension)
    return provider
