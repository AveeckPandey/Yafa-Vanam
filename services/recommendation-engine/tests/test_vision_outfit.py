"""Outfit vision boundary tests (Phase 3 spec sections 18-20).

Synthetic images prove the deterministic CV pipeline; the boundary assertion
(outfit vision never selects products) is enforced structurally: the output
schema has no product fields.
"""
from __future__ import annotations

import io

import numpy as np
from PIL import Image

from app.vision.outfit import analyse_outfit_image


def _image(rgb_colour: tuple[int, int, int], size: int = 220) -> bytes:
    array = np.zeros((size, size, 3), dtype=np.uint8)
    array[:, :] = rgb_colour
    buffer = io.BytesIO()
    Image.fromarray(array).save(buffer, format="PNG")
    return buffer.getvalue()


def _split_image(
    left: tuple[int, int, int], right: tuple[int, int, int], size: int = 220
) -> bytes:
    array = np.zeros((size, size, 3), dtype=np.uint8)
    array[:, : size // 2] = left
    array[:, size // 2 :] = right
    buffer = io.BytesIO()
    Image.fromarray(array).save(buffer, format="PNG")
    return buffer.getvalue()


def test_solid_emerald_outfit_is_detected():
    result = analyse_outfit_image(_image((22, 118, 82)))
    assert result["primary_colour"] == "emerald"
    assert result["confidence"] > 0.5
    assert result["pattern"] is False


def test_navy_is_not_misread_as_black():
    # Bright navy and shadow-dark navy must both read as navy.
    for rgb in ((24, 38, 78), (16, 26, 52)):
        result = analyse_outfit_image(_image(rgb))
        assert result["primary_colour"] == "navy", f"{rgb} -> {result['primary_colour']}"


def test_truly_achromatic_dark_stays_black():
    result = analyse_outfit_image(_image((12, 12, 14)))
    assert result["primary_colour"] == "black"


def test_warm_off_whites_separate_from_white():
    cream = analyse_outfit_image(_image((245, 238, 220)))
    beige = analyse_outfit_image(_image((222, 205, 182)))
    pure_white = analyse_outfit_image(_image((252, 252, 250)))
    assert cream["primary_colour"] in {"cream", "beige"}
    assert beige["primary_colour"] in {"beige", "cream"}
    assert pure_white["primary_colour"] == "white"


def test_uncertain_colour_surfaces_runner_up():
    # Shadowed navy sits close to black: runner-up must be exposed so the
    # caller can be honest instead of confidently inventing the colour.
    result = analyse_outfit_image(_image((16, 26, 52)))
    if result["confidence"] < 0.75:
        assert result.get("runner_up_colour"), "low confidence needs an alternative"
        assert result["runner_up_colour"] in {"black", "charcoal"}


def test_two_colour_outfit_reports_secondary():
    result = analyse_outfit_image(_split_image((22, 118, 82), (201, 162, 71)))
    assert result["primary_colour"] == "emerald"
    assert "gold" in result["secondary_colours"]


def test_unreadable_bytes_raise_value_error():
    import pytest

    with pytest.raises(ValueError):
        analyse_outfit_image(b"not-an-image")


def test_output_is_structured_attributes_only():
    result = analyse_outfit_image(_image((28, 44, 84)))
    allowed_keys = {
        "primary_colour",
        "runner_up_colour",
        "secondary_colours",
        "colour_families",
        "style",
        "pattern",
        "confidence",
    }
    assert set(result.keys()) <= allowed_keys
    # Boundary: no product/recommendation leakage is possible by schema.
    for forbidden in ("products", "recommendations", "product_id", "score"):
        assert forbidden not in result
