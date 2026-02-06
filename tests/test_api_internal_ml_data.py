from fastapi.testclient import TestClient

from sentinel.app import app


def test_internal_ml_router_exists():
    client = TestClient(app)
    resp = client.get("/api/internal/ml/as-of-end-ts", params={"date": "2025-01-01"})
    assert resp.status_code == 200
    payload = resp.json()
    assert "timestamp" in payload
