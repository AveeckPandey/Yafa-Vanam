"""Per-category weight tables — the single configuration point (spec §7/§9/§12).

The datasets already embed these exact tables (lip_recommendation_rules.weights
etc.). Code defaults here are pinned by tests; effective_weights() prefers the
dataset's table and warns on drift, so data stays authoritative without any
engine ever hand-copying a number.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Mapping

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class MakeupWeights:
    """Ordered factor -> weight table for one makeup category."""

    factors: tuple[tuple[str, float], ...]

    def weight_of(self, factor: str) -> float:
        return dict(self.factors).get(factor, 0.0)

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(name for name, _ in self.factors)


LIP_WEIGHTS = MakeupWeights((
    ("user_requested_product_or_finish", 1.0),
    ("desired_color_family", 0.9),
    ("complexion_depth_as_contrast_signal", 0.7),
    ("undertone_compatibility", 0.65),
    ("occasion_and_look_style", 0.6),
    ("outfit_harmony", 0.45),
    ("liner_pairing_if_requested", 0.4),
))

CHEEK_WEIGHTS = MakeupWeights((
    ("user_requested_product_format_or_finish", 1.0),
    ("desired_color_family", 0.9),
    ("complexion_depth_intensity_fit", 0.75),
    ("undertone_compatibility", 0.65),
    ("occasion_and_look_style", 0.6),
    ("outfit_harmony", 0.45),
    ("lip_coordination_if_requested", 0.4),
))

EYE_WEIGHTS = MakeupWeights((
    ("user_requested_product_or_look", 1.0),
    ("product_type_fit", 0.95),
    ("eye_colour_compatibility", 0.8),
    ("desired_intensity", 0.75),
    ("daypart_and_occasion", 0.7),
    ("undertone_compatibility", 0.55),
    ("outfit_harmony", 0.4),
    ("complexion_depth_as_intensity_tuning", 0.3),
))

# Code-owned tables for categories the datasets do NOT carry weight blocks for
# (complexion formula stage, fragrance). Kept here — never inside functions —
# so every tunable lives in exactly one module.
COMPLEXION_FORMULA_WEIGHTS = MakeupWeights((
    ("skin_type_fit", 1.0),
    ("finish_preference", 0.9),
    ("coverage_preference", 0.8),
    ("occasion_wear_goal", 0.6),
))

FRAGRANCE_WEIGHTS = MakeupWeights((
    ("scent_profile_overlap", 1.0),
    ("season_and_occasion", 0.6),
    ("intensity_positioning", 0.4),
))


@dataclass(frozen=True)
class SkincareScale:
    """The datasets' own constant scoring scale (recommendation_profile.scoring_model)."""

    BEST_FOR_MATCH: float = 2.0
    COMPATIBLE_MATCH: float = 1.0
    SUPPORTING_FEATURE: float = 0.5
    MINOR_MISMATCH: float = -0.5
    TOLERANCE_CONCERN: float = -1.0
    SIGNIFICANT_IRRITATION_CONCERN: float = -2.0
    HARD_EXCLUSION: str = "reject"

    # Named calibration knobs: the only two numbers M3 tuning should touch.
    NORMALIZATION_MIN: float = -3.0   # irritation (-2) co-firing with tolerance (-1)
    NORMALIZATION_MAX: float = 4.0    # best_for + supporting features + pairing headroom


SKINCARE_SCALE = SkincareScale()

# Cheek->lip orchestration boost (spec Phase 2 §11): when the orchestrator
# passes CoordinationHints.lip_color_family, a matching lip family earns the
# existing desired_color_family factor at this graded strength (explicit user
# family requests always outrank it via max() in the accumulator).
CHEEK_LIP_COORDINATION_STRENGTH = 0.6

# Baseline score when a profile carries no signal at all — mirrors v1's
# catalogue_fit behaviour: everything degrades gracefully to comparable 0..1.
CATALOGUE_BASELINE_SCORE = 0.5


def effective_weights(
    category: str,
    dataset_table: Mapping[str, Any] | None,
    default: MakeupWeights,
) -> MakeupWeights:
    """Dataset table wins; code default is the tested fallback.

    Drift (dataset value != default) logs a WARNING naming the factor so the
    divergence is visible without breaking ranking.
    """
    if not dataset_table:
        return default
    resolved: list[tuple[str, float]] = []
    for name, code_weight in default.factors:
        if name in dataset_table:
            data_weight = float(dataset_table[name])
            if abs(data_weight - code_weight) > 1e-9:
                logger.warning(
                    "%s weight drift for %r: dataset=%.3f code-default=%.3f (using dataset)",
                    category, name, data_weight, code_weight,
                )
            resolved.append((name, data_weight))
        else:
            resolved.append((name, code_weight))
    extra = {str(key): float(value) for key, value in dataset_table.items()
             if key not in default.names and isinstance(value, (int, float))}
    for name, weight in sorted(extra.items()):
        logger.warning("%s has dataset-only weight %r=%.3f (no engine factor uses it)", category, name, weight)
    return MakeupWeights(tuple(resolved))
