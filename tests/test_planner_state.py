"""Tests for input-driven planner state."""

from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock

import pytest

from sentinel.planner import Planner
from sentinel.planner.models import PlannerState
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
            eligible_symbols=None,
            track_fallback_state=False,
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
                "min_cash_buffer": 0.0,
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
                    "dip_score": 0.5,
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


class TestLongTermPlan:
    def test_plan_projects_contributions_once_and_includes_zero_targets(self):
        plan = Planner._build_long_term_plan(
            ideal={"AAA": 0.5},
            current={"AAA": 0.4, "LEGACY": 0.5},
            total_value=10_000.0,
            signal_bundle={
                "rebalance_signals": {
                    "AAA": {"user_multiplier": 0.9, "opp_score": 0.8},
                    "LEGACY": {"user_multiplier": 0.5, "opp_score": 0.1},
                }
            },
            avg_monthly_net_deposit_eur=500.0,
            as_of_date="2026-01-31",
        )

        assert plan.horizon_months == 12
        assert plan.horizon_end_date == "2027-01-31"
        assert plan.expected_contributions_eur == 6_000.0
        assert plan.terminal_portfolio_value_eur == 16_000.0
        assert plan.current_cash_eur == pytest.approx(1_000.0)
        assert plan.target_cash_allocation == pytest.approx(0.5)
        assert plan.target_cash_value_eur == pytest.approx(8_000.0)
        assert sum(target.target_value_eur for target in plan.targets) + plan.target_cash_value_eur == pytest.approx(
            plan.terminal_portfolio_value_eur
        )
        assert plan.cash_gap_eur == pytest.approx(7_000.0)
        targets = {target.symbol: target for target in plan.targets}
        assert targets["AAA"].target_value_eur == 8_000.0
        assert targets["AAA"].gap_eur == 4_000.0
        assert targets["LEGACY"].target_value_eur == 0.0
        assert targets["LEGACY"].gap_eur == -5_000.0

    def test_plan_treats_no_sell_overweight_as_floor(self):
        plan = Planner._build_long_term_plan(
            ideal={"LOCKED": 0.4, "BUYME": 0.4},
            current={"LOCKED": 0.7, "BUYME": 0.1, "OTHER": 0.1},
            total_value=10_000.0,
            signal_bundle={
                "rebalance_signals": {
                    "LOCKED": {"user_multiplier": 0.8, "opp_score": 0.1},
                    "BUYME": {"user_multiplier": 0.9, "opp_score": 0.8},
                    "OTHER": {"user_multiplier": 0.5, "opp_score": 0.2},
                }
            },
            avg_monthly_net_deposit_eur=0.0,
            as_of_date="2026-01-31",
            security_constraints={
                "LOCKED": {"allow_sell": 0},
                "BUYME": {"allow_sell": 1},
                "OTHER": {"allow_sell": 1},
            },
        )

        targets = {target.symbol: target for target in plan.targets}
        assert targets["LOCKED"].sell_locked is True
        assert targets["LOCKED"].target_value_eur == pytest.approx(7_000.0)
        assert targets["LOCKED"].gap_eur == pytest.approx(0.0)
        assert targets["LOCKED"].target_allocation == pytest.approx(0.7)
        assert targets["LOCKED"].model_target_value_eur == pytest.approx(4_000.0)

        assert targets["BUYME"].target_value_eur == pytest.approx(2_000.0)
        assert targets["BUYME"].gap_eur == pytest.approx(1_000.0)
        assert plan.target_cash_value_eur == pytest.approx(1_000.0)
        assert (sum(target.target_value_eur for target in plan.targets) + plan.target_cash_value_eur) == pytest.approx(
            plan.terminal_portfolio_value_eur
        )

    def test_plan_rechecks_no_sell_floors_after_rescaling(self):
        plan = Planner._build_long_term_plan(
            ideal={"LOCKED": 0.4, "SECOND": 0.1, "BUYME": 0.4},
            current={"LOCKED": 0.7, "SECOND": 0.15, "BUYME": 0.05},
            total_value=10_000.0,
            signal_bundle={
                "rebalance_signals": {
                    "LOCKED": {"user_multiplier": 0.8, "opp_score": 0.1},
                    "SECOND": {"user_multiplier": 0.7, "opp_score": 0.2},
                    "BUYME": {"user_multiplier": 0.9, "opp_score": 0.8},
                }
            },
            avg_monthly_net_deposit_eur=0.0,
            as_of_date="2026-01-31",
            security_constraints={
                "LOCKED": {"allow_sell": 0},
                "SECOND": {"allow_sell": 0},
                "BUYME": {"allow_sell": 1},
            },
        )

        targets = {target.symbol: target for target in plan.targets}
        assert targets["LOCKED"].sell_locked is True
        assert targets["LOCKED"].target_value_eur == pytest.approx(7_000.0)
        assert targets["LOCKED"].gap_eur == pytest.approx(0.0)
        assert targets["SECOND"].sell_locked is True
        assert targets["SECOND"].target_value_eur == pytest.approx(1_500.0)
        assert targets["SECOND"].gap_eur == pytest.approx(0.0)
        assert targets["BUYME"].target_value_eur == pytest.approx(1_200.0)
        assert plan.target_cash_value_eur == pytest.approx(300.0)
        assert (sum(target.target_value_eur for target in plan.targets) + plan.target_cash_value_eur) == pytest.approx(
            plan.terminal_portfolio_value_eur
        )
