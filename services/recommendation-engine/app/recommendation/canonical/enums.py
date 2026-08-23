"""Canonical enums: closed vocabularies the engines actually branch on.

Deliberately small. Large descriptive vocabularies (goals, concerns, colour
families, fragrance facets/moods, ...) are NOT enums — they evolve with the
datasets (the goals list has already drifted 41 -> 43 values) and are tracked
by canonical.normalization.VocabularyRegistry instead: unknown values warn,
never raise. Only vocabularies where code takes a different branch per value
get a real enum here.
"""
from __future__ import annotations

from enum import StrEnum

# Sentinel for "the user never gave us this". Distinct from "" / None so a
# deliberately empty answer can never be mistaken for a missing one.
UNSET = "<unset>"


class Undertone(StrEnum):
    COOL = "cool"
    NEUTRAL = "neutral"
    WARM = "warm"
    OLIVE = "olive"


class ShadeAxis(StrEnum):
    """earth_skin_24 undertone codes (C/N/W/O)."""

    C = "C"
    N = "N"
    W = "W"
    O = "O"


class Occasion(StrEnum):
    DAILY = "daily"
    EVENING = "evening"
    SPECIAL_OCCASION = "special_occasion"


class Daypart(StrEnum):
    DAY = "day"
    EVENING = "evening"


class DepthBand(StrEnum):
    FAIR = "fair"
    LIGHT = "light"
    LIGHT_MEDIUM = "light_medium"
    MEDIUM = "medium"
    MEDIUM_TAN = "medium_tan"
    TAN = "tan"
    DEEP = "deep"
    VERY_DEEP = "very_deep"


class MatchClass(StrEnum):
    EXACT_MATCH = "exact_match"
    BLENDABLE_MATCH = "blendable_match"
    BOUNDARY_NEIGHBOR = "boundary_neighbor"
    MISMATCH = "mismatch"


# depth family -> earth_skin_24 depth_index (mirrors v1._depth_index)
DEPTH_TO_INDEX: dict[str, int] = {
    DepthBand.FAIR: 1,
    DepthBand.LIGHT: 2,
    DepthBand.LIGHT_MEDIUM: 3,
    DepthBand.MEDIUM: 4,
    DepthBand.MEDIUM_TAN: 5,
    DepthBand.TAN: 6,
    DepthBand.DEEP: 7,
    DepthBand.VERY_DEEP: 8,
}

# profile undertone word -> shade axis letter. Used ONLY by the complexion
# stage; makeup categories string-match dataset lists directly.
AXIS_ALIASES: dict[str, ShadeAxis] = {
    "cool": ShadeAxis.C,
    "neutral": ShadeAxis.N,
    "warm": ShadeAxis.W,
    "olive": ShadeAxis.O,
}


def depth_index_for(depth: str | None) -> int | None:
    if not depth:
        return None
    return DEPTH_TO_INDEX.get(str(depth).strip().lower())


def axis_for(undertone: str | None) -> ShadeAxis | None:
    if not undertone:
        return None
    return AXIS_ALIASES.get(str(undertone).strip().lower())
