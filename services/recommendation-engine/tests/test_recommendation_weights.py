"""Weight tables: code defaults == spec numbers == dataset tables; drift warns."""
from __future__ import annotations

import logging

import pytest

from app.recommendation.adapters import get_adapter
from app.recommendation.weights import (
    CATALOGUE_BASELINE_SCORE,
    CHEEK_WEIGHTS,
    COMPLEXION_FORMULA_WEIGHTS,
    EYE_WEIGHTS,
    FRAGRANCE_WEIGHTS,
    LIP_WEIGHTS,
    SKINCARE_SCALE,
    MakeupWeights,
    effective_weights,
)

SPEC_NUMBERS = {
    "lip_recommendation_rules": (
        ("user_requested_product_or_finish", 1.0),
        ("desired_color_family", 0.9),
        ("complexion_depth_as_contrast_signal", 0.7),
        ("undertone_compatibility", 0.65),
        ("occasion_and_look_style", 0.6),
        ("outfit_harmony", 0.45),
        ("liner_pairing_if_requested", 0.4),
    ),
}


@pytest.mark.parametrize("adapter_name,weights_attr,rules_key", [
    ("lips", "LIP_WEIGHTS", "lip_recommendation_rules"),
    ("cheeks", "CHEEK_WEIGHTS", "cheek_recommendation_rules"),
    ("eyes", "EYE_WEIGHTS", "eye_recommendation_rules"),
])
def test_dataset_tables_match_code_defaults(adapter_name, weights_attr, rules_key):
    import app.recommendation.weights as weights_module

    dataset_table = get_adapter(adapter_name).weights_table()
    code_table = getattr(weights_module, weights_attr)
    for factor, weight in code_table.factors:
        assert float(dataset_table[factor]) == weight, f"{adapter_name}.{factor} drifted"


def test_spec_numbers_pinned_for_lips():
    for factor, weight in SPEC_NUMBERS["lip_recommendation_rules"]:
        assert dict(LIP_WEIGHTS.factors)[factor] == weight


def test_effective_weights_prefers_the_dataset_and_warns_on_drift(caplog):
    default = MakeupWeights((("factor_a", 1.0), ("factor_b", 0.5)))
    drifted = {"factor_a": 2.0}  # dataset disagrees on factor_a only
    with caplog.at_level(logging.WARNING):
        resolved = effective_weights("test_category", drifted, default)
    assert dict(resolved.factors)["factor_a"] == 2.0  # dataset wins
    assert dict(resolved.factors)["factor_b"] == 0.5  # untouched factors keep defaults
    assert any("drift" in record.message and "factor_a" in record.message for record in caplog.records)


def test_effective_weights_flags_dataset_only_factors(caplog):
    default = MakeupWeights((("factor_a", 1.0),))
    extra = {"dataset_only_factor": 0.25}
    with caplog.at_level(logging.WARNING):
        resolved = effective_weights("test_category", extra, default)
    assert dict(resolved.factors) == {"factor_a": 1.0}  # engine factors unchanged
    assert any("dataset-only weight" in record.message for record in caplog.records)


def test_effective_weights_passthrough_when_no_dataset_table():
    default = MakeupWeights((("factor_a", 1.0),))
    assert effective_weights("test_category", None, default) is default
    assert effective_weights("test_category", {}, default) is default


def test_hard_exclusion_is_the_string_reject():
    assert SKINCARE_SCALE.HARD_EXCLUSION == "reject"
    table = get_adapter("no_shades").weights_table()
    assert table["hard_exclusion"] == "reject"


def test_calibration_knobs_are_named_constants():
    assert SKINCARE_SCALE.NORMALIZATION_MIN == -3.0
    assert SKINCARE_SCALE.NORMALIZATION_MAX == 4.0
    assert CATALOGUE_BASELINE_SCORE == 0.5


def test_engine_owned_tables_exist_for_categories_without_dataset_blocks():
    names = {name for name, _ in COMPLEXION_FORMULA_WEIGHTS.factors}
    assert names == {"skin_type_fit", "finish_preference", "coverage_preference", "occasion_wear_goal"}
    fragrance = {name: weight for name, weight in FRAGRANCE_WEIGHTS.factors}
    assert fragrance == {"scent_profile_overlap": 1.0, "season_and_occasion": 0.6, "intensity_positioning": 0.4}
