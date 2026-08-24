"""Deterministic message composition for Yafa responses.

NO final LLM is connected in these phases. Messages are assembled from fixed
templates + reason-code phrases so every customer-facing sentence is auditable
and claim-safe (spec Phase 2 §8: describe WHY something ranked, never
"scientifically perfect").

A future generation model would consume build_generation_context() and remain
constrained to the validated ids/chunks it receives.
"""
from __future__ import annotations

from typing import Any

REASON_PHRASES: dict[str, str] = {
    "catalogue_baseline": "currently ranks well across the catalogue",
    "warm_undertone_match": "aligns with a warm undertone",
    "cool_undertone_match": "aligns with a cool undertone",
    "neutral_undertone_match": "aligns with a neutral undertone",
    "olive_undertone_match": "aligns with an olive undertone",
    "complexion_depth_contrast_match": "suits your complexion depth",
    "complexion_depth_intensity_tuned": "intensity tuned to your complexion depth",
    "requested_finish_or_product_match": "matches the finish you asked for",
    "desired_intensity_match": "matches the intensity you asked for",
    "look_style_soft_glam_priority": "fits a soft-glam look",
    "look_style_natural_priority": "fits a natural look",
    "look_style_bold_priority": "fits a bold look",
    "skin_type_best_for": "is a strong fit for your skin type",
    "skin_type_compatible": "works with your skin type",
    "skin_type_caution_penalty": "use with some caution for your skin type",
    "concern_primary_match": "targets your primary concern",
    "goal_direct_match": "supports the goal you described",
    "routine_step_time_fit": "fits the routine step you asked about",
    "brow_hair_depth_temperature_match": "matches your hair depth and temperature",
    "mascara_default_neutral_tone": "a reliable everyday definition choice",
    "eyeliner_neutral_default": "a versatile neutral liner choice",
}

_LIVE_DOMAIN_PHRASES: dict[str, str] = {
    "inventory": "whether it is in stock right now",
    "price": "its current price",
    "order_status": "your order status",
    "cart": "your bag",
    "reviews": "customer reviews",
    "ratings": "customer ratings",
    "shipping": "shipping details",
}


def reason_phrase(code: str) -> str:
    return REASON_PHRASES.get(code)


def describe_recommendation(item: dict[str, Any]) -> str:
    """One short ranking explanation; never overstates certainty."""
    name = item.get("product_name") or item.get("product_id")
    shade = item.get("shade_name")
    label = f"{name}" + (f" in {shade}" if shade else "")
    phrases = [
        phrase
        for phrase in (reason_phrase(code) for code in item.get("reason_codes", []))
        if phrase
    ]
    if not phrases:
        return f"{label} ranks well for what you described."
    return f"{label} — {', '.join(phrases[:3])}."


def product_information_message(
    chunks: list[dict[str, Any]],
    *,
    rag_available: bool,
    requires_qualification_note: bool = False,
) -> str:
    if not chunks:
        if not rag_available:
            return (
                "I don't have my product knowledge base connected right now, "
                "so I can't answer factual questions reliably yet."
            )
        return (
            "I couldn't find verified information about that in the product "
            "knowledge base, so I'd rather not guess."
        )
    parts = [f"Here's what I know: {chunks[0]['content']}"]
    if len(chunks) > 1:
        parts.append(f"Also relevant: {chunks[1]['content']}")
    if requires_qualification_note or any(
        chunk.get("requires_qualification") for chunk in chunks
    ):
        parts.append(
            "Some of this still needs final verification, so treat it as "
            "provisional rather than a confirmed product claim."
        )
    return " ".join(parts)


def recommendation_message(items: list[dict[str, Any]], category_label: str) -> str:
    if not items:
        return (
            f"I couldn't find a strong {category_label} match yet — tell me a "
            "little more about what you're looking for and I'll narrow it down."
        )
    lines = [describe_recommendation(item) for item in items[:3]]
    return "My picks:\n" + "\n".join(f"• {line}" for line in lines)


def full_look_message(selections: dict[str, list[dict[str, Any]]], notes: list[str]) -> str:
    if not selections:
        return (
            "I can build a complete look for you — share your occasion or "
            "outfit colours and I'll coordinate complexion, eyes, cheeks and lips."
        )
    order = ("complexion", "eyes", "cheeks", "lips", "fragrance")
    lines: list[str] = []
    for category in order:
        items = selections.get(category)
        if items:
            lines.append(describe_recommendation(items[0]))
    message = "Here's your coordinated look:\n" + "\n".join(f"• {line}" for line in lines)
    if notes:
        message += "\n\n" + " ".join(notes)
    return message


def live_data_message(domain: str, product_name: str | None) -> str:
    topic = _LIVE_DOMAIN_PHRASES.get(domain, domain.replace("_", " "))
    target = f" for {product_name}" if product_name else ""
    return (
        f"I can't answer {topic}{target} from product knowledge — that's live "
        "commerce data. Let me hand this to the shop so you get the current truth."
    )


def missing_info_question(category: str) -> str:
    questions = {
        "lips": "I can narrow that down — do you want a natural or a bold lip?",
        "cheeks": "Would you like a subtle flush or a more visible blush?",
        "eyes": "Do you want soft definition or a bolder eye?",
        "complexion": (
            "What's your skin type — dry, oily, combination, or normal? "
            "That decides which formula will wear best."
        ),
        "skincare": "What's your main skin concern — dehydration, texture, breakouts, or dullness?",
        "fragrance": "Do you lean fresh and light, or warm and richer?",
    }
    return questions.get(category, "Tell me a little more about what you're looking for.")


def general_message() -> str:
    return (
        "I'm Yafa. I can answer product questions, recommend makeup, skincare "
        "or fragrance, match your shade, and build a coordinated look. What "
        "would you like to do?"
    )


def greeting_message() -> str:
    return (
        "Hi! I'm Yafa, your beauty companion. I can answer product questions, "
        "help with shade matching, or build a look around your outfit. What "
        "are you shopping for today?"
    )


def unclear_message() -> str:
    return (
        "I'm not sure I caught that. I can help with product questions, "
        "recommendations for lips, eyes, cheeks, skincare or fragrance, shade "
        "matching, or a coordinated look. Which of those is closest?"
    )


def unavailable_fact_message(fact_label: str, product_name: str | None) -> str:
    target = f" for {product_name}" if product_name else " for this product"
    return (
        f"I don't have verified {fact_label} information{target}, so I can't "
        "give you a confirmed answer on that."
    )


def fact_answer_prefix(product_name: str | None) -> str:
    return f"About {product_name}: " if product_name else ""


def outfit_missing_colours_message() -> str:
    return (
        "Happy to match your makeup — what colour(s) are you wearing? A quick "
        "description or an outfit photo both work."
    )


def image_no_context_message() -> str:
    return (
        "I can work with an image once I know what's in it. Upload your "
        "outfit photo (I'll read its colours), or use the selfie flow for "
        "shade matching — then tell me what you'd like."
    )


def commerce_message(domain: str, product_name: str | None) -> str:
    return live_data_message(domain, product_name)


def uncertain_colour_note(primary: str | None, runner_up: str | None) -> str:
    """Honest phrasing when colour confidence is low (navy-vs-black class)."""
    if primary and runner_up:
        return (
            f"This looks {primary.replace('_', ' ')} to me, but if it's "
            f"{runner_up.replace('_', ' ')} I can adjust the recommendation."
        )
    return ""
