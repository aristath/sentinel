"""Tests for the twelve-month plan returned with recommendations."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from sentinel.planner.models import LongTermPlan, LongTermTarget, TradeRecommendation


def _plan() -> LongTermPlan:
    return LongTermPlan(
        as_of_date="2026-07-16",
        horizon_end_date="2027-07-16",
        horizon_months=12,
        current_total_value_eur=10_000.0,
        avg_monthly_net_deposit_eur=500.0,
        expected_contributions_eur=6_000.0,
        terminal_portfolio_value_eur=16_000.0,
        current_cash_eur=1_000.0,
        target_cash_allocation=0.5,
        target_cash_value_eur=8_000.0,
        cash_gap_eur=7_000.0,
        targets=[
            LongTermTarget(
                symbol="AAA",
                clara_score=0.9,
                opportunity_score=0.8,
                target_allocation=0.5,
                current_value_eur=2_000.0,
                target_value_eur=8_000.0,
                gap_eur=6_000.0,
                current_quantity=20,
                target_quantity=80,
                quantity_delta=60,
                price=100.0,
                currency="EUR",
                lot_size=1,
            )
        ],
    )


@pytest.mark.asyncio
async def test_recommendations_endpoint_includes_fixed_plan_snapshot():
    import sentinel.api.routers.planner as planner_router

    rec = TradeRecommendation(
        symbol="AAA",
        action="buy",
        current_allocation=0.2,
        target_allocation=0.5,
        allocation_delta=0.6,
        current_value_eur=2_000.0,
        target_value_eur=8_000.0,
        value_delta_eur=1_000.0,
        quantity=10,
        price=100.0,
        currency="EUR",
        lot_size=1,
        contrarian_score=0.8,
        priority=1_000.0,
        reason="test",
        timing_eligible=True,
        target_gap_ratio=0.75,
    )
    planner = MagicMock()
    planner.get_recommendations_with_plan = AsyncMock(return_value=([rec], _plan()))
    portfolio = MagicMock()
    portfolio.total_cash_eur = AsyncMock(return_value=1_500.0)
    fee_calculator = MagicMock()
    fee_calculator.calculate_batch = AsyncMock(
        return_value={
            "total_sell_value": 0.0,
            "total_buy_value": 1_000.0,
            "total_fees": 4.0,
            "sell_fees": 0.0,
            "buy_fees": 4.0,
        }
    )
    deps = MagicMock()
    deps.settings.get = AsyncMock(return_value=100.0)
    deps.db.get_job_schedule = AsyncMock(return_value={"interval_minutes": 60, "interval_market_open_minutes": 20})

    with (
        patch.object(planner_router, "Planner", return_value=planner),
        patch.object(planner_router, "Portfolio", return_value=portfolio),
        patch.object(planner_router, "FeeCalculator", return_value=fee_calculator),
        patch.object(planner_router, "get_open_market_symbols", AsyncMock(return_value={"AAA"})),
    ):
        result = await planner_router.get_recommendations(deps)

    assert result["plan"]["horizon_months"] == 12
    assert result["plan"]["horizon_end_date"] == "2027-07-16"
    assert result["plan"]["terminal_portfolio_value_eur"] == 16_000.0
    assert result["plan"]["target_cash_allocation_pct"] == 50.0
    assert result["plan"]["target_cash_value_eur"] == 8_000.0
    assert result["plan"]["targets"][0] == {
        "symbol": "AAA",
        "clara_score": 0.9,
        "opportunity_score": 0.8,
        "target_allocation_pct": 50.0,
        "current_value_eur": 2_000.0,
        "target_value_eur": 8_000.0,
        "gap_eur": 6_000.0,
        "model_target_allocation_pct": 50.0,
        "model_target_value_eur": 8_000.0,
        "sell_locked": False,
        "current_quantity": 20,
        "target_quantity": 80,
        "quantity_delta": 60,
        "price": 100.0,
        "currency": "EUR",
        "lot_size": 1,
    }
    assert result["recommendations"][0]["timing_eligible"] is True
    assert result["recommendations"][0]["target_gap_ratio"] == 0.75
    assert result["recommendations"][0]["is_fallback"] is False
    assert result["recommendations"][0]["reason_code"] is None
    assert result["summary"]["valid_for_minutes"] == 20
    assert result["summary"]["current_cash"] == 1_000.0
    portfolio.total_cash_eur.assert_not_awaited()
    planner.get_recommendations_with_plan.assert_awaited_once_with(
        min_trade_value=100.0,
        eligible_symbols={"AAA"},
    )
