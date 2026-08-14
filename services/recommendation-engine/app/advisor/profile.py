from __future__ import annotations

from typing import Any

from .models import AdvisorSession, Depth, Goal, Undertone
from .shade_matcher import resolve_master_shade


def _clean(value: Any) -> Any:
    return None if value in {"unknown", "none", "surprise", ""} else value


def apply_answer(session: AdvisorSession, question_id: str, answer: Any) -> None:
    session.answers[question_id] = answer
    p = session.profile
    value = _clean(answer)
    if question_id == "goal" and value:
        p.goal = Goal(value)
    elif question_id == "match_method":
        if value == "manual": p.complexion.source = "manual"
        elif value == "known_shade": p.complexion.source = "known_shade"
        elif value == "selfie": p.complexion.source = "vision"
    elif question_id == "depth":
        p.complexion.depth = Depth(value) if value else None
    elif question_id == "undertone":
        p.complexion.undertone = Undertone(value) if value else None
    elif question_id == "known_shade":
        p.complexion.shade_code = str(value).upper() if value else None
        p.complexion.source = "known_shade"
        shade = resolve_master_shade(p)
        if value and not shade:
            p.complexion.shade_code = None
            raise ValueError("Unknown YAFA VANAM master shade code")
        p.complexion.shade_name = shade.name if shade else None
        p.complexion.confirmed = bool(shade)
    elif question_id == "skin_type": p.skin.type = value
    elif question_id == "coverage": p.preferences.coverage = value
    elif question_id == "finish": p.preferences.finish = value
    elif question_id == "occasion": p.occasion = value
    elif question_id == "style": p.preferences.style = value
    elif question_id == "colour_family": p.preferences.colour_family = value
    elif question_id == "lip_finish": p.preferences.lip_finish = value
    elif question_id == "eye_look": p.preferences.eye_look = value
    elif question_id == "mascara_priority": p.preferences.mascara_priority = value
    elif question_id == "concealer_mode": p.preferences.concealer_mode = value
    elif question_id == "corrector_concern": p.preferences.corrector_concern = value

    shade = resolve_master_shade(p)
    if shade:
        p.complexion.shade_code = shade.code
        p.complexion.shade_name = shade.name


def apply_changes(session: AdvisorSession, changes: dict[str, Any]) -> None:
    aliases = {
        "depth": "depth", "undertone": "undertone", "skin_type": "skin_type", "coverage": "coverage",
        "finish": "finish", "occasion": "occasion", "style": "style", "colour_family": "colour_family",
        "lip_finish": "lip_finish", "eye_look": "eye_look", "mascara_priority": "mascara_priority",
        "concealer_mode": "concealer_mode", "corrector_concern": "corrector_concern", "goal": "goal", "match_method": "match_method",
    }
    for key, value in changes.items():
        if key in aliases:
            apply_answer(session, aliases[key], value)
