"""Tests for atomic settings batch updates."""

import os
import tempfile
from unittest.mock import MagicMock

import pytest
import pytest_asyncio
from fastapi import HTTPException

from sentinel.database import Database
from sentinel.settings import Settings


def strategy_values(**overrides):
    values = {
        "strategy_core_target_pct": 70,
        "strategy_opportunity_target_pct": 30,
        "strategy_min_opp_score": 0.6,
        "strategy_core_floor_pct": 0.1,
        "strategy_entry_t1_dd": -0.10,
        "strategy_entry_t2_dd": -0.16,
        "strategy_entry_t3_dd": -0.22,
        "strategy_entry_memory_days": 45,
        "strategy_memory_max_boost": 0.12,
        "strategy_opportunity_addon_threshold": 0.75,
        "strategy_max_opportunity_buys_per_cycle": 1,
        "strategy_max_new_opportunity_buys_per_cycle": 1,
    }
    values.update(overrides)
    return values


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
async def test_set_setting_rejects_removed_strategy_knobs(deps):
    from sentinel.api.routers.settings import set_setting

    with pytest.raises(HTTPException) as exc:
        await set_setting("strategy_opportunity_target_max_pct", {"value": 30}, deps)

    assert exc.value.status_code == 400
    assert await deps.db.get_setting("strategy_opportunity_target_max_pct") is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("transaction_fee_fixed", 3.0),
        ("transaction_fee_percent", 0.35),
        ("strategy_core_new_min_score", 0.4),
        ("strategy_core_new_min_dip_score", 0.25),
        ("strategy_max_funding_sells_per_cycle", 3),
        ("strategy_max_funding_turnover_pct", 0.18),
        ("strategy_funding_conviction_bias", 1.2),
        ("user_multiplier_blend_pct", 75.0),
        ("user_multiplier_decay_factor", 0.85),
    ],
)
async def test_set_setting_invalidates_planner_cache_for_recommendation_settings(deps, key, value):
    from sentinel.api.routers.settings import set_setting

    await deps.db.cache_set("planner:recommendations:100.00", "[]", ttl_seconds=600)
    assert await deps.db.cache_get("planner:recommendations:100.00") == "[]"

    result = await set_setting(key, {"value": value}, deps)

    assert result == {"status": "ok"}
    assert await deps.db.cache_get("planner:recommendations:100.00") is None


@pytest.mark.asyncio
async def test_set_settings_batch_persists_strategy_values(deps):
    from sentinel.api.routers.settings import set_settings_batch

    payload = {"values": strategy_values()}

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
    payload = {"values": strategy_values(strategy_opportunity_target_pct=20, strategy_min_opp_score=-0.1)}

    with pytest.raises(HTTPException):
        await set_settings_batch(payload, deps)

    for key, value in original.items():
        assert await deps.db.get_setting(key) == value


@pytest.mark.asyncio
async def test_set_settings_batch_rejects_targets_not_summing_to_hundred(deps):
    from sentinel.api.routers.settings import set_settings_batch

    payload = {"values": strategy_values(strategy_core_target_pct=80, strategy_opportunity_target_pct=30)}

    with pytest.raises(HTTPException):
        await set_settings_batch(payload, deps)
