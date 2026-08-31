"""RAG settings: Supabase/OpenRouter configuration parsing and safety rules."""

from __future__ import annotations

from pathlib import Path

from app.rag.config import EmbeddingSpaceMismatchError, RagSettings


def test_vector_store_must_be_explicitly_configured():
    """DATABASE_URL (commerce) must never silently become the vector store."""
    settings = RagSettings.from_env({
        "DATABASE_URL": "postgresql://commerce.example/yafa_vanam",
    })
    assert settings.vector_database_url is None

    settings = RagSettings.from_env({
        "DATABASE_URL": "postgresql://commerce.example/yafa_vanam",
        "VECTOR_DATABASE_URL": "postgresql://db.ref.supabase.co:6543/postgres",
    })
    assert settings.vector_database_url == "postgresql://db.ref.supabase.co:6543/postgres"


def test_locked_openrouter_defaults():
    settings = RagSettings.from_env({})
    assert settings.embedding_provider == "hashing"  # offline fallback for dev/CI
    assert settings.rerank_enabled is False          # Phase 1 keeps reranking off
    assert settings.openrouter_base_url == "https://openrouter.ai/api/v1"
    assert settings.agentic_enabled is False
    assert settings.agent_model == "amazon.nova-lite-v1:0"
    assert settings.max_concurrent_embeddings == 8

    settings = RagSettings.from_env({
        "EMBEDDING_PROVIDER": "openrouter",
        "EMBEDDING_MODEL": "nvidia/nemotron-3-embed-1b:free",
        "EMBEDDING_DIMENSION": "2048",
        "OPENROUTER_API_KEY": "sk-or-x",
        "RAG_RERANK_ENABLED": "true",
    })
    assert settings.embedding_model == "nvidia/nemotron-3-embed-1b:free"
    assert settings.embedding_dimension == 2048
    assert settings.openrouter_api_key == "sk-or-x"
    assert settings.rerank_enabled is True


def test_rerank_flag_accepts_common_spellings():
    for raw in ("1", "true", "YES", "on"):
        assert RagSettings.from_env({"RAG_RERANK_ENABLED": raw}).rerank_enabled is True
    for raw in ("0", "false", "no", "off", ""):
        assert RagSettings.from_env({"RAG_RERANK_ENABLED": raw}).rerank_enabled is False


def test_catalogue_path_defaults_to_repo_root():
    settings = RagSettings.from_env({})
    expected = Path(__file__).resolve().parents[3] / "data" / "processed" / "Product.json"
    assert settings.catalogue_path.resolve() == expected.resolve()


def test_embedding_space_error_exists_for_rebuild_flow():
    # Raised when stored embeddings come from a different provider/model/dimension.
    assert issubclass(EmbeddingSpaceMismatchError, RuntimeError)


def test_production_controls_validate_positive_values():
    settings = RagSettings.from_env({
        "RAG_CACHE_TTL_SECONDS": "120",
        "RAG_MAX_CONCURRENT_EMBEDDINGS": "4",
        "RAG_QUERY_TIMEOUT_SECONDS": "3.5",
        "RAG_MIN_GROUNDING_SIMILARITY": "0.7",
        "YAFA_AGENTIC_RAG_ENABLED": "true",
        "YAFA_AGENT_MAX_TOOL_CALLS": "2",
    })
    assert settings.cache_ttl_seconds == 120
    assert settings.max_concurrent_embeddings == 4
    assert settings.query_timeout_seconds == 3.5
    assert settings.min_grounding_similarity == 0.7
    assert settings.agentic_enabled is True
