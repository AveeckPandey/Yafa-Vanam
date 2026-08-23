"""Embedding provider abstraction.

Documents and queries are embedded through distinct methods because asymmetric
models such as nvidia/nemotron embed use different modes per side:

    passage -> product chunks   (embed_document / embed_documents)
    query   -> user questions   (embed_query)

Provider-specific network code lives in sibling modules; the rest of the RAG
layer depends solely on this interface.
"""

from __future__ import annotations

import hashlib
import math
import re
from abc import ABC, abstractmethod

from app.rag.config import DimensionMismatchError

_TOKENIZE = re.compile(r"[a-z0-9]+")


class EmbeddingProvider(ABC):
    """All embedders expose identity + output dimension so startup can validate them."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        ...

    @property
    @abstractmethod
    def dimension(self) -> int:
        ...

    @property
    @abstractmethod
    def model_name(self) -> str:
        ...

    @abstractmethod
    async def embed_document(self, text: str) -> list[float]:
        """Embed one product-knowledge chunk (input_type=passage)."""
        ...

    @abstractmethod
    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Embed product-knowledge chunks in order (input_type=passage)."""
        ...

    @abstractmethod
    async def embed_query(self, text: str) -> list[float]:
        """Embed a user question (input_type=query)."""
        ...


class EmbeddingProviderError(RuntimeError):
    """Embedding request failed after its limited retries (or non-retryably)."""


class EmbeddingAuthError(EmbeddingProviderError):
    """Provider rejected credentials — never retried."""


class EmbeddingRateLimitError(EmbeddingProviderError):
    """Rate limit survived every retry — ingestion stops safely and resumes later."""


def validate_vectors(vectors: list[list[float]], expected_dimension: int) -> None:
    """Reject wrong-shaped provider responses outright.

    Never truncates, pads or silently accepts a different dimension.
    """
    for position, vector in enumerate(vectors):
        if len(vector) != expected_dimension:
            raise DimensionMismatchError(
                f"Expected {expected_dimension} dimensions, got {len(vector)} (vector {position})"
            )


class HashingEmbeddingProvider(EmbeddingProvider):
    """Deterministic local feature-hashing embedder (no network, no API key).

    Quality is below a trained model but it keeps development, integration tests
    and CI fully offline while exercising the exact same retrieval path. It is
    mode-agnostic: passage and query inputs hash identically.
    """

    DEFAULT_DIMENSION = 384
    MODEL_NAME = "yafa-hashing-v1"

    def __init__(self, dimension: int = DEFAULT_DIMENSION) -> None:
        self._dimension = dimension

    @property
    def provider_name(self) -> str:
        return "hashing"

    @property
    def dimension(self) -> int:
        return self._dimension

    @property
    def model_name(self) -> str:
        return self.MODEL_NAME

    def _vectorize(self, text: str) -> list[float]:
        vector = [0.0] * self._dimension
        tokens = _TOKENIZE.findall(text.lower())
        features = tokens + [f"{a}_{b}" for a, b in zip(tokens, tokens[1:])]
        for feature in features:
            digest = hashlib.blake2b(feature.encode("utf-8"), digest_size=8).digest()
            index = int.from_bytes(digest, "big") % self._dimension
            sign = 1.0 if digest[0] % 2 else -1.0
            vector[index] += sign
        norm = math.sqrt(sum(component * component for component in vector))
        if norm > 0:
            vector = [component / norm for component in vector]
        return vector

    async def embed_document(self, text: str) -> list[float]:
        return self._vectorize(text)

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._vectorize(text) for text in texts]

    async def embed_query(self, text: str) -> list[float]:
        return self._vectorize(text)
