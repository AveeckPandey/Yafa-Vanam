from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import json
import os
from typing import Any


class DerivedBeautyProfileStore:
    """Development repository. Stores derived fields only; never accepts image bytes."""

    def __init__(self) -> None:
        self._profiles: dict[str, dict[str, Any]] = {}
        self._analysis_events: list[dict[str, Any]] = []

    def get(self, user_id: str) -> dict[str, Any] | None:
        value = self._profiles.get(user_id)
        return deepcopy(value) if value else None

    def save(self, user_id: str, profile: dict[str, Any]) -> dict[str, Any]:
        clean = deepcopy(profile)
        clean.pop("raw_image", None)
        clean.pop("image_bytes", None)
        clean["user_id"] = user_id
        clean["updated_at"] = datetime.now(timezone.utc).isoformat()
        self._profiles[user_id] = clean
        return deepcopy(clean)

    def save_analysis_event(self, user_id: str, event: dict[str, Any]) -> None:
        clean = deepcopy(event)
        clean.pop("raw_image", None)
        clean.pop("image_bytes", None)
        clean["user_id"] = user_id
        clean["created_at"] = datetime.now(timezone.utc).isoformat()
        self._analysis_events.append(clean)


class PostgresDerivedBeautyProfileStore(DerivedBeautyProfileStore):
    """PostgreSQL implementation, enabled only when YAFA_DATABASE_URL is supplied."""

    def __init__(self, database_url: str) -> None:
        import psycopg  # Optional production dependency; development remains DB-free.
        self._connection = psycopg.connect(database_url)

    def get(self, user_id: str) -> dict[str, Any] | None:
        with self._connection.cursor() as cursor:
            cursor.execute("SELECT profile_json FROM user_beauty_profiles WHERE user_id = %s", (user_id,))
            row = cursor.fetchone()
        return row[0] if row else None

    def save(self, user_id: str, profile: dict[str, Any]) -> dict[str, Any]:
        clean = deepcopy(profile); clean.pop("raw_image", None); clean.pop("image_bytes", None)
        clean["user_id"] = user_id; clean["updated_at"] = datetime.now(timezone.utc).isoformat()
        skin = clean.get("skin") or {}; prefs = clean.get("makeup_preferences") or {}; lab = skin.get("lab") or {}
        with self._connection.cursor() as cursor:
            cursor.execute("""INSERT INTO user_beauty_profiles
                (user_id, confirmed_shade_code, confirmed_shade_source, estimated_depth_family, estimated_undertone, lab_l, lab_a, lab_b, ita, cv_confidence, skin_types, concerns, preferred_coverage, preferred_finish, preferred_intensity, user_confirmed, profile_json)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (user_id) DO UPDATE SET confirmed_shade_code=EXCLUDED.confirmed_shade_code, confirmed_shade_source=EXCLUDED.confirmed_shade_source, estimated_depth_family=EXCLUDED.estimated_depth_family, estimated_undertone=EXCLUDED.estimated_undertone, lab_l=EXCLUDED.lab_l, lab_a=EXCLUDED.lab_a, lab_b=EXCLUDED.lab_b, ita=EXCLUDED.ita, cv_confidence=EXCLUDED.cv_confidence, skin_types=EXCLUDED.skin_types, concerns=EXCLUDED.concerns, preferred_coverage=EXCLUDED.preferred_coverage, preferred_finish=EXCLUDED.preferred_finish, preferred_intensity=EXCLUDED.preferred_intensity, user_confirmed=EXCLUDED.user_confirmed, profile_json=EXCLUDED.profile_json, updated_at=now()""",
                (user_id, skin.get("shade_code"), skin.get("shade_source"), skin.get("depth_family"), skin.get("undertone"), lab.get("L"), lab.get("a"), lab.get("b"), skin.get("ita"), skin.get("shade_confidence"), json.dumps(skin.get("skin_types", [])), json.dumps(skin.get("concerns", [])), prefs.get("coverage"), prefs.get("finish"), prefs.get("intensity"), skin.get("user_confirmed", False), json.dumps(clean)))
        self._connection.commit()
        return clean

    def save_analysis_event(self, user_id: str, event: dict[str, Any]) -> None:
        clean = deepcopy(event); clean.pop("raw_image", None); clean.pop("image_bytes", None)
        with self._connection.cursor() as cursor:
            cursor.execute("INSERT INTO skin_analysis_events (user_id, predicted_shade_code, candidate_1, candidate_2, candidate_3, confidence, source, event_json) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)", (user_id, clean.get("predicted_shade_code"), clean.get("candidate_1"), clean.get("candidate_2"), clean.get("candidate_3"), clean.get("confidence"), clean.get("source"), json.dumps(clean)))
        self._connection.commit()


profile_store: DerivedBeautyProfileStore = PostgresDerivedBeautyProfileStore(os.environ["YAFA_DATABASE_URL"]) if os.getenv("YAFA_DATABASE_URL") else DerivedBeautyProfileStore()
