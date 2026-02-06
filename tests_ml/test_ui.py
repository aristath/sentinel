from fastapi.testclient import TestClient

from sentinel_ml.app import app

client = TestClient(app)


def test_ml_ui_index_served():
    resp = client.get("/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers.get("content-type", "")
    assert "Sentinel ML Console" in resp.text


def test_ml_ui_config_endpoint():
    resp = client.get("/ui/config")
    assert resp.status_code == 200
    payload = resp.json()
    assert "monolith_base_url" in payload
    assert payload["monolith_base_url"].startswith("http")


def test_ml_ui_config_update_validation():
    resp = client.put("/ui/config", json={"monolith_base_url": "not-a-url"})
    assert resp.status_code == 400
