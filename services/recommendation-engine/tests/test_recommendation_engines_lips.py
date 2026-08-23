"""Spec Test A — lips engine: boosts only, outfit harmony ranks, low-info safe."""
from __future__ import annotations

import pytest

from app.recommendation.adapters import get_adapter
from app.recommendation.canonical.normalization import to_canonical_profile
from app.recommendation.engines import lips
from app.recommendation.weights import LIP_WEIGHTS


def _profile():
    return to_canonical_profile({
        "skin": {"depth": "medium_tan", "undertone": "warm"},
        "makeup_preferences": {"intensity": "soft_glam"},
        "context": {"occasion": "brunch", "outfit": {"primary_colour": "emerald"}},
    })


def test_nothing_is_excluded_and_codes_are_boosts_only():
    result = lips.recommend(_profile(), limit=8)
    assert result.items, "full profile must still return recommendations"
    for item in result.items:
        for code in item.reason_codes:
            assert "exclusion" not in code and "reject" not in code
            assert code == code.lower().replace(" ", "_"), "codes are machine tokens"


def test_emerald_outfit_harmony_fires_and_lifts_ranking():
    with_outfit = lips.recommend(_profile(), limit=10)
    boosted = [item for item in with_outfit.items if "emerald_outfit_harmony" in item.reason_codes]
    assert boosted, "emerald is a dataset harmony colour; at least one lip must credit it"

    bare = to_canonical_profile({
        "skin": {"depth": "medium_tan", "undertone": "warm"},
        "makeup_preferences": {"intensity": "soft_glam"},
        "context": {"occasion": "brunch"},
    })
    scores_without = {item.product_id: item.score for item in lips.recommend(bare, limit=10).items}
    for item in boosted:
        if item.product_id in scores_without:
            assert item.score >= scores_without[item.product_id]


def test_low_information_profile_returns_baseline_scored_results():
    result = lips.recommend(to_canonical_profile({}), limit=5)
    assert len(result.items) == 5
    for item in result.items:
        assert item.score == 0.5  # CATALOGUE_BASELINE_SCORE — no invented signals
        assert "catalogue_baseline" in item.reason_codes


def test_requested_lip_finish_structured_match():
    profile = to_canonical_profile({"makeup_preferences": {"preferred_lip_finish": "soft_matte"}})
    result = lips.recommend(profile, limit=10)
    credited = [item for item in result.items if "requested_finish_or_product_match" in item.reason_codes]
    assert credited, "structured shade finish must earn the requested-finish factor"


def test_weights_come_from_the_dataset_table():
    table = get_adapter("lips").weights_table()
    for name, weight in LIP_WEIGHTS.factors:
        assert float(table[name]) == weight


@pytest.mark.parametrize("limit", [1, 3, 10])
def test_limit_is_respected(limit: int):
    assert len(lips.recommend(_profile(), limit=limit).items) <= limit
