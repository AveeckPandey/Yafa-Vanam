"""Amazon Bedrock embedding provider for the private AWS RAG deployment."""

from __future__ import annotations

import asyncio
import json
from typing import Any

from app.rag.providers.base import EmbeddingAuthError, EmbeddingProvider, EmbeddingProviderError, validate_vectors


DEFAULT_BEDROCK_MODEL = "amazon.titan-embed-text-v2:0"
DEFAULT_DIMENSION = 1024


class BedrockEmbeddingProvider(EmbeddingProvider):
    """Uses the task/instance IAM role; no model key is stored in the app."""

    def __init__(self, *, model: str = DEFAULT_BEDROCK_MODEL, dimension: int = DEFAULT_DIMENSION,
                 region: str = "ap-south-1", client: Any | None = None) -> None:
        self._model = model
        self._dimension = int(dimension)
        if self._dimension not in {256, 512, 1024}:
            raise ValueError("Bedrock Titan v2 embedding dimension must be 256, 512, or 1024")
        if client is None:
            try:
                import boto3
                client = boto3.client("bedrock-runtime", region_name=region)
            except ImportError as exc:
                raise EmbeddingAuthError("boto3 is required for EMBEDDING_PROVIDER=bedrock") from exc
        self._client = client

    @property
    def provider_name(self) -> str:
        return "bedrock"

    @property
    def model_name(self) -> str:
        return self._model

    @property
    def dimension(self) -> int:
        return self._dimension

    async def embed_document(self, text: str) -> list[float]:
        return (await self.embed_documents([text]))[0]

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        # Titan's InvokeModel request accepts one input at a time. Keeping this
        # loop bounded avoids consuming excess Bedrock throughput during ingest.
        vectors = [await self._embed(text) for text in texts]
        validate_vectors(vectors, self._dimension)
        return vectors

    async def embed_query(self, text: str) -> list[float]:
        return await self._embed(text)

    async def _embed(self, text: str) -> list[float]:
        try:
            response = await asyncio.to_thread(
                self._client.invoke_model,
                modelId=self._model,
                contentType="application/json",
                accept="application/json",
                body=json.dumps({"inputText": text, "dimensions": self._dimension, "normalize": True}),
            )
            payload = json.loads(response["body"].read())
            vector = payload.get("embedding")
            if not isinstance(vector, list):
                raise EmbeddingProviderError("Bedrock returned no embedding")
            validate_vectors([vector], self._dimension)
            return [float(value) for value in vector]
        except EmbeddingProviderError:
            raise
        except Exception as exc:
            name = type(exc).__name__
            if name in {"AccessDeniedException", "UnrecognizedClientException"}:
                raise EmbeddingAuthError("Bedrock rejected the configured IAM identity") from exc
            raise EmbeddingProviderError(f"Bedrock embedding request failed: {name}") from exc
