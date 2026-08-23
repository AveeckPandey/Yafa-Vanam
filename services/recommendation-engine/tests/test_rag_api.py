"""POST /internal/rag/search + GET /internal/rag/health: service-token auth
and response shapes. Health reports status flags only — never credentials."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import app.api.rag_search as rag_api
from app.rag.models import LiveDataDomain, TrustLevel
from app.rag.schemas import LiveRequirement, RagSearchRequest, RagSearchResponse, RetrievedChunk

TOKEN = "x" * 40


class StubRetriever:
    async def search(self, request: RagSearchRequest) -> RagSearchResponse:
        return RagSearchResponse(
            query=request.query,
            product_id="yv-frag-010",
            resolved_product_id=None,
            resolution="page_context",
            results=[
                RetrievedChunk(
                    chunk_id="abc", product_id="yv-frag-010",
                    product_name="Soft Ember Warm Fragrance Concept",
                    chunk_type="scent_profile", content="Warm amber, saffron, black tea.",
                    similarity=0.91, trust_level=TrustLevel.AUTHORITATIVE_CATALOGUE,
                    customer_factual_eligible=True, requires_qualification=False,
                )
            ],
            requires_live_data=[
                LiveRequirement(domain=LiveDataDomain.INVENTORY, reason="stock lives in commerce"),
            ],
        )


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setenv("YAFA_INTERNAL_SERVICE_TOKEN", TOKEN)
    monkeypatch.setattr(rag_api, "_retriever", StubRetriever())
    application = FastAPI()
    application.include_router(rag_api.router)
    return TestClient(application)


def test_missing_token_is_unauthorized(client):
    response = client.post("/internal/rag/search", json={"query": "What does this smell like?"})
    assert response.status_code == 401


def test_wrong_token_is_unauthorized(client):
    response = client.post(
        "/internal/rag/search",
        json={"query": "What does this smell like?"},
        headers={"X-Yafa-Service-Token": "y" * 40},
    )
    assert response.status_code == 401


def test_short_configured_token_rejected(client, monkeypatch):
    monkeypatch.setenv("YAFA_INTERNAL_SERVICE_TOKEN", "short")
    response = client.post(
        "/internal/rag/search",
        json={"query": "q"},
        headers={"X-Yafa-Service-Token": "short"},
    )
    assert response.status_code == 401


def test_valid_token_returns_raw_chunks_and_live_flags(client):
    response = client.post(
        "/internal/rag/search",
        json={"query": "What does this smell like?", "page_context": {"type": "product", "product_id": "yv-frag-010"}},
        headers={"X-Yafa-Service-Token": TOKEN},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["resolution"] == "page_context"
    assert payload["results"][0]["chunk_type"] == "scent_profile"
    assert payload["results"][0]["similarity"] > 0.9
    assert payload["requires_live_data"][0]["domain"] == "inventory"
    # Raw retrieval only — no generated answer in Phase 1 (spec §24).
    assert "answer" not in payload


def test_request_validation_rejects_bad_top_k(client):
    response = client.post(
        "/internal/rag/search",
        json={"query": "hello", "top_k": 999},
        headers={"X-Yafa-Service-Token": TOKEN},
    )
    assert response.status_code == 422


# -- health ------------------------------------------------------------------


class FakeHealthRepo:
    """Configurable stand-in for the repository used by /health."""

    connected = True
    pgvector = True
    dimension_value = 2048
    metadata: dict | None = None

    def connection(self):
        health = self

        class Cursor:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def execute(self, query, params=None):
                if "pg_extension" in query:
                    self._row = {"enabled": health.pgvector}
                elif self._row is None:
                    self._row = {}

            _row = None

            def fetchone(self):
                return getattr(self, "_row", {})

        class Conn:
            def cursor(self):
                return Cursor()

        return Conn()

    def stored_dimension(self) -> int | None:
        return self.dimension_value

    def get_embedding_metadata(self) -> dict | None:
        return self.metadata

    def close(self) -> None:
        pass


class BrokenRepo(FakeHealthRepo):
    def connection(self):
        raise RuntimeError("connection refused: password authentication failed")


def health_client(monkeypatch, repo, **env):
    monkeypatch.setenv("YAFA_INTERNAL_SERVICE_TOKEN", TOKEN)
    monkeypatch.setenv("VECTOR_DATABASE_URL", "postgresql://db.ref.supabase.co:6543/postgres")
    monkeypatch.setenv("EMBEDDING_PROVIDER", "hashing")
    monkeypatch.setattr(rag_api, "RagRepository", lambda dsn: repo)
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    application = FastAPI()
    application.include_router(rag_api.router)
    return TestClient(application)


def test_health_requires_token(monkeypatch):
    monkeypatch.setenv("YAFA_INTERNAL_SERVICE_TOKEN", TOKEN)
    application = FastAPI()
    application.include_router(rag_api.router)
    client = TestClient(application)
    assert client.get("/internal/rag/health").status_code == 401


def test_health_reports_ok_when_everything_matches(monkeypatch):
    repo = FakeHealthRepo()
    repo.metadata = {
        "embedding_provider": "hashing",
        "embedding_model": "yafa-hashing-v1",
        "embedding_dimension": 2048,
    }
    client = health_client(monkeypatch, repo, EMBEDDING_DIMENSION="2048")
    response = client.get("/internal/rag/health", headers={"X-Yafa-Service-Token": TOKEN})
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["database_connected"] is True
    assert payload["pgvector_enabled"] is True
    assert payload["stored_dimension"] == 2048
    assert payload["embedding_space_consistent"] is True


def test_health_flags_missing_pgvector_as_degraded(monkeypatch):
    repo = FakeHealthRepo()
    repo.pgvector = False
    client = health_client(monkeypatch, repo, EMBEDDING_DIMENSION="2048")
    payload = client.get(
        "/internal/rag/health", headers={"X-Yafa-Service-Token": TOKEN}
    ).json()
    assert payload["status"] == "degraded"
    assert payload["database_connected"] is True
    assert payload["pgvector_enabled"] is False


def test_health_reports_error_without_leaking_internals(monkeypatch):
    client = health_client(monkeypatch, BrokenRepo(), EMBEDDING_DIMENSION="2048")
    response = client.get("/internal/rag/health", headers={"X-Yafa-Service-Token": TOKEN})
    body = response.text
    payload = response.json()
    assert payload["status"] == "error"
    assert payload["database_connected"] is False
    # No raw exception text, DSN fragments or credential hints may leak.
    assert "password" not in body.lower()
    assert "supabase" not in body.lower()
    assert "refused" not in body.lower()


def test_health_detects_mixed_embedding_space(monkeypatch):
    repo = FakeHealthRepo()
    repo.metadata = {
        "embedding_provider": "openrouter",
        "embedding_model": "nvidia/nemotron-3-embed-1b:free",
        "embedding_dimension": 2048,
    }
    client = health_client(monkeypatch, repo, EMBEDDING_DIMENSION="2048")
    payload = client.get(
        "/internal/rag/health", headers={"X-Yafa-Service-Token": TOKEN}
    ).json()
    assert payload["status"] == "degraded"
    assert payload["embedding_space_consistent"] is False


def test_health_unconfigured_reports_cleanly(monkeypatch):
    monkeypatch.delenv("VECTOR_DATABASE_URL", raising=False)
    monkeypatch.setenv("YAFA_INTERNAL_SERVICE_TOKEN", TOKEN)
    application = FastAPI()
    application.include_router(rag_api.router)
    client = TestClient(application)
    payload = client.get("/internal/rag/health", headers={"X-Yafa-Service-Token": TOKEN}).json()
    assert payload["status"] == "unconfigured"
