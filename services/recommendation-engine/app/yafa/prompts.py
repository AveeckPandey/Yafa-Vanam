"""Claim-safe response composition for the RAG-only Yafa chat."""
from __future__ import annotations

_LIVE_DOMAIN_PHRASES: dict[str, str] = {
    "inventory": "whether it is in stock right now",
    "price": "its current price",
    "order_status": "your order status",
    "cart": "your bag",
    "reviews": "customer reviews",
    "ratings": "customer ratings",
    "shipping": "shipping details",
}


def product_information_message(
    chunks: list[dict], *, rag_available: bool, requires_qualification_note: bool = False
) -> str:
    if not chunks:
        if not rag_available:
            return "Yafa's product knowledge is temporarily unavailable. Please try again in a moment so I can answer from verified information."
        return "I couldn't find verified information about that in the product knowledge base, so I'd rather not guess."
    parts = [f"Here's what I know: {chunks[0]['content']}"]
    if len(chunks) > 1:
        parts.append(f"Also relevant: {chunks[1]['content']}")
    if requires_qualification_note or any(chunk.get("requires_qualification") for chunk in chunks):
        parts.append("Some of this still needs final verification, so treat it as provisional rather than a confirmed product claim.")
    return " ".join(parts)


def scent_catalogue_message() -> str:
    """Compact lead-in for an unscoped scent search.

    The verified scent excerpt and product-page link are presented by the
    storefront cards, so repeating several full fragrance records in the chat
    bubble makes the useful results harder to reach.
    """
    return "I found verified YAFA VANAM fragrance profiles related to your question. Explore the product details below."


def live_data_message(domain: str) -> str:
    topic = _LIVE_DOMAIN_PHRASES.get(domain, domain.replace("_", " "))
    return f"I can't answer {topic} from product knowledge — that's live commerce data. Please check the shop for the current information."


def greeting_message() -> str:
    return "Hi! I'm Yafa. I can answer verified questions about YAFA VANAM products and brand information."


def general_message() -> str:
    return "I can help with verified product, ingredient, usage, warning, scent, and brand-policy questions."


def recommendation_unavailable_message() -> str:
    return "Yafa now provides product knowledge only, so I can't generate personalised product recommendations or shade matches. Ask me about a product's verified details instead."


def unavailable_fact_message(fact_label: str) -> str:
    return f"I don't have verified {fact_label} information for this product, so I can't give you a confirmed answer."
