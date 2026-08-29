"""Deterministic intent classification (spec Phase 2 section 28 + chat UX fixes).

Keyword-rule based on purpose: the orchestrator must be testable and must
never depend on an LLM to decide which tool runs. An explicit ``intent``
override in the request always wins over classification.

Routing contract:
- greetings NEVER reach RAG
- commerce questions NEVER reach RAG or the engines
- outfit matching reaches the colour engines, never product-fact retrieval
"""
from __future__ import annotations

import re
from enum import Enum


class Intent(str, Enum):
    GREETING_OR_SMALL_TALK = "greeting_or_small_talk"
    BRAND_VALUES_POLICY = "brand_values_policy"

    PRODUCT_INFORMATION = "product_information"
    PRODUCT_PAGE_QUESTION = "product_page_question"  # info scoped to current page product
    PRODUCT_COMPARISON = "product_comparison"

    RECOMMEND_PRODUCT = "recommend_product"
    RECOMMEND_FULL_LOOK = "recommend_full_look"
    OUTFIT_MATCHING = "outfit_matching"

    SKINCARE_RECOMMENDATION = "skincare_recommendation"
    FRAGRANCE_RECOMMENDATION = "fragrance_recommendation"
    LIP_RECOMMENDATION = "lip_recommendation"
    CHEEK_RECOMMENDATION = "cheek_recommendation"
    EYE_RECOMMENDATION = "eye_recommendation"
    COMPLEXION_RECOMMENDATION = "complexion_recommendation"

    SHADE_MATCH_REQUEST = "shade_match_request"
    IMAGE_ASSISTED_QUERY = "image_assisted_query"

    ROUTINE_BUILD = "routine_build"
    INGREDIENT_QUESTION = "ingredient_question"
    COMPATIBILITY_QUESTION = "compatibility_question"

    COMMERCE_QUESTION = "commerce_question"
    ADVISOR_START = "advisor_start"
    UNSUPPORTED_OR_UNCLEAR = "unsupported_or_unclear"
    GENERAL = "general"


CATEGORY_INTENTS: dict[str, Intent] = {
    "skincare": Intent.SKINCARE_RECOMMENDATION,
    "moisturizer": Intent.SKINCARE_RECOMMENDATION,
    "moisturiser": Intent.SKINCARE_RECOMMENDATION,
    "cleanser": Intent.SKINCARE_RECOMMENDATION,
    "serum": Intent.SKINCARE_RECOMMENDATION,
    "sunscreen": Intent.SKINCARE_RECOMMENDATION,
    "fragrance": Intent.FRAGRANCE_RECOMMENDATION,
    "perfume": Intent.FRAGRANCE_RECOMMENDATION,
    "lips": Intent.LIP_RECOMMENDATION,
    "lip": Intent.LIP_RECOMMENDATION,
    "lipstick": Intent.LIP_RECOMMENDATION,
    "cheeks": Intent.CHEEK_RECOMMENDATION,
    "cheek": Intent.CHEEK_RECOMMENDATION,
    "blush": Intent.CHEEK_RECOMMENDATION,
    "eyes": Intent.EYE_RECOMMENDATION,
    "eye": Intent.EYE_RECOMMENDATION,
    "mascara": Intent.EYE_RECOMMENDATION,
    "eyeliner": Intent.EYE_RECOMMENDATION,
    "eyeshadow": Intent.EYE_RECOMMENDATION,
    "brow": Intent.EYE_RECOMMENDATION,
    "brows": Intent.EYE_RECOMMENDATION,
    "complexion": Intent.COMPLEXION_RECOMMENDATION,
    "foundation": Intent.COMPLEXION_RECOMMENDATION,
}

# Word-boundary greetings: "hi" must never substring-match inside other words.
_GREETING = re.compile(
    r"(^|\s)(hi|hiya|hey|hello|yo|good\s(morning|afternoon|evening)|"
    r"how\sare\syou|thanks|thank\syou|thankyou|bye|goodbye)(\s|[!.?,]|$)",
    re.IGNORECASE,
)

_BRAND_VALUES = re.compile(
    r"\b(cruelty[- ]?free|animal test(?:ing|ed)?|tested on animals|vegan|"
    r"animal[- ]derived|charit(?:y|able)|donat(?:e|es|ed|ing|ion|ions)|"
    r"give back|giving policy|non[- ]?profit|one percent|1%)\b",
    re.IGNORECASE,
)

_CAPABILITY = re.compile(
    r"\b(what can you do|who are you|what are you|help me|can you help|"
    r"(makeup|beauty|skincare) help\b|how (does|do) (this|you) work|what do you do)\b",
    re.IGNORECASE,
)

_IMAGE_REFERENCE = re.compile(
    r"\b(photo|picture|pic|image|uploaded|selfie|swatch)\b",
    re.IGNORECASE,
)

_OUTFIT_MATCH = re.compile(
    r"\b(match|matching|goes with|go with|suit|pair with|coordinate)\b[^\n]{0,40}"
    r"\b(outfit|dress|saree|lehenga|look|clothes|colours?|colors?)\b"
    # "...to this / that / the photo" - anaphoric outfit references.
    r"|\b(match(ing)?|go with|pair with|suit)\b[^\n]{0,25}"
    r"\b(this|that|it|the photo|the image|the picture)\b"
    r"|\bmy (outfit|dress|saree|lehenga)\b",
    re.IGNORECASE,
)

_WEARING = re.compile(r"\b(i am|i'm|im|am|wearing|dressed in)\s+[a-z]", re.IGNORECASE)

# Ordered first-match-wins rules. Specific intents before generic ones.
_RULES: list[tuple[Intent, tuple[str, ...]]] = [
    (
        Intent.SHADE_MATCH_REQUEST,
        ("shade match", "match my shade", "find my shade", "my foundation shade",
         "my shade", "what shade", "which shade", "shade for my skin",
         "which foundation shade"),
    ),
    (
        Intent.ROUTINE_BUILD,
        ("build a routine", "build my routine", "skincare routine", "my routine",
         "routine for", "step order", "what order"),
    ),
    (
        Intent.PRODUCT_COMPARISON,
        (" vs ", "versus", "difference between", "compare", "or should i"),
    ),
    (
        Intent.RECOMMEND_FULL_LOOK,
        ("full look", "complete look", "whole look", "entire look", "build my look",
         "build the look", "build a look", "look for my", "makeup look",
         "everything together"),
    ),
    (
        Intent.INGREDIENT_QUESTION,
        ("ingredient", "ingredients", "inci", "niacinamide", "salicylic",
         "hyaluronic", "retinol", "vitamin c", "spf filter", "fragrance allergen"),
    ),
    (
        Intent.COMPATIBILITY_QUESTION,
        ("can i use", "can i mix", "work together", "compatible with",
         "layer with", "combine with", "safe with", "along with"),
    ),
    (
        Intent.PRODUCT_INFORMATION,
        ("what does", "how do i use", "how to use", "where does this fit",
         "fit in my routine", "smell like", "scent", "scent profile",
         "what is this", "what are the", "warnings", "tell me about", "designed for",
         "expiry", "expire", "expiration", "shelf life", "best before"),
    ),
]

_RECOMMEND_VERB = re.compile(
    r"\b(recommend|suggest|should i (get|buy|try|wear|use)|looking for|"
    r"need a|want a|which .+ (should|would)|any ideas for|help me (pick|choose|find))\b"
)


def classify(message: str) -> Intent:
    """Classify a customer message; falls back to GENERAL."""
    text = f" {message.strip().lower()} "

    # 1. Greetings/small talk always win: they must never trigger RAG.
    if _GREETING.search(text):
        return Intent.GREETING_OR_SMALL_TALK

    # 2. Capability questions get the orientation answer, not tools.
    if _CAPABILITY.search(text):
        return Intent.ADVISOR_START

    # Brand values are non-product knowledge and must never fail because a
    # catalogue product could not be resolved.
    if _BRAND_VALUES.search(text):
        return Intent.BRAND_VALUES_POLICY

    # 3. Explicit whole-look requests outrank outfit matching phrasing.
    if re.search(
        r"\b(full look|complete look|whole look|entire look|build my look|"
        r"build the look|build a look)\b",
        text,
    ):
        return Intent.RECOMMEND_FULL_LOOK

    # 4. Outfit matching before generic recommendation/product rules.
    if _OUTFIT_MATCH.search(text):
        return Intent.OUTFIT_MATCHING

    # 5. Explicitly wearing something ("I'm wearing navy blue and beige")
    #    is styling context even without the word "match".
    if _WEARING.search(text) and any(
        token in text for token in ("makeup", "look", "match", "wear to", "go with")
    ):
        return Intent.OUTFIT_MATCHING
    if _WEARING.search(text) and any(
        _colour_like(token) for token in text.split()
    ):
        return Intent.OUTFIT_MATCHING

    # 6. Image-referencing queries without another explicit goal.
    if _IMAGE_REFERENCE.search(text):
        return Intent.IMAGE_ASSISTED_QUERY

    for intent, patterns in _RULES:
        if any(pattern in text for pattern in patterns):
            return intent

    if _RECOMMEND_VERB.search(text):
        for token, category_intent in CATEGORY_INTENTS.items():
            if re.search(rf"\b{re.escape(token)}\b", text):
                return category_intent
        return Intent.RECOMMEND_PRODUCT

    for token, category_intent in CATEGORY_INTENTS.items():
        if re.search(rf"\b{token}s?\b", text) and any(
            word in text for word in ("best", "good", "which", "what", "my")
        ):
            return category_intent

    return Intent.GENERAL


_COLOUR_TOKENS = {
    "emerald", "green", "gold", "red", "burgundy", "maroon", "blue", "navy",
    "purple", "pink", "orange", "peach", "terracotta", "black", "white",
    "brown", "beige", "cream", "grey", "gray", "silver", "olive", "yellow",
}


def _colour_like(token: str) -> bool:
    cleaned = token.strip(".,!?;:()'\"")
    return cleaned.lower() in _COLOUR_TOKENS


def categories_for_intent(intent: Intent, message: str) -> list[str]:
    """Engine categories an intent needs, in orchestration order."""
    mapping: dict[Intent, list[str]] = {
        Intent.SKINCARE_RECOMMENDATION: ["skincare"],
        Intent.FRAGRANCE_RECOMMENDATION: ["fragrance"],
        Intent.LIP_RECOMMENDATION: ["lips"],
        Intent.CHEEK_RECOMMENDATION: ["cheeks"],
        Intent.EYE_RECOMMENDATION: ["eyes"],
        Intent.COMPLEXION_RECOMMENDATION: ["complexion"],
        Intent.ROUTINE_BUILD: ["skincare"],
        Intent.RECOMMEND_FULL_LOOK: ["complexion", "eyes", "cheeks", "lips"],
        # Outfit/image styling coordinates the face categories; fragrance is
        # deliberately excluded unless explicitly requested elsewhere.
        Intent.OUTFIT_MATCHING: ["complexion", "eyes", "cheeks", "lips"],
        Intent.IMAGE_ASSISTED_QUERY: ["complexion", "eyes", "cheeks", "lips"],
    }
    if intent is Intent.RECOMMEND_PRODUCT:
        text = message.lower()
        found = [
            token for token in ("skincare", "fragrance", "lips", "cheeks", "eyes", "complexion")
            if token in text
        ]
        return found[:1] or ["lips"]
    return mapping.get(intent, [])
