"""RAG configuration from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _default_catalogue_path() -> Path:
    # service/app/rag/config.py -> repo root/data/processed/Product.json
    return Path(__file__).resolve().parents[4] / "data" / "processed" / "Product.json"


def _env_flag(source: dict[str, str], key: str, default: bool = False) -> bool:
    raw = (source.get(key) or "").strip().lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class RagSettings:
    vector_database_url: str | None
    embedding_provider: str
    embedding_model: str
    embedding_dimension: int | None
    catalogue_path: Path
    internal_token: str | None
    openrouter_api_key: str
    openrouter_base_url: str
    rerank_enabled: bool

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> "RagSettings":
        source = env if env is not None else os.environ
        raw_dimension = (source.get("EMBEDDING_DIMENSION") or "").strip()
        return cls(
            # Deliberately no DATABASE_URL fallback: the vector store (Supabase in
            # production) must never silently become the commerce database.
            vector_database_url=(source.get("VECTOR_DATABASE_URL") or "").strip() or None,
            embedding_provider=(source.get("EMBEDDING_PROVIDER") or "hashing").strip().lower(),
            embedding_model=(source.get("EMBEDDING_MODEL") or "").strip(),
            embedding_dimension=int(raw_dimension) if raw_dimension else None,
            catalogue_path=Path(
                source.get("YAFA_CATALOGUE_PATH") or str(_default_catalogue_path())
            ),
            internal_token=(source.get("YAFA_INTERNAL_SERVICE_TOKEN") or "").strip() or None,
            openrouter_api_key=(source.get("OPENROUTER_API_KEY") or "").strip(),
            openrouter_base_url=(
                source.get("OPENROUTER_BASE_URL") or "https://openrouter.ai/api/v1"
            ).strip(),
            rerank_enabled=_env_flag(source, "RAG_RERANK_ENABLED", default=False),
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
