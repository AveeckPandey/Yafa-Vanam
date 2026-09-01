"""Minimal, auditable routing for a RAG-only product chat."""
from __future__ import annotations

import re
from enum import Enum


class Intent(str, Enum):
    GREETING_OR_SMALL_TALK = "greeting_or_small_talk"
    PRODUCT_INFORMATION = "product_information"
    PRODUCT_PAGE_QUESTION = "product_page_question"
    PRODUCT_COMPARISON = "product_comparison"
    COMMERCE_QUESTION = "commerce_question"
    RECOMMENDATION_UNAVAILABLE = "recommendation_unavailable"
    GENERAL = "general"


_GREETING = re.compile(r"(^|\s)(hi|hiya|hey|hello|yo|good\s(morning|afternoon|evening)|how\sare\syou|thanks|thank\syou|thankyou|bye|goodbye)(\s|[!.?,]|$)", re.IGNORECASE)
_CAPABILITY = re.compile(r"\b(what can you do|who are you|what are you|help me|can you help|how (does|do) (this|you) work|what do you do)\b", re.IGNORECASE)
_RECOMMENDATION = re.compile(r"\b(recommend|suggest|(?<!how )should i (get|buy|try|wear|use)|looking for|need a|want a|full look|complete look|build (my |a )?look|match my makeup|find my shade)\b", re.IGNORECASE)
_PRODUCT_FACT = re.compile(
    r"\b("
    r"ingredients?|inci|contains?|"
    r"how (do|should|to) (i )?use|how is .+ used|uses?|usage|directions?|instructions?|apply|application|"
    r"warnings?|allerg(?:y|ies|en(?:s|ic)?)|benefits?|features?|claims?|designed for|suitable for|what does .+ do|"
    r"scent|smell|fragrance notes?|expiry|expiration|shelf life|"
    r"cruelty[- ]?free|vegan|animal test|charit|donat|giving policy|"
    r"product (details?|facts?|information)|tell me about|compare|versus| vs "
    r")\b",
    re.IGNORECASE,
)


def classify(message: str) -> Intent:
    text = f" {message.strip().lower()} "
    if _GREETING.search(text):
        return Intent.GREETING_OR_SMALL_TALK
    if _CAPABILITY.search(text):
        return Intent.GENERAL
    if _RECOMMENDATION.search(text):
        return Intent.RECOMMENDATION_UNAVAILABLE
    if " vs " in text or "versus" in text or "compare" in text:
        return Intent.PRODUCT_COMPARISON
    if _PRODUCT_FACT.search(text):
        return Intent.PRODUCT_INFORMATION
    return Intent.GENERAL
