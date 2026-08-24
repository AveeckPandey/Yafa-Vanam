"""Context helper unit tests: live-data routing + slot extraction (sync)."""
from __future__ import annotations

from app.yafa.context import (
    detect_live_data_domain,
    extract_slots,
    merge_slots_into_profile,
)


def test_detect_live_data_domains():
    assert detect_live_data_domain("Is this in stock?") == "inventory"
    assert detect_live_data_domain("what's the price") == "price"
    assert detect_live_data_domain("where is my order") == "order_status"
    assert detect_live_data_domain("any reviews?") == "reviews"
    assert detect_live_data_domain("what does it smell like") is None


def test_extract_slots_vocabulary_backed_only():
    slots = extract_slots(
        "evening wedding with emerald and gold dress, soft glam",
        {"outfit_colours": ["emerald", "gold"]},
    )
    assert slots["occasion"] == "wedding"
    assert slots["daypart"] == "evening"
    assert slots["look_style"] == "soft_glam"
    assert slots["outfit_primary_colour"] == "emerald"
    assert slots["outfit_secondary_colours"] == ["gold"]


def test_extract_slots_never_invents():
    assert extract_slots("hello", {"outfit_colours": ["emerald"]}) == {}


def test_merge_slots_request_wins():
    merged = merge_slots_into_profile(
        {
            "skin": {"depth": "medium_tan"},
            "context": {"occasion": "brunch"},
        },
        {"occasion": "wedding", "outfit_primary_colour": "emerald"},
    )
    # Explicit request payload wins over conversation slots:
    assert merged["context"]["occasion"] == "brunch"
    assert merged["context"]["outfit"]["primary_colour"] == "emerald"
    assert merged["skin"]["depth"] == "medium_tan"


def test_merge_slots_fills_gaps():
    merged = merge_slots_into_profile(
        {},
        {
            "occasion": "wedding",
            "daypart": "evening",
            "look_style": "soft_glam",
        },
    )
    assert merged["context"]["occasion"] == "wedding"
    assert merged["context"]["daypart"] == "evening"
    assert merged["makeup_preferences"]["intensity"] == "soft_glam"
