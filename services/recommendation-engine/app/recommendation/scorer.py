"""Weighted-factor accumulator shared by every category engine.

Two normalizations, both candidate-mix-independent (golden tests stay stable):

- makeup: score = sum(w_i * s_i for PRESENT factors) / sum(w_i for PRESENT
  factors), clamped to [0,1]. A factor whose profile input is missing is
  omitted from numerator AND denominator — that is how "never invent missing
  profile values" is enforced mechanically. An empty profile scores exactly
  CATALOGUE_BASELINE_SCORE.
- skincare: signed raw signal sum over the dataset's own scale, mapped
  linearly through the named NORMALIZATION_MIN/MAX knobs; the raw sum stays
  in the breakdown so every mapping is auditable.
"""
from __future__ import annotations

from typing import Any

from app.recommendation.weights import CATALOGUE_BASELINE_SCORE, MakeupWeights, SKINCARE_SCALE


class FactorAccumulator:
    def __init__(self, weights: MakeupWeights | None = None) -> None:
        self._weights = weights
        self._satisfied: dict[str, float] = {}   # factor -> graded fit 0..1 (present factors only)
        self._raw_sum: float = 0.0               # skincare raw signal total
        self.reason_codes: list[str] = []
        self.warnings: list[str] = []

    # -- makeup path -----------------------------------------------------
    def credit(self, factor: str, satisfied: bool | float, *codes: str, warning: str | None = None) -> None:
        """Record a factor ONLY when its profile input exists and is satisfied.

        False/None/0 input records nothing (factor absent from normalization);
        True records full weight; a float in (0,1) grades it. Codes attach
        whenever the factor contributes anything.
        """
        if satisfied is None or satisfied is False:
            return
        strength = 1.0 if satisfied is True else float(satisfied)
        if not 0.0 < strength <= 1.0:
            strength = max(0.0, min(1.0, strength))
            if strength == 0.0:
                return
        self._satisfied[factor] = max(self._satisfied.get(factor, 0.0), strength)
        if warning and warning not in self.warnings:
            self.warnings.append(warning)
        for code in codes:
            if code and code not in self.reason_codes:
                self.reason_codes.append(code)

    def baseline(self) -> None:
        """Mark pure-catalogue candidates (no profile signal fired)."""
        if not self._satisfied:
            self.reason_codes.append("catalogue_baseline")

    # -- skincare signed path ---------------------------------------------
    def add_signal(self, value: float, *codes: str, warning: str | None = None) -> None:
        """Add one dataset-scale (+2..-2) signal to the raw sum."""
        if value == 0:
            return
        self._raw_sum += value
        if warning and warning not in self.warnings:
            self.warnings.append(warning)
        for code in codes:
            if code and code not in self.reason_codes:
                self.reason_codes.append(code)

    penalize = add_signal  # readability alias for negative contributions

    # -- finalization -------------------------------------------------------
    def finalize_makeup(self) -> tuple[float, dict[str, float]]:
        breakdown: dict[str, float] = {}
        numerator = 0.0
        denominator = 0.0
        for name, weight in (self._weights.factors if self._weights else []):
            if name in self._satisfied:
                strength = self._satisfied[name]
                numerator += weight * strength
                denominator += weight
                breakdown[name] = round(weight * strength, 3)  # weighted points earned
        if denominator == 0.0:
            return CATALOGUE_BASELINE_SCORE, {}
        return max(0.0, min(1.0, numerator / denominator)), breakdown

    def finalize_skincare(self) -> tuple[float, dict[str, float]]:
        scale = SKINCARE_SCALE
        span = scale.NORMALIZATION_MAX - scale.NORMALIZATION_MIN
        score = max(0.0, min(1.0, (self._raw_sum - scale.NORMALIZATION_MIN) / span))
        breakdown: dict[str, float] = {
            "raw_signal_sum": round(self._raw_sum, 3),
            "normalization_min": scale.NORMALIZATION_MIN,
            "normalization_max": scale.NORMALIZATION_MAX,
        }
        return score, breakdown
