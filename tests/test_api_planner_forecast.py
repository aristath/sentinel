"""Tests for the /planner/forecast endpoint."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from sentinel.planner.models import TradeRecommendation


@pytest.mark.asyncio
async def test_forecast_endpoint_serializes_monthly_plans():
    import sentinel.api.routers.planner as planner_router

    rec = TradeRecommendation(
        symbol="AAA",
        action="buy",
        current_allocation=0.0,
        target_allocation=0.5,
        allocation_delta=0.5,
        current_value_eur=0.0,
        target_value_eur=1000.0,
        value_delta_eur=900.0,
        quantity=9,
        price=100.0,
        currency="EUR",
        lot_size=1,
        contrarian_score=0.5,
        priority=1000.0,
        reason="test",
    )
    mock_planner = MagicMock()
    mock_planner.forecast_monthly_plans = AsyncMock(
        return_value=[
            {
                "month": 1,
                "starting_cash_eur": 1000.0,
                "starting_total_value_eur": 10_000.0,
                "recommendations": [rec],
                "total_buy_value_eur": 900.0,
                "total_sell_value_eur": 0.0,
                "buy_fees_eur": 3.8,
                "sell_fees_eur": 0.0,
                "total_fees_eur": 3.8,
                "net_trade_cash_delta_eur": -903.8,
                "ending_cash_eur": 100.0,
                "ending_total_value_eur": 10_000.0,
                "next_deposit_eur": 3000.0,
            }
        ]
    )

    deps = MagicMock()
    deps.settings.get = AsyncMock(
        side_effect=lambda key, default=None: {
            "min_trade_value": 100.0,
            "planner_forecast_months": 6,
        }.get(key, default)
    )

    with patch.object(planner_router, "Planner", return_value=mock_planner):
        result = await planner_router.get_forecast(deps)

    mock_planner.forecast_monthly_plans.assert_awaited_once_with(months=6, min_trade_value=100.0)
    assert result["months"][0]["month"] == 1
    assert result["months"][0]["starting_cash_eur"] == 1000.0
    assert result["months"][0]["total_buy_value_eur"] == 900.0
    assert result["months"][0]["total_fees_eur"] == 3.8
    assert result["months"][0]["net_trade_cash_delta_eur"] == -903.8
    assert result["months"][0]["next_deposit_eur"] == 3000.0
    assert result["months"][0]["recommendations"][0]["symbol"] == "AAA"
    assert result["months"][0]["recommendations"][0]["value_delta_eur"] == 900.0


@pytest.mark.asyncio
async def test_forecast_endpoint_uses_configured_months_when_omitted():
    import sentinel.api.routers.planner as planner_router

    mock_planner = MagicMock()
    mock_planner.forecast_monthly_plans = AsyncMock(return_value=[])

    deps = MagicMock()
    deps.settings.get = AsyncMock(
        side_effect=lambda key, default=None: {
            "min_trade_value": 100.0,
            "planner_forecast_months": 9,
        }.get(key, default)
    )

    with patch.object(planner_router, "Planner", return_value=mock_planner):
        await planner_router.get_forecast(deps)

    mock_planner.forecast_monthly_plans.assert_awaited_once_with(months=9, min_trade_value=100.0)


@pytest.mark.asyncio
async def test_forecast_endpoint_explicit_months_override_setting():
    import sentinel.api.routers.planner as planner_router

    mock_planner = MagicMock()
    mock_planner.forecast_monthly_plans = AsyncMock(return_value=[])

    deps = MagicMock()
    deps.settings.get = AsyncMock(return_value=100.0)

    with patch.object(planner_router, "Planner", return_value=mock_planner):
        await planner_router.get_forecast(deps, months=12)

    mock_planner.forecast_monthly_plans.assert_awaited_once_with(months=12, min_trade_value=100.0)
