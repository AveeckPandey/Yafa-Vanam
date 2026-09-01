"""RAG chat context helpers: product scoping and commerce boundaries."""
from __future__ import annotations

import re
from typing import Any

from app.yafa.schemas import PageContext

_LIVE_PATTERNS: dict[str, tuple[str, ...]] = {
    "inventory": ("in stock", "stock", "available", "availability", "sold out", "restock", "back in stock"),
    "price": ("price", "cost", "how much", "expensive", "discount", "sale", "offer", "coupon", "promo"),
    "order_status": ("my order", "order status", "where is my order", "track", "delivery date", "shipped"),
    "cart": ("my cart", "my bag", "checkout"),
    "reviews": ("review", "reviews", "stars"),
    "ratings": ("rating", "ratings"),
    "shipping": ("shipping", "deliver", "dispatch"),
}
_PRONOUN = re.compile(r"\b(this|that|it|this one|that one)\b", re.IGNORECASE)
FACT_TYPES: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {
    "expiry": (("expir", "expiry", "expiration", "pao", "shelf life", "best before", "use by"), ("expiry", "shelf_life", "storage")),
    "scent": (("smell like", "scent", "fragrance notes", "notes of", "smells"), ("scent_profile",)),
    "ingredients": (("ingredient", "inci", "contains", "made with"), ("ingredients", "ingredients_concept")),
    "usage": (("how do i use", "how should i use", "how to use", "how to apply", "application", "usage", "direction", "instruction"), ("usage",)),
    "warnings": (("warning", "allergic", "allergy", "irritat", "patch test", "side effect"), ("warnings",)),
    "benefits": (("benefit", "what does it do", "designed for", "good for"), ("benefits",)),
    "routine": (("where does this fit", "fit in my routine", "routine step", "when do i use"), ("routine_position",)),
}


def detect_fact_types(message: str) -> tuple[str, ...]:
    text = message.lower()
    return tuple(
        label
        for label, (patterns, _) in FACT_TYPES.items()
        if any(pattern in text for pattern in patterns)
    )


def detect_fact_type(message: str) -> str | None:
    """Return the first matching fact type for backwards compatibility."""
    labels = detect_fact_types(message)
    return labels[0] if labels else None


def fact_chunk_types(label: str) -> tuple[str, ...]:
    return FACT_TYPES.get(label, ((), ()))[1]


def detect_live_data_domain(message: str) -> str | None:
    text = message.lower()
    for domain, patterns in _LIVE_PATTERNS.items():
        if any(pattern in text for pattern in patterns):
            return domain
    return None


def resolve_page_product(page_context: PageContext | None) -> dict[str, Any] | None:
    """Scope RAG with the page id without loading the retired catalogue code."""
    if not page_context or not page_context.product_id:
        return None
    return {"id": page_context.product_id}


def message_refers_to_page_product(message: str) -> bool:
    return bool(_PRONOUN.search(message))
