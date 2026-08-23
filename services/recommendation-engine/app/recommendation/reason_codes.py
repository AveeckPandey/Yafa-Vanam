"""Canonical machine-readable reason codes (snake_case).

Engines emit codes ONLY through these constants/builders so the vocabulary
stays contract-stable for the frontend and the Yafa orchestrator. Prose
rendering belongs to a later milestone; nothing here is customer copy.
"""
from __future__ import annotations

from app.recommendation.canonical.normalization import normalize_token

# -- catalogue / safety ------------------------------------------------
CATALOGUE_BASELINE = "catalogue_baseline"
SKIN_TYPE_BEST_FOR = "skin_type_best_for"
SKIN_TYPE_COMPATIBLE = "skin_type_compatible"
SKIN_TYPE_CAUTION_PENALTY = "skin_type_caution_penalty"

def hard_exclusion(condition: str) -> str:
    return f"hard_exclusion_{normalize_token(condition)}"


def soft_penalty(condition: str) -> str:
    return f"soft_penalty_{normalize_token(condition)}"


def compatibility_pairing(concept: str) -> str:
    return f"compatibility_positive_pairing_{normalize_token(concept)}"


COMPATIBILITY_REQUIRES_FORMULA_CONFIRMATION = "compatibility_requires_formula_confirmation"

# -- undertone / complexion -------------------------------------------
def undertone_match(undertone: str) -> str:
    return f"{normalize_token(undertone)}_undertone_match"


COMPLEXION_DEPTH_CONTRAST_MATCH = "complexion_depth_contrast_match"
COMPLEXION_DEPTH_INTENSITY_TUNED = "complexion_depth_intensity_tuned"

# -- colour family / outfit / look ------------------------------------
def desired_color_family(family: str) -> str:
    return f"desired_color_family_{normalize_token(family)}"


def outfit_harmony(outfit_colour: str) -> str:
    return f"{normalize_token(outfit_colour)}_outfit_harmony"


def look_style_priority(style: str) -> str:
    return f"look_style_{normalize_token(style)}_priority"


def occasion_match(occasion: str) -> str:
    return f"occasion_{normalize_token(occasion)}_match"


REQUESTED_FINISH_OR_PRODUCT_MATCH = "requested_finish_or_product_match"
DESIRED_INTENSITY_MATCH = "desired_intensity_match"

# -- eyes --------------------------------------------------------------
def eye_colour_boost(tone: str) -> str:
    return f"eye_colour_boost_{normalize_token(tone)}"


BROW_HAIR_DEPTH_TEMPERATURE_MATCH = "brow_hair_depth_temperature_match"
BROW_SECONDARY_TONE_FIT = "brow_secondary_tone_fit"
MASCARA_DEFAULT_NEUTRAL = "mascara_default_neutral_tone"
PALETTE_SINGLE_SELLABLE_SKU = "palette_single_sellable_sku"
EYELINER_NEUTRAL_DEFAULT = "eyeliner_neutral_default"

# -- lips / cheeks coordination ---------------------------------------
def lip_coordination(family: str) -> str:
    return f"lip_coordination_{normalize_token(family)}"


LIP_LINER_PAIRING_MATCH = "lip_liner_pairing_match"

# -- fragrance ---------------------------------------------------------
FRAGRANCE_PROFILE_OVERLAP = "fragrance_profile_overlap"
FRAGRANCE_SEASON_OCCASION_MATCH = "fragrance_season_occasion_match"
SAME_SCENT_LINE_LAYERING = "same_scent_line_layering_suggestion"

# -- shade resolution --------------------------------------------------
SHADE_CONFIRMED_CODE = "shade_confirmed_code"
SHADE_LAB_MEASURED_DISTANCE = "shade_lab_measured_distance"
SHADE_DEPTH_UNDERTONE_TIEBREAK = "shade_depth_undertone_tiebreak"
SHADE_NEIGHBOUR_GRAPH_FALLBACK = "shade_neighbour_graph_fallback"

# -- goals / routine (skincare) ----------------------------------------
GOAL_DIRECT_MATCH = "goal_direct_match"
ROUTINE_STEP_TIME_FIT = "routine_step_time_fit"
EXPERIENCE_LEVEL_FIT = "experience_level_fit"
CONCERN_PRIMARY_MATCH = "concern_primary_match"
CONCERN_SECONDARY_SUPPORT = "concern_secondary_support"
