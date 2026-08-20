from __future__ import annotations

import io
import json
import math
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from PIL import Image, UnidentifiedImageError

from app.models.skin_analysis import ShadeCandidate, SkinAnalysis, SkinAnalysisResult

DATA_PATH = Path(__file__).resolve().parents[2] / "data" / "skin.json"


def _master_shades() -> list[dict[str, Any]]:
    document = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    # Each complexion formula carries the same canonical 24-shade system.
    product = next(item for item in document["products"] if item.get("product_type") == "Foundation")
    return [variant["shade"] for variant in product["variants"]]


def ciede2000(first: tuple[float, float, float], second: tuple[float, float, float]) -> float:
    l1, a1, b1 = first; l2, a2, b2 = second; avg_l = (l1 + l2) / 2
    c1, c2 = math.hypot(a1, b1), math.hypot(a2, b2); avg_c = (c1 + c2) / 2
    g = .5 * (1 - math.sqrt(avg_c**7 / (avg_c**7 + 25**7))); a1p, a2p = (1 + g) * a1, (1 + g) * a2
    c1p, c2p = math.hypot(a1p, b1), math.hypot(a2p, b2); h1, h2 = math.degrees(math.atan2(b1, a1p)) % 360, math.degrees(math.atan2(b2, a2p)) % 360
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


def select_three_shades(lab: tuple[float, float, float]) -> list[ShadeCandidate]:
    """Return useful neighbours, rather than arbitrary lighter/darker buckets."""
    ranked = []
    for shade in _master_shades():
        measured = shade.get("measured_colour", {}).get("cielab")
        if measured:
            ranked.append((ciede2000(lab, (measured["L"], measured["a"], measured["b"])), shade))
    ranked.sort(key=lambda item: (item[0], item[1]["code"]))
    best_distance, best = ranked[0]
    selected = [(best_distance, best, "best_match")]
    best_depth = best.get("depth_index")
    lighter = next((item for item in ranked[1:] if item[1].get("depth_index") == best_depth - 1), None)
    deeper = next((item for item in ranked[1:] if item[1].get("depth_index") == best_depth + 1), None)
    # Only use depth neighbours if they are competitive colour matches; otherwise use closest alternatives.
    for candidate, role in ((lighter, "slightly_lighter"), (deeper, "slightly_deeper")):
        if candidate and candidate[0] <= best_distance + 8 and candidate[1]["code"] not in {x[1]["code"] for x in selected}:
            selected.append((candidate[0], candidate[1], role))
    for distance, shade in ranked:
        if len(selected) == 3: break
        if shade["code"] not in {item[1]["code"] for item in selected}:
            role = "warmer_alternative" if shade.get("undertone") == "warm" else "undertone_alternative"
            selected.append((distance, shade, role))
    result = []
    for distance, shade, role in selected:
        confidence = max(.35, min(.95, 1 - distance / 25))
        result.append(ShadeCandidate(shade_code=shade["code"], shade_name=shade["name"], role=role, colour_distance=round(distance, 3), confidence=round(confidence, 3)))
    return result


def _rgb_to_lab(rgb: np.ndarray) -> tuple[float, float, float]:
    values = rgb.astype(float) / 255
    values = np.where(values <= .04045, values / 12.92, ((values + .055) / 1.055) ** 2.4)
    x, y, z = np.dot(values, np.array([[.4124564, .3575761, .1804375], [.2126729, .7151522, .072175], [.0193339, .119192, .9503041]])) / np.array([.95047, 1., 1.08883])
    x, y, z = [value ** (1 / 3) if value > .008856 else 7.787 * value + 16 / 116 for value in (x, y, z)]
    return (116 * y - 16, 500 * (x - y), 200 * (y - z))


def _ita(lab: tuple[float, float, float]) -> float:
    return math.degrees(math.atan2(lab[0] - 50, lab[2] if lab[2] else .001))


def _depth(l: float) -> str:
    return "fair" if l >= 80 else "light" if l >= 70 else "light_medium" if l >= 62 else "medium" if l >= 56 else "medium_tan" if l >= 50 else "tan" if l >= 43 else "deep" if l >= 35 else "rich"


def _undertone(a: float, b: float) -> str:
    if a < 11 and b > 19: return "olive"
    if b - a > 12: return "warm"
    if a - b > 2: return "cool"
    return "neutral"


def analyse_skin_image(image_bytes: bytes) -> SkinAnalysisResult:
    """Analyse bytes in memory and return derived data only; it never writes an image."""
    try:
        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    except (UnidentifiedImageError, OSError):
        return SkinAnalysisResult(quality_pass=False, issues=["invalid_image"], retake_required=True)
    rgb = np.asarray(image)
    height, width = rgb.shape[:2]
    issues: list[str] = []
    if min(height, width) < 240: issues.append("image_too_small")
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    brightness, blur = float(gray.mean()), float(cv2.Laplacian(gray, cv2.CV_64F).var())
    if brightness < 55: issues.append("low_light")
    if brightness > 225: issues.append("overexposure")
    if blur < 25: issues.append("blur")
    channel_mean = rgb.reshape(-1, 3).mean(axis=0)
    if abs(float(channel_mean[0] - channel_mean[2])) > 60: issues.append("strong_colour_cast")
    cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    faces = cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(100, 100))
    if len(faces) == 0: issues.append("no_face")
    elif len(faces) > 1: issues.append("multiple_faces")
    if issues:
        return SkinAnalysisResult(quality_pass=False, face_detected=len(faces) > 0, issues=issues, retake_required=True)
    x, y, face_w, face_h = faces[0]
    if min(face_w, face_h) < 120: return SkinAnalysisResult(quality_pass=False, face_detected=True, issues=["face_too_small"], retake_required=True)
    # Approximate cheek regions avoid the eye and mouth bands; landmarks can replace this in a later iteration.
    regions = [rgb[y + int(face_h*.45):y + int(face_h*.7), x + int(face_w*.12):x + int(face_w*.38)], rgb[y + int(face_h*.45):y + int(face_h*.7), x + int(face_w*.62):x + int(face_w*.88)]]
    sample = np.concatenate([region.reshape(-1, 3) for region in regions if region.size], axis=0)
    # Ignore highlights and deep shadows before averaging skin-region pixels.
    usable = sample[(sample.mean(axis=1) > 35) & (sample.mean(axis=1) < 235)]
    if len(usable) < 100: return SkinAnalysisResult(quality_pass=False, face_detected=True, issues=["unreliable_skin_visibility"], retake_required=True)
    mean_rgb = usable.mean(axis=0)
    lab = _rgb_to_lab(mean_rgb)
    candidates = select_three_shades(lab)
    confidence = max(.4, min(.95, .94 - candidates[0].colour_distance / 30 - (candidates[1].colour_distance - candidates[0].colour_distance < .3) * .12))
    return SkinAnalysisResult(quality_pass=True, face_detected=True, analysis=SkinAnalysis(lab={"L": round(lab[0], 2), "a": round(lab[1], 2), "b": round(lab[2], 2)}, ita=round(_ita(lab), 2), depth_family=_depth(lab[0]), undertone=_undertone(lab[1], lab[2])), shade_candidates=candidates, confidence=round(confidence, 3))
