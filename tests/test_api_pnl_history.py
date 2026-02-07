"""Tests for /portfolio/pnl-history endpoint with JSON-based snapshots."""

import os
import tempfile
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

from sentinel.database import Database


def _midnight_utc(iso_date: str) -> int:
    return int(datetime.strptime(iso_date, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp())


@pytest_asyncio.fixture
async def temp_db():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    db = Database(db_path)
    await db.connect()
    yield db
    await db.close()
    db.remove_from_cache()
    for ext in ["", "-wal", "-shm"]:
        p = db_path + ext
        if os.path.exists(p):
            os.unlink(p)


class TestPnlHistoryResponseFormat:
    """Verify the response shape matches frontend expectations."""

    @pytest.mark.asyncio
    async def test_empty_db_returns_empty(self, temp_db):
        """No snapshots returns empty response."""
        from sentinel.api.routers.portfolio import get_portfolio_pnl_history

        currency = MagicMock()
        currency.to_eur_for_date = AsyncMock(side_effect=lambda a, c, d: a)

        deps = MagicMock()
        deps.db = temp_db
        deps.currency = currency

        with patch("sentinel.api.routers.portfolio._backfill_portfolio_snapshots", new_callable=AsyncMock):
            result = await get_portfolio_pnl_history(deps)

        assert result == {"snapshots": [], "summary": None}

    @pytest.mark.asyncio
    async def test_response_has_expected_keys(self, temp_db):
        """Verify each snapshot point has the keys the frontend expects."""
        from sentinel.api.routers.portfolio import get_portfolio_pnl_history

        # Insert 2 years of snapshots so the rolling window can produce output
        base_date = datetime.now(tz=timezone.utc).date() - timedelta(days=750)
        for i in range(750):
            d = base_date + timedelta(days=i)
            ts = _midnight_utc(d.isoformat())
            data = {
                "positions": {"TEST.EU": {"quantity": 10, "value_eur": 1000.0 + i}},
                "cash_eur": 500.0,
            }
            await temp_db.upsert_portfolio_snapshot(ts, data)

        # Insert a cash flow for net deposits
        await temp_db.upsert_cash_flow(
            date=(base_date - timedelta(days=1)).isoformat(),
            type_id="card",
            amount=1000.0,
            currency="EUR",
            comment=None,
            raw_data={"test": True},
        )

        currency = MagicMock()
        currency.to_eur_for_date = AsyncMock(side_effect=lambda a, c, d: a)

        deps = MagicMock()
        deps.db = temp_db
        deps.currency = currency

        with patch("sentinel.api.routers.portfolio._backfill_portfolio_snapshots", new_callable=AsyncMock):
            result = await get_portfolio_pnl_history(deps)

        assert "snapshots" in result
        assert "summary" in result
        assert len(result["snapshots"]) > 0

        # Check keys on a non-future snapshot
        snap = result["snapshots"][0]
        expected_keys = {
            "date",
            "total_value_eur",
            "net_deposits_eur",
            "pnl_eur",
            "pnl_pct",
            "actual_ann_return",
        }
        assert expected_keys == set(snap.keys())

        # Summary
        summary = result["summary"]
        assert "start_value" in summary
        assert "end_value" in summary
        assert "pnl_absolute" in summary
        assert "target_ann_return" in summary
        assert summary["target_ann_return"] == 11.0


class TestPnlHistoryComputations:
    """Verify derived values are computed correctly from JSON snapshots."""

    @pytest.mark.asyncio
    async def test_total_value_from_positions_and_cash(self, temp_db):
        """total_value_eur = sum(position values) + cash_eur."""
        from sentinel.api.routers.portfolio import get_portfolio_pnl_history

        # 2 years of data
        base_date = datetime.now(tz=timezone.utc).date() - timedelta(days=750)
        for i in range(750):
            d = base_date + timedelta(days=i)
            ts = _midnight_utc(d.isoformat())
            data = {
                "positions": {
                    "A": {"quantity": 10, "value_eur": 500.0},
                    "B": {"quantity": 5, "value_eur": 300.0},
                },
                "cash_eur": 200.0,
            }
            await temp_db.upsert_portfolio_snapshot(ts, data)

        currency = MagicMock()
        currency.to_eur_for_date = AsyncMock(side_effect=lambda a, c, d: a)

        deps = MagicMock()
        deps.db = temp_db
        deps.currency = currency

        with patch("sentinel.api.routers.portfolio._backfill_portfolio_snapshots", new_callable=AsyncMock):
            result = await get_portfolio_pnl_history(deps)

        # All points should have total_value = 500 + 300 + 200 = 1000
        for snap in result["snapshots"]:
            if snap["total_value_eur"] is not None:
                assert snap["total_value_eur"] == 1000.0

    @pytest.mark.asyncio
    async def test_net_deposits_from_cash_flows(self, temp_db):
        """net_deposits_eur is computed from cash_flows table."""
        from sentinel.api.routers.portfolio import get_portfolio_pnl_history

        base_date = datetime.now(tz=timezone.utc).date() - timedelta(days=750)

        # Insert a deposit
        await temp_db.upsert_cash_flow(
            date=(base_date - timedelta(days=1)).isoformat(),
            type_id="card",
            amount=5000.0,
            currency="EUR",
            comment=None,
            raw_data={"test": True},
        )

        for i in range(750):
            d = base_date + timedelta(days=i)
            ts = _midnight_utc(d.isoformat())
            data = {"positions": {"A": {"quantity": 10, "value_eur": 5500.0}}, "cash_eur": 0.0}
            await temp_db.upsert_portfolio_snapshot(ts, data)

        currency = MagicMock()
        currency.to_eur_for_date = AsyncMock(side_effect=lambda a, c, d: a)

        deps = MagicMock()
        deps.db = temp_db
        deps.currency = currency

        with patch("sentinel.api.routers.portfolio._backfill_portfolio_snapshots", new_callable=AsyncMock):
            result = await get_portfolio_pnl_history(deps)

        # All points should have net_deposits = 5000
        for snap in result["snapshots"]:
            if snap["net_deposits_eur"] is not None:
                assert snap["net_deposits_eur"] == 5000.0

    @pytest.mark.asyncio
    @pytest.mark.asyncio
    async def test_backfill_triggered_when_stale(self, temp_db):
        """Backfill runs when latest snapshot is older than today."""
        from sentinel.api.routers.portfolio import get_portfolio_pnl_history

        # Insert a snapshot from yesterday
        yesterday = datetime.now(tz=timezone.utc).date() - timedelta(days=1)
        ts = _midnight_utc(yesterday.isoformat())
        await temp_db.upsert_portfolio_snapshot(ts, {"positions": {}, "cash_eur": 0.0})

        currency = MagicMock()
        currency.to_eur_for_date = AsyncMock(side_effect=lambda a, c, d: a)

        deps = MagicMock()
        deps.db = temp_db
        deps.currency = currency

        backfill_mock = AsyncMock()
        with patch("sentinel.api.routers.portfolio._backfill_portfolio_snapshots", backfill_mock):
            await get_portfolio_pnl_history(deps)

        # Backfill should have been called since yesterday < today
        backfill_mock.assert_called_once()
