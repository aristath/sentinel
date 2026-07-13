"""Tests for input-driven planner state."""

from datetime import date
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock

import pytest

from sentinel.planner import Planner
from sentinel.planner.models import PlannerState, TradeRecommendation
from sentinel.planner.rebalance import RebalanceEngine
from sentinel.settings import Settings


@pytest.fixture(autouse=True)
def clear_settings_singleton():
    cast(Any, Settings)._clear()
    yield
    cast(Any, Settings)._clear()


class TestPlannerStateInputs:
    @pytest.mark.asyncio
    async def test_get_recommendations_uses_supplied_eur_state(self):
        planner = Planner(db=MagicMock(), broker=MagicMock(), portfolio=MagicMock())
        state = PlannerState(
            positions=[
                {
                    "symbol": "AAA",
                    "quantity": 4,
                    "current_price": 100.0,
                    "currency": "USD",
                    "value_eur": 400.0,
                },
                {
                    "symbol": "BBB",
                    "quantity": 5,
                    "current_price": 100.0,
                    "currency": "CHF",
                    "value_eur": 500.0,
                },
            ],
            cash_balances={"EUR": 100.0},
            avg_monthly_net_deposit_eur=3000.0,
        )

        planner._allocation_calculator.calculate_ideal_portfolio = AsyncMock(return_value={"AAA": 0.5, "BBB": 0.5})
        planner._allocation_calculator.get_last_signal_bundle = MagicMock(return_value={})
        planner._portfolio_analyzer.get_current_allocations = AsyncMock(return_value={"WRONG": 1.0})
        planner._portfolio_analyzer.get_total_value = AsyncMock(return_value=999999.0)
        planner._rebalance_engine.get_recommendations = AsyncMock(return_value=[])
        planner._currency.get_rate = AsyncMock(side_effect=AssertionError("PlannerState values must already be EUR"))

        await planner.get_recommendations(state=state)

        planner._portfolio_analyzer.get_current_allocations.assert_not_awaited()
        planner._portfolio_analyzer.get_total_value.assert_not_awaited()
        planner._rebalance_engine.get_recommendations.assert_awaited_once_with(
            ideal={"AAA": 0.5, "BBB": 0.5},
            current={"AAA": 0.4, "BBB": 0.5},
            total_value=1000.0,
            min_trade_value=None,
            as_of_date=None,
            precomputed_rebalance_signals=None,
            precomputed_sleeves=None,
            state=state,
        )

    @pytest.mark.asyncio
    async def test_get_recommendations_rejects_non_eur_state_cash(self):
        planner = Planner(db=MagicMock(), broker=MagicMock(), portfolio=MagicMock())
        state = PlannerState(
            positions=[],
            cash_balances={"EUR": 100.0, "USD": 900.0},
            avg_monthly_net_deposit_eur=3000.0,
        )

        planner._allocation_calculator.calculate_ideal_portfolio = AsyncMock(return_value={})
        planner._allocation_calculator.get_last_signal_bundle = MagicMock(return_value={})

        with pytest.raises(ValueError, match="PlannerState cash must be EUR-only"):
            await planner.get_recommendations(state=state)


class TestRebalanceEngineStateInputs:
    @pytest.mark.asyncio
    async def test_engine_uses_state_for_positions_cash_and_deposit_assumption(self):
        db = MagicMock()
        db.cache_get = AsyncMock(return_value=None)
        db.cache_set = AsyncMock()
        db.get_all_positions = AsyncMock(side_effect=AssertionError("state positions should be used"))
        db.get_all_securities = AsyncMock(
            return_value=[
                {
                    "symbol": "AAA",
                    "currency": "EUR",
                    "min_lot": 1,
                    "allow_buy": 1,
                    "allow_sell": 1,
                    "user_multiplier": 1.0,
                }
            ]
        )
        db.get_prices_for_symbols = AsyncMock(
            return_value={"AAA": [{"date": f"2025-01-{i:02d}", "close": 100.0} for i in range(1, 251)]}
        )
        db.get_strategy_states = AsyncMock(return_value={})
        db.get_latest_trades_for_symbols = AsyncMock(return_value={})

        engine = RebalanceEngine(db=db)
        engine._settings = MagicMock()
        engine._settings.get = AsyncMock(
            side_effect=lambda key, default=None: {
                "max_position_pct": 100.0,
                "transaction_fee_fixed": 0.0,
                "transaction_fee_percent": 0.0,
            }.get(key, default)
        )
        engine._portfolio = MagicMock()
        engine._portfolio.total_cash_eur = AsyncMock(side_effect=AssertionError("state cash should be used"))
        engine._currency = MagicMock()
        engine._currency.get_rate = AsyncMock(return_value=1.0)
        engine._currency.to_eur = AsyncMock(side_effect=lambda amount, _currency: amount)
        engine._deposit_history = MagicMock()
        engine._deposit_history.get_rolling_6m_avg_net_deposit = AsyncMock(
            side_effect=AssertionError("state deposit assumption should be used")
        )
        engine._deposit_history.get_rolling_6m_avg_deposit = AsyncMock(
            side_effect=AssertionError("state deposit assumption should be used")
        )

        state = PlannerState(
            positions=[
                {
                    "symbol": "AAA",
                    "quantity": 4,
                    "current_price": 100.0,
                    "currency": "EUR",
                    "value_eur": 400.0,
                }
            ],
            cash_balances={"EUR": 1000.0},
            avg_monthly_net_deposit_eur=3000.0,
        )

        recs = await engine.get_recommendations(
            ideal={"AAA": 1.0},
            current={"AAA": 400.0 / 1400.0},
            total_value=1400.0,
            min_trade_value=100.0,
            as_of_date="2025-01-31",
            precomputed_rebalance_signals={
                "AAA": {
                    "opp_score": 0.5,
                    "opp_score_raw": 0.5,
                    "sleeve": "core",
                    "user_multiplier": 1.0,
                    "clara_target_pct": 1.0,
                }
            },
            precomputed_sleeves={"AAA": "core"},
            state=state,
        )

        assert recs
        assert recs[0].symbol == "AAA"
        assert recs[0].action == "buy"
        assert recs[0].quantity == 10
        assert recs[0].value_delta_eur == 1000.0


class TestPlannerForecast:
    @pytest.mark.asyncio
    async def test_build_current_state_converts_external_values_to_eur_boundary(self):
        planner = Planner(db=MagicMock(), broker=MagicMock(), portfolio=MagicMock())
        planner._portfolio.positions = AsyncMock(
            return_value=[
                {
                    "symbol": "USD1",
                    "quantity": 2,
                    "current_price": 100.0,
                    "currency": "USD",
                }
            ]
        )
        planner._portfolio.get_cash_balances = AsyncMock(return_value={"EUR": 500.0, "USD": 100.0})
        planner._currency.to_eur = AsyncMock(
            side_effect=lambda amount, currency: amount * 0.9 if currency == "USD" else amount
        )
        planner._rebalance_engine._get_avg_monthly_net_deposit = AsyncMock(return_value=3000.0)

        state = await planner.build_current_state()

        assert state.cash_balances == {"EUR": 590.0}
        assert state.positions == [
            {
                "symbol": "USD1",
                "quantity": 2,
                "current_price": 100.0,
                "currency": "USD",
                "value_eur": 180.0,
            }
        ]
        assert state.avg_monthly_net_deposit_eur == 3000.0

    @pytest.mark.asyncio
    async def test_forecast_executes_each_month_then_deposits_into_next_state(self):
        planner = Planner(db=MagicMock(), broker=MagicMock(), portfolio=MagicMock())
        planner._settings.get = AsyncMock(
            side_effect=lambda key, default=None: {
                "transaction_fee_fixed": 0.0,
                "transaction_fee_percent": 0.0,
            }.get(key, default)
        )

        initial_state = PlannerState(
            positions=[
                {
                    "symbol": "AAA",
                    "quantity": 0,
                    "current_price": 100.0,
                    "currency": "EUR",
                    "value_eur": 0.0,
                }
            ],
            cash_balances={"EUR": 1000.0},
            avg_monthly_net_deposit_eur=3000.0,
        )

        plans = [
            [
                TradeRecommendation(
                    symbol="AAA",
                    action="buy",
                    current_allocation=0.0,
                    target_allocation=1.0,
                    allocation_delta=1.0,
                    current_value_eur=0.0,
                    target_value_eur=1000.0,
                    value_delta_eur=1000.0,
                    quantity=10,
                    price=100.0,
                    currency="EUR",
                    lot_size=1,
                    contrarian_score=0.5,
                    priority=1000.0,
                    reason="test",
                )
            ],
            [
                TradeRecommendation(
                    symbol="BBB",
                    action="buy",
                    current_allocation=0.0,
                    target_allocation=1.0,
                    allocation_delta=1.0,
                    current_value_eur=0.0,
                    target_value_eur=3000.0,
                    value_delta_eur=3000.0,
                    quantity=30,
                    price=100.0,
                    currency="EUR",
                    lot_size=1,
                    contrarian_score=0.5,
                    priority=3000.0,
                    reason="test",
                )
            ],
        ]
        planner.get_recommendations = AsyncMock(side_effect=plans)

        forecast = await planner.forecast_monthly_plans(months=2, initial_state=initial_state)

        assert len(forecast) == 2
        assert forecast[0]["starting_cash_eur"] == 1000.0
        assert forecast[0]["ending_cash_eur"] == 0.0
        assert forecast[1]["starting_cash_eur"] == 3000.0
        assert forecast[1]["ending_cash_eur"] == 0.0

        first_state = planner.get_recommendations.await_args_list[0].kwargs["state"]
        second_state = planner.get_recommendations.await_args_list[1].kwargs["state"]
        assert first_state.cash_balances == {"EUR": 1000.0}
        assert second_state.cash_balances == {"EUR": 3000.0}
        assert second_state.positions[0]["symbol"] == "AAA"
        assert second_state.positions[0]["value_eur"] == 1000.0

    @pytest.mark.asyncio
    async def test_forecast_advances_as_of_date_each_month(self):
        planner = Planner(db=MagicMock(), broker=MagicMock(), portfolio=MagicMock())
        planner._settings.get = AsyncMock(
            side_effect=lambda key, default=None: {
                "transaction_fee_fixed": 0.0,
                "transaction_fee_percent": 0.0,
            }.get(key, default)
        )
        planner.get_recommendations = AsyncMock(return_value=[])

        initial_state = PlannerState(
            positions=[],
            cash_balances={"EUR": 1000.0},
            avg_monthly_net_deposit_eur=0.0,
        )

        forecast = await planner.forecast_monthly_plans(
            months=3,
            initial_state=initial_state,
            start_date=date(2026, 1, 31),
        )

        assert [month["as_of_date"] for month in forecast] == ["2026-01-31", "2026-02-28", "2026-03-31"]
        assert [call.kwargs["as_of_date"] for call in planner.get_recommendations.await_args_list] == [
            "2026-01-31",
            "2026-02-28",
            "2026-03-31",
        ]

    @pytest.mark.asyncio
    async def test_forecast_includes_monthly_eur_trade_totals(self):
        planner = Planner(db=MagicMock(), broker=MagicMock(), portfolio=MagicMock())
        planner._settings.get = AsyncMock(
            side_effect=lambda key, default=None: {
                "transaction_fee_fixed": 2.0,
                "transaction_fee_percent": 1.0,
            }.get(key, default)
        )

        initial_state = PlannerState(
            positions=[
                {
                    "symbol": "AAA",
                    "quantity": 10,
                    "current_price": 100.0,
                    "currency": "EUR",
                    "value_eur": 1000.0,
                }
            ],
            cash_balances={"EUR": 1000.0},
            avg_monthly_net_deposit_eur=0.0,
        )
        planner.get_recommendations = AsyncMock(
            return_value=[
                TradeRecommendation(
                    symbol="AAA",
                    action="sell",
                    current_allocation=0.5,
                    target_allocation=0.25,
                    allocation_delta=-0.25,
                    current_value_eur=1000.0,
                    target_value_eur=500.0,
                    value_delta_eur=-500.0,
                    quantity=5,
                    price=100.0,
                    currency="EUR",
                    lot_size=1,
                    contrarian_score=0.5,
                    priority=1000.0,
                    reason="test",
                ),
                TradeRecommendation(
                    symbol="BBB",
                    action="buy",
                    current_allocation=0.0,
                    target_allocation=0.5,
                    allocation_delta=0.5,
                    current_value_eur=0.0,
                    target_value_eur=1000.0,
                    value_delta_eur=1000.0,
                    quantity=10,
                    price=100.0,
                    currency="EUR",
                    lot_size=1,
                    contrarian_score=0.5,
                    priority=900.0,
                    reason="test",
                ),
            ]
        )

        forecast = await planner.forecast_monthly_plans(months=1, initial_state=initial_state)

        assert forecast[0]["total_buy_value_eur"] == 1000.0
        assert forecast[0]["total_sell_value_eur"] == 500.0
        assert forecast[0]["buy_fees_eur"] == 12.0
        assert forecast[0]["sell_fees_eur"] == 7.0
        assert forecast[0]["total_fees_eur"] == 19.0
        assert forecast[0]["net_trade_cash_delta_eur"] == -519.0
        assert forecast[0]["ending_cash_eur"] == 481.0
