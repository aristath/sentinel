"""Tests for Freedom24 Favorites universe reconciliation."""

import os
import tempfile
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio

from sentinel.database import Database
from sentinel.universe import (
    BROKER_POSITION_UNIVERSE_SOURCE,
    FREEDOM24_UNIVERSE_SOURCE,
    reconcile_universe_from_freedom24_default_list,
)


@pytest_asyncio.fixture
async def temp_db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    db = Database(path)
    await db.connect()

    yield db

    await db.close()
    db.remove_from_cache()
    for ext in ("", "-wal", "-shm"):
        target = path + ext
        if os.path.exists(target):
            os.unlink(target)


def _broker_with_favorites(*symbols: str):
    broker = AsyncMock()
    broker.get_user_stock_lists = AsyncMock(
        return_value={
            "defaultId": 1,
            "selectedId": 1,
            "userStockLists": [{"id": 1, "name": "default", "tickers": list(symbols)}],
        }
    )
    broker.get_security_info = AsyncMock(
        side_effect=lambda symbol: {
            "short_name": f"{symbol} Corp",
            "currency": "EUR",
            "mrkt": {"mkt_id": 123},
            "lot": "1.00000000",
        }
    )
    broker.get_historical_prices_bulk = AsyncMock(
        side_effect=lambda symbols, years=20: {
            symbol: [{"date": "2026-01-01", "close": 100.0}] for symbol in symbols
        }
    )
    return broker


@pytest.mark.asyncio
async def test_reconcile_imports_new_favorite(temp_db):
    broker = _broker_with_favorites("AMD.EU")

    result = await reconcile_universe_from_freedom24_default_list(temp_db, broker)

    row = await temp_db.get_security("AMD.EU")
    assert result.imported == ["AMD.EU"]
    assert row is not None
    assert int(row["active"]) == 1
    assert int(row["allow_buy"]) == 1
    assert int(row["allow_sell"]) == 1
    assert row["universe_source"] == FREEDOM24_UNIVERSE_SOURCE
    assert row["universe_last_seen_at"] is not None
    broker.get_historical_prices_bulk.assert_awaited_once_with(["AMD.EU"], years=20)


@pytest.mark.asyncio
async def test_reconcile_removes_non_held_security_missing_from_favorites(temp_db):
    await temp_db.upsert_security("MOH.GR", name="Motor Oil", active=1, allow_buy=1, allow_sell=1)
    for symbol in ("KEEP1.EU", "KEEP2.EU", "KEEP3.EU"):
        await temp_db.upsert_security(symbol, name=symbol, active=1, allow_buy=1, allow_sell=1)
    broker = _broker_with_favorites("AMD.EU", "KEEP1.EU", "KEEP2.EU", "KEEP3.EU")

    result = await reconcile_universe_from_freedom24_default_list(temp_db, broker)

    row = await temp_db.get_security("MOH.GR")
    imported = await temp_db.get_security("AMD.EU")
    assert result.removed == ["MOH.GR"]
    assert row is not None
    assert int(row["active"]) == 0
    assert int(row["allow_buy"]) == 0
    assert int(row["allow_sell"]) == 0
    assert imported is not None


@pytest.mark.asyncio
async def test_reconcile_disables_buys_for_held_security_missing_from_favorites(temp_db):
    await temp_db.upsert_security("ASML.EU", name="ASML", active=1, allow_buy=1, allow_sell=1)
    await temp_db.upsert_position("ASML.EU", quantity=4, current_price=700, currency="EUR")
    for symbol in ("KEEP1.EU", "KEEP2.EU", "KEEP3.EU"):
        await temp_db.upsert_security(symbol, name=symbol, active=1, allow_buy=1, allow_sell=1)
    broker = _broker_with_favorites("AMD.EU", "KEEP1.EU", "KEEP2.EU", "KEEP3.EU")

    result = await reconcile_universe_from_freedom24_default_list(temp_db, broker)

    row = await temp_db.get_security("ASML.EU")
    assert result.buy_disabled == ["ASML.EU"]
    assert row is not None
    assert int(row["active"]) == 1
    assert int(row["allow_buy"]) == 0
    assert int(row["allow_sell"]) == 1
    assert row["universe_source"] == BROKER_POSITION_UNIVERSE_SOURCE


@pytest.mark.asyncio
async def test_reconcile_skips_when_more_than_half_the_universe_would_change(temp_db):
    for symbol in ("KEEP.EU", "OLD1.EU", "OLD2.EU", "OLD3.EU"):
        await temp_db.upsert_security(symbol, name=symbol, active=1, allow_buy=1, allow_sell=1)
    broker = _broker_with_favorites("KEEP.EU")

    result = await reconcile_universe_from_freedom24_default_list(temp_db, broker)

    assert result.changed is False
    assert result.skipped == ["change_ratio_guard"]
    for symbol in ("OLD1.EU", "OLD2.EU", "OLD3.EU"):
        row = await temp_db.get_security(symbol)
        assert row is not None
        assert int(row["active"]) == 1
        assert int(row["allow_buy"]) == 1
        assert int(row["allow_sell"]) == 1


@pytest.mark.asyncio
async def test_reconcile_skips_when_more_than_half_the_universe_would_be_imported(temp_db):
    for symbol in ("KEEP1.EU", "KEEP2.EU", "KEEP3.EU", "KEEP4.EU"):
        await temp_db.upsert_security(symbol, name=symbol, active=1, allow_buy=1, allow_sell=1)
    broker = _broker_with_favorites("KEEP1.EU", "KEEP2.EU", "KEEP3.EU", "KEEP4.EU", "NEW1.EU", "NEW2.EU", "NEW3.EU")

    result = await reconcile_universe_from_freedom24_default_list(temp_db, broker)

    assert result.changed is False
    assert result.skipped == ["change_ratio_guard"]
    assert await temp_db.get_security("NEW1.EU") is None
    assert await temp_db.get_security("NEW2.EU") is None
    assert await temp_db.get_security("NEW3.EU") is None


@pytest.mark.asyncio
async def test_reconcile_reenables_buys_when_broker_position_returns_to_favorites(temp_db):
    await temp_db.upsert_security(
        "ASML.EU",
        name="ASML",
        active=1,
        allow_buy=0,
        allow_sell=1,
        universe_source=BROKER_POSITION_UNIVERSE_SOURCE,
    )
    await temp_db.upsert_position("ASML.EU", quantity=4, current_price=700, currency="EUR")
    broker = _broker_with_favorites("ASML.EU")

    result = await reconcile_universe_from_freedom24_default_list(temp_db, broker)

    row = await temp_db.get_security("ASML.EU")
    assert result.buy_reenabled == ["ASML.EU"]
    assert row is not None
    assert int(row["active"]) == 1
    assert int(row["allow_buy"]) == 1
    assert int(row["allow_sell"]) == 1
    assert row["universe_source"] == FREEDOM24_UNIVERSE_SOURCE


@pytest.mark.asyncio
async def test_reconcile_does_not_change_local_state_when_default_list_unavailable(temp_db):
    await temp_db.upsert_security("ASML.EU", name="ASML", active=1, allow_buy=1, allow_sell=1)
    broker = AsyncMock()
    broker.get_user_stock_lists = AsyncMock(return_value=None)

    result = await reconcile_universe_from_freedom24_default_list(temp_db, broker)

    row = await temp_db.get_security("ASML.EU")
    assert result.changed is False
    assert result.skipped == ["default_list"]
    assert row is not None
    assert int(row["active"]) == 1
    assert int(row["allow_buy"]) == 1
    assert int(row["allow_sell"]) == 1


@pytest.mark.asyncio
async def test_reconcile_does_not_change_local_state_when_default_list_empty(temp_db):
    await temp_db.upsert_security("ASML.EU", name="ASML", active=1, allow_buy=1, allow_sell=1)
    broker = _broker_with_favorites()

    result = await reconcile_universe_from_freedom24_default_list(temp_db, broker)

    row = await temp_db.get_security("ASML.EU")
    assert result.changed is False
    assert result.skipped == ["empty_default_list"]
    assert row is not None
    assert int(row["active"]) == 1
    assert int(row["allow_buy"]) == 1
    assert int(row["allow_sell"]) == 1
