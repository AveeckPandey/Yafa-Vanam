import io

from fastapi.testclient import TestClient
from PIL import Image

from app.main import app
from app.v1 import ciede2000, normalise_profile, rank
from app.vision.analyzer import select_three_shades
from app.models.skin_analysis import ShadeCandidate, SkinAnalysis, SkinAnalysisResult


client = TestClient(app)


def _request(intent="full_look"):
    return {
        "intent": intent,
        "profile": {
            "skin": {"shade_code": "5O", "depth": "medium_tan", "undertone": "olive", "skin_types": ["combination"]},
            "face": {"eye_colour": "brown", "hair_colour": "dark_brown", "hair_depth": "deep"},
            "makeup_preferences": {"coverage": "medium", "finish": "natural", "intensity": "soft_glam"},
            "context": {"occasion": "wedding", "daypart": "evening", "outfit": {"primary_colour": "emerald", "secondary_colours": ["gold"], "temperature": "warm"}},
        },
        "max_results_per_category": 3,
    }


def test_five_dataset_catalogue_is_authoritative_and_unique():
    response = client.get("/v1/catalogue/status")
    assert response.status_code == 200
    assert response.json()["datasets"] == {"skin": 11, "eyes": 15, "lips": 8, "cheeks": 6, "no_shades": 38}
    assert response.json()["unique_product_ids"] == 78


def test_confirmed_shade_wins_and_full_look_coordinates():
    response = client.post("/v1/recommend", json=_request())
    body = response.json()
    assert response.status_code == 200
    assert body["recommendations"]["skin"]["primary_match"]["shade"]["code"] == "5O"
    assert body["recommendations"]["eyes"]
    assert body["recommendations"]["lips"]["primary"]
    assert body["kit"]["items"]


def test_lab_colour_matching_uses_ciede2000_without_undertone_filter():
    request = _request("foundation_shade")
    request["profile"]["skin"] = {"lab": {"L": 52.4, "a": 13.7, "b": 28.0}, "undertone": "cool"}
    response = client.post("/v1/recommend/skin", json=request)
    assert response.status_code == 200
    primary = response.json()["recommendations"]["skin"]["primary_match"]
    assert primary["shade"]["code"] == "5O"
    assert primary["score_breakdown"]["shade_match"] > 0
    assert ciede2000((52.4, 13.7, 28.0), (52.3, 13.5, 27.8)) < 1


def test_hard_exclusion_removes_retinol_not_scores_it_low():
    request = _request("skincare")
    request["profile"]["safety_conditions"] = ["pregnant_or_planning_pregnancy"]
    response = client.post("/v1/recommend/skincare", json=request)
    names = {item["product"] for routine in response.json()["recommendations"]["skincare"].values() for item in routine}
    assert "Rootrenew Retinol Night Serum" not in names
    profile = normalise_profile(request["profile"])
    all_candidates = rank("no_shades", profile, 100, product_filter=lambda product: product["product_type"] == "Retinol Night Serum")
    assert all_candidates == []


def test_low_information_has_one_useful_follow_up():
    response = client.post("/v1/recommend/lips", json={"intent": "lips", "profile": {}})
    assert response.status_code == 200
    assert response.json()["confidence"]["level"] == "low"
    assert response.json()["follow_up_question"]


def test_customer_output_never_exposes_mock_validation_claims():
    response = client.post("/v1/recommend", json=_request())
    serialised = str(response.json()).lower()
    for forbidden in ("wear hours", "ophthalmological", "regulatory approval", "inci", "verified spf 50"):
        assert forbidden not in serialised


def test_debug_is_explicitly_opt_in():
    request = _request("lips")
    normal = client.post("/v1/recommend/lips", json=request).json()
    assert "debug" not in normal["recommendations"]["lips"]["primary"]
    request["debug"] = True
    debug = client.post("/v1/recommend/lips", json=request).json()
    assert debug["recommendations"]["lips"]["primary"]["debug"]["data_source"] == "authoritative_catalogue_json"


def test_quiz_is_goal_adaptive():
    lips = client.get("/v1/quiz?intent=lips").json()["questions"]
    full_look = client.get("/v1/quiz?intent=full_look").json()["questions"]
    assert [question["id"] for question in lips] == ["intent"]
    assert {"shade", "eye_colour", "hair_colour", "outfit"}.issubset({question["id"] for question in full_look})


def test_kit_has_no_duplicate_product_role_conflicts():
    body = client.post("/v1/recommend/kit", json=_request("kit")).json()
    items = body["kit"]["items"]
    product_ids = [item["recommendation"]["product_id"] for item in items]
    assert len(product_ids) == len(set(product_ids))


def test_planned_sunscreen_never_becomes_a_verified_claim():
    response = client.post("/v1/recommend/skincare", json={"profile": {"skin": {"skin_types": ["normal"]}}})
    text = str(response.json()).lower()
    assert "verified spf 50" not in text


def test_cv_shade_ranker_returns_three_useful_candidates_with_5o_first():
    candidates = select_three_shades((52.4, 13.7, 28.0))
    assert len(candidates) == 3
    assert candidates[0].shade_code == "5O"
    assert candidates[0].role == "best_match"
    assert len({candidate.shade_code for candidate in candidates}) == 3


def test_poor_image_requires_retake_and_is_never_persisted():
    image = Image.new("RGB", (300, 300), "black")
    payload = io.BytesIO(); image.save(payload, format="PNG")
    response = client.post("/v1/vision/analyse-skin", data={"user_id": "privacy-test"}, files={"image": ("dark.png", payload.getvalue(), "image/png")})
    assert response.status_code == 200
    body = response.json()
    assert body["quality_pass"] is False
    assert body["retake_required"] is True
    assert body["raw_image_persisted"] is False
    assert client.get("/v1/profile/beauty?user_id=privacy-test").json()["profile"] is None


def test_manual_confirmation_overrides_cv_and_is_reused_for_recommendation():
    user_id = "shade-confirmation-test"
    response = client.patch("/v1/profile/beauty", json={"user_id": user_id, "profile": {"skin": {"shade_code": "5O", "shade_source": "computer_vision", "user_confirmed": False}}})
    assert response.status_code == 200
    confirmed = client.post("/v1/profile/confirm-shade", json={"user_id": user_id, "shade_code": "5W"})
    assert confirmed.status_code == 200
    assert confirmed.json()["profile"]["skin"]["shade_code"] == "5W"
    recommendation = client.post("/v1/recommend/skin", json={"user_id": user_id, "profile": {}}).json()
    assert recommendation["profile_reused"] is True
    assert recommendation["recommendations"]["skin"]["primary_match"]["shade"]["code"] == "5W"


def test_returning_customer_is_not_asked_for_another_selfie():
    user_id = "returning-customer-test"
    client.patch("/v1/profile/beauty", json={"user_id": user_id, "profile": {"skin": {"shade_code": "5O", "user_confirmed": True}}})
    response = client.post("/v1/yafa/next-question", json={"user_id": user_id, "intent": "wedding_guest_kit"})
    body = response.json()
    assert body["profile_reused"] is True
    assert "selfie" not in str(body["next_question"]).lower()


def test_successful_cv_persists_only_derived_profile_data(monkeypatch):
    import app.v1 as routes

    result = SkinAnalysisResult(
        quality_pass=True, face_detected=True,
        analysis=SkinAnalysis(lab={"L": 52.4, "a": 13.7, "b": 28.0}, ita=4.8, depth_family="medium_tan", undertone="olive"),
        shade_candidates=[
            ShadeCandidate(shade_code="5O", shade_name="Olive Honey", role="best_match", colour_distance=.2, confidence=.95),
            ShadeCandidate(shade_code="4O", shade_name="Olive Almond", role="slightly_lighter", colour_distance=4.1, confidence=.84),
            ShadeCandidate(shade_code="6N", shade_name="Caramel Earth", role="slightly_deeper", colour_distance=4.5, confidence=.82),
        ], confidence=.89,
    )
    monkeypatch.setattr(routes, "analyse_skin_image", lambda _: result)
    response = client.post("/v1/vision/analyse-skin", data={"user_id": "cv-success-test"}, files={"image": ("selfie.png", b"temporary-image-bytes", "image/png")})
    assert response.status_code == 200
    assert response.json()["raw_image_persisted"] is False
    saved = client.get("/v1/profile/beauty?user_id=cv-success-test").json()["profile"]
    assert saved["skin"]["shade_code"] == "5O"
    assert "raw_image" not in str(saved)
    assert "temporary-image-bytes" not in str(saved)
