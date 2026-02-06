from fastapi.testclient import TestClient

from sentinel_ml.app import app


def test_health_endpoint():
    client = TestClient(app)
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "healthy"


def test_version_endpoint():
    client = TestClient(app)
    resp = client.get("/version")
    assert resp.status_code == 200
    assert "version" in resp.json()
