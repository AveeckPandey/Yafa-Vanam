"""Colour science: verbatim v1 parity, dataset band boundaries, anchor model."""
from __future__ import annotations

import pytest

from app.recommendation.adapters import get_adapter
from app.recommendation.canonical.enums import MatchClass
from app.recommendation.colorimetry import ciede2000, classify_delta_e, piecewise_confidence


def _labs() -> list[tuple[float, float, float]]:
    labs = []
    for shade in get_adapter("skin").shade_records():
        lab = (shade.get("measured_colour") or {}).get("cielab")
        if lab:
            labs.append((float(lab["L"]), float(lab["a"]), float(lab["b"])))
    return labs


def test_ciede2000_matches_v1_across_every_shade_pair():
    from app.v1 import ciede2000 as v1_ciede2000

    labs = _labs()
    assert len(labs) == 24
    for first in labs:
        for second in labs:
            ours = ciede2000(first, second)
            theirs = v1_ciede2000(first, second)
            assert abs(ours - theirs) < 1e-12


def test_band_boundaries_honour_the_dataset_table_exactly():
    thresholds = get_adapter("skin").delta_e_thresholds()
    for band in thresholds:
        high = band.get("max")
        if high is None:
            continue  # tail band: {min_exclusive} only, no upper edge to probe
        edge = float(high)
        assert classify_delta_e(edge, thresholds) == MatchClass(band["class"])
        if band.get("min_exclusive") is not None:
            assert classify_delta_e(edge + 0.001, thresholds) != MatchClass(band["class"])


def test_dataset_carries_the_three_documented_match_bands():
    thresholds = get_adapter("skin").delta_e_thresholds()
    classes = {MatchClass(band["class"]) for band in thresholds}
    assert {"exact_match", "blendable_match", "boundary_neighbor"} <= classes


def test_confidence_anchors_interpolate_and_cap_by_capture():
    anchors = get_adapter("skin").confidence_anchors()
    points = sorted((float(a["delta_e00"]), float(a["score"])) for a in anchors)
    first_x, first_y = points[0]
    last_x, _ = points[-1]

    assert piecewise_confidence(first_x, anchors) == first_y  # perfect-match anchor (0 -> 100)
    exact_hits = [(x, y) for x, y in points if x > first_x and x == int(x)]
    if exact_hits:
        x, y = exact_hits[0]
        assert piecewise_confidence(x, anchors) == y
    assert piecewise_confidence(last_x + 10.0, anchors) == 0.0  # past the last anchor

    capped = piecewise_confidence(first_x, anchors, capture_confidence=0.5)
    assert capped == min(first_y, 0.5)  # overall follows min(match_score, capture)


@pytest.mark.parametrize("delta_e", [-0.5, 999.0])
def test_classifier_total_over_extreme_inputs(delta_e: float):
    thresholds = get_adapter("skin").delta_e_thresholds()
    assert isinstance(classify_delta_e(delta_e, thresholds), MatchClass)
