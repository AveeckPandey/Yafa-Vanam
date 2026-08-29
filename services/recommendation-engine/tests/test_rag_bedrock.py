from __future__ import annotations

import asyncio
import io
import json

from app.rag.config import RagSettings
from app.rag.providers import provider_identity
from app.rag.providers.bedrock import BedrockEmbeddingProvider


class _Client:
    def invoke_model(self, **_: object) -> dict[str, object]:
        return {"body": io.BytesIO(json.dumps({"embedding": [0.25] * 256}).encode())}


def test_bedrock_provider_uses_iam_client_and_validates_vector_shape():
    provider = BedrockEmbeddingProvider(dimension=256, client=_Client())
    assert provider.provider_name == "bedrock"
    assert asyncio.run(provider.embed_query("hydrating moisturiser")) == [0.25] * 256


def test_bedrock_settings_need_no_api_key():
    settings = RagSettings.from_env({
        "EMBEDDING_PROVIDER": "bedrock",
        "EMBEDDING_MODEL": "amazon.titan-embed-text-v2:0",
        "EMBEDDING_DIMENSION": "1024",
        "BEDROCK_REGION": "ap-south-1",
    })
    assert provider_identity(settings) == ("bedrock", "amazon.titan-embed-text-v2:0", 1024)
