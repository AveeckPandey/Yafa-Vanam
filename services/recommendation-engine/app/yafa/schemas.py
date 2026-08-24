"""YAFA orchestrator: one assistant, different page/tool contexts (Phase 2 §27).

Schemas for the internal chat contract consumed by the Go backend. Responses
carry only machine-checkable content: recommendations come from the
deterministic engines, factual grounding comes from RAG retrieval, and no LLM
is connected in this phase — messages are composed from fixed templates.
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class PageContext(BaseModel):
    """Where the customer is when they talk to Yafa (spec Phase 2 §35)."""

    type: Literal["global", "product", "category", "cart", "account"] = "global"
    product_id: str | None = None
    variant_id: str | None = None
    shade_id: str | None = None


class AttachmentMeta(BaseModel):
    """Metadata for an image the customer attached to this message.

    Only derived attributes travel with the message - never raw image bytes.
    """

    model_config = {"extra": "forbid"}

    kind: Literal["outfit", "selfie", "reference"] = "reference"
    colours: list[str] = Field(default_factory=list)
    confidence: float | None = None
    runner_up_colour: str | None = None


class YafaChatRequest(BaseModel):
    model_config = {"extra": "forbid"}

    conversation_id: str | None = Field(default=None, max_length=128)
    user_id: str | None = Field(default=None, max_length=128)
    message: str = Field(min_length=1, max_length=1000)
    page_context: PageContext | None = None
    # Canonical-profile payload (same shape the engines already accept).
    profile: dict[str, Any] = Field(default_factory=dict)
    attachment: AttachmentMeta | None = None


class RecommendationCard(BaseModel):
    """One ranked candidate; ids are always catalogue-validated."""

    product_id: str
    variant_id: str | None = None
    category: str
    score: float
    reason_codes: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    product_name: str | None = None
    color_family: str | None = None
    shade_name: str | None = None
    shade_hex: str | None = None
    source_file: str | None = None
    # Commerce truth stays with Go; cards are rendered from live data there.
    commerce_validation_required: bool = True


class GroundingChunk(BaseModel):
    """Retrieved factual chunk (no embeddings, no internals)."""

    product_id: str
    chunk_type: str
    content: str
    similarity: float
    trust_level: str
    requires_qualification: bool


class LiveRequirement(BaseModel):
    domain: str
    product_id: str | None = None


class YafaChatResponse(BaseModel):
    conversation_id: str
    intent: str
    message: str
    recommendations: list[RecommendationCard] = Field(default_factory=list)
    # Non-null when the answer must come from the Go backend (spec §14/§37).
    requires: LiveRequirement | None = None
    grounding: list[GroundingChunk] = Field(default_factory=list)
    # Structured policy metadata preserved from RAG answer policies.
    citation_required_topics: list[str] = Field(default_factory=list)
    medical_escalation_topics: list[str] = Field(default_factory=list)


class RecommendRequest(BaseModel):
    """Direct engine invocation (no conversation state required)."""

    model_config = {"extra": "forbid"}

    categories: list[str] = Field(min_length=1, max_length=6)
    profile: dict[str, Any] = Field(default_factory=dict)
    limit_per_category: int = Field(default=3, ge=1, le=10)
    coordinate_full_look: bool = False
