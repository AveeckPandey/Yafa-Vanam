"""Adapters: structural validation, counts, joins, palette handling, drift policy."""
from __future__ import annotations

import pytest

from app.recommendation.adapters import (
    EXPECTED_COUNTS,
    clear_caches,
    get_adapter,
    load_all,
)
from app.recommendation.adapters.base import BaseAdapter


@pytest.fixture(scope="module")
def adapters():
    return load_all()


def test_all_five_datasets_load_with_expected_counts(adapters):
    assert EXPECTED_COUNTS == {"skin": 11, "lips": 8, "cheeks": 6, "eyes": 15, "no_shades": 38}
    assert sum(len(a.products()) for a in adapters.values()) == 78


def test_product_ids_unique_across_the_whole_catalogue(adapters):
    ids = [p["id"] for adapter in adapters.values() for p in adapter.products()]
    assert len(ids) == len(set(ids)) == 78


def test_skin_shade_records_are_the_24_master_shades(adapters):
    shades = adapters["skin"].shade_records()
    assert len(shades) == 24
    codes = {shade["code"] for shade in shades}
    assert {"1C", "5O", "8W"} <= codes
    for shade in shades:
        cielab = shade["measured_colour"]["cielab"]
        assert all(channel in cielab for channel in ("L", "a", "b"))
        assert shade["depth_family"] and shade["undertone"]


def test_neighbor_graph_exposes_seasonal_fallback(adapters):
    neighbors = adapters["skin"].neighbors("1C")
    assert "1N" in neighbors["horizontal_same_depth"]
    assert neighbors["seasonal_deeper_same_undertone"] == "2C"
    fallback = neighbors["seasonal_missing_axis_fallback"]
    assert fallback == "rank_all_shades_at_target_depth_by_delta_e00"


def test_delta_bands_and_confidence_anchors_read_from_dataset(adapters):
    skin = adapters["skin"]
    classes = [band["class"] for band in skin.delta_e_thresholds()]
    assert classes == ["exact_match", "blendable_match", "boundary_neighbor", "mismatch"]
    anchors = {a["delta_e00"]: a["score"] for a in skin.confidence_anchors()}
    assert anchors == {0.0: 100, 1.5: 85, 3.2: 65, 5.0: 35, 6.0: 0}


def test_lip_shade_profiles_join_through_variant_refs(adapters):
    lips = adapters["lips"]
    profiles = lips.shade_profiles_for_product("yv-lip-001")
    assert len(profiles) >= 6
    families = {profile["color_profile"]["color_family"] for profile in profiles}
    assert "rose_pink" in families
    recommendation = profiles[0]["recommendation"]
    # colour-theory fields present as signals; never a hard exclusion
    assert recommendation["hard_exclusion"] is False
    assert recommendation["undertone_compatibility"]


def test_lip_weights_table_is_the_spec_table(adapters):
    assert adapters["lips"].weights_table() == {
        "user_requested_product_or_finish": 1.0,
        "desired_color_family": 0.9,
        "complexion_depth_as_contrast_signal": 0.7,
        "undertone_compatibility": 0.65,
        "occasion_and_look_style": 0.6,
        "outfit_harmony": 0.45,
        "liner_pairing_if_requested": 0.4,
    }


def test_cheek_shared_systems_expose_lip_coordination_data(adapters):
    cheeks = adapters["cheeks"]
    profiles = cheeks.shared_profiles("blush_system_a_6")
    assert len(profiles) == 6
    dawn_petal = profiles["dawn-petal"]["recommendation"]
    assert dawn_petal["recommended_lip_color_families"][:2] == ["nude_earth", "rose_pink"]
    assert dawn_petal["application_intensity_by_complexion_depth"]["very_deep"] == "rich_or_layered"
    # grouped outfit table is empty — per-shade lists are authoritative
    assert cheeks.outfit_families() == {}


def test_cheek_depth_application_rules_carry_four_tiers(adapters):
    rules = adapters["cheeks"].depth_application_rules()
    assert set(rules) == {"fair_light", "light_medium_medium", "medium_tan_tan", "deep_very_deep"}


def test_eye_colour_rules_cover_all_five_colours_boost_only(adapters):
    eyes = adapters["eyes"]
    matching = eyes.eye_colour_matching()
    assert set(matching["rules"]) == {"blue", "brown", "green", "grey", "hazel"}
    assert matching["method"] == "weighted preference, never hard exclusion"


def test_brow_rules_order_black_before_soft_black_for_black_hair(adapters):
    rules = adapters["eyes"].brow_rules()
    black_rows = [rule for rule in rules if "black" in rule["hair_depth"]]
    assert black_rows[0]["recommended"][:2] == ["Black Brown", "Soft Black"]
    assert adapters["eyes"].brow_matching()["do_not_use_as_primary"] == ["outfit_colour"]


def test_brow_variants_join_to_shared_system_profiles(adapters):
    eyes = adapters["eyes"]
    brows = eyes.by_type()["Brows"]
    names = set()
    for product in brows:
        for variant in product.get("variants", []):
            profile = eyes.shade_profiles_for_variant(variant)
            if profile:
                names.add(profile["name"])
    shared_names = set(eyes.shared_profiles("brow_10_with_clear")) | set(eyes.shared_profiles("brow_9_coloured"))
    coloured_names = {profile["name"] for profile in eyes.shared_profiles("brow_9_coloured").values()}
    assert coloured_names <= names  # every coloured brow shade reachable from real variants


def test_palettes_stay_one_candidate_with_pans_attached(adapters):
    eyes = adapters["eyes"]
    palettes = eyes.palettes()
    assert palettes, "expected pan-based eye products"
    palette, pans = palettes[0]
    assert len(palette.get("variants", [])) == 1  # ONE sellable SKU
    assert len(pans) >= 2  # ...with several pans that are NOT variants


def test_skincare_candidates_exclude_primer_setting_spray_and_fragrance(adapters):
    no_shades = adapters["no_shades"]
    candidates = no_shades.skincare_candidates()
    assert len(candidates) == 24
    types = {product["product_type"] for product in candidates}
    assert "Face Primer" not in types and "Setting Spray" not in types
    assert all(not product.get("fragrance_profile") for product in candidates)
    assert len(no_shades.fragrances()) == 12


def test_single_repo_wide_hard_exclusion_is_retinol_pregnancy(adapters):
    rule = None
    for adapter in adapters.values():
        for product in adapter.products():
            exclusions = (product.get("recommendation_profile") or {}).get("hard_exclusions") or []
            for candidate_rule in exclusions:
                rule = (product["id"], candidate_rule)
    assert rule is not None
    assert rule == (
        "yv-skin-019",
        {
            "condition": "pregnant_or_planning_pregnancy",
            "reason": "Precautionary retinoid recommendation pending final formulation and target-market regulatory sign-off.",
            "evidence_scope": "conservative_safety_inference",
            "source": "https://www.ema.europa.eu/en/medicines/human/referrals/retinoid-containing-medicinal-products",
            "status": "requires_regulatory_review",
        },
    )


def test_compatibility_rules_are_concept_keyed_and_require_confirmation(adapters):
    rules_by_product = adapters["no_shades"].compatibility_rules()
    assert rules_by_product
    for _product_id, rules in rules_by_product.items():
        for rule in rules:
            assert rule["rule_type"] in {"positive_pairing", "soft_penalty"}
            assert "_" in rule["with"] or rule["with"].islower()  # concept token, not a product id
            assert rule.get("requires_formula_confirmation") is True
            assert rule.get("evidence_scope")


def test_unknown_vocabulary_warns_instead_of_raising():
    from app.recommendation.canonical import REGISTRY

    REGISTRY.reset()
    clear_caches()
    try:
        load_all()  # repopulates known vocabulary from datasets
        token = REGISTRY.check("lips", "color_family", "galactic_mauve")
        assert token == "galactic_mauve"  # kept verbatim, never invented around
        warnings = REGISTRY.warnings()
        assert any("galactic_mauve" in warning for warning in warnings)
    finally:
        REGISTRY.reset()
        clear_caches()


def test_structural_breakage_raises(tmp_path, monkeypatch):
    from app.recommendation import adapters as adapter_module

    broken_dir = tmp_path / "data"
    broken_dir.mkdir()
    (broken_dir / "skin.json").write_text('{"products": [{"id": "", "name": "nope"}]}', encoding="utf-8")
    monkeypatch.setattr(adapter_module, "DATA_DIR", broken_dir)
    clear_caches()
    try:
        with pytest.raises(RuntimeError):
            get_adapter("skin")
    finally:
        clear_caches()
