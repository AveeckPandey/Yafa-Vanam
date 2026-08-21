from __future__ import annotations

import json
from pathlib import Path

DEFAULT_CONFIDENCE_THRESHOLD = 0.72
CONFIG_PATH = Path(__file__).resolve().parents[2] / "calibration_config.json"


def confidence_threshold() -> float:
    """Read a validated, version-controlled calibration threshold.

    The service fails closed to a conservative default when no approved
    calibration output has been deployed yet.
    """
    try:
        value = float(json.loads(CONFIG_PATH.read_text(encoding="utf-8")).get("CONFIDENCE_THRESHOLD"))
    except (OSError, TypeError, ValueError, json.JSONDecodeError):
        return DEFAULT_CONFIDENCE_THRESHOLD
    return value if 0.5 <= value <= 0.95 else DEFAULT_CONFIDENCE_THRESHOLD
