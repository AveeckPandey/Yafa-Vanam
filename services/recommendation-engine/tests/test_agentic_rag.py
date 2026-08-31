"""Agentic RAG must never serve an answer without verified tool citations."""
from __future__ import annotations

import pytest

from app.rag.config import RagSettings
from app.yafa.agent import BedrockYafaAgent, ToolSearchResult

pytestmark = pytest.mark.asyncio

CHUNK_ID = "123e4567-e89b-12d3-a456-426614174000"


class FakeBedrockClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def converse(self, **kwargs):
        self.calls.append(kwargs)
        return self.responses.pop(0)


async def verified_search(query: str, product_id: str | None) -> ToolSearchResult:
    assert query == "What does Soft Ember smell like?"
    assert product_id == "yv-frag-010"
    return ToolSearchResult(
        chunks=[{
            "chunk_id": CHUNK_ID,
            "product_id": "yv-frag-010",
            "chunk_type": "scent_profile",
            "content": "Warm amber, saffron, and black tea.",
            "similarity": 0.91,
            "trust_level": "authoritative_catalogue",
            "requires_qualification": False,
        }],
        citation_required_topics=["scent"],
        medical_escalation_topics=[],
        available=True,
    )


def settings(**overrides) -> RagSettings:
    return RagSettings.from_env({
        "YAFA_AGENTIC_RAG_ENABLED": "true",
        "YAFA_AGENT_MAX_TOOL_CALLS": "2",
        **overrides,
    })


def tool_use_response():
    return {
        "output": {"message": {"content": [{"toolUse": {
            "toolUseId": "tool-1",
            "name": "search_verified_product_knowledge",
            "input": {"query": "What does Soft Ember smell like?", "product_id": "untrusted"},
        }}]}},
        "stopReason": "tool_use",
    }


async def test_agent_uses_verified_tool_and_strips_valid_source_tags():
    client = FakeBedrockClient([
        tool_use_response(),
        {"output": {"message": {"content": [{"text": f"It has warm amber and black tea notes [source:{CHUNK_ID}]."}]}}, "stopReason": "end_turn"},
    ])
    answer = await BedrockYafaAgent(settings(), client=client).answer(
        message="What does Soft Ember smell like?",
        page_product_id="yv-frag-010",
        search=verified_search,
    )

    assert answer is not None
    assert answer.message == "Warm amber, saffron, and black tea."
    assert answer.chunks[0]["chunk_id"] == CHUNK_ID
    assert len(client.calls) == 2


async def test_agent_rejects_uncited_model_response():
    client = FakeBedrockClient([
        tool_use_response(),
        {"output": {"message": {"content": [{"text": "It is a fresh fragrance."}]}}, "stopReason": "end_turn"},
    ])
    answer = await BedrockYafaAgent(settings(), client=client).answer(
        message="What does Soft Ember smell like?",
        page_product_id="yv-frag-010",
        search=verified_search,
    )
    assert answer is None


async def test_agent_rejects_a_trailing_citation_that_does_not_cover_every_claim():
    client = FakeBedrockClient([
        tool_use_response(),
        {"output": {"message": {"content": [{
            "text": f"It has warm amber notes. It lasts all day [source:{CHUNK_ID}]."
        }]}}, "stopReason": "end_turn"},
    ])
    answer = await BedrockYafaAgent(settings(), client=client).answer(
        message="What does Soft Ember smell like?",
        page_product_id="yv-frag-010",
        search=verified_search,
    )
    assert answer is None


async def test_cited_but_invented_claim_is_replaced_with_exact_source_fact():
    client = FakeBedrockClient([
        tool_use_response(),
        {"output": {"message": {"content": [{
            "text": f"It lasts for twenty-four hours [source:{CHUNK_ID}]."
        }]}}, "stopReason": "end_turn"},
    ])
    answer = await BedrockYafaAgent(settings(), client=client).answer(
        message="What does Soft Ember smell like?",
        page_product_id="yv-frag-010",
        search=verified_search,
    )
    assert answer is not None
    assert answer.message == "Warm amber, saffron, and black tea."
    assert "twenty-four" not in answer.message


async def test_agent_rejects_unknown_tool_before_any_data_is_accessed():
    client = FakeBedrockClient([{
        "output": {"message": {"content": [{"toolUse": {
            "toolUseId": "tool-1", "name": "delete_customer_data", "input": {},
        }}]}},
        "stopReason": "tool_use",
    }])

    async def forbidden_search(*_args):
        raise AssertionError("unknown tool must not reach retrieval")

    answer = await BedrockYafaAgent(settings(), client=client).answer(
        message="hello", page_product_id=None, search=forbidden_search
    )
    assert answer is None
