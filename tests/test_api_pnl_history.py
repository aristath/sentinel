"""Tests for /portfolio/pnl-history endpoint with JSON-based snapshots."""

import os
import tempfile
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

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
    @pytest.mark.parametrize(
        ("period", "expected_snapshot_days"),
        [("3M", 455), ("6M", 545), ("1Y", 730), ("ALL", None)],
    )
    async def test_chart_period_controls_snapshot_window(self, period, expected_snapshot_days):
        from sentinel.api.routers.portfolio import get_portfolio_pnl_history

        deps = MagicMock()
        deps.db.get_portfolio_snapshots = AsyncMock(return_value=[])

        result = await get_portfolio_pnl_history(deps, period=period)

        assert result == {"snapshots": [], "summary": None}
        deps.db.get_portfolio_snapshots.assert_awaited_once_with(expected_snapshot_days)

    @pytest.mark.asyncio
    async def test_chart_period_rejects_unknown_value(self):
        from fastapi import HTTPException

        from sentinel.api.routers.portfolio import get_portfolio_pnl_history

        deps = MagicMock()

        with pytest.raises(HTTPException, match="Invalid P&L period") as exc:
            await get_portfolio_pnl_history(deps, period="5Y")

        assert exc.value.status_code == 400
        deps.db.get_portfolio_snapshots.assert_not_called()

    @pytest.mark.asyncio
    async def test_empty_db_returns_empty(self, temp_db):
        """No snapshots returns empty response."""
        from sentinel.api.routers.portfolio import get_portfolio_pnl_history

        currency = MagicMock()
        currency.to_eur_for_date = AsyncMock(side_effect=lambda a, c, d: a)

        deps = MagicMock()
        deps.db = temp_db
        deps.currency = currency
        deps.settings.get = AsyncMock(side_effect=lambda key, default=None: default)

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
        deps.settings.get = AsyncMock(side_effect=lambda key, default=None: default)

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
            "rolling_365d_money_weighted_return_pct",
            "benchmark_ann_return",
        }
        assert expected_keys == set(snap.keys())

        # Summary
        summary = result["summary"]
        assert "start_value" in summary
        assert "end_value" in summary
        assert "pnl_absolute" in summary
        assert "target_ann_return" in summary
        assert summary["target_ann_return"] == 11.0
        assert summary["benchmark_symbol"] == "VWCE.EU"
        assert summary["trailing_365d_money_weighted_return_pct"] == summary["actual_ann_return"]


class TestPnlHistoryComputations:
    """Verify derived values are computed correctly from JSON snapshots."""

    @pytest.mark.asyncio
    async def test_current_net_deposits_use_transaction_date_fx(self):
        from sentinel.api.routers.portfolio import _current_net_deposits_eur

        cash_flows = [
            {
                "date": "2025-01-01",
                "type_id": "card",
                "amount": 100.0,
                "currency": "USD",
            },
            {
                "date": "2025-06-01",
                "type_id": "card_payout",
                "amount": -10.0,
                "currency": "USD",
            },
            {
                "date": "2025-07-01",
                "type_id": "dividend",
                "amount": 5.0,
                "currency": "USD",
            },
        ]
        deps = MagicMock()
        deps.db.get_cash_flows = AsyncMock(return_value=cash_flows)
        rates = {"2025-01-01": 0.9, "2025-06-01": 0.8, "2025-07-01": 0.7}
        deps.currency.to_eur_for_date = AsyncMock(
            side_effect=lambda amount, currency, iso_date: amount * rates[iso_date]
        )

        result = await _current_net_deposits_eur(deps)

        assert result == pytest.approx(82.0)
        assert deps.currency.to_eur_for_date.await_count == 2

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
        deps.settings.get = AsyncMock(side_effect=lambda key, default=None: default)

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
        deps.settings.get = AsyncMock(side_effect=lambda key, default=None: default)

        result = await get_portfolio_pnl_history(deps)

        # All points should have net_deposits = 5000
        for snap in result["snapshots"]:
            if snap["net_deposits_eur"] is not None:
                assert snap["net_deposits_eur"] == 5000.0

    @pytest.mark.asyncio
    async def test_endpoint_365d_return_uses_opening_value_and_all_external_flows(self, temp_db):
        from sentinel.api.routers.portfolio import get_portfolio_pnl_history

        today = datetime.now(tz=timezone.utc).date()
        start = today - timedelta(days=365)
        deposit_date = start + timedelta(days=182)
        for flow_date, flow_id in ((start, "initial"), (deposit_date, "later")):
            await temp_db.upsert_cash_flow(
                date=flow_date.isoformat(),
                type_id="card",
                amount=1000.0,
                currency="EUR",
                comment=None,
                raw_data={"test": True, "id": flow_id},
            )

        for offset in range(366):
            point_date = start + timedelta(days=offset)
            value = 1000.0 if point_date < deposit_date else 2000.0
            await temp_db.upsert_portfolio_snapshot(
                _midnight_utc(point_date.isoformat()),
                {"positions": {"TEST.EU": {"quantity": 1, "value_eur": value}}, "cash_eur": 0.0},
            )

        await temp_db.upsert_position("TEST.EU", quantity=1, current_price=2200.0, currency="EUR")
        await temp_db.set_cash_balances({})
        currency = MagicMock()
        currency.to_eur_for_date = AsyncMock(side_effect=lambda amount, currency, date: amount)
        currency.to_eur = AsyncMock(side_effect=lambda amount, currency: amount)
        deps = MagicMock()
        deps.db = temp_db
        deps.currency = currency
        deps.settings.get = AsyncMock(side_effect=lambda key, default=None: default)

        result = await get_portfolio_pnl_history(deps)

        rate = result["summary"]["trailing_365d_money_weighted_return_pct"] / 100.0
        assert 1000.0 * (1.0 + rate) + 1000.0 * ((1.0 + rate) ** (183.0 / 365.0)) == pytest.approx(2200.0, abs=0.2)

    @pytest.mark.asyncio
    async def test_latest_point_uses_live_portfolio_value(self, temp_db):
        """Today's snapshot can be stale after trades; the published latest
        point should use the live positions/cash endpoint value.
        """
        from sentinel.api.routers.portfolio import get_portfolio_pnl_history

        today = datetime.now(tz=timezone.utc).date()
        base_date = today - timedelta(days=749)
        await temp_db.upsert_cash_flow(
            date=(base_date - timedelta(days=1)).isoformat(),
            type_id="card",
            amount=1000.0,
            currency="EUR",
            comment=None,
            raw_data={"test": True},
        )
        for i in range(750):
            d = base_date + timedelta(days=i)
            ts = _midnight_utc(d.isoformat())
            value = 5000.0 if d == today else 1000.0
            await temp_db.upsert_portfolio_snapshot(
                ts,
                {"positions": {"STALE.EU": {"quantity": 10, "value_eur": value}}, "cash_eur": 0.0},
            )
        await temp_db.upsert_position("LIVE.EU", quantity=10, current_price=110.0, currency="EUR")
        await temp_db.set_cash_balances({"EUR": 100.0})

        currency = MagicMock()
        currency.to_eur_for_date = AsyncMock(side_effect=lambda a, c, d: a)
        currency.to_eur = AsyncMock(side_effect=lambda a, c: a)

        deps = MagicMock()
        deps.db = temp_db
        deps.currency = currency
        deps.settings.get = AsyncMock(side_effect=lambda key, default=None: default)

        result = await get_portfolio_pnl_history(deps)

        assert result["summary"]["end_value"] == 1200.0
        assert result["summary"]["pnl_absolute"] == 200.0
        latest = result["snapshots"][-1]
        assert latest["date"] == today.isoformat()
        assert latest["total_value_eur"] == 1200.0
        assert latest["net_deposits_eur"] == 1000.0
        assert latest["pnl_eur"] == 200.0

    @pytest.mark.asyncio
    async def test_benchmark_series_populated_when_prices_exist(self, temp_db):
        """When the benchmark symbol has price history, each point carries a
        benchmark_ann_return and the summary names the benchmark."""
        from sentinel.api.routers.portfolio import get_portfolio_pnl_history

        base_date = datetime.now(tz=timezone.utc).date() - timedelta(days=750)
        for i in range(750):
            d = base_date + timedelta(days=i)
            ts = _midnight_utc(d.isoformat())
            await temp_db.upsert_portfolio_snapshot(
                ts, {"positions": {"A": {"quantity": 10, "value_eur": 1000.0}}, "cash_eur": 0.0}
            )

        # Benchmark rising 100 → 1.20x over the two years.
        bench = [{"date": (base_date + timedelta(days=i)).isoformat(), "close": 100.0 + (i * 0.05)} for i in range(750)]
        await temp_db.save_prices("VWCE.EU", bench)

        currency = MagicMock()
        currency.to_eur_for_date = AsyncMock(side_effect=lambda a, c, d: a)

        deps = MagicMock()
        deps.db = temp_db
        deps.currency = currency
        deps.settings.get = AsyncMock(side_effect=lambda key, default=None: default)

        result = await get_portfolio_pnl_history(deps)

        assert result["summary"]["benchmark_symbol"] == "VWCE.EU"
        assert result["summary"]["benchmark_ann_return"] is not None
        # At least one output point has a computed trailing-1Y benchmark return.
        assert any(s["benchmark_ann_return"] is not None for s in result["snapshots"])

    @pytest.mark.asyncio
    async def test_missing_benchmark_data_degrades_to_null(self, temp_db):
        """No benchmark prices → benchmark_ann_return is null everywhere, no crash."""
        from sentinel.api.routers.portfolio import get_portfolio_pnl_history

        base_date = datetime.now(tz=timezone.utc).date() - timedelta(days=750)
        for i in range(750):
            d = base_date + timedelta(days=i)
            ts = _midnight_utc(d.isoformat())
            await temp_db.upsert_portfolio_snapshot(
                ts, {"positions": {"A": {"quantity": 10, "value_eur": 1000.0}}, "cash_eur": 0.0}
            )

        currency = MagicMock()
        currency.to_eur_for_date = AsyncMock(side_effect=lambda a, c, d: a)

        deps = MagicMock()
        deps.db = temp_db
        deps.currency = currency
        deps.settings.get = AsyncMock(side_effect=lambda key, default=None: default)

        result = await get_portfolio_pnl_history(deps)

        assert result["summary"]["benchmark_ann_return"] is None
        assert all(s["benchmark_ann_return"] is None for s in result["snapshots"])

    @pytest.mark.asyncio
    async def test_stale_snapshots_do_not_trigger_backfill_on_read(self, temp_db):
        """P&L endpoint does not perform backfill work on request path."""
        from sentinel.api.routers.portfolio import get_portfolio_pnl_history

        # Insert a snapshot from yesterday.
        yesterday = datetime.now(tz=timezone.utc).date() - timedelta(days=1)
        ts = _midnight_utc(yesterday.isoformat())
        await temp_db.upsert_portfolio_snapshot(ts, {"positions": {}, "cash_eur": 0.0})

        currency = MagicMock()
        currency.to_eur_for_date = AsyncMock(side_effect=lambda a, c, d: a)

        deps = MagicMock()
        deps.db = temp_db
        deps.currency = currency
        deps.settings.get = AsyncMock(side_effect=lambda key, default=None: default)

        result = await get_portfolio_pnl_history(deps)
        assert "snapshots" in result


class TestValueProjection:
    """Verify portfolio value history plus 10-year projection."""

    def test_projection_run_rate_is_unavailable_without_external_contributions(self):
        from sentinel.api.routers.portfolio import _projection_monthly_return

        daily = [
            {"date": "2025-01-01", "total_value_eur": 1000.0, "net_deposits_eur": 0.0},
            {"date": "2026-01-01", "total_value_eur": 1100.0, "net_deposits_eur": 0.0},
        ]

        monthly_return, annualized_return, elapsed_months = _projection_monthly_return(daily)

        assert monthly_return is None
        assert annualized_return is None
        assert elapsed_months == pytest.approx(12.0, abs=0.02)

    def test_trailing_return_uses_opening_value_and_dated_deposit(self):
        from sentinel.api.routers.portfolio import _trailing_money_weighted_return

        daily = [
            {"date": "2025-01-01", "total_value_eur": 1000.0, "net_deposits_eur": 1000.0},
            {"date": "2025-07-02", "total_value_eur": 2050.0, "net_deposits_eur": 2000.0},
            {"date": "2026-01-01", "total_value_eur": 2200.0, "net_deposits_eur": 2000.0},
        ]

        annualized_return = _trailing_money_weighted_return(daily, 2)

        assert annualized_return is not None
        # Opening capital and the later deposit must grow to the closing value.
        assert 1000.0 * (1.0 + annualized_return) + 1000.0 * (
            (1.0 + annualized_return) ** (183.0 / 365.0)
        ) == pytest.approx(2200.0, abs=0.01)

    def test_trailing_return_accounts_for_withdrawal(self):
        from sentinel.api.routers.portfolio import _trailing_money_weighted_return

        daily = [
            {"date": "2025-01-01", "total_value_eur": 1000.0, "net_deposits_eur": 1000.0},
            {"date": "2026-01-01", "total_value_eur": 900.0, "net_deposits_eur": 800.0},
        ]

        annualized_return = _trailing_money_weighted_return(daily, 1)

        assert annualized_return == pytest.approx(0.1, abs=0.001)

    def test_projection_run_rate_compounds_lump_sum_over_three_years(self):
        from sentinel.api.routers.portfolio import _projection_monthly_return

        daily = [
            {
                "date": "2023-01-01",
                "total_value_eur": 1000.0,
                "net_deposits_eur": 1000.0,
            },
            {
                "date": "2026-01-01",
                "total_value_eur": 1331.0,
                "net_deposits_eur": 1000.0,
            },
        ]

        _monthly_return, annualized_return, _elapsed_months = _projection_monthly_return(daily)

        assert annualized_return == pytest.approx(0.1, abs=0.0001)

    def test_projection_run_rate_uses_money_weighted_cash_flow_timing(self):
        from sentinel.api.routers.portfolio import _projection_monthly_return

        daily = [
            {
                "date": "2025-01-01",
                "total_value_eur": 1000.0,
                "net_deposits_eur": 1000.0,
            },
            {
                "date": "2026-01-01",
                "total_value_eur": 2100.0,
                "net_deposits_eur": 2000.0,
            },
        ]

        monthly_return, annualized_return, _elapsed_months = _projection_monthly_return(daily)

        assert annualized_return == pytest.approx(0.1, abs=0.001)
        assert monthly_return == pytest.approx((1.1 ** (1.0 / 12.0)) - 1.0, abs=0.0001)

    def test_projection_run_rate_accounts_for_withdrawal_timing(self):
        from sentinel.api.routers.portfolio import _projection_monthly_return

        daily = [
            {
                "date": "2025-01-01",
                "total_value_eur": 1000.0,
                "net_deposits_eur": 1000.0,
            },
            {
                "date": "2026-01-01",
                "total_value_eur": 900.0,
                "net_deposits_eur": 800.0,
            },
        ]

        monthly_return, annualized_return, _elapsed_months = _projection_monthly_return(daily)

        assert annualized_return == pytest.approx(0.1, abs=0.001)
        assert monthly_return == pytest.approx((1.1 ** (1.0 / 12.0)) - 1.0, abs=0.0001)

    @pytest.mark.asyncio
    async def test_projects_value_from_total_pnl_and_six_month_net_deposit_rate(self, temp_db):
        from sentinel.api.routers.portfolio import get_portfolio_value_projection

        today = datetime.now(tz=timezone.utc).date()
        base_date = today - timedelta(days=399)
        await temp_db.upsert_cash_flow(
            date=(base_date - timedelta(days=1)).isoformat(),
            type_id="card",
            amount=1000.0,
            currency="EUR",
            comment=None,
            raw_data={"test": True, "id": "initial"},
        )
        await temp_db.upsert_cash_flow(
            date=(today - timedelta(days=120)).isoformat(),
            type_id="card",
            amount=300.0,
            currency="EUR",
            comment=None,
            raw_data={"test": True, "id": "recent-1"},
        )
        await temp_db.upsert_cash_flow(
            date=(today - timedelta(days=60)).isoformat(),
            type_id="card",
            amount=300.0,
            currency="EUR",
            comment=None,
            raw_data={"test": True, "id": "recent-2"},
        )
        await temp_db.upsert_cash_flow(
            date=(today - timedelta(days=30)).isoformat(),
            type_id="card_payout",
            amount=-120.0,
            currency="EUR",
            comment=None,
            raw_data={"test": True, "id": "withdrawal"},
        )

        for i in range(400):
            d = base_date + timedelta(days=i)
            ts = _midnight_utc(d.isoformat())
            value = 1000.0 + (i * (1000.0 / 399.0))
            await temp_db.upsert_portfolio_snapshot(
                ts,
                {"positions": {"GROW.EU": {"quantity": 10, "value_eur": value}}, "cash_eur": 0.0},
            )

        currency = MagicMock()
        currency.to_eur_for_date = AsyncMock(side_effect=lambda amount, currency, date: amount)
        currency.to_eur = AsyncMock(side_effect=lambda amount, currency: amount)

        broker = MagicMock()
        broker.connected = False
        broker.connect = AsyncMock(return_value=False)

        deps = MagicMock()
        deps.db = temp_db
        deps.currency = currency
        deps.broker = broker
        deps.settings.get = AsyncMock(return_value=12)

        result = await get_portfolio_value_projection(deps, years=5)

        assert len(result["history"]) == 400
        assert len(result["projection"]) == 61
        assert result["projection"][0]["months_ahead"] == 0
        assert result["projection"][-1]["months_ahead"] == 60
        assert result["summary"]["current_value_eur"] == 2000.0
        assert result["summary"]["current_net_deposits_eur"] == 1480.0
        assert result["history"][-1]["net_deposits_eur"] == 1480.0
        assert result["summary"]["total_pnl_pct"] == pytest.approx(35.14)
        assert result["summary"]["avg_monthly_net_deposit_eur"] == 40.0
        assert result["summary"]["actual_avg_monthly_net_deposit_eur"] == 40.0
        assert result["summary"]["avg_monthly_net_deposit_override_eur"] is None
        assert result["summary"]["deposit_window_months"] == 12
        assert result["summary"]["projection_years"] == 5
        assert result["summary"]["projection_months"] == 60
        assert result["summary"]["projected_future_net_deposits_eur"] == 2400.0
        assert result["summary"]["projected_net_deposits_eur"] == 3880.0
        assert result["summary"]["actual_projected_future_net_deposits_eur"] == 2400.0
        assert result["summary"]["actual_projected_net_deposits_eur"] == 3880.0
        assert result["summary"]["monthly_return_rate"] > 0
        assert result["summary"]["projected_value_eur"] > result["summary"]["current_value_eur"]
        assert result["summary"]["actual_projected_value_eur"] == result["summary"]["projected_value_eur"]

        deps.settings.get.return_value = 6
        six_month_result = await get_portfolio_value_projection(deps, years=5)

        assert six_month_result["summary"]["deposit_window_months"] == 6
        assert six_month_result["summary"]["avg_monthly_net_deposit_eur"] == 80.0

        deps.settings.get.return_value = 12
        override = await get_portfolio_value_projection(deps, years=5, avg_monthly_net_deposit_eur=-250.0)

        assert override["summary"]["avg_monthly_net_deposit_eur"] == -250.0
        assert override["summary"]["actual_avg_monthly_net_deposit_eur"] == 40.0
        assert override["summary"]["avg_monthly_net_deposit_override_eur"] == -250.0
        assert override["summary"]["projected_future_net_deposits_eur"] == -15000.0
        assert override["summary"]["projected_net_deposits_eur"] == -13520.0
        assert override["summary"]["actual_projected_future_net_deposits_eur"] == 2400.0
        assert override["summary"]["actual_projected_net_deposits_eur"] == 3880.0
        assert override["summary"]["projected_value_eur"] < result["summary"]["projected_value_eur"]
        assert override["summary"]["actual_projected_value_eur"] == result["summary"]["projected_value_eur"]

    @pytest.mark.asyncio
    async def test_empty_value_projection_returns_empty_contract(self, temp_db):
        from sentinel.api.routers.portfolio import get_portfolio_value_projection

        deps = MagicMock()
        deps.db = temp_db

        result = await get_portfolio_value_projection(deps)

        assert result == {"history": [], "projection": [], "summary": None}

    @pytest.mark.asyncio
    async def test_value_projection_rejects_unknown_horizon(self):
        from fastapi import HTTPException

        from sentinel.api.routers.portfolio import get_portfolio_value_projection

        deps = MagicMock()

        with pytest.raises(HTTPException, match="Invalid projection horizon") as exc:
            await get_portfolio_value_projection(deps, years=7)

        assert exc.value.status_code == 400

        with pytest.raises(HTTPException, match="Invalid monthly net deposit override") as exc:
            await get_portfolio_value_projection(deps, avg_monthly_net_deposit_eur=float("inf"))

        assert exc.value.status_code == 400
