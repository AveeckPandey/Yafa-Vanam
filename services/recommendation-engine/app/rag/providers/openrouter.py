"""OpenRouter embeddings client (OpenAI-compatible /embeddings endpoint).

Locked provider for Phase 1: nvidia/nemotron embed models via
https://openrouter.ai/api/v1. Asymmetric modes are enforced here — product
chunks go out with input_type=passage, user questions with input_type=query.

Free-tier endpoints rate-limit aggressively, so retryable failures (429/5xx,
timeouts) are retried a limited number of times with exponential backoff that
honours Retry-After, then surfaced as typed errors so ingestion can stop safely
and resume later without duplicates.

Secrets never appear in logs or error messages: the API key travels only in
the Authorization header and failures report status codes plus a short
response snippet, never request headers.
"""

from __future__ import annotations

import asyncio
import logging
import re

import httpx

from app.rag.providers.base import (
    EmbeddingAuthError,
    EmbeddingProvider,
    EmbeddingProviderError,
    EmbeddingRateLimitError,
    validate_vectors,
)

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"
# 429 and transient gateway failures may succeed on retry; everything else fails fast.
_RETRYABLE_STATUSES = frozenset({429, 502, 503, 504})
_SNIPPET_MAX = 200


def _snippet(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()[:_SNIPPET_MAX]


class OpenRouterEmbeddingProvider(EmbeddingProvider):
    def __init__(
        self,
        *,
        model: str,
        api_key: str,
        dimension: int,
        base_url: str = DEFAULT_BASE_URL,
        timeout_seconds: float = 60.0,
        max_attempts: int = 4,
        batch_size: int = 16,
        backoff_seconds: float = 0.75,
        max_backoff_seconds: float = 30.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        if not api_key:
            raise EmbeddingAuthError("OPENROUTER_API_KEY is not configured")
        if max_attempts < 1:
            raise ValueError("max_attempts must be >= 1")
        self._model = model
        self._api_key = api_key
        self._dimension = int(dimension)
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout_seconds
        self._max_attempts = max_attempts
        self._batch_size = max(1, batch_size)
        self._backoff = backoff_seconds
        self._max_backoff = max_backoff_seconds
        self._client = client  # injected clients (tests) are used but never closed

    @property
    def provider_name(self) -> str:
        return "openrouter"

    @property
    def dimension(self) -> int:
        return self._dimension

    @property
    def model_name(self) -> str:
        return self._model

    async def embed_document(self, text: str) -> list[float]:
        return (await self._request([text], input_type="passage"))[0]

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for start in range(0, len(texts), self._batch_size):
            batch = texts[start:start + self._batch_size]
            vectors.extend(await self._request(batch, input_type="passage"))
        return vectors

    async def embed_query(self, text: str) -> list[float]:
        return (await self._request([text], input_type="query"))[0]

    # -- transport ---------------------------------------------------------

    async def _request(self, texts: list[str], *, input_type: str) -> list[list[float]]:
        payload = {
            "model": self._model,
            "input": texts,
            "input_type": input_type,
            "encoding_format": "float",
        }
        last_error: EmbeddingProviderError | None = None
        for attempt in range(1, self._max_attempts + 1):
            failure_wait: float | None = None
            try:
                response = await self._post(payload)
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                last_error = EmbeddingProviderError(
                    f"embedding request failed after {attempt} attempt(s): {type(exc).__name__}"
                )
                logger.warning("embedding attempt %d/%d failed: %s", attempt, self._max_attempts,
                               type(exc).__name__)
            else:
                if response.status_code in (200, 201):
                    return self._parse(response, expected_count=len(texts), input_type=input_type)
                if response.status_code in (401, 403):
                    raise EmbeddingAuthError(
                        f"embedding provider rejected credentials (HTTP {response.status_code})"
                    )
                detail = _snippet(response.text)
                if response.status_code == 429:
                    last_error = EmbeddingRateLimitError(
                        f"embedding rate limited after {attempt} attempt(s); resume ingestion later"
                    )
                    failure_wait = self._retry_after(response)
                elif response.status_code in _RETRYABLE_STATUSES:
                    last_error = EmbeddingProviderError(
                        f"embedding provider temporarily unavailable (HTTP {response.status_code}): {detail}"
                    )
                    failure_wait = self._retry_after(response)
                else:
                    raise EmbeddingProviderError(
                        f"embedding request failed with HTTP {response.status_code}: {detail}"
                    )
            if attempt < self._max_attempts:
                wait = min(failure_wait or self._backoff * (2 ** (attempt - 1)), self._max_backoff)
                logger.warning("retrying embeddings in %.1fs (attempt %d/%d)",
                               wait, attempt, self._max_attempts)
                await asyncio.sleep(wait)
        assert last_error is not None
        raise last_error

    async def _post(self, payload: dict) -> httpx.Response:
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            # OpenRouter app-attribution headers; static values, no secrets.
            "X-Title": "YAFA VANAM recommendation-engine",
        }
        if self._client is not None:
            return await self._client.post(f"{self._base_url}/embeddings", json=payload, headers=headers)
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            return await client.post(f"{self._base_url}/embeddings", json=payload, headers=headers)

    def _retry_after(self, response: httpx.Response) -> float | None:
        """Seconds to wait before the next attempt, per the provider's Retry-After.

        Only the seconds form is parsed (what OpenRouter sends); absent,
        unparsable or negative values fall back to exponential backoff. The
        caller caps whatever this returns at max_backoff_seconds so a hostile
        or oversized header cannot stall ingestion for hours.
        """
        raw = (response.headers.get("Retry-After") or "").strip()
        if not raw:
            return None
        try:
            return max(float(raw), 0.0)
        except ValueError:
            return None

    def _parse(self, response: httpx.Response, *, expected_count: int, input_type: str) -> list[list[float]]:
        try:
            data = response.json()["data"]
            ordered = sorted(data, key=lambda item: item["index"])
            vectors = [[float(component) for component in item["embedding"]] for item in ordered]
        except (KeyError, TypeError, ValueError) as exc:
            raise EmbeddingProviderError(
                f"embedding provider returned an unexpected response body ({input_type} mode)"
            ) from exc
        if len(vectors) != expected_count:
            raise EmbeddingProviderError(
                f"embedding provider returned {len(vectors)} vectors for {expected_count} inputs"
            )
        validate_vectors(vectors, self._dimension)
        return vectors
