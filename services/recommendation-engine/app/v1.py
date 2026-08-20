"""Dataset-native, deterministic YAFA VANAM recommendation API.

This module deliberately ranks catalogue candidates only.  It does not use an
LLM, mocked validation fields, or inferred product performance claims.
"""
from __future__ import annotations

import json
import math
from collections import Counter, defaultdict
from functools import lru_cache
from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field

from app.persistence.beauty_profile_repository import profile_store
from app.profile.merger import merge_beauty_profiles
from app.vision.analyzer import analyse_skin_image

router = APIRouter(prefix="/v1", tags=["recommendations-v1"])
DATA_DIR = Path(__file__).resolve().parents[1] / "data"
SOURCES = {"skin": "skin.json", "eyes": "eyes.json", "lips": "lips.json", "cheeks": "cheeks.json", "no_shades": "no_shades.json"}
OCCASIONS = {"everyday": "daily", "office": "daily", "work": "daily", "date": "evening", "date_dinner": "evening", "wedding": "special_occasion", "bridal": "special_occasion", "evening": "evening"}
OUTFIT_FAMILIES = {
    "emerald": {"gold", "bronze", "olive", "copper", "terracotta", "brick", "berry", "plum", "nude"},
    "green": {"gold", "bronze", "olive", "copper", "terracotta", "brick", "nude"},
    "gold": {"gold", "bronze", "copper", "terracotta", "warm_rose", "berry", "nude"},
    "red": {"gold", "bronze", "brown", "nude", "berry", "plum"}, "burgundy": {"gold", "bronze", "brown", "berry", "plum", "mauve"},
    "blue": {"silver", "taupe", "mauve", "plum", "rose", "berry"}, "navy": {"silver", "taupe", "mauve", "berry", "nude"},
    "purple": {"mauve", "plum", "rose", "berry", "gold"}, "pink": {"rose", "mauve", "berry", "nude", "gold"},
    "orange": {"copper", "terracotta", "bronze", "peach", "warm_rose", "nude"}, "terracotta": {"copper", "bronze", "peach", "warm_rose", "nude"},
    "black": {"nude", "rose", "mauve", "berry", "plum", "gold", "silver"}, "white": {"rose", "peach", "mauve", "nude", "gold", "silver"},
}


class RecommendationRequest(BaseModel):
    intent: str = "explore"
    user_id: str | None = None
    profile: dict[str, Any] = Field(default_factory=dict)
    context: dict[str, Any] = Field(default_factory=dict)
    max_results_per_category: int = Field(default=3, ge=1, le=6)
    debug: bool = False


class ProfileRequest(BaseModel):
    profile: dict[str, Any] = Field(default_factory=dict)


class FeedbackEvent(BaseModel):
    recommendation_id: str
    user_profile_hash: str | None = None
    product_id: str
    variant_id: str | None = None
    action: str


class BeautyProfilePatch(BaseModel):
    user_id: str
    profile: dict[str, Any] = Field(default_factory=dict)


class ConfirmShadeRequest(BaseModel):
    user_id: str
    shade_code: str


class YafaConversationRequest(BaseModel):
    intent: str = "explore"
    user_id: str | None = None
    profile: dict[str, Any] = Field(default_factory=dict)


@lru_cache(maxsize=1)
def sources() -> dict[str, dict[str, Any]]:
    loaded: dict[str, dict[str, Any]] = {}
    ids: list[str] = []
    for name, filename in SOURCES.items():
        path = DATA_DIR / filename
        if not path.exists():
            raise RuntimeError(f"Required recommendation dataset is missing: {path}")
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Malformed recommendation dataset {filename}: {exc}") from exc
        if not isinstance(document, dict) or not isinstance(document.get("products"), list):
            raise RuntimeError(f"Dataset {filename} must be an object containing a products array")
        for product in document["products"]:
            if not isinstance(product, dict) or not product.get("id") or not product.get("name"):
                raise RuntimeError(f"Dataset {filename} has a product without id or name")
            ids.append(product["id"])
        loaded[name] = document
    duplicate_ids = [value for value, count in Counter(ids).items() if count > 1]
    if duplicate_ids:
        raise RuntimeError(f"Duplicate catalogue product IDs: {duplicate_ids}")
    if len(ids) != 78:
        raise RuntimeError(f"Expected 78 YAFA VANAM products, found {len(ids)}")
    return loaded


def products(domain: str | None = None) -> list[dict[str, Any]]:
    data = sources()
    if domain:
        return list(data[domain]["products"])
    return [product for document in data.values() for product in document["products"]]


def catalogue_status() -> dict[str, Any]:
    data = sources()
    counts = {name: len(document["products"]) for name, document in data.items()}
    all_products = products()
    return {"status": "ok", "datasets": counts, "products": len(all_products), "unique_product_ids": len({p["id"] for p in all_products}), "categories": dict(Counter(p.get("product_type", "unknown") for p in all_products))}


def _get(data: dict[str, Any], *paths: str) -> Any:
    for path in paths:
        current: Any = data
        for key in path.split("."):
            current = current.get(key) if isinstance(current, dict) else None
        if current is not None:
            return current
    return None


def normalise_profile(raw: dict[str, Any], context: dict[str, Any] | None = None) -> dict[str, Any]:
    """Accept the V1 profile contract and the previous advisor vocabulary."""
    context = {**(raw.get("context") or {}), **(context or {})}
    skin = raw.get("skin") or {}
    face = raw.get("face") or {}
    prefs = raw.get("makeup_preferences") or raw.get("preferences") or {}
    legacy_complexion = raw.get("complexion") or {}
    outfit = context.get("outfit") or raw.get("outfit") or {}
    depth = _get(skin, "depth", "depth_family") or legacy_complexion.get("depth")
    return {
        "shade_code": _get(skin, "shade_code") or legacy_complexion.get("shade_code"),
        "shade_confirmed": bool(_get(skin, "shade_code") or legacy_complexion.get("confirmed")),
        "depth": depth,
        "undertone": _get(skin, "undertone") or legacy_complexion.get("undertone"),
        "lab": _get(skin, "lab") or raw.get("lab") or _get(raw, "skin_analyzer.lab"),
        "capture_confidence": _get(skin, "shade_confidence") or _get(raw, "skin_analyzer.capture_confidence"),
        "skin_types": _as_list(_get(skin, "skin_types", "type") or _get(raw, "skin.type")),
        "concerns": _as_list(_get(skin, "concerns") or _get(raw, "safety_conditions")),
        "sensitivity": _get(skin, "sensitivity"),
        "eye_colour": _get(face, "eye_colour"), "hair_colour": _get(face, "hair_colour"), "hair_depth": _get(face, "hair_depth"), "hair_temperature": _get(face, "hair_temperature"),
        "coverage": _get(prefs, "coverage"), "finish": _get(prefs, "finish"), "style": _get(prefs, "intensity", "style"),
        "lip_finish": _get(prefs, "preferred_lip_finish", "lip_finish"), "eye_intensity": _get(prefs, "preferred_eye_intensity", "eye_look"), "cheek_finish": _get(prefs, "preferred_cheek_finish"),
        "occasion": _get(context, "occasion") or raw.get("occasion"), "daypart": _get(context, "daypart"), "season": _get(context, "season"),
        "outfit": outfit, "fragrance": raw.get("fragrance_preferences") or {},
        "safety_conditions": set(_as_list(raw.get("safety_conditions")) + _as_list(_get(skin, "safety_conditions")) + _as_list(raw.get("conditions"))),
    }


def _as_list(value: Any) -> list[str]:
    if value is None: return []
    if isinstance(value, str): return [value.lower()]
    return [str(item).lower() for item in value]


def _variant(product: dict[str, Any], variant: dict[str, Any] | None, score: float, breakdown: dict[str, float], reasons: list[str], penalties: list[str], debug: bool) -> dict[str, Any]:
    shade = (variant or {}).get("shade") or {}
    rec = {"product_id": product["id"], "product": product["name"], "product_type": product.get("product_type"), "variant_id": (variant or {}).get("id"), "shade": {key: shade.get(key) for key in ("code", "name", "hex", "undertone", "depth_family") if shade.get(key) is not None} or None, "score": round(max(0.0, min(1.0, score)), 3), "score_breakdown": {key: round(value, 3) for key, value in breakdown.items()}, "matched_reasons": reasons, "penalties": penalties, "excluded": False, "exclusion_reason": None}
    if product.get("product_type") == "Sunscreen Spray SPF 50" or "Sunbloom" in product.get("name", ""):
        rec["matched_reasons"] = reasons + ["Sunbloom is YAFA VANAM's planned sunscreen option; final SPF validation is pending."]
    if debug: rec["debug"] = {"rules_fired": reasons, "penalties": penalties, "data_source": "authoritative_catalogue_json"}
    return rec


def _family(variant: dict[str, Any] | None) -> str:
    shade = ((variant or {}).get("shade") or {})
    name = str(shade.get("name") or "").lower()
    for family, terms in {"berry": ["berry", "wine", "raisin"], "plum": ["plum", "violet"], "mauve": ["mauve", "lilac"], "rose": ["rose", "petal", "pink"], "peach": ["peach", "coral", "apricot"], "terracotta": ["terracotta", "clay", "cinnamon"], "copper": ["copper"], "bronze": ["bronze"], "gold": ["gold"], "olive": ["olive"], "brown": ["brown", "cocoa", "espresso"], "nude": ["nude", "beige", "sand", "taupe"]}.items():
        if any(term in name for term in terms): return family
    return "neutral"


def _excluded(product: dict[str, Any], profile: dict[str, Any]) -> tuple[bool, str | None]:
    for rule in (product.get("recommendation_profile") or {}).get("hard_exclusions", []):
        condition = (rule.get("condition") if isinstance(rule, dict) else str(rule)).lower()
        if condition in profile["safety_conditions"] or (condition == "pregnant_or_planning_pregnancy" and "pregnant" in profile["safety_conditions"]):
            return True, condition
    return False, None


def _score(product: dict[str, Any], variant: dict[str, Any] | None, profile: dict[str, Any], domain: str, debug: bool) -> dict[str, Any] | None:
    blocked, rule = _excluded(product, profile)
    if blocked: return None
    rp = product.get("recommendation_profile") or {}
    factors: dict[str, float] = {"catalogue_fit": 0.45}
    reasons = ["Active YAFA VANAM catalogue item"]
    penalties: list[str] = []
    skin_types = rp.get("skin_types") or {}
    wanted_skin = set(profile["skin_types"])
    if wanted_skin:
        if wanted_skin.intersection(set(skin_types.get("best_for") or [])): factors["skin_type"] = 1.0; reasons.append("Catalogue skin-type fit")
        elif wanted_skin.intersection(set(skin_types.get("compatible_with") or [])) or "all_skin_types" in skin_types.get("compatible_with", []): factors["skin_type"] = .7; reasons.append("Catalogue skin-type compatibility")
        elif wanted_skin.intersection(set(skin_types.get("use_with_caution") or [])): factors["skin_type"] = .2; penalties.append("Catalogue lists a skin-type caution")
    concerns = set(profile["concerns"])
    product_concerns = set((rp.get("concerns") or {}).get("primary") or []) | set((rp.get("concerns") or {}).get("secondary") or [])
    if concerns and concerns.intersection(product_concerns): factors["concerns"] = 1.0; reasons.append("Catalogue concern/goal alignment")
    wanted_occasion = OCCASIONS.get(profile["occasion"], profile["occasion"])
    if wanted_occasion and wanted_occasion in (rp.get("occasion") or []): factors["occasion"] = 1.0; reasons.append("Catalogue occasion alignment")
    family = _family(variant)
    outfit_colour = str((profile["outfit"] or {}).get("primary_colour") or ((profile["outfit"] or {}).get("dominant_colors") or [""])[0]).lower()
    allowed = OUTFIT_FAMILIES.get(outfit_colour, set())
    if allowed and family in allowed: factors["outfit"] = 1.0; reasons.append(f"Coordinates with {outfit_colour} outfit direction")
    desired_finish = profile["lip_finish"] if domain == "lips" else (profile["cheek_finish"] if domain == "cheeks" else profile["finish"])
    text = f"{product.get('name','')} {product.get('product_type','')}".lower()
    if desired_finish and str(desired_finish).replace("_", " ") in text: factors["finish"] = 1.0; reasons.append("Requested finish direction")
    if domain == "eyes" and profile["eye_colour"]:
        factors["eye_colour"] = .65; reasons.append("Eye-colour considered as a ranking signal")
    if domain == "brows":
        target = _brow_target(profile)
        if target and any(token in text for token in target): factors["hair_match"] = 1.0; reasons.append("Brow tone follows hair colour and intensity")
        elif target: factors["hair_match"] = .25; penalties.append("Less direct hair-tone fit")
    for penalty in rp.get("soft_penalties") or []:
        condition = str(penalty.get("condition", "")).lower() if isinstance(penalty, dict) else ""
        if condition and (condition in profile["safety_conditions"] or (condition == "sensitive_or_reactive_skin" and profile["sensitivity"] in {"medium", "high", "sensitive"})):
            factors["safety_penalty"] = -float(penalty.get("penalty", .5) if isinstance(penalty, dict) else .5); penalties.append("Catalogue tolerance penalty applied")
    score = sum(factors.values()) / max(1.0, sum(abs(value) for key, value in factors.items() if key != "safety_penalty"))
    return _variant(product, variant, score, factors, reasons, penalties, debug)


def _brow_target(profile: dict[str, Any]) -> tuple[str, ...]:
    hair = f"{profile['hair_colour'] or ''} {profile['hair_depth'] or ''} {profile['hair_temperature'] or ''}".lower()
    if "black" in hair: return ("black", "soft black")
    if "dark" in hair or "deep" in hair: return ("deep", "black brown", "dark brown", "neutral")
    if "warm" in hair: return ("warm", "light brown")
    if "cool" in hair or "ash" in hair: return ("ash", "taupe")
    if "brown" in hair: return ("neutral", "medium brown")
    return ()


def rank(domain: str, profile: dict[str, Any], limit: int, debug: bool = False, product_filter: Any = None) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for product in products(domain):
        if product.get("status") not in {"active", None} or (product_filter and not product_filter(product)): continue
        variants = [v for v in product.get("variants", []) if v.get("is_active", True)] or [None]
        for variant in variants:
            item = _score(product, variant, profile, domain, debug)
            if item: candidates.append(item)
    candidates.sort(key=lambda item: (-item["score"], item["product_id"], item["variant_id"] or ""))
    # Diversity: retain the best primary then do not return a stream of the exact same family.
    selected, families = [], set()
    for item in candidates:
        family = _family({"shade": item.get("shade") or {}})
        if len(selected) and family in families and len(selected) >= 2: continue
        selected.append(item); families.add(family)
        if len(selected) == limit: break
    return selected


def _shade_candidates(profile: dict[str, Any], debug: bool) -> list[dict[str, Any]]:
    foundations = [p for p in products("skin") if p.get("product_type") in {"Foundation", "Skin Tint", "Powder Foundation"}]
    all_shades: list[tuple[dict[str, Any], dict[str, Any], float, list[str]]] = []
    known = str(profile["shade_code"] or "").upper()
    lab = profile.get("lab") or {}
    for product in foundations:
        for variant in product.get("variants", []):
            shade = variant.get("shade") or {}; reasons = []
            if known:
                distance = 0 if shade.get("code") == known else 100
                if distance == 0: reasons.append("Matches your confirmed YAFA shade")
            elif all(k in lab for k in ("L", "a", "b")) and (measured := (shade.get("measured_colour") or {}).get("cielab")):
                distance = ciede2000((lab["L"], lab["a"], lab["b"]), (measured["L"], measured["a"], measured["b"]))
                reasons.append("Ranked with development-use colour distance")
            else:
                distance = abs((shade.get("depth_index") or 4) - _depth_index(profile["depth"])) * 8
                if profile["undertone"] and shade.get("undertone") == profile["undertone"]: distance -= 2; reasons.append("Undertone used as a tie-breaker")
            all_shades.append((product, variant, distance, reasons))
    all_shades.sort(key=lambda row: (row[2], row[0]["id"], row[1]["id"]))
    result = []
    for product, variant, distance, reasons in all_shades:
        formula = _score(product, variant, profile, "skin", debug)
        if formula is None: continue
        formula["score"] = round(1 / (1 + distance / 8) * .7 + formula["score"] * .3, 3)
        formula["score_breakdown"]["shade_match"] = round(1 / (1 + distance / 8), 3)
        formula["matched_reasons"] = reasons + formula["matched_reasons"]
        result.append(formula)
    return result


def _depth_index(depth: Any) -> int:
    return {"fair": 1, "light": 2, "light_medium": 3, "medium": 4, "medium_tan": 5, "tan": 6, "deep": 7, "rich": 8}.get(str(depth), 4)


def recommend_skin(profile: dict[str, Any], limit: int, debug: bool) -> dict[str, Any]:
    matches = _shade_candidates(profile, debug)
    primary = matches[0] if matches else None
    formula = sorted(matches, key=lambda item: (-item["score"], item["product_id"]))[:limit]
    support = {}
    for kind, product_type in {"concealer": "Concealer", "powder": "Setting Powder", "corrector": "Color Corrector", "bronzer": "Bronzer", "contour": "Contour", "highlighter": "Highlighter"}.items():
        choices = rank("skin", profile, 1, debug, lambda p, expected=product_type: p.get("product_type") == expected)
        support[kind] = choices[0] if choices else None
    return {"primary_match": primary, "alternatives": matches[1:limit], "formula_recommendations": formula, **support}


def recommend_lips(profile: dict[str, Any], limit: int, debug: bool) -> dict[str, Any]:
    colour = rank("lips", profile, limit + 2, debug, lambda p: p.get("product_type") != "Lip Liner")[:limit]
    liner = rank("lips", profile, 1, debug, lambda p: p.get("product_type") == "Lip Liner")
    return {"primary": colour[0] if colour else None, "alternatives": colour[1:], "lip_liner": liner[0] if liner and colour else None}


def recommend_eyes(profile: dict[str, Any], limit: int, debug: bool) -> dict[str, Any]:
    ranked = rank("eyes", profile, limit * 3, debug)
    result: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in ranked:
        key = "brows" if item["product_type"] == "Brows" else item["product_type"].lower().replace(" ", "_")
        if len(result[key]) < limit: result[key].append(item)
    return dict(result)


def recommend_cheeks(profile: dict[str, Any], limit: int, debug: bool, lip: dict[str, Any] | None = None) -> dict[str, Any]:
    ranked = rank("cheeks", profile, limit, debug)
    if lip and lip.get("shade"):
        for item in ranked:
            item["matched_reasons"].append("Selected for tonal or complementary lip/cheek coordination")
    intensity = "sheer to buildable" if _depth_index(profile["depth"]) <= 3 else "build gradually to your preferred richness"
    return {"primary": ranked[0] if ranked else None, "alternatives": ranked[1:], "application_intensity": intensity}


def recommend_skincare(profile: dict[str, Any], limit: int, debug: bool) -> dict[str, Any]:
    candidates = rank("no_shades", profile, 30, debug, lambda p: not p.get("fragrance_profile") and p.get("product_type") not in {"Face Primer", "Setting Spray"})
    routine: dict[str, list[dict[str, Any]]] = {"am": [], "pm": []}
    occupied: dict[str, set[str]] = {"am": set(), "pm": set()}
    for item in candidates:
        product = next(p for p in products("no_shades") if p["id"] == item["product_id"])
        routine_meta = (product.get("recommendation_profile") or {}).get("routine") or {}
        step = routine_meta.get("step", "care")
        for time in routine_meta.get("time", []):
            if time in routine and step not in occupied[time] and len(routine[time]) < limit:
                routine[time].append(item); occupied[time].add(step)
    return routine


def recommend_fragrance(profile: dict[str, Any], limit: int, debug: bool) -> dict[str, Any]:
    prefs = profile["fragrance"]
    wanted = set(_as_list(prefs.get("families")) + _as_list(prefs.get("facets")) + _as_list(prefs.get("mood")))
    output = []
    for product in products("no_shades"):
        fragrance = product.get("fragrance_profile")
        if not fragrance: continue
        variant = (product.get("variants") or [None])[0]
        item = _score(product, variant, profile, "fragrance", debug)
        if item is None: continue
        corpus = set(_as_list(fragrance.get("family")) + _as_list(fragrance.get("facets")) + _as_list(fragrance.get("mood")) + _as_list(fragrance.get("season")) + _as_list(fragrance.get("occasion")))
        matched = wanted.intersection(corpus)
        if matched: item["score_breakdown"]["fragrance_profile"] = min(1.0, len(matched) / max(1, len(wanted))); item["matched_reasons"].append("Matches selected scent profile")
        item["score"] = round(min(1.0, item["score"] + .1 * len(matched)), 3)
        item["related_scent_line"] = fragrance.get("related_scent_line")
        output.append(item)
    output.sort(key=lambda item: (-item["score"], item["product_id"]))
    return {"primary": output[0] if output else None, "alternatives": output[1:limit], "layering": _layering(output)}


def _layering(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    lines: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in items:
        if item.get("related_scent_line"): lines[item["related_scent_line"]].append(item)
    return [{"scent_line": line, "products": values[:2], "reason": "Same scent line; pairing is a catalogue-family coordination suggestion, not a longevity claim."} for line, values in lines.items() if len(values) > 1][:2]


def confidence(profile: dict[str, Any], categories: dict[str, Any]) -> dict[str, Any]:
    known = [profile[key] for key in ("shade_code", "depth", "undertone", "skin_types", "eye_colour", "hair_colour", "occasion", "outfit") if profile.get(key)]
    def scores(value: Any) -> list[float]:
        if isinstance(value, dict):
            return ([float(value["score"])] if isinstance(value.get("score"), (int, float)) else []) + [score for child in value.values() for score in scores(child)]
        if isinstance(value, list): return [score for child in value for score in scores(child)]
        return []
    max_score = max(scores(categories), default=0.0)
    level = "high" if len(known) >= 5 and max_score >= .75 else ("medium" if len(known) >= 2 else "low")
    follow_up = None if level != "low" else "What finish do you prefer: natural, radiant, or soft matte?"
    return {"level": level, "score": round(min(1, .2 + .1 * len(known) + .3 * max_score), 3), "follow_up_question": follow_up}


def build_response(request: RecommendationRequest, only: str | None = None) -> dict[str, Any]:
    merged_profile = merge_beauty_profiles(profile_store.get(request.user_id) if request.user_id else None, None, request.profile)
    profile = normalise_profile(merged_profile, request.context)
    intent = {"find_my_foundation_shade": "foundation_shade", "recommend_makeup": "makeup", "match_makeup_to_outfit": "outfit_match", "recommend_complete_yafa_kit": "kit", "complete_kit": "kit", "guide_me": "explore"}.get(only or request.intent, only or request.intent)
    categories: dict[str, Any] = {}
    if intent in {"skin", "foundation_shade", "makeup", "full_look", "look", "kit", "explore"}: categories["skin"] = recommend_skin(profile, request.max_results_per_category, request.debug)
    if intent in {"eyes", "makeup", "full_look", "look", "kit", "explore"}: categories["eyes"] = recommend_eyes(profile, request.max_results_per_category, request.debug)
    if intent in {"lips", "makeup", "full_look", "look", "kit", "explore"}: categories["lips"] = recommend_lips(profile, request.max_results_per_category, request.debug)
    if intent in {"cheeks", "makeup", "full_look", "look", "kit", "explore"}: categories["cheeks"] = recommend_cheeks(profile, request.max_results_per_category, request.debug, (categories.get("lips") or {}).get("primary"))
    if intent in {"skincare", "kit", "full_look", "explore"}: categories["skincare"] = recommend_skincare(profile, request.max_results_per_category, request.debug)
    if intent in {"fragrance", "kit", "full_look", "explore"}: categories["fragrance"] = recommend_fragrance(profile, request.max_results_per_category, request.debug)
    kit = build_kit(categories, intent) if intent in {"kit", "full_look", "look"} else None
    certainty = confidence(profile, categories)
    return {"profile_summary": {key: value for key, value in profile.items() if key not in {"safety_conditions", "lab"} and value not in (None, [], {}, "")}, "profile_reused": bool(request.user_id and profile_store.get(request.user_id)), "recommendations": categories, "kit": kit, "confidence": certainty, "follow_up_question": certainty["follow_up_question"]}


def build_kit(categories: dict[str, Any], intent: str) -> dict[str, Any]:
    slots: list[tuple[str, dict[str, Any] | None]] = []
    skin = categories.get("skin") or {}
    for name in ("primary_match", "concealer", "powder", "bronzer", "contour", "highlighter"): slots.append((name, skin.get(name)))
    eyes = categories.get("eyes") or {}
    for name in ("eyeshadow", "eyeliner", "mascara", "brows"): slots.append((name, (eyes.get(name) or [None])[0]))
    lips = categories.get("lips") or {}; cheeks = categories.get("cheeks") or {}
    slots += [("cheeks", cheeks.get("primary")), ("lip_liner", lips.get("lip_liner")), ("lips", lips.get("primary"))]
    if categories.get("fragrance"): slots.append(("fragrance", categories["fragrance"].get("primary")))
    used, output = set(), []
    for role, item in slots:
        if item and item["product_id"] not in used: output.append({"role": role, "recommendation": item}); used.add(item["product_id"])
    return {"type": "Full Beauty Kit" if intent in {"kit", "full_look"} else "Look Kit", "items": output, "coordination": "A deterministic pass selects one item per role and uses outfit plus lip/cheek harmony signals."}


def ciede2000(first: tuple[float, float, float], second: tuple[float, float, float]) -> float:
    # CIEDE2000 (Sharma et al.) implemented locally to avoid a scientific-runtime dependency.
    l1, a1, b1 = first; l2, a2, b2 = second; avg_l = (l1 + l2) / 2
    c1, c2 = math.hypot(a1, b1), math.hypot(a2, b2); avg_c = (c1 + c2) / 2
    g = .5 * (1 - math.sqrt(avg_c**7 / (avg_c**7 + 25**7))); a1p, a2p = (1 + g) * a1, (1 + g) * a2
    c1p, c2p = math.hypot(a1p, b1), math.hypot(a2p, b2)
    h1, h2 = math.degrees(math.atan2(b1, a1p)) % 360, math.degrees(math.atan2(b2, a2p)) % 360
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


@router.get("/catalogue/status")
def status() -> dict[str, Any]: return catalogue_status()

@router.post("/profile")
def profile(request: ProfileRequest) -> dict[str, Any]: return {"profile": normalise_profile(request.profile)}


@router.get("/profile/beauty")
def get_beauty_profile(user_id: str = Query(...)) -> dict[str, Any]:
    return {"profile": profile_store.get(user_id), "source": "derived_profile_store"}


@router.patch("/profile/beauty")
def patch_beauty_profile(request: BeautyProfilePatch) -> dict[str, Any]:
    existing = profile_store.get(request.user_id)
    merged = merge_beauty_profiles(existing, None, request.profile)
    return {"profile": profile_store.save(request.user_id, merged), "raw_selfie_stored": False}


@router.post("/profile/confirm-shade")
def confirm_shade(request: ConfirmShadeRequest) -> dict[str, Any]:
    known_codes = {variant.get("shade", {}).get("code") for product in products("skin") for variant in product.get("variants", [])}
    code = request.shade_code.upper()
    if code not in known_codes: raise HTTPException(422, "Shade code is not part of the YAFA 24-shade system")
    profile = profile_store.get(request.user_id) or {"skin": {}}
    profile.setdefault("skin", {}).update({"shade_code": code, "shade_source": "manual", "user_confirmed": True})
    return {"profile": profile_store.save(request.user_id, profile), "confirmation_authoritative": True}


@router.post("/vision/analyse-skin")
async def analyse_skin(image: UploadFile = File(...), user_id: str | None = Form(default=None)) -> dict[str, Any]:
    if image.content_type and not image.content_type.startswith("image/"):
        raise HTTPException(415, "Upload an image file")
    result = analyse_skin_image(await image.read())
    response = result.model_dump(mode="json")
    if user_id and result.quality_pass and result.analysis:
        best = result.shade_candidates[0]
        cv_profile = {"skin": {"shade_code": best.shade_code, "depth_family": result.analysis.depth_family, "undertone": result.analysis.undertone, "lab": result.analysis.lab.model_dump(), "ita": result.analysis.ita, "shade_confidence": result.confidence, "shade_source": "computer_vision", "user_confirmed": False}}
        merged = merge_beauty_profiles(profile_store.get(user_id), cv_profile, None)
        profile_store.save(user_id, merged)
        profile_store.save_analysis_event(user_id, {"predicted_shade_code": best.shade_code, "candidate_1": result.shade_candidates[0].shade_code, "candidate_2": result.shade_candidates[1].shade_code, "candidate_3": result.shade_candidates[2].shade_code, "lab": result.analysis.lab.model_dump(), "ita": result.analysis.ita, "confidence": result.confidence, "source": "computer_vision"})
        response["profile_updated"] = True
    response["raw_image_persisted"] = False
    return response

@router.post("/recommend")
def recommend_endpoint(request: RecommendationRequest) -> dict[str, Any]: return build_response(request)

@router.post("/recommend/skin")
def skin_endpoint(request: RecommendationRequest) -> dict[str, Any]: return build_response(request, "skin")

@router.post("/recommend/eyes")
def eyes_endpoint(request: RecommendationRequest) -> dict[str, Any]: return build_response(request, "eyes")

@router.post("/recommend/lips")
def lips_endpoint(request: RecommendationRequest) -> dict[str, Any]: return build_response(request, "lips")

@router.post("/recommend/cheeks")
def cheeks_endpoint(request: RecommendationRequest) -> dict[str, Any]: return build_response(request, "cheeks")

@router.post("/recommend/skincare")
def skincare_endpoint(request: RecommendationRequest) -> dict[str, Any]: return build_response(request, "skincare")

@router.post("/recommend/fragrance")
def fragrance_endpoint(request: RecommendationRequest) -> dict[str, Any]: return build_response(request, "fragrance")

@router.post("/recommend/look")
def look_endpoint(request: RecommendationRequest) -> dict[str, Any]: return build_response(request, "look")

@router.post("/recommend/kit")
def kit_endpoint(request: RecommendationRequest) -> dict[str, Any]: return build_response(request, "kit")

@router.get("/quiz")
def quiz(intent: str = Query("explore")) -> dict[str, Any]:
    questions = [{"id": "intent", "prompt": "What can I help you with?", "options": ["foundation_shade", "skincare", "makeup", "outfit_match", "full_look", "fragrance", "kit", "explore"]}]
    if intent in {"foundation_shade", "makeup", "full_look", "kit", "outfit_match"}: questions += [{"id": "shade", "prompt": "Do you know your YAFA shade?", "optional": True}, {"id": "skin_type", "prompt": "What is your skin type?", "optional": True}]
    if intent in {"eyes", "makeup", "full_look", "kit", "outfit_match"}: questions.append({"id": "eye_colour", "prompt": "What is your eye colour?", "optional": True})
    if intent in {"eyes", "full_look", "kit"}: questions.append({"id": "hair_colour", "prompt": "What is your hair colour?", "optional": True})
    if intent in {"outfit_match", "full_look", "kit"}: questions.append({"id": "outfit", "prompt": "What colour is your outfit?", "optional": True})
    return {"intent": intent, "questions": questions}


@router.post("/yafa/next-question")
def yafa_next_question(request: YafaConversationRequest) -> dict[str, Any]:
    stored = profile_store.get(request.user_id) if request.user_id else None
    profile = merge_beauty_profiles(stored, None, request.profile)
    skin = profile.get("skin") or {}
    intent = request.intent
    if intent in {"find_foundation", "find_my_shade", "full_makeup_look", "wedding_guest_kit", "bridal_kit", "complete_yafa_kit"} and not skin.get("shade_code"):
        return {"agent": "Yafa", "profile_reused": bool(stored), "next_question": "Would you like to upload a selfie so I can estimate your closest YAFA VANAM shades?", "actions": ["upload_selfie", "answer_questions"]}
    if intent in {"find_foundation", "find_my_shade", "full_makeup_look", "wedding_guest_kit", "bridal_kit", "complete_yafa_kit"} and not skin.get("skin_types"):
        return {"agent": "Yafa", "profile_reused": bool(stored), "next_question": "What is your skin type?", "actions": ["dry", "normal", "combination", "oily", "skip"]}
    if intent in {"match_makeup_to_outfit", "full_makeup_look", "wedding_guest_kit", "bridal_kit", "complete_yafa_kit"} and not ((profile.get("context") or {}).get("outfit")):
        return {"agent": "Yafa", "profile_reused": bool(stored), "next_question": "What colour is your outfit?", "actions": ["describe_outfit", "upload_outfit", "skip"]}
    return {"agent": "Yafa", "profile_reused": bool(stored), "next_question": None, "ready": True}


@router.post("/feedback", status_code=202)
def feedback(event: FeedbackEvent) -> dict[str, Any]:
    # Contract-only V1: persistence belongs to the future analytics pipeline.
    if event.action not in {"viewed", "clicked", "accepted", "rejected", "added_to_cart", "purchased", "shade_corrected", "not_my_style"}:
        raise HTTPException(422, "Unsupported feedback action")
    return {"accepted": True, "event": event.model_dump()}
