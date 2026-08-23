"""Query-intent filters that keep static catalogue data out of live-commerce answers.

Product.json deliberately carries no authoritative inventory/price/review data
(see each record's live_data_contract). When a question is about a live domain,
the retriever flags `requires_live_data` so the Yafa orchestrator can fetch the
truth from the Go commerce backend instead of letting RAG answer from JSON.
"""

from __future__ import annotations

import re

from app.rag.models import LiveDataDomain

# Keyword patterns per live domain. Matched against the lowercased query.
_DOMAIN_PATTERNS: tuple[tuple[LiveDataDomain, tuple[str, ...]], ...] = (
    (LiveDataDomain.INVENTORY, ("in stock", "stock", "restock", "sold out", "back in store")),
    (LiveDataDomain.AVAILABILITY, ("available", "availability", "still be bought", "where can i buy")),
    (LiveDataDomain.PRICE, ("price", "cost", "how much", "mrp", "expensive")),
    (LiveDataDomain.DISCOUNTS, ("discount", "sale on", "offer", "coupon", "promo code", "cheaper")),
    (LiveDataDomain.REVIEWS, ("review", "reviews", "what do people say", "feedback on")),
    (LiveDataDomain.RATINGS, ("rating", "rated", "stars")),
    (LiveDataDomain.CART, ("cart", "checkout")),
    (LiveDataDomain.ORDER_STATUS, ("my order", "order status", "tracking", "shipped", "delivered")),
    (LiveDataDomain.SHIPPING, ("shipping", "delivery time", "when will it arrive", "dispatch")),
)

# Tokens with no standalone meaning, used to judge whether anything substantive
# remains after the live-domain phrases are removed.
_STOPWORDS = frozenset(
    """a an and any are do does is it its me my of on in into the this that what which who
    when where why how you your i we they there here have has had will would can could should
    tell know get got go going want need to for from with about if at as be been by""".split()
)

# Product-knowledge intent markers. If one survives alongside a live-domain
# phrase, the question is mixed and RAG should still retrieve knowledge.
_KNOWLEDGE_KEYWORDS = frozenset(
    """smell scent aroma notes ingredient ingredients formula inci routine step apply
    usage use warning warnings safe safety shade shades colour color undertone benefit
    benefits designed positioned finish coverage texture skin layer evidence research
    verified unverified vegan cruelty pregnancy retinoid spf""".split()
)

_TOKEN = re.compile(r"[a-z0-9]+")
# Longest phrases first so "in stock" wins over "stock".
_ALL_PHRASES: tuple[tuple[str, LiveDataDomain], ...] = tuple(
    sorted(
        ((phrase, domain) for domain, phrases in _DOMAIN_PATTERNS for phrase in phrases),
        key=lambda item: len(item[0]),
        reverse=True,
    )
)


def detect_live_data_domains(query: str) -> list[LiveDataDomain]:
    """Which live-commerce domains does this query touch? Deterministic order."""
    lowered = " " + re.sub(r"[^a-z0-9\s]", " ", query.lower()) + " "
    found: list[LiveDataDomain] = []
    remaining = lowered
    for phrase, domain in _ALL_PHRASES:
        if phrase in remaining:
            if domain not in found:
                found.append(domain)
            remaining = remaining.replace(phrase, " ")
    return found


def is_pure_live_data_query(query: str) -> bool:
    """True when the question is only about live commerce domains.

    Pure questions ("Is this in stock?", "How much does Soft Ember cost?")
    must be answered solely by the Go commerce backend, so retrieval results
    are suppressed. Mixed questions ("What does it smell like and how much is
    it?") still retrieve knowledge. Questions with no live-domain signal are
    never classified as live, however short they are.
    """
    if not detect_live_data_domains(query):
        return False
    lowered = " " + re.sub(r"[^a-z0-9\s]", " ", query.lower()) + " "
    remaining = lowered
    for phrase, _ in _ALL_PHRASES:
        remaining = remaining.replace(phrase, " ")
    content_tokens = [t for t in _TOKEN.findall(remaining) if t not in _STOPWORDS]
    return not any(token in _KNOWLEDGE_KEYWORDS or token.rstrip("s") in _KNOWLEDGE_KEYWORDS for token in content_tokens)
