"""Tests for the table-only /portfolio/period-stats endpoint."""

from datetime import date, datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest


def _timestamp(iso_date: str) -> int:
    return int(datetime.strptime(iso_date, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp())


def _trade(symbol: str, side: str, quantity: float, price: float, iso_date: str, currency: str = "EUR") -> dict:
    return {
        "symbol": symbol,
        "side": side,
        "quantity": quantity,
        "price": price,
        "commission": 0.0,
        "commission_currency": currency,
        "executed_at": _timestamp(iso_date),
    }


def _snapshot(iso_date: str, total_value_eur: float) -> dict:
    return {
        "date": _timestamp(iso_date),
        "data": {
            "positions": {"TEST": {"value_eur": total_value_eur}},
            "cash_eur": 0.0,
        },
    }


def _deps(
    *,
    cash_flows,
    cash_flow_summary,
    positions,
    cash,
    trades=None,
    securities=None,
    prices=None,
    snapshots=None,
):
    prices = prices or {}
    deps = MagicMock()
    deps.db.get_cash_flows = AsyncMock(return_value=cash_flows)
    deps.db.get_cash_flow_summary = AsyncMock(return_value=cash_flow_summary)
    deps.db.get_all_positions = AsyncMock(return_value=positions)
    deps.db.get_cash_balances = AsyncMock(return_value=cash)
    deps.db.get_trades = AsyncMock(return_value=trades or [])
    deps.db.get_all_securities = AsyncMock(return_value=securities or [{"symbol": "TEST", "currency": "EUR"}])
    deps.db.get_portfolio_snapshots = AsyncMock(return_value=snapshots or [])

    async def get_prices(symbol, days=None, end_date=None):
        rows = prices.get(symbol, [])
        if end_date is not None:
            rows = [row for row in rows if row["date"] <= end_date]
        rows = sorted(rows, key=lambda row: row["date"], reverse=True)
        return rows[:days] if days else rows

    deps.db.get_prices = AsyncMock(side_effect=get_prices)
    deps.currency.to_eur_for_date = AsyncMock(side_effect=lambda amount, currency, iso_date: amount)
    deps.currency.to_eur = AsyncMock(side_effect=lambda amount, currency: amount)
    deps.settings.get = AsyncMock(side_effect=lambda key, default=None: default)
    deps.broker.connect = AsyncMock(return_value=False)
    deps.broker.get_portfolio = AsyncMock(return_value={"positions": [], "cash": {}})
    return deps


def _fake_portfolio(monkeypatch, total_value: float):
    from sentinel.api.routers import portfolio as portfolio_router

    class FakePortfolio:
        def __init__(self, db=None):
            self.db = db

        async def total_value(self):
            return total_value

    monkeypatch.setattr(portfolio_router, "Portfolio", FakePortfolio)


@pytest.mark.asyncio
async def test_period_stats_use_live_current_value_and_adjust_period_deposits(monkeypatch):
    from sentinel.api.routers.portfolio import get_portfolio_period_stats

    today = date.today()
    week_ago = today - timedelta(days=7)
    _fake_portfolio(monkeypatch, 1250.0)

    deps = _deps(
        cash_flows=[
            {
                "date": (week_ago - timedelta(days=1)).isoformat(),
                "type_id": "card",
                "amount": 1000.0,
                "currency": "EUR",
            },
            {"date": today.isoformat(), "type_id": "card", "amount": 100.0, "currency": "EUR"},
        ],
        cash_flow_summary={"card": {"EUR": 1100.0}},
        positions=[{"symbol": "TEST", "quantity": 10.0, "currency": "EUR"}],
        cash={"EUR": 100.0},
        prices={
            "TEST": [{"date": week_ago.isoformat(), "close": 100.0}],
            "VWCE.EU": [
                {"date": week_ago.isoformat(), "close": 100.0},
                {"date": today.isoformat(), "close": 110.0},
            ],
        },
    )

    result = await get_portfolio_period_stats(deps)

    assert set(result["period_stats"]) == {"1D", "1W", "1M", "3M", "6M", "1Y", "YTD", "All"}
    assert result["period_stats"]["1W"]["portfolio_eur"] == 150.0
    assert result["period_stats"]["1W"]["portfolio_pct"] == pytest.approx(15.0)
    assert result["period_stats"]["1W"]["benchmark_pct"] == pytest.approx(10.0)
    assert result["period_stats"]["All"]["portfolio_eur"] == 150.0
    assert result["period_stats"]["All"]["portfolio_pct"] == pytest.approx(13.64)


@pytest.mark.asyncio
async def test_period_stats_reconstruct_start_before_trades(monkeypatch):
    from sentinel.api.routers.portfolio import get_portfolio_period_stats

    today = date.today()
    yesterday = today - timedelta(days=1)
    _fake_portfolio(monkeypatch, 110.0)

    deps = _deps(
        cash_flows=[],
        cash_flow_summary={},
        positions=[{"symbol": "TEST", "quantity": 1.0, "currency": "EUR"}],
        cash={"EUR": 0.0},
        trades=[_trade("TEST", "BUY", 1.0, 100.0, today.isoformat())],
        prices={
            "TEST": [{"date": yesterday.isoformat(), "close": 100.0}],
            "VWCE.EU": [
                {"date": yesterday.isoformat(), "close": 100.0},
                {"date": today.isoformat(), "close": 101.0},
            ],
        },
    )

    result = await get_portfolio_period_stats(deps)

    assert result["period_stats"]["1D"]["portfolio_eur"] == 10.0
    assert result["period_stats"]["1D"]["portfolio_pct"] == pytest.approx(10.0)
    assert result["period_stats"]["All"]["portfolio_eur"] == 110.0


@pytest.mark.asyncio
async def test_period_stats_use_broker_intraday_for_1d(monkeypatch):
    from sentinel.api.routers.portfolio import get_portfolio_period_stats

    today = date.today()
    _fake_portfolio(monkeypatch, 990.0)

    deps = _deps(
        cash_flows=[],
        cash_flow_summary={},
        positions=[{"symbol": "TEST", "quantity": 10.0, "currency": "EUR", "current_price": 99.0}],
        cash={"EUR": 0.0},
        prices={"TEST": [{"date": (today - timedelta(days=30)).isoformat(), "close": 120.0}]},
    )
    deps.broker.connect = AsyncMock(return_value=True)
    deps.broker.get_portfolio = AsyncMock(
        return_value={
            "positions": [
                {
                    "symbol": "TEST",
                    "quantity": 10.0,
                    "current_price": 99.0,
                    "close_price": 100.0,
                    "currency": "EUR",
                }
            ],
            "cash": {},
        }
    )

    result = await get_portfolio_period_stats(deps)

    assert result["period_stats"]["1D"]["portfolio_eur"] == -10.0
    assert result["period_stats"]["1D"]["portfolio_pct"] == pytest.approx(-1.0)


@pytest.mark.asyncio
async def test_period_stats_do_not_use_stale_component_prices(monkeypatch):
    from sentinel.api.routers.portfolio import get_portfolio_period_stats

    today = date.today()
    yesterday = today - timedelta(days=1)
    stale_date = today - timedelta(days=30)
    _fake_portfolio(monkeypatch, 110.0)

    deps = _deps(
        cash_flows=[],
        cash_flow_summary={},
        positions=[{"symbol": "TEST", "quantity": 1.0, "currency": "EUR", "current_price": 110.0}],
        cash={"EUR": 0.0},
        prices={
            "TEST": [{"date": stale_date.isoformat(), "close": 100.0}],
            "VWCE.EU": [
                {"date": yesterday.isoformat(), "close": 100.0},
                {"date": today.isoformat(), "close": 101.0},
            ],
        },
    )

    result = await get_portfolio_period_stats(deps)

    assert result["period_stats"]["1D"]["portfolio_eur"] is None
    assert result["period_stats"]["1D"]["portfolio_pct"] is None


@pytest.mark.asyncio
async def test_period_stats_fill_1w_and_1m_from_current_price_fallback_when_component_prices_are_stale(monkeypatch):
    from sentinel.api.routers.portfolio import get_portfolio_period_stats

    today = date.today()
    week_ago = today - timedelta(days=7)
    month_ago = today - timedelta(days=30)
    stale_date = today - timedelta(days=45)
    _fake_portfolio(monkeypatch, 1250.0)

    deps = _deps(
        cash_flows=[
            {
                "date": (month_ago - timedelta(days=1)).isoformat(),
                "type_id": "card",
                "amount": 1000.0,
                "currency": "EUR",
            }
        ],
        cash_flow_summary={"card": {"EUR": 1000.0}},
        positions=[{"symbol": "TEST", "quantity": 10.0, "currency": "EUR", "current_price": 125.0}],
        cash={"EUR": 0.0},
        prices={
            "TEST": [{"date": stale_date.isoformat(), "close": 100.0}],
            "VWCE.EU": [
                {"date": month_ago.isoformat(), "close": 100.0},
                {"date": week_ago.isoformat(), "close": 105.0},
                {"date": today.isoformat(), "close": 110.0},
            ],
        },
        snapshots=[
            _snapshot(month_ago.isoformat(), 1000.0),
            _snapshot(week_ago.isoformat(), 1100.0),
        ],
    )

    result = await get_portfolio_period_stats(deps)

    assert result["period_stats"]["1W"]["portfolio_eur"] == 0.0
    assert result["period_stats"]["1W"]["portfolio_pct"] == pytest.approx(0.0)
    assert result["period_stats"]["1M"]["portfolio_eur"] == 0.0
    assert result["period_stats"]["1M"]["portfolio_pct"] == pytest.approx(0.0)


@pytest.mark.asyncio
async def test_period_stats_do_not_turn_stale_benchmark_prices_into_zero(monkeypatch):
    from sentinel.api.routers.portfolio import get_portfolio_period_stats

    today = date.today()
    week_ago = today - timedelta(days=7)
    stale_end = today - timedelta(days=10)
    _fake_portfolio(monkeypatch, 1100.0)

    deps = _deps(
        cash_flows=[{"date": week_ago.isoformat(), "type_id": "card", "amount": 1000.0, "currency": "EUR"}],
        cash_flow_summary={"card": {"EUR": 1000.0}},
        positions=[{"symbol": "TEST", "quantity": 10.0, "currency": "EUR"}],
        cash={"EUR": 0.0},
        prices={
            "TEST": [{"date": week_ago.isoformat(), "close": 100.0}],
            "VWCE.EU": [
                {"date": week_ago.isoformat(), "close": 100.0},
                {"date": stale_end.isoformat(), "close": 105.0},
            ],
        },
    )

    result = await get_portfolio_period_stats(deps)

    assert result["period_stats"]["1W"]["portfolio_eur"] == 100.0
    assert result["period_stats"]["1W"]["benchmark_pct"] is None
    assert result["period_stats"]["1W"]["alpha_pct"] is None
