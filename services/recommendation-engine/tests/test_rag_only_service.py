"""The Python service exposes only protected RAG and RAG-chat routes."""
from fastapi.testclient import TestClient

from app.main import app


def test_health_and_legacy_recommendation_routes():
    with TestClient(app) as client:
        assert client.get("/health").json() == {"service": "yafa-rag", "status": "ok"}
        assert client.post("/recommendations", json={}).status_code == 404
        assert client.get("/v1/catalogue/status").status_code == 404
        assert client.post("/advisor/session", json={}).status_code == 404
        assert client.post("/internal/yafa/recommend", json={}).status_code == 404
