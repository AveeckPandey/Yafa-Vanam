"""Spec Tests D & E — skincare engine: dataset scale, routine slots, Test E safety."""
from __future__ import annotations

from app.recommendation.adapters import get_adapter
from app.recommendation.candidate_filter import evaluate
from app.recommendation.canonical.normalization import to_canonical_profile
from app.recommendation.engines import skincare
from app.recommendation.weights import SKINCARE_SCALE


def _combination_profile(**extra):
    payload = {
        "skin": {"skin_types": ["combination"], "concerns": ["dehydration"]},
        "goals": ["clean_skin", "hydration"],
    }
    payload.update(extra)
    return to_canonical_profile(payload)


def _routine_step(product_id: str) -> str | None:
    product = get_adapter("no_shades").find(product_id)
    return ((product or {}).get("recommendation_profile") or {}).get("routine", {}).get("step")


def test_combination_skin_ranks_cleansers_with_skin_type_best_for():
    result = skincare.recommend(_combination_profile(), limit=10, debug=True)
    assert len(result.items) >= 5
    top = result.items[0]
    assert "skin_type_best_for" in top.reason_codes
    assert top.score_breakdown["raw_signal_sum"] >= 2.0, "best_for (+2) must dominate the raw sum"
    # Both cleansers earn best-for + clean_skin goal credit. Dehydration-
    # targeting moisturizers outrank them on the primary-concern signal — the
    # routine builder covers step placement, so ranking stays signal-driven.
    cleansers = [item for item in result.items if _routine_step(item.product_id) == "cleanser"]
    assert len(cleansers) == 2, "both catalogue cleansers surface within the ranked page"
    for item in cleansers:
        assert {"skin_type_best_for", "goal_direct_match"} <= set(item.reason_codes)


def test_am_pm_routine_slots_respected():
    result = skincare.recommend(_combination_profile(), limit=8)
    routine = result.notes["routine"]
    am_roles = [slot["role"] for slot in routine["am"]]
    pm_roles = [slot["role"] for slot in routine["pm"]]
    assert "cleanser" in am_roles and "cleanser" in pm_roles
    assert "sunscreen_if_validated" in am_roles, "sunscreen is an AM slot"
    assert all(isinstance(role, str) for role in am_roles + pm_roles)


def test_hard_exclusion_removes_retinol_for_pregnancy_despite_maximal_positives():
    profile = to_canonical_profile({
        "skin": {"skin_types": ["dry", "normal"], "concerns": ["fine_lines", "firmness"],
                 "safety_conditions": ["pregnant_or_planning_pregnancy"]},
        "goals": ["anti_ageing", "hydration"],
    })
    result = skincare.recommend(profile, limit=30)
    ids = [item.product_id for item in result.items]
    assert "yv-skin-019" not in ids, "hard exclusion rejects unconditionally"

    outcome = evaluate(get_adapter("no_shades").find("yv-skin-019"), profile)
    assert outcome.excluded
    assert outcome.reason_code == "hard_exclusion_pregnant_or_planning_pregnancy"


def test_sensitive_skin_penalty_is_warning_plus_score_never_exclusion():
    sensitive = to_canonical_profile({"skin": {"skin_types": ["dry"], "concerns": ["dryness"],
                                              "sensitivity": "high"}})
    neutral = to_canonical_profile({"skin": {"skin_types": ["dry"], "concerns": ["dryness"]}})
    sensitive_run = {item.product_id: item for item in skincare.recommend(sensitive, limit=40).items}
    neutral_run = {item.product_id: item for item in skincare.recommend(neutral, limit=40).items}

    scrub = sensitive_run.get("yv-skin-011")
    assert scrub is not None, "soft penalty warns; it never excludes"
    assert any("soft_penalty_sensitive_or_reactive_skin" in code for code in scrub.reason_codes)
    assert scrub.warnings
    if "yv-skin-011" in neutral_run:
        assert scrub.score < neutral_run["yv-skin-011"].score


def test_compatibility_pairing_fires_with_confirmation_warning():
    profile = to_canonical_profile({
        "skin": {"skin_types": ["dry"]},
        "ingredient_concepts": ["hyaluronic_acid"],
    })
    result = skincare.recommend(profile, limit=40)
    fired = [
        item for item in result.items
        if any(code.startswith("compatibility_positive_pairing_") for code in item.reason_codes)
    ]
    assert fired
    for item in fired:
        assert "compatibility_requires_formula_confirmation" in item.warnings


def test_scale_constants_match_dataset_table():
    from app.recommendation.adapters import get_adapter

    table = get_adapter("no_shades").weights_table()
    assert table["best_for_match"] == SKINCARE_SCALE.BEST_FOR_MATCH
    assert table["compatible_match"] == SKINCARE_SCALE.COMPATIBLE_MATCH
    assert table["supporting_feature"] == SKINCARE_SCALE.SUPPORTING_FEATURE
    assert table["minor_mismatch"] == SKINCARE_SCALE.MINOR_MISMATCH
    assert table["tolerance_concern"] == SKINCARE_SCALE.TOLERANCE_CONCERN
    assert table["significant_irritation_concern"] == SKINCARE_SCALE.SIGNIFICANT_IRRITATION_CONCERN
    assert table["hard_exclusion"] == SKINCARE_SCALE.HARD_EXCLUSION == "reject"


def test_empty_profile_scores_baseline_not_invented_signals():
    result = skincare.recommend(to_canonical_profile({}), limit=3, debug=True)
    for item in result.items:
        # raw sum 0 maps linearly: (0 - (-3)) / 7 = 3/7 ≈ 0.429 — the neutral
        # point of the dataset's signed scale, not a fabricated positive.
        expected = round((0.0 - SKINCARE_SCALE.NORMALIZATION_MIN) /
                         (SKINCARE_SCALE.NORMALIZATION_MAX - SKINCARE_SCALE.NORMALIZATION_MIN), 3)
        assert item.score == expected
