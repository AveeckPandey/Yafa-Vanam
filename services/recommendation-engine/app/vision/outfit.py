"""Outfit vision: photo -> structured styling attributes ONLY (Phase 3 18-20).

Boundary: this analyzer NEVER recommends products. It extracts colours,
pattern and a coarse formality hint so the recommendation engines can rank.
Everything is deterministic CV (k-means in CIELAB) - no external vision API,
and no identity, demographic or personality inference.

Colour accuracy notes: nearest-neighbour matching alone confuses dark
blue-leaning fabrics (navy) with black, and warm off-whites (cream/beige)
with white. Rule-based post-processing in Lab space separates those families;
when two candidates are close, the runner-up is returned so the caller can be
honest about uncertainty instead of inventing a confident colour.
"""
from __future__ import annotations

import io
from typing import Any

import cv2
import numpy as np
from PIL import Image, UnidentifiedImageError

# Outfit colour vocabulary - keys mirror v1's OUTFIT_FAMILIES harmony table so
# extracted tokens plug straight into engine outfit signals.
_COLOUR_REFERENCES: dict[str, tuple[int, int, int]] = {
    "emerald": (22, 118, 82),
    "green": (58, 125, 68),
    "gold": (201, 162, 71),
    "red": (178, 44, 48),
    "burgundy": (108, 32, 48),
    "maroon": (94, 34, 44),
    "blue": (52, 92, 158),
    "navy": (24, 38, 78),
    "purple": (112, 66, 148),
    "pink": (222, 143, 158),
    "orange": (216, 116, 52),
    "peach": (240, 184, 152),
    "terracotta": (178, 102, 74),
    "black": (14, 14, 16),
    "charcoal": (56, 58, 62),
    "grey": (128, 130, 132),
    "silver": (188, 190, 194),
    "white": (250, 250, 248),
    "cream": (245, 238, 220),
    "beige": (222, 205, 182),
    "brown": (98, 68, 48),
    "olive": (96, 104, 52),
}

_FORMAL_COLOURS = frozenset({"black", "navy", "burgundy", "emerald"})
_MAX_MATCH_DISTANCE = 60.0  # CIELAB units; beyond this a cluster stays unnamed


def _srgb_to_lab(rgb: np.ndarray) -> np.ndarray:
    """Vectorised sRGB -> CIELAB for an Nx3 array."""
    values = rgb.astype(np.float64) / 255.0
    values = np.where(
        values <= 0.04045, values / 12.92, ((values + 0.055) / 1.055) ** 2.4
    )
    matrix = np.array(
        [
            [0.4124564, 0.3575761, 0.1804375],
            [0.2126729, 0.7151522, 0.0721750],
            [0.0193339, 0.1191920, 0.9503041],
        ]
    )
    xyz = values @ matrix.T / np.array([0.95047, 1.0, 1.08883])
    xyz = np.where(xyz > 0.008856, np.cbrt(xyz), 7.787 * xyz + 16.0 / 116.0)
    lab = np.empty_like(xyz)
    lab[:, 0] = 116.0 * xyz[:, 1] - 16.0
    lab[:, 1] = 500.0 * (xyz[:, 0] - xyz[:, 1])
    lab[:, 2] = 200.0 * (xyz[:, 1] - xyz[:, 2])
    return lab


def _reference_labs() -> dict[str, tuple[float, float, float]]:
    return {
        name: tuple(_srgb_to_lab(np.array([rgb], dtype=np.uint8))[0])
        for name, rgb in _COLOUR_REFERENCES.items()
    }


def _ranked_colour_matches(lab: np.ndarray) -> list[tuple[str, float]]:
    """All reference colours ordered by Lab distance (closest first)."""
    refs = _reference_labs()
    ranked = sorted(
        ((name, float(np.linalg.norm(lab - np.array(reference)))) for name, reference in refs.items()),
        key=lambda item: item[1],
    )
    return ranked


def _refine_dark_and_light(name: str, lab: np.ndarray) -> str | None:
    """Rule-based disambiguation for families nearest-neighbour gets wrong.

    Dark blues photographed in shadow carry very low L and sit numerically
    closer to the black reference than to navy; near-whites with any warmth
    land on white. Chroma/hue rules correct both without inventing colours.
    """
    lightness, a_star, b_star = float(lab[0]), float(lab[1]), float(lab[2])
    chroma = (a_star**2 + b_star**2) ** 0.5

    if name == "black":
        if chroma >= 3.0 and b_star <= -2.5:
            return "navy"          # blue-leaning dark fabric
        if chroma < 3.0:
            if lightness > 30:
                return "grey"
            if lightness >= 12:
                return "charcoal"
        return None                # keep black

    if name == "navy":
        if chroma < 3.0 and lightness < 12:
            return "black"         # truly achromatic darkness
        return None

    if name == "white":
        if chroma >= 2.0 and b_star >= 3.0:
            return "cream" if lightness >= 88 else "beige"
        if chroma >= 8.0:
            return "beige"
        return None

    return None


def _nearest_colour(lab: np.ndarray) -> tuple[str | None, float, str | None]:
    """Nearest reference colour after rule refinement, plus honest runner-up."""
    ranked = _ranked_colour_matches(lab)
    distances = dict(ranked)
    best_name, best_distance = ranked[0]
    refined = _refine_dark_and_light(best_name, lab)

    if refined is not None and refined != best_name:
        # Rule refinement overrides the raw winner; the previous nearest
        # becomes the honest alternative ("looks navy, might be black").
        return refined, distances.get(refined, best_distance), best_name

    runner_up = next((n for n, _d in ranked[1:] if n != best_name), None)
    margin = ranked[1][1] - best_distance if len(ranked) > 1 else 99.0
    # Two plausible answers within ~8 Lab units: keep the winner but surface
    # the alternative so callers can express uncertainty.
    if margin < 8.0 and runner_up:
        ambiguous_pair = {best_name, runner_up}
        if ambiguous_pair <= {"navy", "black", "charcoal"} or ambiguous_pair <= {
            "cream", "beige", "white"
        } or ambiguous_pair <= {"grey", "charcoal", "silver"}:
            return best_name, best_distance, runner_up
    return best_name, best_distance, None


def analyse_outfit_image(image_bytes: bytes) -> dict[str, Any]:
    """Analyse in memory; return derived attributes only; never persist."""
    try:
        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    except (UnidentifiedImageError, OSError) as error:
        raise ValueError("unreadable image") from error

    max_side = 256
    image.thumbnail((max_side, max_side))
    rgb = np.asarray(image).reshape(-1, 3)

    samples = _srgb_to_lab(rgb).astype(np.float32)
    criteria = (
        cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER,
        25,
        0.5,
    )
    _, labels, centroids = cv2.kmeans(
        samples, 4, None, criteria, 3, cv2.KMEANS_PP_CENTERS
    )
    counts = np.bincount(labels.flatten(), minlength=4)
    order = np.argsort(-counts)
    total = float(counts.sum())

    named: list[tuple[str, float]] = []
    primary_confidence = 0.0
    primary_runner_up: str | None = None
    for index in order:
        share = counts[index] / total
        name, distance, runner_up = _nearest_colour(centroids[index].astype(np.float64))
        if name is None:
            continue
        proximity = max(0.0, 1.0 - distance / _MAX_MATCH_DISTANCE)
        if not named:
            primary_confidence = round(min(0.97, 0.55 * proximity + 0.45 * share), 3)
            if runner_up:
                # Ambiguity must lower expressed confidence, never hide it.
                primary_confidence = round(primary_confidence * 0.75, 3)
                primary_runner_up = runner_up
            named.append((name, share))
        elif share >= 0.12 and name != named[0][0]:
            named.append((name, share))
        if len(named) >= 3:
            break

    if not named:
        return {
            "primary_colour": None,
            "runner_up_colour": None,
            "secondary_colours": [],
            "colour_families": [],
            "style": None,
            "pattern": True,
            "confidence": 0.0,
        }

    primary = named[0][0]
    secondary_names: list[str] = []
    for name, _share in named[1:]:
        if name != primary and name not in secondary_names:
            secondary_names.append(name)

    top_share = counts[order[0]] / total
    pattern = bool(top_share < 0.45 or len(secondary_names) >= 2)
    style = "formal" if (primary in _FORMAL_COLOURS and not pattern) else None

    families = [primary] + [name for name in secondary_names]
    return {
        "primary_colour": primary,
        "runner_up_colour": primary_runner_up,
        "secondary_colours": secondary_names[:2],
        "colour_families": families[:3],
        "style": style,
        "pattern": pattern,
        "confidence": primary_confidence,
    }


__all__ = ["analyse_outfit_image"]
