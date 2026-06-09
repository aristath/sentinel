"""Tests for the /planner/recommendations endpoint surfacing deferred trades."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _fee_summary():
    return {
        "total_sell_value": 0.0,
        "total_buy_value": 0.0,
        "total_fees": 0.0,
        "sell_fees": 0.0,
        "buy_fees": 0.0,
    }


def _patches(planner, deferred_rows):
    """Patch the module-level deps used by the endpoint."""
    mock_planner = MagicMock()
    mock_planner.get_recommendations = AsyncMock(return_value=[])

    mock_portfolio = MagicMock()
    mock_portfolio.total_cash_eur = AsyncMock(return_value=1000.0)

    mock_fee_calc = MagicMock()
    mock_fee_calc.calculate_batch = AsyncMock(return_value=_fee_summary())

    deps = MagicMock()
    deps.settings.get = AsyncMock(return_value=100.0)
    deps.db.get_pending_trades = AsyncMock(return_value=deferred_rows)

    return (
        deps,
        patch.object(planner, "Planner", return_value=mock_planner),
        patch.object(planner, "Portfolio", return_value=mock_portfolio),
        patch.object(planner, "FeeCalculator", return_value=mock_fee_calc),
    )


@pytest.mark.asyncio
async def test_deferred_trades_are_surfaced():
    import sentinel.api.routers.planner as planner

    rows = [
        {
            "trade_key": "AAPL:buy",
            "symbol": "AAPL",
            "action": "buy",
            "target_amount_eur": 1500.0,
            "reason": "reserved: ~2.0mo of deposits to fund €1,500 buy",
            "created_at": 1_700_000_000,
            "last_evaluated": 1_700_086_400,
        }
    ]
    deps, p_planner, p_portfolio, p_fees = _patches(planner, rows)
    with p_planner, p_portfolio, p_fees:
        result = await planner.get_recommendations(deps)

    assert "deferred" in result
    assert result["deferred"] == [
        {
            "symbol": "AAPL",
            "action": "buy",
            "target_amount_eur": 1500.0,
            "reason": "reserved: ~2.0mo of deposits to fund €1,500 buy",
            "reserved": True,  # derived from the "reserved:" reason prefix
            "created_at": 1_700_000_000,
            "last_evaluated": 1_700_086_400,
        }
    ]


@pytest.mark.asyncio
async def test_deferred_empty_when_bucket_empty():
    import sentinel.api.routers.planner as planner

    deps, p_planner, p_portfolio, p_fees = _patches(planner, [])
    with p_planner, p_portfolio, p_fees:
        result = await planner.get_recommendations(deps)

    assert result["deferred"] == []
