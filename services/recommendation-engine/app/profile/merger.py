from __future__ import annotations

from copy import deepcopy
from typing import Any


def merge_beauty_profiles(stored: dict[str, Any] | None, cv: dict[str, Any] | None, quiz: dict[str, Any] | None) -> dict[str, Any]:
    """Merge profile sources without allowing CV to overwrite a confirmed shade.

    Precedence for shade is manual/confirmed stored > current CV > quiz estimate.
    Other fields are filled from stored data first and then current CV/quiz values.
    """
    result = deepcopy(stored or {})
    result.setdefault("skin", {})
    for source in (quiz or {}, cv or {}):
        for section, values in source.items():
            if not isinstance(values, dict):
                if values is not None: result.setdefault(section, values)
                continue
            target = result.setdefault(section, {})
            for key, value in values.items():
                if value is None: continue
                if section == "skin" and key == "shade_code" and result["skin"].get("user_confirmed"):
                    continue
                if key not in target or target[key] in (None, [], ""):
                    target[key] = deepcopy(value)
    # CV should beat an unconfirmed quiz-only estimate, but never a saved confirmation.
    cv_skin = (cv or {}).get("skin") or {}
    if cv_skin and not result["skin"].get("user_confirmed"):
        for key in ("depth_family", "undertone", "lab", "ita", "shade_confidence", "shade_source"):
            if cv_skin.get(key) is not None: result["skin"][key] = deepcopy(cv_skin[key])
    return result
