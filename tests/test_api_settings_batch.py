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
async def test_set_settings_batch_persists_strategy_values(deps):
    from sentinel.api.routers.settings import set_settings_batch

    payload = {
        "values": {
            "strategy_core_target_pct": 70,
            "strategy_opportunity_target_pct": 30,
            "strategy_min_opp_score": 0.6,
            "strategy_core_floor_pct": 0.1,
        }
    }

    result = await set_settings_batch(payload, deps)
    assert result == {"status": "ok"}

    assert await deps.db.get_setting("strategy_core_target_pct") == 70
    assert await deps.db.get_setting("strategy_opportunity_target_pct") == 30
    assert await deps.db.get_setting("strategy_min_opp_score") == 0.6
    assert await deps.db.get_setting("strategy_core_floor_pct") == 0.1


@pytest.mark.asyncio
async def test_set_settings_batch_rejects_invalid_value_without_partial_write(deps):
    from sentinel.api.routers.settings import set_settings_batch

    original = {
        "strategy_core_target_pct": await deps.db.get_setting("strategy_core_target_pct"),
        "strategy_opportunity_target_pct": await deps.db.get_setting("strategy_opportunity_target_pct"),
        "strategy_min_opp_score": await deps.db.get_setting("strategy_min_opp_score"),
        "strategy_core_floor_pct": await deps.db.get_setting("strategy_core_floor_pct"),
    }
    payload = {
        "values": {
            "strategy_core_target_pct": 70,
            "strategy_opportunity_target_pct": 20,
            "strategy_min_opp_score": -0.1,
            "strategy_core_floor_pct": 0.1,
        }
    }

    with pytest.raises(HTTPException):
        await set_settings_batch(payload, deps)

    for key, value in original.items():
        assert await deps.db.get_setting(key) == value


@pytest.mark.asyncio
async def test_set_settings_batch_rejects_targets_not_summing_to_hundred(deps):
    from sentinel.api.routers.settings import set_settings_batch

    payload = {
        "values": {
            "strategy_core_target_pct": 80,
            "strategy_opportunity_target_pct": 30,
            "strategy_min_opp_score": 0.5,
            "strategy_core_floor_pct": 0.1,
        }
    }

    with pytest.raises(HTTPException):
        await set_settings_batch(payload, deps)
