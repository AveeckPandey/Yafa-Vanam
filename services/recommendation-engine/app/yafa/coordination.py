"""Full-look coordination pass (spec Phase 2 §31/§32).

Engines rank independently; this stage makes the COMBINATION cohesive:

1. cheek -> lip family coordination via the dataset's
   ``recommended_lip_color_families`` (already surfaced as
   ``CoordinationHints.lip_color_family``).
2. colour-temperature cohesion across eye/cheek/lip winners.
3. boldness balance: avoid very bold eye + very bold blush + very bold lip
   unless the customer asked for a bold look.

Everything stays deterministic: no LLM, no invented products, only reason
codes and re-selection among engine-ranked candidates.
"""
from __future__ import annotations

from typing import Any

from app.recommendation.canonical.schemas import CoordinationHints

WARM_FAMILIES = frozenset({
    "peach", "terracotta", "brick", "copper", "bronze", "gold", "warm_rose",
    "warm_brown", "brown", "coral", "apricot", "olive", "champagne",
})
COOL_FAMILIES = frozenset({
    "rose_pink", "rose", "berry", "plum", "mauve", "cool_brown", "taupe",
    "silver", "charcoal", "pink",
})
BOLD_FAMILIES = frozenset({"berry", "plum", "brick", "red", "deep_berry", "vivid"})


def family_temperature(family: str | None) -> str | None:
    if not family:
        return None
    if family in WARM_FAMILIES:
        return "warm"
    if family in COOL_FAMILIES:
        return "cool"
    return None


def _boldness(item: dict[str, Any]) -> bool:
    family = (item.get("color_family") or "").lower()
    if family in BOLD_FAMILIES:
        return True
    return any("bold" in code for code in item.get("reason_codes", []))


def lip_hints_from_cheek(cheek_items: list[dict[str, Any]]) -> CoordinationHints:
    """CoordinationHints for the lip engine from the cheek winner."""
    top = cheek_items[0] if cheek_items else None
    hints = CoordinationHints()
    if top and top.get("color_family"):
        hints.lip_color_family = top["color_family"]
    style = None
    if top:
        for code in top.get("reason_codes", []):
            if code.endswith("_match") and "glam" in code:
                style = code.replace("_match", "")
                break
    hints.look_style = style
    return hints


def apply_cohesion(
    selections: dict[str, list[dict[str, Any]]],
    *,
    bold_requested: bool = False,
) -> dict[str, list[str]]:
    """Second-stage pass over per-category winners.

    Mutates nothing; returns extra reason codes per category. A warm/cool match
    across two or more of {eyes, cheeks, lips} earns ``look_cohesion_*`` codes;
    an all-bold trio earns a warning unless a bold look was requested.
    """
    extra: dict[str, list[str]] = {}

    temperatures = {
        category: family_temperature((items[0].get("color_family") if items else None))
        for category, items in selections.items()
        if category in {"eyes", "cheeks", "lips"}
    }
    present = {temp for temp in temperatures.values() if temp}
    if len(present) >= 2:
        dominant = max(present, key=lambda t: sum(1 for v in temperatures.values() if v == t))
        aligned = [c for c, t in temperatures.items() if t == dominant]
        for category in aligned:
            extra.setdefault(category, []).append(f"look_cohesion_{dominant}_family")

    if not bold_requested:
        bold_categories = [
            category
            for category, items in selections.items()
            if category in {"eyes", "cheeks", "lips"} and items and _boldness(items[0])
        ]
        if len(bold_categories) >= 3:
            for category in bold_categories[1:]:
                extra.setdefault(category, []).append("intensity_balance_warning")
    return extra


def coordination_notes(selections: dict[str, list[dict[str, Any]]]) -> list[str]:
    """Human-readable summary lines for the composed message."""
    notes: list[str] = []
    cheek = selections.get("cheeks")
    lip = selections.get("lips")
    if cheek and lip and cheek[0].get("color_family") and lip[0].get("color_family"):
        notes.append(
            "Cheek and lip families were coordinated so the combination reads "
            "as one look rather than separate picks."
        )
    extras = apply_cohesion(selections)
    if any("look_cohesion_warm_family" in codes for codes in extras.values()):
        notes.append("The picks share a warm colour direction across categories.")
    elif any("look_cohesion_cool_family" in codes for codes in extras.values()):
        notes.append("The picks share a cool colour direction across categories.")
    return notes
