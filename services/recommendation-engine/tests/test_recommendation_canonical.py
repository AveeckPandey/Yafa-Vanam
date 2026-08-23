"""Canonical layer: token normalization, aliases, profile conversion parity."""
from __future__ import annotations

import pytest

from app.recommendation.canonical import (
    CanonicalProfile,
    canonical_occasion,
    family_matches,
    from_beauty_profile,
    normalize_token,
    to_canonical_profile,
)
from app.v1 import normalise_profile


def test_normalize_token_handles_hyphens_spaces_case():
    assert normalize_token("light-medium") == "light_medium"
    assert normalize_token("Soft-Glam") == "soft_glam"
    assert normalize_token("soft glam") == "soft_glam"
    assert normalize_token("  Special Occasion ") == "special_occasion"
    assert normalize_token(None) == ""
    assert normalize_token("date.night") == "date_night"


def test_occasion_aliases_match_v1_semantics():
    assert canonical_occasion("everyday") == "daily"
    assert canonical_occasion("office") == "daily"
    assert canonical_occasion("work") == "daily"
    assert canonical_occasion("brunch") == "daily"
    assert canonical_occasion("date_night") == "evening"
    assert canonical_occasion("evening") == "evening"
    assert canonical_occasion("wedding") == "special_occasion"
    assert canonical_occasion("bridal") == "special_occasion"
    assert canonical_occasion("unknown_gala") is None


def test_family_aliases_bridge_compound_and_simple_tokens():
    assert family_matches("rose_peach", "peach")
    assert family_matches("peach", "rose_peach")
    assert family_matches("terracotta_brick", "terracotta")
    assert family_matches("nude_earth", "nude")
    assert not family_matches("mauve", "copper")
    assert not family_matches(None, "nude")


def _shared_payload() -> dict:
    return {
        "skin": {
            "shade_code": None,
            "depth_family": "Medium-Tan",
            "undertone": "Warm",
            "skin_types": ["combination"],
            "concerns": ["Dark Spots"],
        },
        "face": {"eye_colour": "brown", "hair_colour": "black", "hair_depth": "black"},
        "makeup_preferences": {"finish": "soft_matte", "preferred_lip_finish": "Satin"},
        "context": {"occasion": "date-night", "outfit": {"primary_colour": "Emerald"}},
        "safety_conditions": [],
    }


def test_to_canonical_profile_matches_v1_normalise_profile_values():
    payload = _shared_payload()
    canonical = to_canonical_profile(payload)
    legacy = normalise_profile(payload)

    assert canonical.depth == normalize_token(legacy["depth"]) == "medium_tan"
    assert canonical.undertone == normalize_token(legacy["undertone"]) == "warm"
    assert canonical.skin_types == ["combination"]
    assert canonical.concerns == ["dark_spots"]
    assert canonical.eye_colour == legacy["eye_colour"] == "brown"
    # occasion tokens differ only in separator convention, never in meaning
    assert normalize_token(legacy["occasion"]) == canonical.occasion == "date_night"
    assert canonical.outfit == legacy["outfit"] == {"primary_colour": "Emerald"}
    assert canonical.lip_finish == normalize_token(legacy["lip_finish"]) == "satin"


def test_legacy_complexion_and_conditions_paths_still_merge():
    payload = {"complexion": {"shade_code": "5o", "confirmed": True}, "conditions": ["pregnant"]}
    canonical = to_canonical_profile(payload)
    legacy = normalise_profile(payload)

    assert canonical.shade_code == "5O"  # uppercased for earth_skin_24 comparison
    assert canonical.shade_confirmed is True
    assert legacy["shade_confirmed"] is True
    assert canonical.safety_conditions == {"pregnant"}


def test_missing_fields_stay_unset_never_invented():
    profile = to_canonical_profile({})
    assert isinstance(profile, CanonicalProfile)
    assert profile.depth is None
    assert profile.undertone is None
    assert profile.skin_types == []
    assert profile.outfit is None
    assert profile.safety_conditions == set()


def test_raw_payload_retained_for_provenance():
    payload = _shared_payload()
    profile = to_canonical_profile(payload, context={"daypart": "day"})
    assert profile.raw == payload
    assert profile.daypart == "day"


def test_from_beauty_profile_accepts_user_beauty_profile_shape():
    advisor_payload = {
        "skin": {"shade_code": "5O", "depth_family": "medium_tan", "undertone": "olive",
                 "skin_types": ["oily"], "concerns": []},
        "face": {"eye_colour": "hazel"},
        "makeup_preferences": {"finish": "natural", "intensity": "medium"},
    }
    profile = from_beauty_profile(advisor_payload)
    assert profile.shade_code == "5O"
    assert profile.undertone == "olive"
    assert profile.style == "medium"  # makeup_preferences.intensity -> style
    assert profile.finish == "natural"

    class _FakeModel:
        def model_dump(self):
            return advisor_payload

    assert from_beauty_profile(_FakeModel()).shade_code == "5O"


def test_lab_extraction_requires_all_three_channels():
    partial = to_canonical_profile({"skin": {"lab": {"L": 50.0}}})
    assert partial.lab is None
    full = to_canonical_profile({"skin": {"lab": {"L": 50.0, "a": 8.0, "b": 12.0}}})
    assert full.lab == {"L": 50.0, "a": 8.0, "b": 12.0}
