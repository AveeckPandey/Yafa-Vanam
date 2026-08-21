"""Derive a reviewed CV confidence threshold from test_artifacts/test_results.json."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "test_artifacts" / "test_results.json"
CONFIG = ROOT / "calibration_config.json"
CURVE = ROOT / "test_artifacts" / "calibration_curve.svg"


def main() -> None:
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    rows = [row for row in report["results"] if isinstance(row.get("confidence"), (int, float))]
    if not rows:
        raise SystemExit("No confidence-bearing results found.")
    points = []
    suggested = None
    for threshold in [round(.5 + index * .05, 2) for index in range(10)]:
        selected = [row for row in rows if row["confidence"] >= threshold]
        accuracy = sum(row["correct"] for row in selected) / len(selected) if selected else 0
        points.append({"threshold": threshold, "sample_count": len(selected), "accuracy": round(accuracy, 3)})
        if selected and accuracy >= .85:
            suggested = threshold
    if suggested is None:
        raise SystemExit("No threshold reaches 85% accuracy; do not deploy CV shade determination.")
    CONFIG.write_text(json.dumps({"CONFIDENCE_THRESHOLD": suggested, "status": "review_required", "source_images": len(rows)}, indent=2), encoding="utf-8")
    CURVE.write_text(_svg(points), encoding="utf-8")


def _svg(points: list[dict]) -> str:
    coordinates = " ".join(f"{30 + index * 55},{170 - point['accuracy'] * 140:.0f}" for index, point in enumerate(points))
    labels = "".join(f"<text x='{30 + index * 55}' y='190' font-size='10'>{point['threshold']:.2f}</text>" for index, point in enumerate(points))
    return f"<svg xmlns='http://www.w3.org/2000/svg' width='560' height='210'><rect width='100%' height='100%' fill='white'/><text x='20' y='18'>CV confidence calibration</text><line x1='25' y1='170' x2='535' y2='170' stroke='black'/><polyline fill='none' stroke='#315b40' stroke-width='3' points='{coordinates}'/>{labels}</svg>"


if __name__ == "__main__":
    main()
