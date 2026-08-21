import base64

from fastapi.testclient import TestClient

import app.api.yafa_analysis as yafa_analysis
from app.main import app
from app.models.skin_analysis import ShadeCandidate, SkinAnalysis, SkinAnalysisResult


def _result(confidence: float) -> SkinAnalysisResult:
    return SkinAnalysisResult(
        quality_pass=True,
        face_detected=True,
        analysis=SkinAnalysis(lab={"L": 52.4, "a": 13.7, "b": 28.0}, ita=4.8, depth_family="medium_tan", undertone="olive"),
        shade_candidates=[
            ShadeCandidate(shade_code="5O", shade_name="Olive Honey", role="best_match", colour_distance=.2, confidence=.95),
            ShadeCandidate(shade_code="4O", shade_name="Olive Almond", role="slightly_lighter", colour_distance=4.1, confidence=.84),
            ShadeCandidate(shade_code="6N", shade_name="Caramel Earth", role="slightly_deeper", colour_distance=4.5, confidence=.82),
        ],
        confidence=confidence,
        skin_region_ratio=.08,
    )


def test_internal_analysis_returns_calibrated_result(monkeypatch):
    monkeypatch.setenv("YAFA_INTERNAL_SERVICE_TOKEN", "t" * 32)
    monkeypatch.setattr(yafa_analysis, "analyse_skin_image", lambda _: _result(.9))
    response = TestClient(app).post("/ai/analyze-image", headers={"X-Yafa-Service-Token": "t" * 32}, json={"image_base64": base64.b64encode(b"test-image").decode("ascii")})
    assert response.status_code == 200
    body = response.json()
    assert body["cv_used"] is True
    assert body["shade_determined"] is True
    assert len(body["candidates"]) == 3
    assert body["analysis"]["undertone"] == "olive"


def test_low_confidence_does_not_return_cv_shades(monkeypatch):
    monkeypatch.setenv("YAFA_INTERNAL_SERVICE_TOKEN", "t" * 32)
    monkeypatch.setattr(yafa_analysis, "analyse_skin_image", lambda _: _result(.6))
    response = TestClient(app).post("/ai/analyze-image", headers={"X-Yafa-Service-Token": "t" * 32}, json={"image_base64": base64.b64encode(b"test-image").decode("ascii")})
    assert response.status_code == 200
    body = response.json()
    assert body["cv_used"] is False
    assert body["shade_determined"] is False
    assert body["candidates"] == []
