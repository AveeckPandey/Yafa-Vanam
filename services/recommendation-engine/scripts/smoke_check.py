"""Smoke check for the private YAFA product-knowledge RAG service."""

import os
import sys
from pathlib import Path

from fastapi.testclient import TestClient

TOKEN = "smoke-test-token-0123456789abcdef0123"
os.environ["YAFA_INTERNAL_SERVICE_TOKEN"] = TOKEN
os.environ.pop("VECTOR_DATABASE_URL", None)
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.main import app


client = TestClient(app)
auth = {"x-yafa-service-token": TOKEN}
failures: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {name}" + (f" -- {detail}" if detail and not condition else ""))
    if not condition:
        failures.append(name)


health = client.get("/health")
check("GET /health identifies yafa-rag", health.status_code == 200 and health.json() == {"service": "yafa-rag", "status": "ok"}, health.text)

missing_auth = client.post("/internal/yafa/chat", json={"message": "hi"})
check("chat rejects missing token", missing_auth.status_code == 401, str(missing_auth.status_code))

recommendation = client.post("/internal/yafa/chat", headers=auth, json={"message": "Recommend a lipstick for me"})
recommendation_body = recommendation.json()
check("recommendation request stays explicit", recommendation.status_code == 200 and recommendation_body["intent"] == "recommendation_unavailable", recommendation.text[:180])
check("recommendation request returns no ranked products", recommendation_body["recommendations"] == [])

live = client.post("/internal/yafa/chat", headers=auth, json={"message": "Is this product in stock?"})
check("live commerce request defers to commerce API", live.status_code == 200 and live.json()["requires"]["domain"] == "inventory", live.text[:180])

fact = client.post("/internal/yafa/chat", headers=auth, json={"message": "What does this product contain?"})
check("fact request degrades honestly without vector DB", fact.status_code == 200 and "verified" in fact.json()["message"].lower(), fact.text[:180])

rag_health = client.get("/internal/rag/health", headers=auth)
check("RAG health reports unconfigured database", rag_health.status_code == 200 and rag_health.json()["status"] == "unconfigured", rag_health.text[:180])

for path in ("/internal/yafa/recommend", "/advisor/session", "/v1/catalogue/status", "/internal/yafa/vision/outfit"):
    retired = client.post(path, headers=auth, json={})
    check(f"retired endpoint {path} is absent", retired.status_code == 404, str(retired.status_code))

if failures:
    raise SystemExit(f"SMOKE RESULT: {len(failures)} failure(s): {failures}")
print("SMOKE RESULT: ALL CHECKS PASSED")
