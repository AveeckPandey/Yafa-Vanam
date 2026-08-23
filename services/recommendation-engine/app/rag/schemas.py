"""Pydantic schemas for the internal RAG search endpoint."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.rag.models import LiveDataDomain, TrustLevel


class PageContext(BaseModel):
    type: str = "global"  # "product" when opened from a PDP
    product_id: str | None = None


class RagSearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=1000)
    product_id: str | None = None
    page_context: PageContext | None = None
    top_k: int = Field(default=5, ge=1, le=25)
    allowed_for_customer: bool = True
    # Explicit retrieval filters (update spec §14).
    chunk_types: list[str] | None = None
    trust_levels: list[TrustLevel] | None = None


class RetrievedChunk(BaseModel):
    chunk_id: str
    product_id: str
    product_name: str
    chunk_type: str
    content: str
    similarity: float
    trust_level: TrustLevel
    customer_factual_eligible: bool
    requires_qualification: bool
    metadata: dict[str, Any] = Field(default_factory=dict)


class LiveRequirement(BaseModel):
    domain: LiveDataDomain
    reason: str


class RagSearchResponse(BaseModel):
    query: str
    product_id: str | None = None
    resolved_product_id: str | None = None
    resolution: str = "none"  # none | exact_alias | normalized_alias | page_context
    results: list[RetrievedChunk] = Field(default_factory=list)
    requires_live_data: list[LiveRequirement] = Field(default_factory=list)
    answer_policy: dict[str, Any] | None = None
    citation_required_topics: list[str] = Field(default_factory=list)
    medical_escalation_topics: list[str] = Field(default_factory=list)


class RagHealthResponse(BaseModel):
    """Infrastructure diagnostic. Flags only — never credentials or raw errors."""

    status: str  # ok | degraded | error | unconfigured
    database_connected: bool
    pgvector_enabled: bool
    embedding_provider: str
    embedding_model: str | None = None
    embedding_dimension: int | None = None
    stored_dimension: int | None = None
    embedding_space_consistent: bool | None = None
