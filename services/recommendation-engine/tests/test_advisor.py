from fastapi.testclient import TestClient

from app.advisor.catalogue import load_catalogue
from app.advisor.models import BeautyProfile, ComplexionProfile, Depth, Goal, Preferences, SkinProfile, Undertone
from app.advisor.recommender import recommend
from app.advisor.shade_matcher import brightening_variant, master_code, resolve_master_shade
from app.main import app

client = TestClient(app)


def test_catalogue_is_current_78_product_source():
    assert len(load_catalogue()) == 78


def test_medium_tan_olive_maps_to_5o_olive_honey():
    profile = BeautyProfile(complexion=ComplexionProfile(depth=Depth.medium_tan, undertone=Undertone.olive))
    assert master_code("medium_tan", "olive") == "5O"
    shade = resolve_master_shade(profile)
    assert shade is not None
    assert shade.code == "5O"
    assert shade.name == "Olive Honey"


def test_full_look_light_natural_prefers_skin_tint_and_exact_5o():
    profile = BeautyProfile(
        goal=Goal.full_look,
        complexion=ComplexionProfile(depth=Depth.medium_tan, undertone=Undertone.olive, shade_code="5O", shade_name="Olive Honey", confirmed=True),
        skin=SkinProfile(type="combination"),
        preferences=Preferences(coverage="light", finish="natural", style="soft_glam", colour_family="mauve", lip_finish="velvet"),
        occasion="date_dinner",
    )
    recs = recommend(profile)
    assert recs
    assert recs[0].product_name == "Mistveil Skin Tint"
    assert recs[0].shade is not None
    assert recs[0].shade.code == "5O"
    assert recs[0].shade.name == "Olive Honey"


def test_brightening_concealer_moves_only_one_depth_and_keeps_compatible_undertone():
    profile = BeautyProfile(
        goal=Goal.complexion,
        complexion=ComplexionProfile(depth=Depth.medium_tan, undertone=Undertone.olive, shade_code="5O"),
        preferences=Preferences(concealer_mode="brightening"),
    )
    concealer = next(p for p in load_catalogue() if p["name"] == "Underleaf Cover Concealer")
    variant = brightening_variant(concealer, profile)
    assert variant is not None
    shade = variant["shade"]
    assert shade["depth_index"] == 4
    assert shade["undertone"] in {"olive", "neutral", "warm", "cool"}


def test_corrector_not_recommended_without_explicit_concern():
    profile = BeautyProfile(
        goal=Goal.full_look,
        complexion=ComplexionProfile(depth=Depth.medium, undertone=Undertone.neutral, shade_code="4N"),
    )
    recs = recommend(profile)
    assert all(r.product_name != "Tonepetal Color Corrector" for r in recs)


def test_mascara_priority_is_deterministic():
    for priority, expected in [("volume", "Fernwing Volume Mascara"), ("lift", "Nightbloom Lift Mascara"), ("tubing", "Softwing Tubing Mascara")]:
        profile = BeautyProfile(goal=Goal.eyes, preferences=Preferences(mascara_priority=priority, eye_look="natural"))
        recs = recommend(profile)
        mascara = next(r for r in recs if "Mascara" in r.product_name)
        assert mascara.product_name == expected


def test_session_can_modify_without_restarting():
    created = client.post("/advisor/session", json={"goal": "lips"})
    assert created.status_code == 200
    session = created.json()
    sid = session["id"]
    # lips path starts at occasion after goal because complexion is not needed
    for question_id, answer in [
        ("occasion", "date_dinner"), ("style", "soft_glam"), ("colour_family", "mauve"), ("lip_finish", "velvet")
    ]:
        response = client.post(f"/advisor/session/{sid}/answer", json={"question_id": question_id, "answer": answer})
        assert response.status_code == 200, response.text
    result = client.post(f"/advisor/session/{sid}/recommend")
    assert result.status_code == 200
    before = result.json()
    modified = client.post(f"/advisor/session/{sid}/modify", json={"changes": {"lip_finish": "satin"}})
    assert modified.status_code == 200
    after = modified.json()
    assert after["profile"]["preferences"]["lip_finish"] == "satin"
    assert after["answers"]["occasion"] == before["answers"]["occasion"]
    assert after["answers"]["colour_family"] == before["answers"]["colour_family"]


def test_unknown_answers_do_not_create_fake_profile_values():
    response = client.post("/advisor/session", json={"goal": "complexion"})
    sid = response.json()["id"]
    client.post(f"/advisor/session/{sid}/answer", json={"question_id": "match_method", "answer": "manual"})
    response = client.post(f"/advisor/session/{sid}/answer", json={"question_id": "depth", "answer": "unknown"})
    assert response.status_code == 200
    body = response.json()
    assert body["profile"]["complexion"]["depth"] is None


def test_image_analysis_never_returns_fake_analysis_when_provider_disabled():
    response = client.post("/advisor/session", json={"goal": "complexion"})
    sid = response.json()["id"]
    result = client.post(f"/advisor/session/{sid}/image-analysis", json={"kind": "selfie", "image_url": "https://example.invalid/selfie.jpg"})
    assert result.status_code == 200
    assert result.json()["status"] == "not_configured"
    assert result.json()["analysis"] is None

def test_undertone_options_follow_the_canonical_24_shade_catalogue():
    response = client.post("/advisor/session", json={"goal": "complexion"})
    sid = response.json()["id"]
    client.post(f"/advisor/session/{sid}/answer", json={"question_id": "match_method", "answer": "manual"})
    response = client.post(f"/advisor/session/{sid}/answer", json={"question_id": "depth", "answer": "fair"})
    options = {x["value"] for x in response.json()["current_step"]["options"]}
    assert "olive" not in options
    assert {"cool", "neutral", "warm"}.issubset(options)


def test_known_shade_rejects_non_catalogue_code():
    response = client.post("/advisor/session", json={"goal": "complexion"})
    sid = response.json()["id"]
    client.post(f"/advisor/session/{sid}/answer", json={"question_id": "match_method", "answer": "known_shade"})
    response = client.post(f"/advisor/session/{sid}/answer", json={"question_id": "known_shade", "answer": "99Z"})
    assert response.status_code == 422
