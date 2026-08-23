"""Spec Test B — cheeks engine: very-deep depth tunes intensity, never gates."""
from __future__ import annotations

from app.recommendation.adapters import get_adapter
from app.recommendation.canonical.normalization import to_canonical_profile
from app.recommendation.engines import cheeks


def _depth_only(depth: str):
    return to_canonical_profile({"skin": {"depth": depth}})


def test_very_deep_zero_exclusions_and_intensity_note():
    result = cheeks.recommend(_depth_only("very_deep"), limit=8)
    assert result.items
    for item in result.items:
        for code in item.reason_codes:
            assert "exclusion" not in code

    guidance = get_adapter("cheeks").depth_application_rules()["deep_very_deep"]
    assert result.notes["application_intensity"] == guidance
    assert "rich" in result.notes["application_intensity"].lower()


def test_depth_signal_fires_universally_and_never_gates():
    # Every cheek shade lists every depth band as eligible — depth tunes
    # APPLICATION INTENSITY here; it is never an eligibility filter.
    result = cheeks.recommend(_depth_only("very_deep"), limit=20)
    assert result.items
    for item in result.items:
        assert "complexion_depth_intensity_tuned" in item.reason_codes


def test_lighter_families_stay_eligible_never_removed():
    # Depth never gates: the very-deep profile returns exactly the same
    # products as an empty profile — only their order changes.
    baseline = cheeks.recommend(to_canonical_profile({}), limit=20)
    deep = cheeks.recommend(_depth_only("very_deep"), limit=20)
    assert {item.product_id for item in deep.items} == {item.product_id for item in baseline.items}


def test_lip_coordination_factor_fires_with_hints():
    from app.recommendation.canonical.schemas import CoordinationHints

    profile = _depth_only("medium")
    with_hints = cheeks.recommend(profile, limit=10, coordination=CoordinationHints(lip_color_family="rose_pink"))
    without_hints = cheeks.recommend(profile, limit=10)
    credited = [item for item in with_hints.items if any(c.startswith("lip_coordination_") for c in item.reason_codes)]
    assert credited, "rose_pink is a dataset-recommended lip family; coordination must fire"
    scores_without = {item.product_id: item.score for item in without_hints.items}
    for item in credited:
        if item.product_id in scores_without:
            assert item.score >= scores_without[item.product_id]


def test_low_information_profile_is_baseline():
    result = cheeks.recommend(to_canonical_profile({}), limit=4)
    assert len(result.items) == 4
    for item in result.items:
        assert item.score == 0.5
        assert "catalogue_baseline" in item.reason_codes
