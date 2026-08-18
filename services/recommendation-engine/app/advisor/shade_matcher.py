from __future__ import annotations

from typing import Any

from .catalogue import active_products, product_by_id, variant_is_available
from .models import BeautyProfile, Depth, ShadeResult, Undertone

DEPTH_INDEX = {
    Depth.fair.value: 1,
    Depth.light.value: 2,
    Depth.light_medium.value: 3,
    Depth.medium.value: 4,
    Depth.medium_tan.value: 5,
    Depth.tan.value: 6,
    Depth.deep.value: 7,
    Depth.rich.value: 8,
}
UNDERTONE_CODE = {
    Undertone.cool.value: "C",
    Undertone.neutral.value: "N",
    Undertone.warm.value: "W",
    Undertone.olive.value: "O",
}
EXACT_MATCH_TYPES = {"Foundation", "Skin Tint", "Powder Foundation", "Concealer"}

# The current normalized catalogue preserves master shade codes but some
# complexion rows do not yet repeat the friendly display metadata. Keep the
# canonical naming fallback at the matching boundary instead of inventing it
# separately in each recommendation path.
MASTER_SHADE_NAMES = {
    "5O": "Olive Honey",
}


def shade_result(shade: dict[str, Any]) -> ShadeResult:
    code = shade.get("code")
    return ShadeResult(
        code=code,
        name=shade.get("name") or MASTER_SHADE_NAMES.get(code),
        hex=shade.get("hex"),
    )


def master_code(depth: str | None, undertone: str | None) -> str | None:
    if not depth or not undertone:
        return None
    idx = DEPTH_INDEX.get(depth)
    suffix = UNDERTONE_CODE.get(undertone)
    return f"{idx}{suffix}" if idx and suffix else None


def variant_for_code(product: dict[str, Any], code: str) -> dict[str, Any] | None:
    for variant in product.get("variants", []):
        shade = variant.get("shade") or {}
        if shade.get("code") == code and variant_is_available(variant):
            return variant
    return None


def exact_match_variant(product: dict[str, Any], profile: BeautyProfile) -> dict[str, Any] | None:
    code = profile.complexion.shade_code or master_code(
        profile.complexion.depth.value if profile.complexion.depth else None,
        profile.complexion.undertone.value if profile.complexion.undertone else None,
    )
    return variant_for_code(product, code) if code else None


def resolve_master_shade(profile: BeautyProfile) -> ShadeResult | None:
    code = profile.complexion.shade_code or master_code(
        profile.complexion.depth.value if profile.complexion.depth else None,
        profile.complexion.undertone.value if profile.complexion.undertone else None,
    )
    if not code:
        return None
    for product in active_products():
        if product.get("subcategory") != "Complexion" or product.get("product_type") not in EXACT_MATCH_TYPES:
            continue
        variant = variant_for_code(product, code)
        if variant:
            shade = variant.get("shade") or {}
            return shade_result(shade)
    return None


def brightening_variant(product: dict[str, Any], profile: BeautyProfile) -> dict[str, Any] | None:
    if not profile.complexion.depth or not profile.complexion.undertone:
        return None
    current = DEPTH_INDEX[profile.complexion.depth.value]
    lighter = max(1, current - 1)
    code = f"{lighter}{UNDERTONE_CODE[profile.complexion.undertone.value]}"
    variant = variant_for_code(product, code)
    if variant:
        return variant
    # Neighbouring lighter depth may not carry every undertone (e.g. olive).
    # Fall back only within that lighter depth to neutral, then warm/cool.
    for suffix in ("N", "W", "C", "O"):
        variant = variant_for_code(product, f"{lighter}{suffix}")
        if variant:
            return variant
    return None


def suitable_supporting_variant(product: dict[str, Any], profile: BeautyProfile) -> tuple[dict[str, Any] | None, list[str]]:
    depth = profile.complexion.depth.value if profile.complexion.depth else None
    undertone = profile.complexion.undertone.value if profile.complexion.undertone else None
    best: tuple[float, dict[str, Any] | None, list[str]] = (-999, None, [])
    for variant in product.get("variants", []):
        if not variant_is_available(variant):
            continue
        suitability = variant.get("suitability") or {}
        score = 0.0
        reasons: list[str] = []
        if depth:
            if depth in suitability.get("best_for_depths", []):
                score += 2
                reasons.append("depth_best")
            elif depth in suitability.get("compatible_depths", []):
                score += 1
                reasons.append("depth_compatible")
            elif suitability.get("best_for_depths"):
                score -= 1
        if undertone:
            if undertone in suitability.get("best_for_undertones", []):
                score += 1
                reasons.append("undertone_best")
            elif undertone in suitability.get("compatible_undertones", []):
                score += 0.5
                reasons.append("undertone_compatible")
        if product.get("product_type") == "Color Corrector":
            concern = profile.preferences.corrector_concern
            roles = suitability.get("selection_role", [])
            if not concern:
                continue
            if concern in roles:
                score += 3
                reasons.append("corrector_concern_match")
            else:
                score -= 3
        if score > best[0]:
            best = (score, variant, reasons)
    return best[1], best[2]
