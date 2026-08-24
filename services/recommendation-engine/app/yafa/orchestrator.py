"""The one Yafa orchestrator (spec Phase 2 §27-§39).

Flow: message + page context + conversation slots -> intent -> tool routing
(RAG for facts, engines for rankings) -> catalogue id validation ->
deterministic response composition. Commerce questions short-circuit with
``requires`` so Go stays the authority; the LLM is deliberately not connected.
"""
from __future__ import annotations

import logging
from typing import Any

from app.advisor.catalogue import product_by_id
from app.yafa import coordination as look_coordination
from app.yafa import prompts
from app.yafa.context import (
    detect_fact_type,
    detect_live_data_domain,
    extract_slots,
    fact_chunk_types,
    merge_slots_into_profile,
    message_refers_to_page_product,
    resolve_page_product,
)
from app.yafa.conversation import conversation_store
from app.yafa.intents import Intent, categories_for_intent, classify
from app.yafa.schemas import (
    GroundingChunk,
    LiveRequirement,
    RecommendRequest,
    RecommendationCard,
    YafaChatRequest,
    YafaChatResponse,
)
from app.yafa.tool_router import rag_lookup, run_engine, shade_guidance_outcome

logger = logging.getLogger(__name__)

# Vocabulary for slot extraction — outfit colours mirror v1's harmony keys.
OUTFIT_COLOUR_VOCABULARY: dict[str, list[str]] = {
    "outfit_colours": [
        "emerald", "green", "gold", "red", "burgundy", "blue", "navy",
        "purple", "pink", "orange", "terracotta", "black", "white",
        "brown", "beige", "grey", "silver",
    ],
}

_CATEGORY_LABELS = {
    "lips": "lip", "cheeks": "cheek", "eyes": "eye",
    "complexion": "complexion", "skincare": "skincare", "fragrance": "fragrance",
}

# Categories whose ranking materially changes with a missing input.
_MISSING_INFO_CATEGORIES = {"lips", "cheeks", "eyes", "complexion", "skincare", "fragrance"}


def _has_profile_signal(profile: dict[str, Any]) -> bool:
    """True when any ranking-relevant signal exists in the payload."""
    skin = profile.get("skin") or {}
    context = profile.get("context") or {}
    prefs = profile.get("makeup_preferences") or {}
    fragrance = profile.get("fragrance_preferences") or {}
    return bool(
        skin
        or context.get("occasion")
        or context.get("outfit")
        or prefs
        or fragrance
        or profile.get("shade_code")
        or profile.get("confirmed_shade")
    )


def _profile_missing_for(category: str, profile: dict[str, Any]) -> bool:
    """Material-missing checks only (spec §37: ask what changes the ranking)."""
    if _has_profile_signal(profile):
        return False
    if category == "skincare":
        return not (profile.get("skin") or {}).get("type")
    if category == "complexion":
        return not profile.get("shade_code")
    return True


def _to_card(item: Any) -> RecommendationCard:
    return RecommendationCard(
        product_id=item.product_id,
        variant_id=item.variant_id,
        category=item.category,
        score=item.score,
        reason_codes=list(item.reason_codes),
        warnings=list(item.warnings),
        product_name=item.product_name,
        color_family=item.color_family,
        shade_name=item.shade_name,
        shade_hex=item.shade_hex,
        source_file=item.source.file if item.source else None,
    )


def _validate_cards(cards: list[RecommendationCard]) -> list[RecommendationCard]:
    """Drop anything the canonical catalogue does not know (spec §34)."""
    validated: list[RecommendationCard] = []
    for card in cards:
        if product_by_id(card.product_id) is None:
            logger.warning("dropping non-catalogue recommendation id %s", card.product_id)
            continue
        validated.append(card)
    return validated


def _grounding_from(chunks: list[dict[str, Any]]) -> list[GroundingChunk]:
    return [
        GroundingChunk(
            product_id=chunk["product_id"],
            chunk_type=chunk["chunk_type"],
            content=chunk["content"],
            similarity=chunk["similarity"],
            trust_level=chunk["trust_level"],
            requires_qualification=chunk["requires_qualification"],
        )
        for chunk in chunks
    ]


async def handle_chat(request: YafaChatRequest) -> YafaChatResponse:
    store = conversation_store()
    conv = store.get_or_create(
        request.conversation_id,
        user_id=request.user_id,
        page_context=request.page_context,
    )

    intent = _classify_intent(request)

    # --- greetings/small talk never reach RAG or the engines ---------------
    if intent is Intent.GREETING_OR_SMALL_TALK:
        response = YafaChatResponse(
            conversation_id=conv.conversation_id,
            intent=intent.value,
            message=prompts.greeting_message(),
        )
        conv.record_turn("user", request.message)
        conv.record_turn("yafa", response.message)
        return response

    # --- live commerce truth never comes from static data (spec §14) ------
    domain = detect_live_data_domain(request.message)
    if domain or intent is Intent.COMMERCE_QUESTION:
        page_product = resolve_page_product(conv.page_context)
        resolved_domain = domain or "availability"
        return YafaChatResponse(
            conversation_id=conv.conversation_id,
            intent=Intent.COMMERCE_QUESTION.value,
            message=prompts.commerce_message(
                resolved_domain, page_product.get("name") if page_product else None
            ),
            requires=LiveRequirement(
                domain=resolved_domain,
                product_id=(page_product or {}).get("id"),
            ),
        )

    # --- attachment memory: image context survives later turns -------------
    if request.attachment is not None:
        colours = [c for c in request.attachment.colours if c]
        conv.record_attachment(
            request.attachment.kind, colours, request.attachment.runner_up_colour
        )
        if colours and request.attachment.kind == "outfit":
            absorb: dict[str, Any] = {"outfit_primary_colour": colours[0]}
            if len(colours) > 1:
                absorb["outfit_secondary_colours"] = colours[1:]
            conv.absorb_slots(absorb)

    # --- slot extraction + profile merging ---------------------------------
    slots = extract_slots(request.message, OUTFIT_COLOUR_VOCABULARY)
    conv.absorb_slots(slots)
    conv.record_turn("user", request.message)
    profile = merge_slots_into_profile(request.profile, conv.slots)

    # --- page-product binding ("what about this one?") ---------------------
    page_product = resolve_page_product(conv.page_context)
    refers_to_page = message_refers_to_page_product(request.message)

    if intent in {Intent.GENERAL} and page_product and refers_to_page:
        intent = Intent.PRODUCT_PAGE_QUESTION

    # --- unclear/empty input gets an honest capability answer --------------
    if intent in {Intent.GENERAL, Intent.UNSUPPORTED_OR_UNCLEAR}:
        response = YafaChatResponse(
            conversation_id=conv.conversation_id,
            intent=Intent.UNSUPPORTED_OR_UNCLEAR.value,
            message=prompts.unclear_message(),
        )
        conv.record_turn("yafa", response.message)
        return response

    # --- outfit / image-assisted styling ------------------------------------
    if intent in {Intent.OUTFIT_MATCHING, Intent.IMAGE_ASSISTED_QUERY}:
        has_colours = bool((profile.get("context") or {}).get("outfit"))
        if not has_colours:
            message = (
                prompts.image_no_context_message()
                if intent is Intent.IMAGE_ASSISTED_QUERY
                else prompts.outfit_missing_colours_message()
            )
            response = YafaChatResponse(
                conversation_id=conv.conversation_id,
                intent=intent.value,
                message=message,
            )
            conv.record_turn("yafa", response.message)
            return response
        intent = Intent.RECOMMEND_FULL_LOOK  # coordinate face categories only

    if intent == Intent.SHADE_MATCH_REQUEST:
        outcome = shade_guidance_outcome()
        response = YafaChatResponse(
            conversation_id=conv.conversation_id,
            intent=outcome.intent.value,
            message=prompts.general_message()
            if not outcome.followup_question
            else outcome.followup_question,
        )
        conv.record_turn("yafa", response.message)
        return response

    if intent == Intent.ADVISOR_START:
        response = YafaChatResponse(
            conversation_id=conv.conversation_id,
            intent=intent.value,
            message=prompts.general_message(),
        )
        conv.record_turn("yafa", response.message)
        return response

    if intent in {
        Intent.PRODUCT_INFORMATION,
        Intent.PRODUCT_PAGE_QUESTION,
        Intent.PRODUCT_COMPARISON,
        Intent.INGREDIENT_QUESTION,
        Intent.COMPATIBILITY_QUESTION,
    }:
        scoped_product = page_product if refers_to_page else None
        fact_label = detect_fact_type(request.message)
        chunks, policy, citations, medical, available = await rag_lookup(
            request.message,
            product_id=(scoped_product or {}).get("id"),
            top_k=5,
        )

        # Fact-scoped questions (e.g. expiry): only chunk types that could
        # legitimately answer them. Never substitute unrelated safety text.
        # This check comes FIRST: "we hold no verified <fact>" stays true both
        # when the KB lacks the data and when it cannot be reached.
        if fact_label and intent is not Intent.PRODUCT_COMPARISON:
            wanted_types = set(fact_chunk_types(fact_label))
            relevant = [c for c in chunks if c["chunk_type"] in wanted_types]
            if not relevant:
                message = prompts.unavailable_fact_message(
                    fact_label, (scoped_product or {}).get("name")
                ) if scoped_product else prompts.unavailable_fact_message(fact_label, None)
                response = YafaChatResponse(
                    conversation_id=conv.conversation_id,
                    intent=intent.value,
                    message=message,
                    citation_required_topics=citations,
                    medical_escalation_topics=medical,
                )
                conv.record_turn("yafa", response.message)
                return response
            chunks = relevant

        # Generic question with the KB unreachable: honest degradation.
        if not available:
            response = YafaChatResponse(
                conversation_id=conv.conversation_id,
                intent=intent.value,
                message=prompts.product_information_message([], rag_available=False),
                citation_required_topics=citations,
                medical_escalation_topics=medical,
            )
            conv.record_turn("yafa", response.message)
            return response

        grounding = _grounding_from(chunks)
        prefix = ""
        if fact_label and chunks:
            prefix = prompts.fact_answer_prefix((scoped_product or {}).get("name"))
        body = prompts.product_information_message(chunks, rag_available=available)
        response = YafaChatResponse(
            conversation_id=conv.conversation_id,
            intent=intent.value,
            message=f"{prefix}{body}",
            grounding=grounding[:4],
            citation_required_topics=citations,
            medical_escalation_topics=medical,
        )
        conv.record_turn("yafa", response.message)
        return response

    # --- recommendation intents --------------------------------------------
    categories = categories_for_intent(intent, request.message)
    if intent is Intent.RECOMMEND_PRODUCT:
        if not categories or _profile_missing_for(categories[0], profile):
            question = prompts.missing_info_question(categories[0] if categories else "")
            response = YafaChatResponse(
                conversation_id=conv.conversation_id,
                intent=intent.value,
                message=question,
            )
            conv.record_turn("yafa", response.message)
            return response

    selections: dict[str, list[dict[str, Any]]] = {}
    extra_codes: dict[str, list[str]] = {}
    notes: list[str] = []
    cards: list[RecommendationCard] = []

    if intent is Intent.RECOMMEND_FULL_LOOK:
        bold_requested = "bold" in request.message.lower() or (
            profile.get("makeup_preferences") or {}
        ).get("intensity") in {"bold", "glam", "editorial"}
        cheek_result = run_engine("cheeks", profile, limit=3)
        selections["cheeks"] = [item.model_dump(mode="json") for item in cheek_result.items]
        hints = look_coordination.lip_hints_from_cheek(selections["cheeks"])
        lips_result = run_engine("lips", profile, limit=3, coordination=hints)
        selections["lips"] = [item.model_dump(mode="json") for item in lips_result.items]
        eyes_result = run_engine("eyes", profile, limit=3)
        selections["eyes"] = [item.model_dump(mode="json") for item in eyes_result.items]
        complexion_result = run_engine("complexion", profile, limit=2)
        if complexion_result.items:
            selections["complexion"] = [
                item.model_dump(mode="json") for item in complexion_result.items
            ]
        extra_codes = look_coordination.apply_cohesion(
            selections, bold_requested=bold_requested
        )
        notes = look_coordination.coordination_notes(selections)
    else:
        for category in categories:
            result = run_engine(category, profile, limit=3)
            selections[category] = [item.model_dump(mode="json") for item in result.items]

    for category, items in selections.items():
        for item in items:
            item.setdefault("reason_codes", [])
            item["reason_codes"] = item["reason_codes"] + extra_codes.get(category, [])
        label = _CATEGORY_LABELS.get(category, category)
        cards.extend(RecommendationCard(**item) for item in items[:3])

    validated = _validate_cards(cards)
    if intent is Intent.RECOMMEND_FULL_LOOK:
        message = prompts.full_look_message(selections, notes)
    else:
        first_category = next(iter(selections), "")
        message = prompts.recommendation_message(
            selections.get(first_category, []),
            _CATEGORY_LABELS.get(first_category, "product"),
        )
        if len(validated) == 0 and selections:
            message = (
                "I found some options but couldn't verify them against the "
                "live catalogue. Please try again shortly."
            )

    response = YafaChatResponse(
        conversation_id=conv.conversation_id,
        intent=intent.value,
        message=message,
        recommendations=validated,
    )
    conv.record_turn("yafa", response.message)
    return response


def _classify_intent(request: YafaChatRequest) -> Intent:
    explicit = (request.profile or {}).get("intent")
    if explicit:
        try:
            return Intent(str(explicit))
        except ValueError:
            pass
    return classify(request.message)


def handle_recommend(payload: dict[str, Any]) -> dict[str, list[RecommendationCard]]:
    """Direct engine invocation endpoint logic (no conversation state)."""
    parsed = RecommendRequest(**payload)
    profile_payload = parsed.profile
    cards: list[RecommendationCard] = []

    if parsed.coordinate_full_look and set(parsed.categories) >= {"cheeks", "lips"}:
        cheek = run_engine("cheeks", profile_payload, limit=1)
        hints = _cheek_hints(cheek)
        for category in parsed.categories:
            coordination = hints if category == "lips" else None
            result = run_engine(
                category, profile_payload,
                limit=parsed.limit_per_category, coordination=coordination,
            )
            cards.extend(_to_card(item) for item in result.items)
    else:
        for category in parsed.categories:
            result = run_engine(
                category, profile_payload, limit=parsed.limit_per_category
            )
            cards.extend(_to_card(item) for item in result.items)
    return {"recommendations": _validate_cards(cards)}


def _cheek_hints(cheek_result: Any) -> Any:
    from app.recommendation.canonical.schemas import CoordinationHints

    top = cheek_result.items[0] if cheek_result.items else None
    hints = CoordinationHints()
    if top and top.color_family:
        hints.lip_color_family = top.color_family
    return hints


__all__ = ["handle_chat", "handle_recommend"]
