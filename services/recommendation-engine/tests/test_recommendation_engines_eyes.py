"""Spec Test C — eyes engine: brow rows dominate, boosts never gate, palettes stay one."""
from __future__ import annotations

from app.recommendation.canonical.normalization import to_canonical_profile
from app.recommendation.engines import eyes


def _brow_profile(outfit: dict | None = None):
    payload = {
        "face": {"hair_colour": "black", "hair_temperature": "neutral"},
        "makeup_preferences": {"intensity": "natural"},
    }
    if outfit:
        payload["context"] = {"outfit": outfit}
    return to_canonical_profile(payload)


def test_black_hair_neutral_temperature_ranks_black_brown_first_soft_black_after():
    # Full catalogue: the property is an ordering one — the limit cut must not
    # decide whether the secondary row is visible.
    result = eyes.recommend(_brow_profile(), limit=40)
    brow_rows = [
        item for item in result.items
        if "brow_hair_depth_temperature_match" in item.reason_codes
    ]
    assert brow_rows, "black + neutral hair must hit the primary brow row"
    names = [item.shade_name for item in brow_rows]
    assert names[0] == "Black Brown"
    assert "Soft Black" in names, "the secondary brow row must rank within the catalogue"
    assert names.index("Black Brown") < names.index("Soft Black")
    black_brown = next(item for item in brow_rows if item.shade_name == "Black Brown")
    soft_black = next(item for item in brow_rows if item.shade_name == "Soft Black")
    assert black_brown.score > soft_black.score


def test_loud_outfit_produces_identical_brow_order():
    quiet = eyes.recommend(_brow_profile(), limit=40)
    loud = eyes.recommend(_brow_profile(outfit={"primary_colour": "fuchsia"}), limit=40)
    quiet_brows = [(i.product_id, i.shade_name, i.score) for i in quiet.items
                   if "brow_hair_depth_temperature_match" in i.reason_codes]
    loud_brows = [(i.product_id, i.shade_name, i.score) for i in loud.items
                  if "brow_hair_depth_temperature_match" in i.reason_codes]
    assert quiet_brows == loud_brows, "outfit is never a brow signal"


def test_blue_eye_copper_boost_is_signal_not_gate():
    profile = to_canonical_profile({"face": {"eye_colour": "blue"}})
    result = eyes.recommend(profile, limit=15)
    codes = {code for item in result.items for code in item.reason_codes}
    assert any(code.startswith("eye_colour_boost_") for code in codes), "blue must earn copper/plum boosts"
    # boosts never gate: unboosted products stay present as catalogue baselines
    baselines = [item for item in result.items if "catalogue_baseline" in item.reason_codes]
    assert baselines


def test_palette_is_one_candidate_with_single_sellable_sku_code():
    profile = to_canonical_profile({
        "face": {"eye_colour": "blue"},
        "skin": {"depth": "medium", "undertone": "warm"},
    })
    result = eyes.recommend(profile, limit=30)
    palettes = [item for item in result.items if item.product_id == "yv-eye-005"]
    assert len(palettes) == 1, "palette pans must never fan out into candidates"
    assert "palette_single_sellable_sku" in palettes[0].reason_codes


def test_low_information_profile_returns_catalogue_with_neutral_defaults():
    result = eyes.recommend(to_canonical_profile({}), limit=10)
    assert result.items
    # Dataset guidance defaults mascara toward brown/black even without profile
    # info — a catalogue default, not a personalised claim.
    mascara = [item for item in result.items if item.product_type == "Mascara"]
    assert mascara
    assert any("mascara_default_neutral_tone" in item.reason_codes for item in mascara)
    for item in result.items:
        assert 0.0 <= item.score <= 1.0
