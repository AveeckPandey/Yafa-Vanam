"""Tool routing: intent -> deterministic tools (spec Phase 2 §29/§30).

Tools available to the orchestrator:
- ``rag_lookup``      grounded factual chunks from the RAG service (optional;
                      degrades to unavailable when no vector DB is configured)
- ``run_engines``     the six category engines behind one uniform contract
- ``shade_guidance``  points the customer at the existing selfie/shade flow

The router never calls an LLM and never invents product ids: every id in a
tool outcome comes from engine output or catalogue lookup.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from fastapi import HTTPException

from app.recommendation.canonical.normalization import to_canonical_profile
from app.recommendation.canonical.schemas import CoordinationHints, EngineResult
from app.recommendation.engines import get_engine
from app.rag.schemas import PageContext as RagPageContext
from app.rag.schemas import RagSearchRequest
from app.yafa.intents import Intent

logger = logging.getLogger(__name__)


@dataclass
class ToolOutcome:
    intent: Intent
    recommendations: list[dict[str, Any]] = field(default_factory=list)
    grounding: list[dict[str, Any]] = field(default_factory=list)
    answer_policy: dict[str, Any] | None = None
    citation_required_topics: list[str] = field(default_factory=list)
    medical_escalation_topics: list[str] = field(default_factory=list)
    followup_question: str | None = None
    rag_available: bool = False


async def rag_lookup(
    query: str,
    *,
    product_id: str | None = None,
    page_context: RagPageContext | None = None,
    top_k: int = 4,
) -> tuple[list[dict[str, Any]], dict[str, Any] | None, list[str], list[str], bool]:
    """Grounded retrieval; returns ([chunks], policy, citations, medical, available)."""
    try:
        from app.api.rag_search import _get_retriever

        request = RagSearchRequest(
            query=query,
            product_id=product_id,
            page_context=page_context,
            top_k=top_k,
            allowed_for_customer=True,
        )
        response = await _get_retriever().search(request)
    except (RuntimeError, HTTPException):
        # Not configured (RuntimeError) or 503 from the lazy singleton.
        return [], None, [], [], False
    except Exception:  # noqa: BLE001 - retrieval must never break the chat
        logger.exception("rag lookup failed")
        return [], None, [], [], False

    chunks = [
        {
            "product_id": chunk.product_id,
            "chunk_type": chunk.chunk_type,
            "content": chunk.content,
            "similarity": chunk.similarity,
            "trust_level": chunk.trust_level.value
            if hasattr(chunk.trust_level, "value")
            else str(chunk.trust_level),
            "requires_qualification": chunk.requires_qualification,
        }
        for chunk in response.results
    ]
    return (
        chunks,
        response.answer_policy,
        list(response.citation_required_topics),
        list(response.medical_escalation_topics),
        True,
    )


def run_engine(
    category: str,
    profile_payload: dict[str, Any],
    *,
    limit: int = 3,
    coordination: CoordinationHints | None = None,
) -> EngineResult:
    profile = to_canonical_profile(profile_payload)
    engine = get_engine(category)
    return engine(profile, limit=limit, coordination=coordination)


def shade_guidance_outcome() -> ToolOutcome:
    outcome = ToolOutcome(intent=Intent.SHADE_MATCH_REQUEST)
    outcome.followup_question = (
        "I can match your shade from a selfie. Open the shade finder and take "
        "a photo in soft natural light with no foundation on — then I'll use "
        "the result to build your look."
    )
    return outcome
