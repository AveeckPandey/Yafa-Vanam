"""Engine registry: category -> recommend(profile, *, limit, coordination, debug).

One uniform signature is the M4 orchestrator contract. `skin`/`no_shades`
dataset names map to their user-facing categories (complexion/skincare +
fragrance).
"""
from __future__ import annotations

from typing import Callable

from app.recommendation.canonical.schemas import (
    CanonicalProfile,
    CoordinationHints,
    EngineResult,
)
from app.recommendation.engines import cheeks, complexion, eyes, fragrance, lips, skincare

EngineFn = Callable[..., EngineResult]

ENGINE_REGISTRY: dict[str, EngineFn] = {
    "complexion": complexion.recommend,
    "lips": lips.recommend,
    "cheeks": cheeks.recommend,
    "eyes": eyes.recommend,
    "skincare": skincare.recommend,
    "fragrance": fragrance.recommend,
}

# Dataset file -> engine categories served from it.
DATASET_ENGINES: dict[str, tuple[str, ...]] = {
    "skin": ("complexion",),
    "no_shades": ("skincare", "fragrance"),
    "lips": ("lips",),
    "cheeks": ("cheeks",),
    "eyes": ("eyes",),
}


def get_engine(category: str) -> EngineFn:
    try:
        return ENGINE_REGISTRY[category]
    except KeyError:
        raise KeyError(f"no recommendation engine for category {category!r}") from None


__all__ = [
    "ENGINE_REGISTRY",
    "DATASET_ENGINES",
    "EngineFn",
    "get_engine",
    "CanonicalProfile",
    "CoordinationHints",
    "EngineResult",
]
