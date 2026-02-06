from fastapi.testclient import TestClient

from sentinel.app import app


def test_monolith_ml_routes_absent():
    client = TestClient(app)
    for path in ["/api/ml/status", "/api/analytics/regimes", "/api/ml/reset-status"]:
        resp = client.get(path)
        assert resp.status_code in (200, 404)
        if resp.status_code == 200:
            assert resp.headers.get("content-type", "").startswith("text/html")
