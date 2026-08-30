"""Schemas for the private RAG-backed Yafa chat contract."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class PageContext(BaseModel):
    type: Literal["global", "product", "category", "cart", "account"] = "global"
    product_id: str | None = None
    variant_id: str | None = None
    shade_id: str | None = None


class AttachmentMeta(BaseModel):
    """Accepted for client compatibility; RAG never processes images."""

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
    # Existing callers still send these fields. They are deliberately ignored
    # after the recommendation and image-analysis engines were removed.
    profile: dict[str, Any] = Field(default_factory=dict)
    attachment: AttachmentMeta | None = None


class GroundingChunk(BaseModel):
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
    # Retained as an empty array to preserve the existing storefront contract.
    recommendations: list[dict[str, Any]] = Field(default_factory=list)
    requires: LiveRequirement | None = None
    grounding: list[GroundingChunk] = Field(default_factory=list)
    citation_required_topics: list[str] = Field(default_factory=list)
    medical_escalation_topics: list[str] = Field(default_factory=list)
