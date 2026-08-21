"""Run the private CV validation endpoint against a consented image manifest."""
from __future__ import annotations

import base64
import json
import os
import time
from collections import defaultdict
from html import escape
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
IMAGES = ROOT / "test_images"
MANIFEST = IMAGES / "manifest.json"
OUTPUT = ROOT / "test_artifacts"
ENDPOINT = os.getenv("CV_TEST_ENDPOINT", "http://127.0.0.1:8000/ai/analyze-image")


def main() -> None:
    token = os.environ.get("YAFA_INTERNAL_SERVICE_TOKEN", "")
    if len(token) < 32:
        raise SystemExit("YAFA_INTERNAL_SERVICE_TOKEN must be set to run the internal CV harness.")
    entries = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if not isinstance(entries, list) or len(entries) < 30:
        raise SystemExit("manifest.json must contain at least 30 labelled test images.")
    OUTPUT.mkdir(exist_ok=True)
    results: list[dict] = []
    with httpx.Client(timeout=20.0) as client:
        for entry in entries:
            image_path = IMAGES / str(entry["filename"])
            started = time.perf_counter()
            response = client.post(ENDPOINT, headers={"X-Yafa-Service-Token": token}, json={"image_base64": base64.b64encode(image_path.read_bytes()).decode("ascii")})
            elapsed = round((time.perf_counter() - started) * 1000, 1)
            payload = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
            analysis = payload.get("analysis") or {}
            predicted_depth = analysis.get("depth_family")
            predicted_undertone = analysis.get("undertone")
            correct = bool(payload.get("shade_determined")) and predicted_depth == entry["ground_truth_depth"] and predicted_undertone == entry["ground_truth_undertone"]
            results.append({**entry, "status_code": response.status_code, "predicted_depth": predicted_depth, "predicted_undertone": predicted_undertone, "confidence": payload.get("confidence"), "shade_determined": payload.get("shade_determined", False), "face_detected": payload.get("face_detected", False), "skin_region_ratio": payload.get("skin_region_ratio"), "processing_time_ms": elapsed, "correct": correct, "high_confidence_error": bool(payload.get("confidence", 0) > .8 and not correct)})
    by_type: dict[str, dict[str, float]] = {}
    for fitzpatrick, rows in _groups(results, "fitzpatrick_type").items():
        by_type[fitzpatrick] = _summary(rows)
    report = {"overall": _summary(results), "by_fitzpatrick_type": by_type, "high_confidence_errors": [row["filename"] for row in results if row["high_confidence_error"]], "results": results}
    (OUTPUT / "test_results.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    (OUTPUT / "test_report.html").write_text(_html(report), encoding="utf-8")
    if report["overall"]["face_detection_rate"] < .95:
        raise SystemExit("Face detection did not meet the 95% validation threshold; inspect test_artifacts/test_report.html.")


def _groups(rows: list[dict], key: str) -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        grouped[str(row[key])].append(row)
    return grouped


def _summary(rows: list[dict]) -> dict[str, float]:
    count = len(rows) or 1
    return {"count": len(rows), "accuracy": round(sum(row["correct"] for row in rows) / count, 3), "face_detection_rate": round(sum(row["face_detected"] for row in rows) / count, 3), "skin_region_over_5pct_rate": round(sum((row["skin_region_ratio"] or 0) > .05 for row in rows) / count, 3), "mean_processing_time_ms": round(sum(row["processing_time_ms"] for row in rows) / count, 1)}


def _html(report: dict) -> str:
    rows = "".join(f"<tr><td>{escape(group)}</td><td>{values['count']}</td><td>{values['accuracy']:.1%}</td><td>{values['face_detection_rate']:.1%}</td><td>{values['skin_region_over_5pct_rate']:.1%}</td></tr>" for group, values in sorted(report["by_fitzpatrick_type"].items()))
    return f"<!doctype html><title>YAFA CV validation</title><h1>YAFA CV validation</h1><p>Overall accuracy: {report['overall']['accuracy']:.1%}. Face detection: {report['overall']['face_detection_rate']:.1%}.</p><table><tr><th>Fitzpatrick</th><th>Images</th><th>Accuracy</th><th>Face detected</th><th>Skin region &gt;5%</th></tr>{rows}</table><p>High-confidence errors: {escape(', '.join(report['high_confidence_errors']) or 'None')}</p>"


if __name__ == "__main__":
    main()
