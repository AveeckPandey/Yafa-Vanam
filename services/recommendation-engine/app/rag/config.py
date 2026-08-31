"""RAG configuration from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _default_catalogue_path() -> Path:
    # service/app/rag/config.py -> repo root/data/processed/Product.json
    return Path(__file__).resolve().parents[4] / "data" / "processed" / "Product.json"


def _default_brand_knowledge_path() -> Path:
    return Path(__file__).resolve().parents[4] / "data" / "processed" / "BrandKnowledge.json"


def _env_flag(source: dict[str, str], key: str, default: bool = False) -> bool:
    raw = (source.get(key) or "").strip().lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "on"}


def _env_int(source: dict[str, str], key: str, default: int, *, minimum: int = 0) -> int:
    raw = (source.get(key) or "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{key} must be an integer") from exc
    if value < minimum:
        raise ValueError(f"{key} must be >= {minimum}")
    return value


def _env_float(source: dict[str, str], key: str, default: float, *, minimum: float = 0.0) -> float:
    raw = (source.get(key) or "").strip()
    if not raw:
        return default
    try:
        value = float(raw)
    except ValueError as exc:
        raise ValueError(f"{key} must be a number") from exc
    if value < minimum:
        raise ValueError(f"{key} must be >= {minimum}")
    return value


@dataclass(frozen=True)
class RagSettings:
    vector_database_url: str | None
    embedding_provider: str
    embedding_model: str
    embedding_dimension: int | None
    catalogue_path: Path
    brand_knowledge_path: Path | None
    internal_token: str | None
    openrouter_api_key: str
    openrouter_base_url: str
    bedrock_region: str
    rerank_enabled: bool
    # Query controls keep a spike of unique requests from overwhelming Bedrock
    # or exhausting the small Free Tier database. The cache namespace should
    # change whenever a new knowledge corpus is promoted.
    cache_ttl_seconds: int
    cache_max_entries: int
    cache_namespace: str
    max_concurrent_embeddings: int
    query_timeout_seconds: float
    min_grounding_similarity: float
    # Agentic generation is deliberately opt-in. A local/test service remains
    # deterministic until AWS model access and production evaluation are ready.
    agentic_enabled: bool
    agent_model: str
    agent_max_tool_calls: int
    agent_timeout_seconds: float
    agent_max_output_tokens: int
    agent_fallback_model: str
    agent_fallback_region: str
    max_context_chars: int
    circuit_breaker_failures: int
    circuit_breaker_reset_seconds: float
    tenant_signing_secret: str

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> "RagSettings":
        source = env if env is not None else os.environ
        raw_dimension = (source.get("EMBEDDING_DIMENSION") or "").strip()
        explicit_catalogue = (source.get("YAFA_CATALOGUE_PATH") or "").strip()
        explicit_brand_knowledge = (source.get("YAFA_BRAND_KNOWLEDGE_PATH") or "").strip()
        return cls(
            # Deliberately no DATABASE_URL fallback: the vector store (Supabase in
            # production) must never silently become the commerce database.
            vector_database_url=(source.get("VECTOR_DATABASE_URL") or "").strip() or None,
            embedding_provider=(source.get("EMBEDDING_PROVIDER") or "hashing").strip().lower(),
            embedding_model=(source.get("EMBEDDING_MODEL") or "").strip(),
            embedding_dimension=int(raw_dimension) if raw_dimension else None,
            catalogue_path=Path(
                explicit_catalogue or str(_default_catalogue_path())
            ),
            # Custom/fixture catalogues stay isolated unless their companion
            # brand source is explicitly supplied. The canonical production
            # catalogue automatically includes the approved brand knowledge.
            brand_knowledge_path=(
                Path(explicit_brand_knowledge)
                if explicit_brand_knowledge
                else (_default_brand_knowledge_path() if not explicit_catalogue else None)
            ),
            internal_token=(source.get("YAFA_INTERNAL_SERVICE_TOKEN") or "").strip() or None,
            openrouter_api_key=(source.get("OPENROUTER_API_KEY") or "").strip(),
            openrouter_base_url=(
                source.get("OPENROUTER_BASE_URL") or "https://openrouter.ai/api/v1"
            ).strip(),
            bedrock_region=(source.get("BEDROCK_REGION") or source.get("AWS_REGION") or "ap-south-1").strip(),
            rerank_enabled=_env_flag(source, "RAG_RERANK_ENABLED", default=False),
            cache_ttl_seconds=_env_int(source, "RAG_CACHE_TTL_SECONDS", 90, minimum=0),
            cache_max_entries=_env_int(source, "RAG_CACHE_MAX_ENTRIES", 500, minimum=1),
            cache_namespace=(source.get("RAG_CACHE_NAMESPACE") or source.get("RELEASE_VERSION") or "local").strip(),
            max_concurrent_embeddings=_env_int(source, "RAG_MAX_CONCURRENT_EMBEDDINGS", 8, minimum=1),
            query_timeout_seconds=_env_float(source, "RAG_QUERY_TIMEOUT_SECONDS", 8.0, minimum=0.1),
            min_grounding_similarity=_env_float(source, "RAG_MIN_GROUNDING_SIMILARITY", 0.62, minimum=0.0),
            agentic_enabled=_env_flag(source, "YAFA_AGENTIC_RAG_ENABLED", default=False),
            agent_model=(source.get("YAFA_AGENT_MODEL") or "amazon.nova-lite-v1:0").strip(),
            agent_max_tool_calls=_env_int(source, "YAFA_AGENT_MAX_TOOL_CALLS", 2, minimum=1),
            agent_timeout_seconds=_env_float(source, "YAFA_AGENT_TIMEOUT_SECONDS", 12.0, minimum=0.1),
            agent_max_output_tokens=_env_int(source, "YAFA_AGENT_MAX_OUTPUT_TOKENS", 350, minimum=64),
            agent_fallback_model=(source.get("YAFA_AGENT_FALLBACK_MODEL") or "").strip(),
            agent_fallback_region=(source.get("YAFA_AGENT_FALLBACK_REGION") or "").strip(),
            max_context_chars=_env_int(source, "RAG_MAX_CONTEXT_CHARS", 6000, minimum=500),
            circuit_breaker_failures=_env_int(source, "RAG_CIRCUIT_BREAKER_FAILURES", 4, minimum=1),
            circuit_breaker_reset_seconds=_env_float(source, "RAG_CIRCUIT_BREAKER_RESET_SECONDS", 20.0, minimum=1.0),
            tenant_signing_secret=(source.get("YAFA_TENANT_SIGNING_SECRET") or "").strip(),
        )


class DimensionMismatchError(RuntimeError):
    """Raised when configured, provider and stored vector dimensions disagree."""


class EmbeddingSpaceMismatchError(RuntimeError):
    """Stored embeddings were produced by a different provider/model/dimension.

    Mixing embedding spaces corrupts similarity search; rebuild embeddings
    instead of ingesting over them.
    """


def validate_dimensions(configured: int | None, provider_dimension: int, stored: int | None = None) -> None:
    """Startup guard: config == embedding model output == database column."""
    if configured is not None and configured != provider_dimension:
        raise DimensionMismatchError(
            f"EMBEDDING_DIMENSION={configured} does not match provider output dimension {provider_dimension}"
        )
    if stored is not None and stored != provider_dimension:
        raise DimensionMismatchError(
            f"database vector dimension {stored} does not match provider output dimension {provider_dimension}; "
            "rebuild embeddings or point VECTOR_DATABASE_URL at the right schema"
        )
