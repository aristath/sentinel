"""HTTP-level tests for LED bridge health telemetry endpoints."""

import os
import tempfile
import time

import pytest
import pytest_asyncio
from fastapi import FastAPI
from fastapi.testclient import TestClient

from sentinel.api.routers.settings import led_router
from sentinel.database import Database
from sentinel.settings import Settings


@pytest_asyncio.fixture
async def temp_db_path():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    db = Database(path)
    await db.connect()
    settings = Settings()
    settings._db = db
    await settings.init_defaults()

    yield path

    await db.close()
    db.remove_from_cache()
    for ext in ["", "-wal", "-shm"]:
        p = path + ext
        if os.path.exists(p):
            os.unlink(p)


def _build_client() -> TestClient:
    app = FastAPI()
    app.include_router(led_router, prefix="/api")
    return TestClient(app)


@pytest.mark.asyncio
async def test_led_bridge_health_defaults(temp_db_path):
    client = _build_client()
    resp = client.get("/api/led/bridge/health")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["bridge_ok"] is False
    assert payload["consecutive_failures"] == 0
    assert payload["last_success_at"] is None
    assert payload["is_stale"] is True
    assert payload["stale_threshold_seconds"] == 600


@pytest.mark.asyncio
async def test_led_bridge_health_store_and_read(temp_db_path):
    client = _build_client()
    now = int(time.time())
    body = {
        "bridge_ok": True,
        "last_attempt_ts": now,
        "last_success_ts": now - 12,
        "consecutive_failures": 0,
        "last_error": None,
        "watchdog_action": "watchdog_recovered",
        "app_instance": "arduino-app/sentinel",
    }
    write_resp = client.post("/api/led/bridge/health", json=body)
    assert write_resp.status_code == 200
    write_payload = write_resp.json()
    assert write_payload["bridge_ok"] is True
    assert write_payload["consecutive_failures"] == 0
    assert write_payload["is_stale"] is False
    assert write_payload["last_success_at"] is not None

    read_resp = client.get("/api/led/bridge/health")
    assert read_resp.status_code == 200
    read_payload = read_resp.json()
    assert read_payload["bridge_ok"] is True
    assert read_payload["watchdog_action"] == "watchdog_recovered"
    assert read_payload["app_instance"] == "arduino-app/sentinel"
    assert read_payload["is_stale"] is False


@pytest.mark.asyncio
async def test_led_status_includes_bridge_health(temp_db_path):
    client = _build_client()
    now = int(time.time())
    body = {
        "bridge_ok": False,
        "last_attempt_ts": now,
        "last_success_ts": now - 900,
        "last_error_ts": now,
        "last_error": "Request 'hm.u' timed out after 10s",
        "consecutive_failures": 6,
        "watchdog_action": "process_exit_watchdog_ping_failed",
        "app_instance": "arduino-app/sentinel",
    }
    resp = client.post("/api/led/bridge/health", json=body)
    assert resp.status_code == 200

    status_resp = client.get("/api/led/status")
    assert status_resp.status_code == 200
    status_payload = status_resp.json()

    assert "bridge" in status_payload
    bridge = status_payload["bridge"]
    assert bridge["bridge_ok"] is False
    assert bridge["consecutive_failures"] == 6
    assert bridge["is_stale"] is True
    assert bridge["last_error"] == "Request 'hm.u' timed out after 10s"
    assert isinstance(status_payload["broker_connected"], bool)
