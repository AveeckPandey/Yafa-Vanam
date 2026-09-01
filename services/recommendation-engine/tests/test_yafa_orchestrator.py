"""RAG-only chat behaviour: facts retrieve, commerce defers, rankings stop."""
from __future__ import annotations

import pytest

import app.yafa.orchestrator as orchestrator
from app.rag.models import TrustLevel
from app.rag.schemas import RagSearchResponse, RetrievedChunk
from app.yafa.orchestrator import handle_chat
from app.yafa.schemas import PageContext, YafaChatRequest

pytestmark = pytest.mark.asyncio


class StubRetriever:
    async def search(self, request):
        return RagSearchResponse(
            query=request.query,
            product_id=request.product_id,
            results=[
                RetrievedChunk(
                    chunk_id="chunk-1",
                    product_id="yv-frag-010",
                    product_name="Soft Ember",
                    chunk_type="scent_profile",
                    content="Warm amber, saffron, and black tea.",
                    similarity=0.91,
                    trust_level=TrustLevel.AUTHORITATIVE_CATALOGUE,
                    customer_factual_eligible=True,
                    requires_qualification=False,
                )
            ],
            citation_required_topics=["scent"],
        )


class BenefitsUsageStubRetriever:
    async def search(self, request):
        assert set(request.chunk_types or []) == {"benefits", "usage"}
        return RagSearchResponse(
            query=request.query,
            product_id=request.product_id,
            results=[
                RetrievedChunk(
                    chunk_id="benefits-1",
                    product_id="yv-cheek-001",
                    product_name="Airbloom Blush",
                    chunk_type="benefits",
                    content="Adds fresh, buildable cheek colour.",
                    similarity=0.93,
                    trust_level=TrustLevel.AUTHORITATIVE_CATALOGUE,
                    customer_factual_eligible=True,
                    requires_qualification=False,
                ),
                RetrievedChunk(
                    chunk_id="usage-1",
                    product_id="yv-cheek-001",
                    product_name="Airbloom Blush",
                    chunk_type="usage",
                    content="Apply to the cheeks and blend to the desired intensity.",
                    similarity=0.92,
                    trust_level=TrustLevel.AUTHORITATIVE_CATALOGUE,
                    customer_factual_eligible=True,
                    requires_qualification=False,
                ),
            ],
        )


def _request(message: str, **kwargs) -> YafaChatRequest:
    return YafaChatRequest(message=message, **kwargs)


async def test_product_fact_uses_rag_and_preserves_grounding(monkeypatch):
    monkeypatch.setattr(orchestrator, "_get_retriever", lambda: StubRetriever())
    response = await handle_chat(
        _request(
            "What does this smell like?",
            page_context=PageContext(type="product", product_id="yv-frag-010"),
        )
    )
    assert response.intent == "product_information"
    assert response.grounding[0].product_id == "yv-frag-010"
    assert response.recommendations == []
    assert "amber" in response.message.lower()


async def test_product_benefits_and_usage_question_reaches_rag(monkeypatch):
    monkeypatch.setattr(orchestrator, "_get_retriever", lambda: BenefitsUsageStubRetriever())
    response = await handle_chat(
        _request("What are the verified benefits and usage instructions for Airbloom Blush?")
    )
    assert response.intent == "product_information"
    assert {chunk.chunk_type for chunk in response.grounding} == {"benefits", "usage"}


async def test_live_inventory_question_short_circuits_to_commerce():
    response = await handle_chat(_request("Is Soft Ember in stock?"))
    assert response.requires is not None
    assert response.requires.domain == "inventory"
    assert response.recommendations == []


async def test_recommendation_request_is_explicitly_unavailable():
    response = await handle_chat(_request("Recommend a lipstick for me"))
    assert response.intent == "recommendation_unavailable"
    assert response.recommendations == []
    assert "can't generate" in response.message.lower()


async def test_greeting_never_uses_rag(monkeypatch):
    monkeypatch.setattr(
        orchestrator,
        "_get_retriever",
        lambda: (_ for _ in ()).throw(AssertionError("RAG should not run")),
    )
    response = await handle_chat(_request("hello"))
    assert response.intent == "greeting_or_small_talk"
    assert response.grounding == []


async def test_product_fact_without_rag_is_honest(monkeypatch):
    monkeypatch.setattr(
        orchestrator,
        "_get_retriever",
        lambda: (_ for _ in ()).throw(RuntimeError("unconfigured")),
    )
    response = await handle_chat(_request("What does this smell like?"))
    assert "temporarily unavailable" in response.message.lower()
    assert "verified information" in response.message.lower()
