"""Tests for atomic settings batch updates."""

import os
import tempfile
from unittest.mock import MagicMock

import pytest
import pytest_asyncio
from fastapi import HTTPException

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

    deps = MagicMock()
    deps.db = db
    deps.settings = settings

    yield deps

    await db.close()
    db.remove_from_cache()
    for ext in ["", "-wal", "-shm"]:
        p = path + ext
        if os.path.exists(p):
            os.unlink(p)


@pytest.mark.asyncio
async def test_set_settings_batch_persists_all_weights(deps):
    from sentinel.api.routers.settings import set_settings_batch

    payload = {
        "values": {
            "ml_weight_wavelet": 0.1,
            "ml_weight_xgboost": 0.8,
            "ml_weight_ridge": 0.3,
            "ml_weight_rf": 0.4,
            "ml_weight_svr": 0.5,
        }
    }

    result = await set_settings_batch(payload, deps)
    assert result == {"status": "ok"}

    assert await deps.db.get_setting("ml_weight_wavelet") == 0.1
    assert await deps.db.get_setting("ml_weight_xgboost") == 0.8
    assert await deps.db.get_setting("ml_weight_ridge") == 0.3
    assert await deps.db.get_setting("ml_weight_rf") == 0.4
    assert await deps.db.get_setting("ml_weight_svr") == 0.5


@pytest.mark.asyncio
async def test_set_settings_batch_rejects_out_of_range_without_partial_write(deps):
    from sentinel.api.routers.settings import set_settings_batch

    original = {
        "ml_weight_wavelet": await deps.db.get_setting("ml_weight_wavelet"),
        "ml_weight_xgboost": await deps.db.get_setting("ml_weight_xgboost"),
        "ml_weight_ridge": await deps.db.get_setting("ml_weight_ridge"),
        "ml_weight_rf": await deps.db.get_setting("ml_weight_rf"),
        "ml_weight_svr": await deps.db.get_setting("ml_weight_svr"),
    }
    payload = {
        "values": {
            "ml_weight_wavelet": 0.2,
            "ml_weight_xgboost": 0.2,
            "ml_weight_ridge": -0.1,
            "ml_weight_rf": 0.2,
            "ml_weight_svr": 0.2,
        }
    }

    with pytest.raises(HTTPException):
        await set_settings_batch(payload, deps)

    for key, value in original.items():
        assert await deps.db.get_setting(key) == value


@pytest.mark.asyncio
async def test_set_settings_batch_rejects_zero_sum(deps):
    from sentinel.api.routers.settings import set_settings_batch

    payload = {
        "values": {
            "ml_weight_wavelet": 0.0,
            "ml_weight_xgboost": 0.0,
            "ml_weight_ridge": 0.0,
            "ml_weight_rf": 0.0,
            "ml_weight_svr": 0.0,
        }
    }

    with pytest.raises(HTTPException):
        await set_settings_batch(payload, deps)
