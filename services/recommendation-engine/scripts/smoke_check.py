"""End-to-end smoke check for the internal Yafa endpoints (no server needed)."""
import base64
import io
import json
import os
import sys

# A valid-looking token (>= 32 chars) purely for this local smoke run.
TOKEN = "smoke-test-token-0123456789abcdef0123"
os.environ["YAFA_INTERNAL_SERVICE_TOKEN"] = TOKEN
os.environ.pop("VECTOR_DATABASE_URL", None)
os.environ.pop("WHISPER_ENABLED", None)

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)
auth = {"x-yafa-service-token": TOKEN}
failures = []


def check(name, condition, detail=""):
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {name}" + (f" -- {detail}" if detail and not condition else ""))
    if not condition:
        failures.append(name)


# 1. Health endpoint (public).
r = client.get("/health")
check("GET /health", r.status_code == 200 and r.json().get("status") == "ok", r.text[:120])

# 2. Auth enforced.
r = client.post("/internal/yafa/chat", json={"message": "hi"})
check("chat rejects missing token (401)", r.status_code == 401, f"got {r.status_code}")
r = client.post("/internal/yafa/chat", json={"message": "hi"}, headers={"x-yafa-service-token": "wrong-wrong-wrong-wrong-wrong"})
check("chat rejects bad token (401)", r.status_code == 401, f"got {r.status_code}")

# 3. Recommendation intent -> catalogue-validated cards.
r = client.post("/internal/yafa/chat", headers=auth, json={
    "message": "Recommend a lipstick for me",
    "profile": {
        "skin": {"depth": "medium_tan", "undertone": "warm"},
        "context": {"occasion": "wedding", "outfit": {"primary_colour": "emerald"}},
    },
})
body = r.json()
check("lip recommendation returns 200", r.status_code == 200, r.text[:200])
check("intent=lip_recommendation", body.get("intent") == "lip_recommendation", str(body.get("intent")))
recs = body.get("recommendations") or []
check("has catalogue-validated recommendations", len(recs) > 0 and all(x["product_id"].startswith("yv-") for x in recs), json.dumps(recs)[:160])

# 4. Full look coordination.
r = client.post("/internal/yafa/chat", headers=auth, json={
    "message": "Build my look for a wedding",
    "profile": {"skin": {"depth": "medium_tan", "undertone": "warm"}, "makeup_preferences": {"intensity": "soft_glam"}},
})
cats = {x["category"] for x in (r.json().get("recommendations") or [])}
check("full look covers cheeks+lips", r.status_code == 200 and {"cheeks", "lips"} <= cats, str(cats))

# 5. Live-data routing.
r = client.post("/internal/yafa/chat", headers=auth, json={"message": "Is Soft Ember in stock?"})
req_ = r.json().get("requires")
check("stock question -> requires inventory (Go)", req_ is not None and req_.get("domain") == "inventory", r.text[:160])

# 6. Product info without RAG configured -> honest degradation, no crash.
r = client.post("/internal/yafa/chat", headers=auth, json={
    "message": "What does this smell like?",
    "page_context": {"type": "product", "product_id": "yv-frag-010"},
})
body = r.json()
# Scent is fact-scoped: without verified data Yafa says so plainly
# ("don't have verified scent information") instead of dumping other facts.
check("product info degrades cleanly without vector DB",
      r.status_code == 200 and "verified" in body["message"].lower(),
      r.text[:160])

# 7. Conversation continuity: slots from turn 1 influence turn 2.
r1 = client.post("/internal/yafa/chat", headers=auth, json={"message": "I'm going to a wedding wearing emerald"})
conv_id = r1.json()["conversation_id"]
r2 = client.post("/internal/yafa/chat", headers=auth, json={"message": "Recommend a lipstick please", "conversation_id": conv_id})
codes = {c for x in (r2.json().get("recommendations") or []) for c in x["reason_codes"]}
check("persisted slots influence ranking", any("outfit_harmony" in c or c == "wedding_match" or c == "occasion_special_occasion_match" for c in codes), str(sorted(codes))[:200])

# 8. Outfit vision: structured attributes only.
def _try_pil():
    try:
        from PIL import Image as PILImage
        return PILImage
    except ImportError:
        return None

img = Image.new("RGB", (220, 220), (22, 118, 82)) if (Image := _try_pil()) else None
if img is not None:
    buf = io.BytesIO(); img.save(buf, format="PNG")
    r = client.post("/internal/yafa/vision/outfit", headers=auth, files={"image": ("outfit.png", buf.getvalue(), "image/png")})
    body = r.json()
    check("outfit vision detects emerald", r.status_code == 200 and body.get("primary_colour") == "emerald", r.text[:160])
    check("outfit vision has no product fields", "products" not in body and "recommendations" not in body)
else:
    check("outfit vision (PIL unavailable, skipped)", True)

# 9. Speech transcribe: 503 when Whisper not enabled.
buf = io.BytesIO(); buf.write(b"fake-bytes"); buf.seek(0)
r = client.post("/internal/yafa/speech/transcribe", headers=auth, files={"audio": ("a.webm", buf, "audio/webm")})
check("speech 503 when whisper unconfigured", r.status_code == 503, f"got {r.status_code} {r.text[:100]}")

# 10. RAG health reports unconfigured without leaking internals.
r = client.get("/internal/rag/health", headers=auth)
b = r.json()
check("rag health honest when unconfigured", r.status_code == 200 and b["status"] == "unconfigured" and b["database_connected"] is False, r.text[:160])
check("rag health leaks no credentials", "@" not in r.text and "postgres://" not in r.text)

print()
if failures:
    print(f"SMOKE RESULT: {len(failures)} failure(s): {failures}")
    sys.exit(1)
print("SMOKE RESULT: ALL CHECKS PASSED")
