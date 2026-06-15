"""Tests for the /planner/recommendations endpoint deferred compatibility field."""

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


def _patches(planner):
    """Patch the module-level deps used by the endpoint."""
    mock_planner = MagicMock()
    mock_planner.get_recommendations = AsyncMock(return_value=[])

    mock_portfolio = MagicMock()
    mock_portfolio.total_cash_eur = AsyncMock(return_value=1000.0)
    mock_portfolio.total_value = AsyncMock(return_value=10_000.0)

    mock_fee_calc = MagicMock()
    mock_fee_calc.calculate_batch = AsyncMock(return_value=_fee_summary())

    mock_deposit_history = MagicMock()
    mock_deposit_history.get_rolling_6m_avg_net_deposit = AsyncMock(return_value=250.0)

    deps = MagicMock()
    deps.settings.get = AsyncMock(
        side_effect=lambda key, default=None: {"min_trade_value": 100.0, "strategy_projection_months": 12}.get(
            key, default
        )
    )
    deps.currency = MagicMock()
    deps.db.get_pending_trades = AsyncMock(
        return_value=[
            {
                "trade_key": "AAPL:buy",
                "symbol": "AAPL",
                "action": "buy",
                "target_amount_eur": 1500.0,
                "reason": "reserved: stale deferred row",
                "created_at": 1_700_000_000,
                "last_evaluated": 1_700_086_400,
            }
        ]
    )

    return (
        deps,
        patch.object(planner, "Planner", return_value=mock_planner),
        patch.object(planner, "Portfolio", return_value=mock_portfolio),
        patch.object(planner, "FeeCalculator", return_value=mock_fee_calc),
        patch.object(planner, "DepositHistoryHelper", return_value=mock_deposit_history),
    )


@pytest.mark.asyncio
async def test_deferred_field_is_empty_even_with_stale_pending_rows():
    import sentinel.api.routers.planner as planner

    deps, p_planner, p_portfolio, p_fees, p_deposits = _patches(planner)
    with p_planner, p_portfolio, p_fees, p_deposits:
        result = await planner.get_recommendations(deps)

    assert "deferred" in result
    assert result["deferred"] == []
    assert result["summary"]["avg_monthly_net_deposit_6m"] == 250.0
    assert result["summary"]["projection_months"] == 12
    assert result["summary"]["projected_contribution_eur"] == 3000.0
    assert result["summary"]["projected_total_value_eur"] == 13_000.0
    deps.db.get_pending_trades.assert_not_called()


@pytest.mark.asyncio
async def test_deferred_empty_for_fresh_plan():
    import sentinel.api.routers.planner as planner

    deps, p_planner, p_portfolio, p_fees, p_deposits = _patches(planner)
    with p_planner, p_portfolio, p_fees, p_deposits:
        result = await planner.get_recommendations(deps)

    assert result["deferred"] == []
