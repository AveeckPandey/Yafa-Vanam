from __future__ import annotations

import colorsys
import re
from typing import Any, Iterable

from .catalogue import active_products, variant_is_available
from .models import BeautyProfile, Recommendation, ScoreReason, ShadeResult
from .shade_matcher import brightening_variant, exact_match_variant, suitable_supporting_variant

OCCASION_MAP = {
    "everyday": "daily", "work_college": "daily", "date_dinner": "evening", "party_night": "evening",
    "wedding": "special_occasion", "special_photos": "special_occasion",
}

COLOUR_WORDS = {
    "nude": {"nude", "neutral", "beige", "sand", "ivory", "linen", "taupe"},
    "rose": {"rose", "pink", "petal", "blush"},
    "peach": {"peach", "coral", "apricot", "terracotta"},
    "mauve": {"mauve", "plum", "violet", "purple", "lavender", "lilac"},
    "brown": {"brown", "espresso", "chocolate", "cocoa", "caramel", "clay", "earth", "bronze", "bark"},
    "red": {"red", "berry", "burgundy", "raisin", "wine", "ruby", "crimson"},
}


def _text(product: dict[str, Any]) -> str:
    description = product.get("description") or {}
    parts = [product.get("name", ""), product.get("product_type", ""), description.get("short", ""), description.get("full", "")]
    parts.extend(product.get("benefits") or [])
    return " ".join(str(x) for x in parts).lower()


def _reason(rule: str, score: float, detail: str | None = None) -> ScoreReason:
    return ScoreReason(rule=rule, score=score, detail=detail)


def _skin_score(product: dict[str, Any], profile: BeautyProfile) -> list[ScoreReason]:
    skin = profile.skin.type
    if not skin:
        return []
    skin_meta = ((product.get("recommendation_profile") or {}).get("skin_types") or {})
    if skin in skin_meta.get("best_for", []):
        return [_reason("skin_type_best", 2, f"Catalogue lists {skin} as best-for")]
    if skin in skin_meta.get("compatible_with", []):
        return [_reason("skin_type_compatible", 1, f"Catalogue lists {skin} as compatible")]
    if skin in skin_meta.get("use_with_caution", []):
        return [_reason("skin_type_caution", -1, f"Catalogue flags caution for {skin}")]
    if "all_skin_types" in skin_meta.get("best_for", []):
        return [_reason("skin_type_all", 1, "Catalogue positions product for all skin types")]
    return []


def _occasion_score(product: dict[str, Any], profile: BeautyProfile) -> list[ScoreReason]:
    if not profile.occasion:
        return []
    wanted = OCCASION_MAP.get(profile.occasion)
    occasions = (product.get("recommendation_profile") or {}).get("occasion") or []
    if wanted and wanted in occasions:
        return [_reason("occasion_match", 1, f"Catalogue occasion matches {wanted}")]
    text = _text(product)
    if profile.occasion in {"party_night", "wedding", "special_photos"} and any(k in text for k in ("longwear", "long-wear", "evening")):
        return [_reason("occasion_supporting_feature", 0.5, "Product positioning supports longer/evening wear")]
    return []


def _formula_score(product: dict[str, Any], profile: BeautyProfile) -> list[ScoreReason]:
    text = _text(product)
    reasons: list[ScoreReason] = []
    coverage = profile.preferences.coverage
    if coverage:
        coverage_score = 0.0
        if coverage == "sheer":
            coverage_score = 3.0 if "sheer" in text else (2.0 if "skin tint" in text else 0.0)
        elif coverage == "light":
            if "skin tint" in text or "lightweight complexion tint" in text:
                coverage_score = 3.0
            elif "lightweight" in text:
                coverage_score = 1.0
        elif coverage == "medium":
            coverage_score = 2.0 if ("buildable" in text or product.get("product_type") == "Foundation") else 0.0
        elif coverage == "full":
            if "full coverage" in text:
                coverage_score = 3.0
            elif "targeted complexion coverage" in text or "cover concealer" in text:
                coverage_score = 2.0
        if coverage_score:
            reasons.append(_reason("coverage_match", coverage_score, f"Catalogue wording supports {coverage} coverage positioning"))
    finish = profile.preferences.finish
    if finish:
        matches = {
            "natural": ("natural", "skin-like", "skin like"),
            "radiant": ("radiant", "glow", "luminosity", "serum"),
            "soft_matte": ("soft-focus", "soft focus", "powder"),
            "matte": ("matte", "shine-control", "shine control", "powder"),
        }
        if any(token in text for token in matches.get(finish, ())):
            reasons.append(_reason("finish_match", 2, f"Catalogue wording supports {finish} finish positioning"))
    return reasons


def _colour_family_from_hex(value: str | None) -> str | None:
    if not value or not re.fullmatch(r"#[0-9A-Fa-f]{6}", value):
        return None
    r, g, b = (int(value[i:i+2], 16) / 255 for i in (1, 3, 5))
    h, s, l = colorsys.rgb_to_hls(r, g, b)
    deg = h * 360
    if s < 0.12:
        return "nude"
    if 345 <= deg or deg < 15:
        return "red"
    if 15 <= deg < 50:
        return "brown" if l < 0.45 else "peach"
    if 300 <= deg < 345:
        return "mauve"
    if 280 <= deg < 300:
        return "mauve"
    return None


def variant_colour_family(variant: dict[str, Any]) -> str | None:
    shade = variant.get("shade") or {}
    name = str(shade.get("name") or "").lower()
    for family, words in COLOUR_WORDS.items():
        if any(word in name for word in words):
            return family
    return _colour_family_from_hex(shade.get("hex"))


def _variant_colour_score(variant: dict[str, Any], profile: BeautyProfile) -> list[ScoreReason]:
    wanted = profile.preferences.colour_family
    if not wanted:
        return []
    actual = variant_colour_family(variant)
    if actual == wanted:
        return [_reason("colour_family_match", 2, f"Shade maps to {wanted} family")]
    return []


def _lip_finish_score(product: dict[str, Any], profile: BeautyProfile) -> list[ScoreReason]:
    wanted = profile.preferences.lip_finish
    if not wanted or product.get("subcategory") != "Lips":
        return []
    text = _text(product)
    mapping = {
        "velvet": ("velvet", "matte"), "satin": ("satin",), "glossy": ("gloss", "glossy"),
        "lip_oil": ("lip oil",), "stain": ("stain",), "plumping": ("plumper", "plumping"),
    }
    if any(x in text for x in mapping.get(wanted, ())):
        return [_reason("lip_finish_match", 3, f"Product type/positioning matches {wanted}")]
    return [_reason("lip_finish_mismatch", -1, f"Product does not directly match {wanted}")]


def _mascara_score(product: dict[str, Any], profile: BeautyProfile) -> list[ScoreReason]:
    wanted = profile.preferences.mascara_priority
    if not wanted or product.get("product_type") != "Mascara":
        return []
    if wanted in _text(product):
        return [_reason("mascara_priority_match", 3, f"Product positioning matches {wanted}")]
    return []


def _eye_look_score(product: dict[str, Any], profile: BeautyProfile) -> list[ScoreReason]:
    wanted = profile.preferences.eye_look
    if not wanted:
        return []
    ptype = product.get("product_type")
    mapping = {
        "natural": {"Mascara": 1.5, "Brows": 1.0, "Eyeshadow": 1.0},
        "soft_smoky": {"Eyeshadow": 2.0, "Eyeliner": 1.0},
        "glam": {"Eyeshadow": 2.0, "Eye Sets": 1.5, "Mascara": 1.0},
        "colourful": {"Eyeshadow": 2.0, "Eyeliner": 1.5, "Eye Sets": 1.0},
        "graphic": {"Eyeliner": 3.0, "Eyeshadow": 1.0},
    }
    score = mapping.get(wanted, {}).get(ptype)
    return [_reason("eye_look_match", score, f"{ptype} supports {wanted} look") ] if score else []


def _base_score(product: dict[str, Any], profile: BeautyProfile) -> tuple[float, list[ScoreReason]]:
    reasons = _skin_score(product, profile) + _occasion_score(product, profile) + _formula_score(product, profile)
    reasons += _lip_finish_score(product, profile) + _mascara_score(product, profile) + _eye_look_score(product, profile)
    return sum(r.score for r in reasons), reasons


def _make_rec(product: dict[str, Any], variant: dict[str, Any] | None, score: float, reasons: list[ScoreReason]) -> Recommendation:
    shade = None
    variant_id = None
    if variant:
        variant_id = variant.get("id")
        s = variant.get("shade") or {}
        shade = ShadeResult(code=s.get("code"), name=s.get("name"), hex=s.get("hex"))
    return Recommendation(
        category=str(product.get("subcategory") or product.get("category") or "makeup"),
        product_id=product["id"], product_name=product["name"], product_slug=product["slug"],
        variant_id=variant_id, shade=shade, score=round(score, 2),
        reason_codes=[r.rule for r in reasons if r.score > 0], reasons=reasons,
        image=(product.get("images") or {}).get("primary"), commerce_validation_required=True,
    )


def _best_variant(product: dict[str, Any], profile: BeautyProfile) -> tuple[dict[str, Any] | None, list[ScoreReason]]:
    best: tuple[float, dict[str, Any] | None, list[ScoreReason]] = (-999, None, [])
    for variant in product.get("variants", []):
        if not variant_is_available(variant):
            continue
        reasons = _variant_colour_score(variant, profile)
        score = sum(r.score for r in reasons)
        # stable deterministic tie-break: catalogue order wins.
        if score > best[0]:
            best = (score, variant, reasons)
    return best[1], best[2]


def _rank_product_set(products: Iterable[dict[str, Any]], profile: BeautyProfile) -> list[Recommendation]:
    output: list[Recommendation] = []
    for product in products:
        score, reasons = _base_score(product, profile)
        variant, vr = _best_variant(product, profile)
        reasons += vr
        score += sum(r.score for r in vr)
        output.append(_make_rec(product, variant, score, reasons))
    return sorted(output, key=lambda r: (-r.score, r.product_id, r.variant_id or ""))


def _complexion_recommendations(products: list[dict[str, Any]], profile: BeautyProfile, full: bool) -> list[Recommendation]:
    recs: list[Recommendation] = []
    base_products = [p for p in products if p.get("subcategory") == "Complexion" and p.get("product_type") in {"Foundation", "Skin Tint", "Powder Foundation"}]
    candidates: list[Recommendation] = []
    for p in base_products:
        variant = exact_match_variant(p, profile)
        if not variant:
            continue
        score, reasons = _base_score(p, profile)
        reasons.append(_reason("shade_exact", 4, "Exact master depth + undertone variant"))
        candidates.append(_make_rec(p, variant, score + 4, reasons))
    if candidates:
        recs.append(sorted(candidates, key=lambda r: (-r.score, r.product_id))[0])

    concealers = [p for p in products if p.get("product_type") == "Concealer"]
    if concealers and profile.complexion.shade_code:
        p = concealers[0]
        mode = profile.preferences.concealer_mode or "exact"
        variant = brightening_variant(p, profile) if mode == "brightening" else exact_match_variant(p, profile)
        if variant:
            score, reasons = _base_score(p, profile)
            code = "concealer_brightening_neighbor" if mode == "brightening" else "shade_exact"
            reasons.append(_reason(code, 3, "Validated neighbouring lighter depth" if mode == "brightening" else "Exact master shade"))
            recs.append(_make_rec(p, variant, score + 3, reasons))

    if full:
        for ptype in ("Setting Powder", "Bronzer", "Contour", "Highlighter"):
            matches = [p for p in products if p.get("product_type") == ptype]
            if not matches:
                continue
            p = matches[0]
            variant, codes = suitable_supporting_variant(p, profile)
            if variant:
                score, reasons = _base_score(p, profile)
                mapped = [_reason(code, 2 if code.endswith("best") else 1, "Catalogue suitability mapping") for code in codes]
                recs.append(_make_rec(p, variant, score + sum(x.score for x in mapped), reasons + mapped))
        # Corrector is intentionally omitted unless a concern was explicitly selected.
        if profile.preferences.corrector_concern:
            matches = [p for p in products if p.get("product_type") == "Color Corrector"]
            if matches:
                p = matches[0]
                variant, codes = suitable_supporting_variant(p, profile)
                if variant:
                    mapped = [_reason(code, 2, "Catalogue corrector concern/depth mapping") for code in codes]
                    recs.append(_make_rec(p, variant, sum(x.score for x in mapped), mapped))
    return recs


def recommend(profile: BeautyProfile) -> list[Recommendation]:
    products = [p for p in active_products() if p.get("category") == "Makeup"]
    goal = profile.goal.value if profile.goal else "guide_me"
    recs: list[Recommendation] = []
    full = goal in {"full_look", "outfit_match", "guide_me"}

    if goal in {"complexion", "full_look", "outfit_match", "guide_me"}:
        recs.extend(_complexion_recommendations(products, profile, full=full))

    if goal in {"lips", "full_look", "outfit_match", "guide_me"}:
        lip = [p for p in products if p.get("subcategory") == "Lips"]
        ranked = _rank_product_set(lip, profile)
        if ranked: recs.append(ranked[0])

    if goal in {"cheeks", "full_look", "outfit_match", "guide_me"}:
        cheek = [p for p in products if p.get("subcategory") == "Cheeks & Multi-Use"]
        ranked = _rank_product_set(cheek, profile)
        if ranked: recs.append(ranked[0])

    if goal in {"eyes", "full_look", "outfit_match", "guide_me"}:
        eye = [p for p in products if p.get("subcategory") == "Eyes"]
        mascaras = _rank_product_set([p for p in eye if p.get("product_type") == "Mascara"], profile)
        colour_eye = _rank_product_set([p for p in eye if p.get("product_type") in {"Eyeshadow", "Eyeliner", "Eye Sets"}], profile)
        if mascaras: recs.append(mascaras[0])
        if colour_eye: recs.append(colour_eye[0])

    # Preserve category/slot generation order; never use the LLM to choose the winner.
    return recs
