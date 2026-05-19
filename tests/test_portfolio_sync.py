"""Tests for portfolio synchronization side effects."""

import os
import tempfile
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio

from sentinel.database import Database
from sentinel.portfolio import Portfolio
from sentinel.universe import BROKER_POSITION_UNIVERSE_SOURCE


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


def _broker_with_position(symbol: str):
    broker = AsyncMock()
    broker.get_portfolio = AsyncMock(
        return_value={
            "positions": [
                {
                    "symbol": symbol,
                    "name": f"{symbol} Holding",
                    "quantity": 2,
                    "current_price": 100.0,
                    "currency": "EUR",
                }
            ],
            "cash": {},
        }
    )
    broker.get_security_info = AsyncMock(
        return_value={
            "short_name": f"{symbol} Corp",
            "currency": "EUR",
            "mrkt": {"mkt_id": 123},
            "lot": "1.00000000",
        }
    )
    broker.get_historical_prices_bulk = AsyncMock(
        return_value={symbol: [{"date": "2026-01-01", "close": 100.0}]}
    )
    return broker


@pytest.mark.asyncio
async def test_sync_fully_imports_new_held_security(temp_db):
    broker = _broker_with_position("NEW.EU")
    portfolio = Portfolio(db=temp_db, broker=broker)

    await portfolio.sync()

    row = await temp_db.get_security("NEW.EU")
    prices = await temp_db.get_prices("NEW.EU", days=10)
    position = await temp_db.get_position("NEW.EU")
    assert row is not None
    assert int(row["active"]) == 1
    assert int(row["allow_buy"]) == 1
    assert int(row["allow_sell"]) == 1
    assert row["universe_source"] == BROKER_POSITION_UNIVERSE_SOURCE
    assert row["market_id"] == "123"
    assert row["data"] is not None
    assert len(prices) == 1
    assert position is not None
    assert position["quantity"] == 2
    broker.get_security_info.assert_awaited_once_with("NEW.EU")
    broker.get_historical_prices_bulk.assert_awaited_once_with(["NEW.EU"], years=20)


@pytest.mark.asyncio
async def test_sync_self_heals_when_metadata_is_temporarily_unavailable(temp_db):
    broker = _broker_with_position("BROKEN.EU")
    broker.get_security_info = AsyncMock(return_value=None)
    broker.get_historical_prices_bulk = AsyncMock(return_value={})
    portfolio = Portfolio(db=temp_db, broker=broker)

    await portfolio.sync()

    row = await temp_db.get_security("BROKEN.EU")
    prices = await temp_db.get_prices("BROKEN.EU", days=10)
    position = await temp_db.get_position("BROKEN.EU")
    assert row is not None
    assert int(row["active"]) == 1
    assert int(row["allow_buy"]) == 1
    assert int(row["allow_sell"]) == 1
    assert row["name"] == "BROKEN.EU Holding"
    assert row["currency"] == "EUR"
    assert row["universe_source"] == BROKER_POSITION_UNIVERSE_SOURCE
    assert row["data"] is None
    assert prices == []
    assert position is not None
    assert position["quantity"] == 2
