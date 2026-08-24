"""Page/conversation context helpers: product scoping + live-data routing.

Two contexts stay separate (spec Phase 2 §38):
- page context  -> which catalogue product "this" refers to right now
- conversation  -> accumulated slots (occasion, outfit, style...) that persist
                   while the customer navigates.

Live commerce domains (spec §14/Phase 2 §39) are detected here so the
orchestrator can short-circuit with ``requires`` instead of answering from
static JSON.
"""
from __future__ import annotations

import re
from typing import Any

from app.advisor.catalogue import product_by_id, product_by_slug
from app.yafa.schemas import PageContext

# Commerce truths owned by the Go backend — never answerable from datasets.
_LIVE_PATTERNS: dict[str, tuple[str, ...]] = {
    "inventory": ("in stock", "stock", "available", "availability", "sold out",
                  "restock", "back in stock"),
    "price": ("price", "cost", "how much", "expensive", "discount", "sale",
              "offer", "coupon", "promo"),
    "order_status": ("my order", "order status", "where is my order",
                     "track", "delivery date", "shipped"),
    "cart": ("my cart", "my bag", "checkout"),
    "reviews": ("review", "reviews", "stars"),
    "ratings": ("rating", "ratings"),
    "shipping": ("shipping", "deliver", "dispatch"),
}

_PRONOUN = re.compile(r"\b(this|that|it|this one|that one)\b", re.IGNORECASE)

# Specific product facts a customer may ask for, mapped to the RAG chunk
# types that could legitimately answer them. When none of those chunk types
# exist for the product, Yafa must say the fact is unavailable instead of
# returning unrelated warnings/evidence text (hallucination guard).
FACT_TYPES: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {
    # label -> (message patterns, chunk types that could answer)
    "expiry": (
        ("expir", "expiry", "expiration", "pao", "shelf life", "best before", "use by"),
        ("expiry", "shelf_life", "storage"),
    ),
    "scent": (
        ("smell like", "scent", "fragrance notes", "notes of", "smells"),
        ("scent_profile",),
    ),
    "ingredients": (
        ("ingredient", "inci", "contains", "made with"),
        ("ingredients",),
    ),
    "usage": (
        ("how do i use", "how to use", "how to apply", "application"),
        ("usage",),
    ),
    "warnings": (
        ("warning", "allergic", "allergy", "irritat", "patch test", "side effect"),
        ("warnings",),
    ),
    "benefits": (
        ("benefit", "what does it do", "designed for", "good for"),
        ("benefits",),
    ),
    "routine": (
        ("where does this fit", "fit in my routine", "routine step", "when do i use"),
        ("routine_position",),
    ),
}

_FACT_LABELS = {
    "expiry": "expiry / shelf-life",
    "scent": "scent",
    "ingredients": "full ingredient",
    "usage": "usage",
    "warnings": "safety",
    "benefits": "benefit",
    "routine": "routine-position",
}


def detect_fact_type(message: str) -> str | None:
    """Return the specific product-fact label when the question asks for one."""
    text = message.lower()
    for label, (patterns, _types) in FACT_TYPES.items():
        if any(pattern in text for pattern in patterns):
            return label
    return None


def fact_chunk_types(label: str) -> tuple[str, ...]:
    return FACT_TYPES.get(label, (( ), ()))[1]


def fact_label_human(label: str) -> str:
    return _FACT_LABELS.get(label, label)


def detect_live_data_domain(message: str) -> str | None:
    """Return the Go-owned domain when the question is about live truth."""
    text = message.lower()
    for domain, patterns in _LIVE_PATTERNS.items():
        if any(pattern in text for pattern in patterns):
            return domain
    return None


def resolve_page_product(page_context: PageContext | None) -> dict[str, Any] | None:
    """Validate the page-context product against the canonical catalogue."""
    if not page_context or not page_context.product_id:
        return None
    product = product_by_id(page_context.product_id) or product_by_slug(
        page_context.product_id
    )
    return product


def message_refers_to_page_product(message: str) -> bool:
    """True when "this"/"it" should bind to the current page product."""
    return bool(_PRONOUN.search(message))


def extract_slots(message: str, vocabulary: dict[str, list[str]]) -> dict[str, Any]:
    """Pull confident profile slots out of free text.

    Only vocabulary-backed tokens are extracted; nothing is invented.
    ``vocabulary`` maps slot name -> accepted tokens (lowercase).
    """
    text = f" {message.strip().lower()} "
    slots: dict[str, Any] = {}

    occasion_tokens: dict[str, str] = {
        "wedding": "wedding", "bridal": "bridal", "brunch": "brunch",
        "office": "office", "work": "work", "date": "date_night",
        "party": "party", "everyday": "everyday", "daily": "daily",
    }
    for token, value in occasion_tokens.items():
        if re.search(rf"\b{token}\b", text):
            slots["occasion"] = value
            break

    daypart_tokens: dict[str, str] = {
        "morning": "day", "daytime": "day", "afternoon": "day",
        "evening": "evening", "night": "evening",
    }
    for token, value in daypart_tokens.items():
        if re.search(rf"\b{token}\b", text):
            slots["daypart"] = value
            break

    style_tokens: dict[str, str] = {
        "natural": "natural", "soft glam": "soft_glam", "soft-glam": "soft_glam",
        "bold": "bold", "glam": "glam", "editorial": "editorial",
        "minimal": "minimalist", "no makeup": "no_makeup_look",
    }
    for token, value in style_tokens.items():
        if token in text:
            slots["look_style"] = value
            break

    outfit_colours: list[str] = []
    for colour in vocabulary.get("outfit_colours", []):
        if re.search(rf"\b{re.escape(colour)}\b", text):
            outfit_colours.append(colour)
    if outfit_colours:
        slots["outfit_primary_colour"] = outfit_colours[0]
        if len(outfit_colours) > 1:
            slots["outfit_secondary_colours"] = outfit_colours[1:]

    return slots


def merge_slots_into_profile(profile: dict[str, Any], slots: dict[str, Any]) -> dict[str, Any]:
    """Fold conversation slots into an engine payload (request wins).

    Engines read the canonical payload shape produced by v1/to_canonical_profile;
    slots are written into the same keys the frontend already sends.
    """
    merged: dict[str, Any] = {
        "skin": dict(profile.get("skin") or {}),
        "context": dict(profile.get("context") or {}),
        "makeup_preferences": dict(profile.get("makeup_preferences") or {}),
        "fragrance_preferences": dict(profile.get("fragrance_preferences") or {}),
    }
    for key, value in profile.items():
        merged.setdefault(key, value)

    context = merged["context"]
    if "occasion" in slots and not context.get("occasion"):
        context["occasion"] = slots["occasion"]
    if "daypart" in slots:
        context.setdefault("daypart", slots["daypart"])
    if "outfit_primary_colour" in slots and not context.get("outfit"):
        outfit: dict[str, Any] = {"primary_colour": slots["outfit_primary_colour"]}
        if "outfit_secondary_colours" in slots:
            outfit["secondary_colours"] = slots["outfit_secondary_colours"]
        context["outfit"] = outfit
    if "look_style" in slots:
        prefs = merged["makeup_preferences"]
        prefs.setdefault("intensity", slots["look_style"])
    return merged
