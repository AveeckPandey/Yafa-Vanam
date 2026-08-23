"""Embedding provider contract: passage/query modes, dimension validation,
retry economics, and secret hygiene for the locked OpenRouter provider."""

from __future__ import annotations

import json

import httpx
import pytest

from app.rag.config import DimensionMismatchError, RagSettings
from app.rag.providers import (
    DEFAULT_OPENROUTER_MODEL,
    EmbeddingAuthError,
    EmbeddingProviderError,
    EmbeddingRateLimitError,
    HashingEmbeddingProvider,
    OpenRouterEmbeddingProvider,
    build_provider,
    validate_vectors,
)

MODEL = "nvidia/nemotron-3-embed-1b:free"
KEY = "sk-or-test-key-not-real"


def make_provider(handler, *, dimension: int = 2048, **kwargs) -> tuple[OpenRouterEmbeddingProvider, list[dict]]:
    """Provider wired to an in-memory transport; returns it plus captured requests."""
    requests: list[dict] = []

    def capture(request: httpx.Request) -> httpx.Response:
        requests.append(json.loads(request.content))
        return handler(request)

    client = httpx.AsyncClient(transport=httpx.MockTransport(capture))
    provider = OpenRouterEmbeddingProvider(
        model=MODEL, api_key=KEY, dimension=dimension,
        backoff_seconds=0.001, max_backoff_seconds=0.002, **kwargs,
    )
    # Tests drive the injected client directly so no real sockets are opened.
    provider._client = client
    return provider, requests


def embedding_response(vectors: list[list[float]], status_code: int = 200) -> httpx.Response:
    return httpx.Response(
        status_code,
        json={"data": [{"index": i, "embedding": vector} for i, vector in enumerate(vectors)]},
        request=httpx.Request("POST", "https://openrouter.ai/api/v1/embeddings"),
    )


class TestOpenRouterModes:
    async def test_embed_query_sends_input_type_query(self):
        provider, requests = make_provider(
            lambda request: embedding_response([[0.5] * 2048])
        )
        vector = await provider.embed_query("What does Soft Ember smell like?")
        assert len(vector) == 2048
        assert requests[0]["input_type"] == "query"

    async def test_embed_document_sends_input_type_passage(self):
        provider, requests = make_provider(
            lambda request: embedding_response([[0.1] * 2048])
        )
        vector = await provider.embed_document("Scent profile of Soft Ember...")
        assert len(vector) == 2048
        assert requests[0]["input_type"] == "passage"

    async def test_embed_documents_splits_into_batches(self):
        seen_sizes: list[int] = []

        def handler(request: httpx.Request) -> httpx.Response:
            payload = json.loads(request.content)
            seen_sizes.append(len(payload["input"]))
            return embedding_response([[0.5] * 2048 for _ in payload["input"]])

        provider, _ = make_provider(handler, batch_size=2)
        vectors = await provider.embed_documents(["a", "b", "c"])
        assert len(vectors) == 3
        assert seen_sizes == [2, 1]

    async def test_request_shape_is_openai_compatible_float(self):
        provider, requests = make_provider(lambda request: embedding_response([[0.5] * 2048]))
        await provider.embed_query("hello")
        assert requests[0]["model"] == MODEL
        assert requests[0]["encoding_format"] == "float"


class TestDimensionValidation:
    async def test_wrong_dimension_rejected_not_padded(self):
        provider, _ = make_provider(lambda request: embedding_response([[0.5] * 1536]))
        with pytest.raises(DimensionMismatchError, match="Expected 2048 dimensions, got 1536"):
            await provider.embed_query("hello")

    async def test_count_mismatch_rejected(self):
        provider, _ = make_provider(lambda request: embedding_response([[0.5] * 2048]))  # 1 vector
        with pytest.raises(EmbeddingProviderError, match="returned 1 vectors for 3 inputs"):
            await provider.embed_documents(["a", "b", "c"])

    def test_validate_vectors_helper(self):
        validate_vectors([[0.1] * 4], 4)
        with pytest.raises(DimensionMismatchError):
            validate_vectors([[0.1] * 3], 4)


class TestRetryEconomics:
    async def test_rate_limit_then_success(self):
        calls = {"n": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            calls["n"] += 1
            if calls["n"] == 1:
                return httpx.Response(429, json={"error": "rate limited"})
            return embedding_response([[0.5] * 2048])

        provider, _ = make_provider(handler)
        assert len(await provider.embed_query("hello")) == 2048
        assert calls["n"] == 2

    async def test_rate_limit_exhausts_retries(self):
        calls = {"n": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            calls["n"] += 1
            return httpx.Response(429, json={"error": "still limited"})

        provider, _ = make_provider(handler, max_attempts=3)
        with pytest.raises(EmbeddingRateLimitError):
            await provider.embed_query("hello")
        assert calls["n"] == 3  # bounded — never retries indefinitely

    async def test_retry_after_header_is_honoured_without_sleeping_long(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(429, json={}, headers={"Retry-After": "3600"})

        provider, _ = make_provider(handler, max_attempts=2)
        # Capped at max_backoff_seconds (0.002s here), so this returns quickly.
        with pytest.raises(EmbeddingRateLimitError):
            await provider.embed_query("hello")

    async def test_auth_errors_never_retry(self):
        calls = {"n": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            calls["n"] += 1
            return httpx.Response(401, json={"error": "bad key"})

        provider, _ = make_provider(handler)
        with pytest.raises(EmbeddingAuthError):
            await provider.embed_query("hello")
        assert calls["n"] == 1

    async def test_unexpected_client_error_fails_fast(self):
        provider, _ = make_provider(lambda request: httpx.Response(400, json={"error": "bad request"}))
        with pytest.raises(EmbeddingProviderError, match="HTTP 400"):
            await provider.embed_query("hello")

    async def test_transport_failures_are_bounded(self):
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("connection refused")

        provider, _ = make_provider(handler, max_attempts=2)
        with pytest.raises(EmbeddingProviderError, match="attempt"):
            await provider.embed_query("hello")


class TestSecretHygiene:
    async def test_api_key_never_appears_in_logs_or_errors(self, caplog):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(500, json={"error": "boom"})

        provider, _ = make_provider(handler, max_attempts=1)
        with caplog.at_level("DEBUG"), pytest.raises(EmbeddingProviderError) as excinfo:
            await provider.embed_query("hello")
        assert KEY not in caplog.text
        assert KEY not in str(excinfo.value)

    def test_missing_key_is_configuration_error(self):
        with pytest.raises(EmbeddingAuthError):
            OpenRouterEmbeddingProvider(model=MODEL, api_key="", dimension=2048)


class TestBuildProvider:
    def test_openrouter_requires_key(self):
        settings = RagSettings.from_env({
            "EMBEDDING_PROVIDER": "openrouter",
            "EMBEDDING_DIMENSION": "2048",
            "OPENROUTER_API_KEY": "",
        })
        with pytest.raises(RuntimeError, match="OPENROUTER_API_KEY"):
            build_provider(settings)

    def test_openrouter_requires_dimension(self):
        settings = RagSettings.from_env({
            "EMBEDDING_PROVIDER": "openrouter",
            "OPENROUTER_API_KEY": KEY,
        })
        with pytest.raises(RuntimeError, match="EMBEDDING_DIMENSION"):
            build_provider(settings)

    def test_openrouter_locked_model_default(self):
        settings = RagSettings.from_env({
            "EMBEDDING_PROVIDER": "openrouter",
            "EMBEDDING_DIMENSION": "2048",
            "OPENROUTER_API_KEY": KEY,
        })
        provider = build_provider(settings)
        assert provider.model_name == DEFAULT_OPENROUTER_MODEL
        assert provider.dimension == 2048
        assert provider.provider_name == "openrouter"

    def test_configured_dimension_must_match_model_output(self):
        settings = RagSettings.from_env({
            "EMBEDDING_PROVIDER": "hashing",
            "EMBEDDING_DIMENSION": "9999",
        })
        with pytest.raises(DimensionMismatchError):
            build_provider(settings)


class TestHashingFallback:
    async def test_implements_all_three_modes(self):
        provider = HashingEmbeddingProvider(dimension=2048)
        document_vector = await provider.embed_document("product chunk")
        query_vector = await provider.embed_query("user question")
        batch = await provider.embed_documents(["one", "two"])
        assert len(document_vector) == len(query_vector) == 2048
        assert len(batch) == 2 and all(len(vector) == 2048 for vector in batch)
