"""Owner-approved non-product knowledge for Yafa.

Brand values and conversational guidance must remain answerable when vector
retrieval is unavailable or when a message does not name a product. The JSON
source is also suitable for future vector ingestion, while this loader gives
the chat orchestrator a deterministic, audited fallback today.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any


BRAND_KNOWLEDGE_ID = "yv-brand-knowledge-001"


def _knowledge_path() -> Path:
    return Path(__file__).resolve().parents[4] / "data" / "processed" / "BrandKnowledge.json"


@lru_cache(maxsize=1)
def load_brand_knowledge() -> dict[str, Any]:
    return json.loads(_knowledge_path().read_text(encoding="utf-8"))


def policy_answer(message: str, *, product_name: str | None = None) -> tuple[str, str]:
    """Return an approved answer and the policy section used for grounding."""
    text = message.casefold()
    policy = load_brand_knowledge()["public_policy"]

    asks_cruelty = any(term in text for term in (
        "cruelty", "animal test", "tested on animals", "test on animals",
        "leaping bunny", "peta certified",
    ))
    asks_vegan = any(term in text for term in (
        "vegan", "animal-derived", "animal derived", "beeswax", "lanolin", "carmine",
    ))
    asks_charity = any(term in text for term in (
        "charity", "charitable", "donate", "donation", "give back", "giving",
        "nonprofit", "non-profit", "1%", "one percent",
    ))

    if sum((asks_cruelty, asks_vegan, asks_charity)) > 1:
        sections: list[str] = []
        if asks_cruelty:
            sections.append(policy["cruelty_free"]["short_answer"])
        if asks_vegan:
            sections.append(_vegan_answer(policy["vegan"], product_name))
        if asks_charity:
            sections.append(policy["charitable_giving"]["short_answer"])
        return " ".join(sections), "brand_values_policy"
    if asks_vegan:
        return _vegan_answer(policy["vegan"], product_name), "vegan_policy"
    if asks_charity:
        return policy["charitable_giving"]["short_answer"], "charitable_giving_policy"
    return policy["cruelty_free"]["short_answer"], "cruelty_free_policy"


def policy_content(section: str) -> str:
    """Expanded policy content for an auditable grounding chunk."""
    policy = load_brand_knowledge()["public_policy"]
    if section == "vegan_policy":
        item = policy["vegan"]
    elif section == "charitable_giving_policy":
        item = policy["charitable_giving"]
    elif section == "brand_values_policy":
        return " ".join(
            f"{item['approved_answer']} {item['star_note']}"
            for item in policy.values()
        )
    else:
        item = policy["cruelty_free"]
    return f"{item['approved_answer']} {item['star_note']}"


def _vegan_answer(item: dict[str, Any], product_name: str | None) -> str:
    if product_name:
        return (
            f"I can only call {product_name} Vegan* when its current product page carries "
            "the Vegan* designation. If the designation is absent, it has not yet been "
            "verified for that claim."
        )
    return item["short_answer"]


__all__ = [
    "BRAND_KNOWLEDGE_ID",
    "load_brand_knowledge",
    "policy_answer",
    "policy_content",
]
