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
