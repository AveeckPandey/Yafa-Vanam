"""Token normalization, alias tables and the vocabulary registry.

The five datasets disagree on casing conventions (eyes.json hyphenates
"soft-glam"/"light-medium"; lips/cheeks underscore the same values), so every
comparison in the engine layer goes through normalize_token first. Original
values are never mutated — normalization is comparison-only.
"""
from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any, Iterable

from app.recommendation.canonical.schemas import CanonicalProfile

logger = logging.getLogger(__name__)

_UNWANTED = {"-", " ", "."}


def normalize_token(value: Any) -> str:
    """Canonical comparison form: lowercase, [- . space] -> single underscore."""
    if value is None:
        return ""
    token = str(value).strip().lower()
    for character in _UNWANTED:
        token = token.replace(character, "_")
    while "__" in token:
        token = token.replace("__", "_")
    return token.strip("_")


def normalize_list(values: Iterable[Any] | None) -> list[str]:
    if not values:
        return []
    return [normalize_token(value) for value in values if normalize_token(value)]


# v1 OCCASIONS port (same merge semantics): free-text occasion -> canonical band.
OCCASION_ALIASES: dict[str, str] = {
    "everyday": "daily",
    "daily": "daily",
    "office": "daily",
    "work": "daily",
    "brunch": "daily",
    "day": "daily",
    "date": "evening",
    "date_night": "evening",
    "date_dinner": "evening",
    "evening": "evening",
    "night_out": "evening",
    "wedding": "special_occasion",
    "bridal": "special_occasion",
    "special_occasion": "special_occasion",
}


def canonical_occasion(value: Any) -> str | None:
    token = normalize_token(value)
    return OCCASION_ALIASES.get(token)


def expand_occasion(value: Any) -> set[str]:
    """All canonical bands a dataset occasion tag could represent.

    Used to compare profile occasions against per-shade occasion_tags lists
    without assuming the dataset picked the same word ("work" vs "daily").
    """
    token = normalize_token(value)
    canonical = OCCASION_ALIASES.get(token, token)
    return {canonical} if canonical else set()


# Compound dataset colour families -> component families they may be matched
# against. The datasets use compound tokens ("rose_peach", "terracotta_brick")
# where users say simple ones ("peach"); this keeps both directions working
# without resurrecting v1's name-substring guessing.
FAMILY_ALIASES: dict[str, frozenset[str]] = {
    "rose_peach": frozenset({"rose_pink", "peach"}),
    "terracotta_brick": frozenset({"terracotta", "brick"}),
    "plum_wine": frozenset({"plum", "wine", "berry"}),
    "nude_earth": frozenset({"nude", "brown"}),
    "brown_black": frozenset({"brown", "black"}),
    "woody_green_aromatic": frozenset({"woody", "green", "aromatic"}),
}


def family_matches(candidate_family: str | None, desired: str | None) -> bool:
    """True when a dataset colour family satisfies a requested family token,
    comparing through FAMILY_ALIASES in both directions."""
    if not candidate_family or not desired:
        return False
    candidate = normalize_token(candidate_family)
    wanted = normalize_token(desired)
    if candidate == wanted:
        return True
    return wanted in FAMILY_ALIASES.get(candidate, frozenset()) or candidate in FAMILY_ALIASES.get(wanted, frozenset())


class VocabularyRegistry:
    """Load-time observation of every enum-ish dataset value.

    Unknown values are logged once and retained; nothing ever raises here —
    structural breakage raises in adapters/base.py, vocabulary drift warns so
    datasets can evolve without code releases while still being noticed.
    """

    def __init__(self) -> None:
        self._known: dict[tuple[str, str], set[str]] = defaultdict(set)
        self._warned: set[tuple[str, str]] = set()

    def observe(self, category: str, field: str, values: Iterable[Any]) -> None:
        bucket = self._known[(normalize_token(category), normalize_token(field))]
        bucket.update(token for value in values if (token := normalize_token(value)))

    def known(self, category: str, field: str) -> frozenset[str]:
        return frozenset(self._known[(normalize_token(category), normalize_token(field))])

    def check(self, category: str, field: str, value: Any) -> str:
        """Return the normalized token, warning once if it was never observed."""
        token = normalize_token(value)
        if not token:
            return token
        key = (normalize_token(category), normalize_token(field))
        if token not in self._known[key] and (key, token) not in self._warned:
            logger.warning(
                "Unrecognized %s.%s value %r — kept verbatim, never invented around.",
                key[0], key[1], value,
            )
            self._warned.add((key, token))
        return token

    def warnings(self) -> list[str]:
        return [f"{key[0]}.{key[1]}:{token}" for key, token in sorted(self._warned)]

    def reset(self) -> None:
        self._known.clear()
        self._warned.clear()


REGISTRY = VocabularyRegistry()


def _get(data: dict[str, Any], *paths: str) -> Any:
    for path in paths:
        current: Any = data
        for key in path.split("."):
            current = current.get(key) if isinstance(current, dict) else None
        if current is not None:
            return current
    return None


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value.lower()]
    return [str(item).lower() for item in value]


def to_canonical_profile(raw: dict[str, Any] | None, context: dict[str, Any] | None = None) -> CanonicalProfile:
    """Accept the v1/advisor profile contract and produce a CanonicalProfile.

    Field-for-field port of v1.normalise_profile (same merge order, same
    legacy aliases: complexion.* fallbacks, preferences|makeup_preferences,
    safety_conditions|conditions) with normalized tokens and the original
    payload retained under `.raw`.
    """
    raw = raw or {}
    merged_context = {**(raw.get("context") or {}), **(context or {})}
    skin = raw.get("skin") or {}
    face = raw.get("face") or {}
    prefs = raw.get("makeup_preferences") or raw.get("preferences") or {}
    legacy_complexion = raw.get("complexion") or {}
    outfit = merged_context.get("outfit") or raw.get("outfit") or {}
    depth = _get(skin, "depth", "depth_family") or legacy_complexion.get("depth")
    shade_code = _get(skin, "shade_code") or legacy_complexion.get("shade_code")
    capture_confidence = _get(skin, "shade_confidence") or _get(raw, "skin_analyzer.capture_confidence")
    lab = _get(skin, "lab") or raw.get("lab") or _get(raw, "skin_analyzer.lab")

    def _float_or_none(value: Any) -> float | None:
        try:
            return float(value) if value is not None else None
        except (TypeError, ValueError):
            return None

    return CanonicalProfile(
        shade_code=str(shade_code).upper() if shade_code else None,
        shade_confirmed=bool(_get(skin, "shade_code") or legacy_complexion.get("confirmed")),
        depth=normalize_token(depth) or None,
        undertone=normalize_token(_get(skin, "undertone") or legacy_complexion.get("undertone")) or None,
        lab={key: float(lab[key]) for key in ("L", "a", "b")} if isinstance(lab, dict) and all(key in lab for key in ("L", "a", "b")) else None,
        capture_confidence=_float_or_none(capture_confidence),
        skin_types=[normalize_token(item) for item in _as_list(_get(skin, "skin_types", "type") or _get(raw, "skin.type")) if normalize_token(item)],
        concerns=[normalize_token(item) for item in _as_list(_get(skin, "concerns") or _get(raw, "safety_conditions")) if normalize_token(item)],
        sensitivity=normalize_token(_get(skin, "sensitivity")) or None,
        eye_colour=normalize_token(_get(face, "eye_colour")) or None,
        hair_colour=normalize_token(_get(face, "hair_colour")) or None,
        hair_depth=normalize_token(_get(face, "hair_depth")) or None,
        hair_temperature=normalize_token(_get(face, "hair_temperature")) or None,
        coverage=normalize_token(_get(prefs, "coverage")) or None,
        finish=normalize_token(_get(prefs, "finish")) or None,
        style=normalize_token(_get(prefs, "intensity", "style")) or None,
        lip_finish=normalize_token(_get(prefs, "preferred_lip_finish", "lip_finish")) or None,
        eye_intensity=normalize_token(_get(prefs, "preferred_eye_intensity", "eye_look")) or None,
        cheek_finish=normalize_token(_get(prefs, "preferred_cheek_finish")) or None,
        occasion=normalize_token(merged_context.get("occasion") or raw.get("occasion")) or None,
        daypart=normalize_token(merged_context.get("daypart")) or None,
        season=normalize_token(merged_context.get("season")) or None,
        outfit=dict(outfit) if isinstance(outfit, dict) and outfit else None,
        fragrance=dict(raw["fragrance_preferences"]) if raw.get("fragrance_preferences") else None,
        safety_conditions={
            token
            for token in (
                normalize_token(item)
                for item in _as_list(raw.get("safety_conditions"))
                + _as_list(_get(skin, "safety_conditions"))
                + _as_list(raw.get("conditions"))
            )
            if token
        },
        raw=dict(raw),
    )


def from_beauty_profile(profile: Any, context: dict[str, Any] | None = None) -> CanonicalProfile:
    """Adapter-model convenience alias.

    Accepts anything shaped like app/models/user_profile.UserBeautyProfile or
    the advisor BeautyProfile (skin/face/makeup_preferences keys), dumped or
    as a pydantic model — both flow through to_canonical_profile unchanged.
    """
    if hasattr(profile, "model_dump"):
        try:
            profile = profile.model_dump(exclude_none=False)
        except TypeError:  # duck-typed models without pydantic's kwargs
            profile = profile.model_dump()
    return to_canonical_profile(profile, context)


# Backwards-friendly short name used by engines/tests.
from_v1_payload = to_canonical_profile
