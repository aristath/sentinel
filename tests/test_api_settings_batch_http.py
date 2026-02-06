"""HTTP-level tests for /api/settings batch updates."""

import os
import tempfile

import pytest
import pytest_asyncio
from fastapi import FastAPI
from fastapi.testclient import TestClient

from sentinel.api.dependencies import CommonDependencies
from sentinel.api.routers.settings import get_common_deps
from sentinel.api.routers.settings import router as settings_router
from sentinel.broker import Broker
from sentinel.currency import Currency
from sentinel.database import Database
from sentinel.settings import Settings


@pytest_asyncio.fixture
async def deps():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    db = Database(path)
    await db.connect()

    settings = Settings()
    settings._db = db
    await settings.init_defaults()

    yield CommonDependencies(
        db=db,
        settings=settings,
        broker=Broker(),
        currency=Currency(),
    )

    await db.close()
    db.remove_from_cache()
    for ext in ["", "-wal", "-shm"]:
        p = path + ext
        if os.path.exists(p):
            os.unlink(p)


def _build_client(deps: CommonDependencies) -> TestClient:
    app = FastAPI()
    app.include_router(settings_router, prefix="/api")

    async def override_deps():
        return deps

    app.dependency_overrides[get_common_deps] = override_deps
    return TestClient(app)


@pytest.mark.asyncio
async def test_settings_batch_http_success(deps):
    client = _build_client(deps)
    resp = client.put(
        "/api/settings",
        json={
            "values": {
                "ml_weight_wavelet": 0.1,
                "ml_weight_xgboost": 0.8,
                "ml_weight_ridge": 0.3,
                "ml_weight_rf": 0.4,
                "ml_weight_svr": 0.5,
            }
        },
    )
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_settings_batch_http_rejects_boolean(deps):
    client = _build_client(deps)
    resp = client.put(
        "/api/settings",
        json={
            "values": {
                "ml_weight_wavelet": True,
                "ml_weight_xgboost": 0.8,
                "ml_weight_ridge": 0.3,
                "ml_weight_rf": 0.4,
                "ml_weight_svr": 0.5,
            }
        },
    )
    assert resp.status_code == 400
    assert "must be a number" in resp.json().get("detail", "")
