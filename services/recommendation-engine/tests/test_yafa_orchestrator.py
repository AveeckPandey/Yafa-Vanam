"""Orchestrator behaviour tests (Phase 2 spec sections 29-39).

RAG is not configured in the test environment, so grounding degrades to
"unavailable" - exactly what production must do when Supabase is down.
"""
from __future__ import annotations

import pytest

from app.advisor.catalogue import product_by_id
from app.yafa.context import (
    detect_live_data_domain,
    extract_slots,
    merge_slots_into_profile,
)
from app.yafa.orchestrator import handle_chat
from app.yafa.schemas import PageContext, YafaChatRequest

pytestmark = pytest.mark.asyncio


def _request(message: str, **kwargs) -> YafaChatRequest:
    return YafaChatRequest(message=message, **kwargs)


async def test_live_inventory_question_short_circuits_to_go():
    response = await handle_chat(_request("Is Soft Ember in stock?"))
    assert response.requires is not None
    assert response.requires.domain == "inventory"
    assert "stock" in response.message.lower()
    assert response.recommendations == []


async def test_price_question_routes_to_commerce():
    response = await handle_chat(_request("How much does it cost?"))
    assert response.requires is not None
    assert response.requires.domain == "price"


async def test_product_information_without_rag_reports_unavailable():
    response = await handle_chat(
        _request(
            "Tell me about this product?",
            page_context=PageContext(type="product", product_id="yv-lip-001"),
        )
    )
    # RAG unconfigured in tests: honest degradation, never invented facts.
    assert response.intent in {"product_page_question", "product_information"}
    assert response.grounding == []
    assert "knowledge base" in response.message.lower()


async def test_scent_fact_without_data_is_fact_scoped_not_kb_dump():
    response = await handle_chat(
        _request(
            "What does this smell like?",
            page_context=PageContext(type="product", product_id="yv-frag-010"),
        )
    )
    # Scent is a specific fact ask: answer stays scoped to that fact.
    assert "verified scent information" in response.message.lower()
    assert response.grounding == []


async def test_lip_recommendation_returns_catalogue_validated_cards():
    response = await handle_chat(
        _request(
            "Recommend a lipstick for a warm medium-tan complexion with an emerald outfit",
            profile={
                "skin": {"depth": "medium_tan", "undertone": "warm"},
                "context": {
                    "occasion": "wedding",
                    "outfit": {"primary_colour": "emerald"},
                },
            },
        )
    )
    assert response.intent == "lip_recommendation"
    assert response.recommendations, "full signal profile must return candidates"
    for card in response.recommendations:
        assert product_by_id(card.product_id), "no LLM-invented or unknown ids"
        assert card.commerce_validation_required is True


async def test_full_look_runs_multiple_engines_with_coordination():
    response = await handle_chat(
        _request(
            "Build my look for a wedding, I'm wearing emerald and gold",
            profile={
                "skin": {"depth": "medium_tan", "undertone": "warm"},
                "makeup_preferences": {"intensity": "soft_glam"},
            },
        )
    )
    assert response.intent == "recommend_full_look"
    categories = {card.category for card in response.recommendations}
    assert {"cheeks", "lips"} <= categories
    for card in response.recommendations:
        assert product_by_id(card.product_id)


async def test_cheek_to_lip_coordination_codes_present():
    from app.yafa.tool_router import run_engine
    from app.recommendation.canonical.schemas import CoordinationHints

    payload: dict = {}
    plain = run_engine("lips", payload, limit=10)
    hints = CoordinationHints(lip_color_family="terracotta")
    coordinated = run_engine("lips", payload, limit=10, coordination=hints)

    def codes(result):
        return {code for item in result.items for code in item.reason_codes}

    assert "cheek_lip_family_coordination" not in codes(plain)
    assert "cheek_lip_family_coordination" in codes(coordinated), (
        "coordinated family must earn the code"
    )
    # The boost must actually lift coordinated families above baseline.
    boosted = [
        item for item in coordinated.items
        if "cheek_lip_family_coordination" in item.reason_codes
    ]
    assert all(item.score >= 0.5 for item in boosted)


async def test_conversation_slots_persist_and_merge():
    store_response = await handle_chat(
        _request("I'm going to a wedding in the evening wearing emerald")
    )
    assert store_response.conversation_id
    conv_id = store_response.conversation_id

    follow_up = await handle_chat(
        _request("Recommend a lipstick please", conversation_id=conv_id)
    )
    assert follow_up.conversation_id == conv_id
    # The wedding/evening/emerald slots must have been extracted and reused:
    assert follow_up.recommendations, "slots alone should be enough to rank"
    boosted = [
        card
        for card in follow_up.recommendations
        if "wedding_match" in card.reason_codes
        or "emerald_outfit_harmony" in card.reason_codes
        or any("outfit_harmony" in code for code in card.reason_codes)
    ]
    assert boosted, "persisted outfit/occasion slots must influence ranking"


async def test_page_context_binds_pronoun_to_current_product():
    response = await handle_chat(
        _request(
            "What about this one?",
            conversation_id="conv_page_ctx_test",
            page_context=PageContext(type="product", product_id="yv-lip-001"),
        )
    )
    assert response.intent == "product_page_question"


# --- chat UX routing fixes ----------------------------------------------------


async def test_greeting_never_triggers_rag_or_engines():
    for message in ("hi", "hello", "thanks"):
        response = await handle_chat(_request(message))
        assert response.intent == "greeting_or_small_talk"
        assert response.grounding == []
        assert response.recommendations == []
        assert "yafa" in response.message.lower()


async def test_unclear_input_gets_capability_answer():
    response = await handle_chat(_request("asdfgh qwerty"))
    assert response.intent == "unsupported_or_unclear"
    assert response.grounding == []


async def test_commerce_question_intent_label():
    response = await handle_chat(_request("where is my order?"))
    assert response.intent == "commerce_question"
    assert response.requires is not None
    assert response.requires.domain == "order_status"


async def test_expiry_fact_without_data_says_unavailable():
    response = await handle_chat(
        _request(
            "What is the expiry date of this product?",
            page_context=PageContext(type="product", product_id="yv-lip-001"),
        )
    )
    # No expiry/shelf-life chunks exist in the catalogue: must say so plainly,
    # never substitute unrelated warnings/evidence text.
    assert "don't have verified" in response.message.lower()
    assert "expiry" in response.message.lower()
    assert response.grounding == []


async def test_attachment_colours_are_remembered_for_later_turns():
    first = await handle_chat(
        _request(
            "Here's my outfit",
            attachment={"kind": "outfit", "colours": ["navy", "beige"], "confidence": 0.7},
        )
    )
    assert first.conversation_id

    second = await handle_chat(
        _request("match my makeup to this", conversation_id=first.conversation_id)
    )
    # The stored navy/beige context must power the styling flow - no re-ask.
    assert second.intent in {"recommend_full_look", "outfit_matching"}
    assert "what colour" not in second.message.lower()
    categories = {card.category for card in second.recommendations}
    assert categories  # engines produced candidates


async def test_outfit_matching_without_any_colour_context_asks_once():
    fresh = await handle_chat(_request("match my makeup to this"))
    assert fresh.intent == "outfit_matching"
    assert fresh.recommendations == []
    assert "?" in fresh.message


async def test_smell_question_with_page_context_scopes_to_product():
    response = await handle_chat(
        _request(
            "What does this smell like?",
            page_context=PageContext(type="product", product_id="yv-frag-010"),
            conversation_id="conv_smell_scope",
        )
    )
    assert response.intent == "product_information"
    # RAG unconfigured here -> honest degradation; crucially no OTHER product's
    # facts may appear (grounding empty when nothing was retrieved).
    assert response.grounding == []
