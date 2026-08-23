"""Core RAG domain types: trust levels, chunk types and live-data domains."""

from __future__ import annotations

from enum import Enum


class TrustLevel(str, Enum):
    """Provenance classification for every ingested fact.

    Levels are NOT interchangeable: only some may back customer-facing factual
    statements. See source_policy.can_surface_as_customer_fact.
    """

    VERIFIED = "VERIFIED"
    AUTHORITATIVE_CATALOGUE = "AUTHORITATIVE_CATALOGUE"
    RESEARCHED_QUALIFIED = "RESEARCHED_QUALIFIED"
    BRAND_CONFIRMED = "BRAND_CONFIRMED"
    INFERRED_AESTHETIC = "INFERRED_AESTHETIC"
    VISUAL_ESTIMATE = "VISUAL_ESTIMATE"
    LEGACY_CONCEPT = "LEGACY_CONCEPT"
    MOCK_DEVELOPMENT = "MOCK_DEVELOPMENT"
    PENDING_VERIFICATION = "PENDING_VERIFICATION"


class ChunkType(str, Enum):
    """Semantic section types produced by the chunker."""

    PRODUCT_OVERVIEW = "product_overview"
    BENEFITS = "benefits"
    USAGE = "usage"
    WARNINGS = "warnings"
    INGREDIENTS = "ingredients"  # verified/label INCI only; concept-stage data uses ingredients_concept
    INGREDIENTS_CONCEPT = "ingredients_concept"
    EVIDENCE = "evidence"
    FAQ = "faq"
    SHADE_INFORMATION = "shade_information"
    SCENT_PROFILE = "scent_profile"
    COMPATIBILITY = "compatibility"
    ROUTINE_POSITION = "routine_position"


class LiveDataDomain(str, Enum):
    """Commerce truths that must come from the Go backend, never from JSON."""

    INVENTORY = "inventory"
    PRICE = "price"
    CART = "cart"
    ORDER_STATUS = "order_status"
    REVIEWS = "reviews"
    RATINGS = "ratings"
    DISCOUNTS = "discounts"
    AVAILABILITY = "availability"
    SHIPPING = "shipping"


# Chunk types whose text is safe to embed for customer factual retrieval.
EMBEDDABLE_CHUNK_TYPES = frozenset(chunk.value for chunk in ChunkType)
