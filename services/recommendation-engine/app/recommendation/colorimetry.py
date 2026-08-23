"""Colour science shared by the complexion engine and confidence model.

ciede2000 is copied verbatim from app/v1.py (Sharma et al. CIEDE2000) so the
legacy stack stays byte-identical this pass; the two implementations are
pinned equal by tests/test_recommendation_colorimetry.py and get deduplicated
at the parity milestone. Band classification and piecewise confidence read
their thresholds/anchors from skin.json's skin_matching_engine — never from
hardcoded numbers here.
"""
from __future__ import annotations

import math
from typing import Any, Sequence

from app.recommendation.canonical.enums import MatchClass


def ciede2000(first: tuple[float, float, float], second: tuple[float, float, float]) -> float:
    # CIEDE2000 (Sharma et al.) implemented locally to avoid a scientific-runtime dependency.
    l1, a1, b1 = first; l2, a2, b2 = second; avg_l = (l1 + l2) / 2
    c1, c2 = math.hypot(a1, b1), math.hypot(a2, b2); avg_c = (c1 + c2) / 2
    g = .5 * (1 - math.sqrt(avg_c**7 / (avg_c**7 + 25**7))); a1p, a2p = (1 + g) * a1, (1 + g) * a2
    c1p, c2p = math.hypot(a1p, b1), math.hypot(a2p, b2)
    h1, h2 = math.degrees(math.atan2(b1, a1p)) % 360, math.degrees(math.atan2(b2, a2p)) % 360
    dl, dc = l2 - l1, c2p - c1p; dh = h2 - h1
    if c1p * c2p == 0: dh = 0
    elif dh > 180: dh -= 360
    elif dh < -180: dh += 360
    d_h = 2 * math.sqrt(c1p * c2p) * math.sin(math.radians(dh / 2)); avg_lp, avg_cp = (l1 + l2) / 2, (c1p + c2p) / 2
    if c1p * c2p == 0: avg_h = h1 + h2
    elif abs(h1 - h2) <= 180: avg_h = (h1 + h2) / 2
    elif h1 + h2 < 360: avg_h = (h1 + h2 + 360) / 2
    else: avg_h = (h1 + h2 - 360) / 2
    t = 1 - .17 * math.cos(math.radians(avg_h - 30)) + .24 * math.cos(math.radians(2 * avg_h)) + .32 * math.cos(math.radians(3 * avg_h + 6)) - .20 * math.cos(math.radians(4 * avg_h - 63))
    sl = 1 + .015 * (avg_lp - 50) ** 2 / math.sqrt(20 + (avg_lp - 50) ** 2); sc = 1 + .045 * avg_cp; sh = 1 + .015 * avg_cp * t
    rt = -2 * math.sqrt(avg_cp**7 / (avg_cp**7 + 25**7)) * math.sin(math.radians(60 * math.exp(-((avg_h - 275) / 25) ** 2)))
    return math.sqrt((dl / sl) ** 2 + (dc / sc) ** 2 + (d_h / sh) ** 2 + rt * (dc / sc) * (d_h / sh))


def classify_delta_e(delta_e: float, thresholds: Sequence[dict[str, Any]]) -> MatchClass:
    """Map a ΔE00 value onto the dataset's ordered band table.

    Bands are [{max, class}, {min_exclusive, max, class}, ...]; the first
    matching band wins. An unmatched tail entry ({min_exclusive} only) is the
    fallback class.
    """
    for band in thresholds:
        low = band.get("min_exclusive")
        high = band.get("max")
        if low is not None and delta_e <= float(low):
            continue
        if high is not None and delta_e > float(high):
            continue
        return MatchClass(band["class"])
    return MatchClass.MISMATCH


def piecewise_confidence(
    delta_e: float,
    anchors: Sequence[dict[str, Any]],
    capture_confidence: float | None = None,
) -> float:
    """Linear interpolation between the dataset's {delta_e00 -> score} anchors.

    Beyond the last anchor the score is 0. When a capture_confidence is given
    the overall figure follows the dataset rule min(match_score, capture).
    """
    points = sorted(((float(a["delta_e00"]), float(a["score"])) for a in anchors))
    if not points:
        return 0.0
    if delta_e <= points[0][0]:
        score = points[0][1]
    elif delta_e >= points[-1][0]:
        score = 0.0
    else:
        score = 0.0
        for (x0, y0), (x1, y1) in zip(points, points[1:]):
            if x0 <= delta_e <= x1:
                span = x1 - x0
                score = y0 if span == 0 else y0 + (y1 - y0) * (delta_e - x0) / span
                break
    if capture_confidence is not None:
        score = min(score, float(capture_confidence))
    return round(score, 3)
