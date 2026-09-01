"""RAG-only Yafa chat orchestration with explicit commerce boundaries."""
from __future__ import annotations

import logging
from typing import Any
from uuid import uuid4

from fastapi import HTTPException

from app.api.rag_search import _get_retriever
from app.rag.config import RagSettings
from app.rag.schemas import RagSearchRequest
from app.yafa.agent import ToolSearchResult, get_agentic_responder
from app.yafa import prompts
from app.yafa.context import (
    detect_fact_types,
    detect_live_data_domain,
    fact_chunk_types,
    message_refers_to_page_product,
    resolve_page_product,
)
from app.yafa.conversation import conversation_store
from app.yafa.intents import Intent, classify
from app.yafa.schemas import GroundingChunk, LiveRequirement, YafaChatRequest, YafaChatResponse

logger = logging.getLogger(__name__)


async def _rag_lookup(
    query: str,
    product_id: str | None,
    fact_labels: tuple[str, ...],
    request_id: str,
) -> tuple[list[dict[str, Any]], list[str], list[str], bool]:
    """Retrieve eligible facts only; a RAG failure must not break the chat."""
    try:
        response = await _get_retriever().search(
            RagSearchRequest(
                query=query,
                request_id=request_id,
                product_id=product_id,
                top_k=5,
                allowed_for_customer=True,
                chunk_types=sorted(
                    {
                        chunk_type
                        for label in fact_labels
                        for chunk_type in fact_chunk_types(label)
                    }
                ) or None,
            )
        )
    except (RuntimeError, HTTPException):
        return [], [], [], False
    except Exception:  # noqa: BLE001 - no RAG internals reach the customer
        logger.exception("rag lookup failed")
        return [], [], [], False
    chunks = [
        {
            "chunk_id": chunk.chunk_id,
            "product_id": chunk.product_id,
            "chunk_type": chunk.chunk_type,
            "content": chunk.content,
            "similarity": chunk.similarity,
            "trust_level": chunk.trust_level.value if hasattr(chunk.trust_level, "value") else str(chunk.trust_level),
            "requires_qualification": chunk.requires_qualification,
        }
        for chunk in response.results
    ]
    return chunks, list(response.citation_required_topics), list(response.medical_escalation_topics), True


async def _agentic_answer(
    *,
    message: str,
    page_product_id: str | None,
    fact_labels: tuple[str, ...],
    request_id: str,
):
    """Ask Bedrock to use the verified-search tool, never raw data access."""
    settings = RagSettings.from_env()
    if not settings.agentic_enabled:
        return None

    allowed_chunk_types = {
        chunk_type
        for label in fact_labels
        for chunk_type in fact_chunk_types(label)
    }

    async def search(query: str, locked_product_id: str | None) -> ToolSearchResult:
        chunks, citations, medical, available = await _rag_lookup(query, locked_product_id, fact_labels, request_id)
        if allowed_chunk_types:
            chunks = [chunk for chunk in chunks if chunk["chunk_type"] in allowed_chunk_types]
        # The model receives only high-confidence semantic matches. A zero
        # score is an explicit verified keyword fallback from the retriever.
        chunks = [
            chunk
            for chunk in chunks
            if chunk["similarity"] == 0.0
            or chunk["similarity"] >= settings.min_grounding_similarity
        ]
        return ToolSearchResult(
            chunks=chunks,
            citation_required_topics=citations,
            medical_escalation_topics=medical,
            available=available,
        )

    try:
        return await get_agentic_responder(settings).answer(
            message=message,
            page_product_id=page_product_id,
            search=search,
            request_id=request_id,
        )
    except Exception:  # no model/provider details should reach customers
        logger.exception("agentic RAG failed; using deterministic evidence fallback")
        return None


async def handle_chat(request: YafaChatRequest) -> YafaChatResponse:
    request_id = uuid4().hex
    conversation = conversation_store().get_or_create(
        request.conversation_id, user_id=request.user_id, page_context=request.page_context
    )
    intent = classify(request.message)
    page_product = resolve_page_product(conversation.page_context)

    if intent is Intent.GREETING_OR_SMALL_TALK:
        response = YafaChatResponse(conversation_id=conversation.conversation_id, intent=intent.value, message=prompts.greeting_message())
    elif domain := detect_live_data_domain(request.message):
        response = YafaChatResponse(
            conversation_id=conversation.conversation_id,
            intent=Intent.COMMERCE_QUESTION.value,
            message=prompts.live_data_message(domain),
            requires=LiveRequirement(domain=domain, product_id=(page_product or {}).get("id")),
        )
    elif intent is Intent.RECOMMENDATION_UNAVAILABLE:
        response = YafaChatResponse(conversation_id=conversation.conversation_id, intent=intent.value, message=prompts.recommendation_unavailable_message())
    else:
        if intent is Intent.GENERAL and page_product and message_refers_to_page_product(request.message):
            intent = Intent.PRODUCT_PAGE_QUESTION
        if intent is Intent.GENERAL:
            response = YafaChatResponse(conversation_id=conversation.conversation_id, intent=intent.value, message=prompts.general_message())
        else:
            fact_labels = detect_fact_types(request.message)
            agent_answer = await _agentic_answer(
                message=request.message,
                page_product_id=(page_product or {}).get("id"),
                fact_labels=fact_labels,
                request_id=request_id,
            )
            if agent_answer is not None:
                response = YafaChatResponse(
                    conversation_id=conversation.conversation_id,
                    request_id=request_id,
                    intent=intent.value,
                    message=agent_answer.message,
                    grounding=[GroundingChunk(**chunk) for chunk in agent_answer.chunks[:4]],
                    citation_required_topics=agent_answer.citation_required_topics,
                    medical_escalation_topics=agent_answer.medical_escalation_topics,
                )
                conversation.record_turn("user", request.message)
                conversation.record_turn("yafa", response.message)
                return response

            chunks, citations, medical, available = await _rag_lookup(
                request.message, (page_product or {}).get("id"), fact_labels, request_id
            )
            allowed_chunk_types = {
                chunk_type
                for label in fact_labels
                for chunk_type in fact_chunk_types(label)
            }
            if allowed_chunk_types:
                chunks = [chunk for chunk in chunks if chunk["chunk_type"] in allowed_chunk_types]
            if not available:
                message = prompts.product_information_message([], rag_available=False)
            elif fact_labels and not chunks:
                message = prompts.unavailable_fact_message(" and ".join(fact_labels))
            elif (
                "scent" in fact_labels
                and not page_product
                and len({chunk["product_id"] for chunk in chunks}) > 1
            ):
                message = prompts.scent_catalogue_message()
            else:
                message = prompts.product_information_message(chunks, rag_available=available)
            response = YafaChatResponse(
                conversation_id=conversation.conversation_id,
                request_id=request_id,
                intent=intent.value,
                message=message,
                grounding=[GroundingChunk(**chunk) for chunk in chunks[:4]],
                citation_required_topics=citations,
                medical_escalation_topics=medical,
            )

    response.request_id = request_id
    conversation.record_turn("user", request.message)
    conversation.record_turn("yafa", response.message)
    return response
