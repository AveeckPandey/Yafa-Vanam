"""End-to-end RAG against a real PostgreSQL + pgvector instance.

Opt-in: set RAG_TEST_DATABASE_URL (e.g. a disposable pgvector database) to
run; skipped otherwise so the default suite stays hermetic. The local
5432 port is contested by two Postgres servers on this machine, so prefer an
explicit DSN over assuming defaults.
"""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

import pytest

from app.rag.config import RagSettings
from app.rag.providers import HashingEmbeddingProvider, build_provider
from app.rag.ingestion import ingest_catalogue
from app.rag.retriever import RagRetriever
from app.rag.repository import RagRepository
from app.rag.schemas import PageContext, RagSearchRequest

DSN = os.getenv("RAG_TEST_DATABASE_URL", "")
pytestmark = pytest.mark.skipif(not DSN, reason="RAG_TEST_DATABASE_URL not set")

CATALOGUE = Path(__file__).resolve().parents[3] / "data" / "processed" / "Product.json"


def _settings() -> RagSettings:
    return RagSettings.from_env({
        "VECTOR_DATABASE_URL": DSN,
        "EMBEDDING_PROVIDER": "hashing",
        "EMBEDDING_DIMENSION": "1024",
        "YAFA_CATALOGUE_PATH": str(CATALOGUE),
    })


@pytest.fixture(scope="module")
def ingested():
    settings = _settings()
    repo = RagRepository(settings.vector_database_url)
    provider = HashingEmbeddingProvider(dimension=1024)
    stats = asyncio.run(ingest_catalogue(repo, provider, settings))
    yield repo, provider, settings, stats
    repo.close()


@pytest.mark.asyncio
async def test_ingestion_is_idempotent_against_real_pgvector(ingested):
    repo, provider, settings, first = ingested
    second = await ingest_catalogue(repo, provider, settings)
    assert second.chunks_new_or_changed == 0
    assert second.chunks_skipped_unchanged == first.chunks_seen


def test_migrations_tracked_and_dimension_is_1024(ingested):
    """Update spec §3/§8: schema comes from tracked SQL migrations with a
    VECTOR(1024) column, applied once and checksum-recorded."""
    repo, _, _, _ = ingested
    conn = repo.connection()
    with conn.cursor() as cursor:
        cursor.execute("SELECT filename FROM rag_schema_migrations ORDER BY filename")
        filenames = [row["filename"] for row in cursor.fetchall()]
        cursor.execute(
            """
            SELECT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vector') AS enabled
            """
        )
        assert cursor.fetchone()["enabled"] is True
        cursor.execute("SELECT embedding_dimension FROM rag_embedding_metadata")
        dimension = int(cursor.fetchone()["embedding_dimension"])
    assert "001_rag_base.sql" in filenames and "002_rag_embeddings.sql" in filenames
    assert dimension == 1024
    assert repo.stored_dimension() == 1024


def test_embedding_metadata_matches_provider(ingested):
    """Update spec §12: stored space identity prevents mixing models."""
    from app.rag.config import EmbeddingSpaceMismatchError

    repo, provider, settings, _ = ingested
    metadata = repo.get_embedding_metadata()
    assert metadata == {
        "embedding_provider": provider.provider_name,
        "embedding_model": provider.model_name,
        "embedding_dimension": 1024,
    }
    # A different model would be refused without an explicit rebuild.
    switched = RagSettings.from_env({
        "VECTOR_DATABASE_URL": DSN,
        "EMBEDDING_PROVIDER": "openrouter",
        "EMBEDDING_MODEL": "nvidia/nemotron-3-embed-1b:free",
        "EMBEDDING_DIMENSION": "1024",
        "OPENROUTER_API_KEY": "sk-or-test",
        "YAFA_CATALOGUE_PATH": str(CATALOGUE),
    })
    with pytest.raises(EmbeddingSpaceMismatchError):
        asyncio.run(ingest_catalogue(repo, build_provider(switched), switched))


@pytest.mark.asyncio
async def test_pdp_question_retrieves_only_that_product(ingested):
    _, provider, settings, _ = ingested
    retriever = RagRetriever(RagRepository(settings.vector_database_url), provider, settings)
    response = await retriever.search(RagSearchRequest(
        query="What does this smell like?",
        page_context=PageContext(type="product", product_id="yv-frag-010"),
    ))
    assert response.results, "expected scent knowledge for Soft Ember"
    assert {result.product_id for result in response.results} == {"yv-frag-010"}
    assert any(result.chunk_type == "scent_profile" for result in response.results)


@pytest.mark.asyncio
async def test_alias_resolution_finds_soft_ember(ingested):
    _, provider, settings, _ = ingested
    retriever = RagRetriever(RagRepository(settings.vector_database_url), provider, settings)
    response = await retriever.search(RagSearchRequest(query="What is the scent profile of Soft Ember?"))
    assert response.resolved_product_id == "yv-frag-010"
    assert response.results
    assert all(result.customer_factual_eligible for result in response.results)


@pytest.mark.asyncio
async def test_customer_mode_never_surfaces_concept_ingredients(ingested):
    _, provider, settings, _ = ingested
    retriever = RagRetriever(RagRepository(settings.vector_database_url), provider, settings)
    response = await retriever.search(RagSearchRequest(
        query="What ingredients does Fernwing Volume Mascara contain?",
        top_k=10,
    ))
    assert response.results
    for result in response.results:
        assert result.trust_level != "LEGACY_CONCEPT"
        assert result.customer_factual_eligible


@pytest.mark.asyncio
async def test_live_data_question_defers_to_commerce(ingested):
    _, provider, settings, _ = ingested
    retriever = RagRetriever(RagRepository(settings.vector_database_url), provider, settings)
    response = await retriever.search(RagSearchRequest(query="Is this in stock?"))
    assert [r.domain.value for r in response.requires_live_data] == ["inventory"]
    assert response.results == []
