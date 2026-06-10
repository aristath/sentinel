"""Tests for patience-based rebalancing philosophy."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from sentinel.planner.rebalance import RebalanceEngine


class TestMonthsToSelfCorrect:
    """Tests for _calculate_months_to_self_correct."""

    @pytest.mark.asyncio
    async def test_normal_self_correction(self):
        """Test months_to_self_correct > 3 → trade."""
        engine = RebalanceEngine(db=MagicMock())
        engine._deposit_history = MagicMock()
        engine._deposit_history.get_rolling_6m_avg_deposit = AsyncMock(return_value=500.0)

        months = await engine._calculate_months_to_self_correct(2000.0)
        assert months == 4.0  # 2000 / 500 = 4

    @pytest.mark.asyncio
    async def test_zero_excess(self):
        """Test with zero excess above target."""
        engine = RebalanceEngine(db=MagicMock())
        engine._deposit_history = MagicMock()
        engine._deposit_history.get_rolling_6m_avg_deposit = AsyncMock(return_value=500.0)

        months = await engine._calculate_months_to_self_correct(0.0)
        assert months == 0.0

    @pytest.mark.asyncio
    async def test_negative_excess(self):
        """Test with negative excess (below target)."""
        engine = RebalanceEngine(db=MagicMock())
        engine._deposit_history = MagicMock()
        engine._deposit_history.get_rolling_6m_avg_deposit = AsyncMock(return_value=500.0)

        months = await engine._calculate_months_to_self_correct(-500.0)
        assert months == -1.0

    @pytest.mark.asyncio
    async def test_no_deposits(self):
        """Test with no deposits available."""
        engine = RebalanceEngine(db=MagicMock())
        engine._deposit_history = MagicMock()
        engine._deposit_history.get_rolling_6m_avg_deposit = AsyncMock(return_value=0.0)

        months = await engine._calculate_months_to_self_correct(1500.0)
        assert months == float("inf")

    @pytest.mark.asyncio
    async def test_fast_self_correction(self):
        """Test months_to_self_correct < 3 → no trade."""
        engine = RebalanceEngine(db=MagicMock())
        engine._deposit_history = MagicMock()
        engine._deposit_history.get_rolling_6m_avg_deposit = AsyncMock(return_value=1000.0)

        months = await engine._calculate_months_to_self_correct(2000.0)
        assert months == 2.0  # 2000 / 1000 = 2


class TestProfitsFirstSelling:
    """Tests for profits-first selling logic."""

    @pytest.mark.asyncio
    async def test_profit_sell(self):
        """Test selling only profits, not principal."""
        # Create a real engine with mocked dependencies
        db = MagicMock()
        engine = RebalanceEngine(db=db)

        # Mock dependencies
        engine._deposit_history = MagicMock()
        engine._deposit_history.get_rolling_6m_avg_deposit = AsyncMock(return_value=500.0)
        engine._check_cooloff_violation = AsyncMock(return_value=(False, ""))
        engine._check_price_anomaly = MagicMock(return_value=(False, ""))
        engine._currency = MagicMock()
        engine._currency.get_rate = AsyncMock(return_value=1.0)
        engine._currency.to_eur = AsyncMock(side_effect=lambda amt, curr: amt)

        # Mock months_to_self_correct to return a value > 3 to ensure trade is recommended
        engine._calculate_months_to_self_correct = AsyncMock(return_value=4.0)

        # Mock the call to get_rolling_6m_avg_deposit to avoid actual DB calls
        engine._deposit_history.get_rolling_6m_avg_deposit = AsyncMock(return_value=500.0)

        # Test with a position that has profit
        rec = await engine._build_recommendation(
            symbol="TEST",
            ideal={"TEST": 0.05, "OTHER": 0.10},
            current={"TEST": 0.10},
            total_value=10000.0,
            security_data={
                "TEST": {
                    "price": 100.0,
                    "currency": "EUR",
                    "fx_rate": 1.0,
                    "lot_size": 1,
                    "current_qty": 10,
                    "avg_cost": 80.0,
                    "allow_buy": 1,
                    "allow_sell": 1,
                    "trade_blocked": False,
                    "lot_class": "standard",
                    "ticket_pct": 0.0,
                    "min_ticket_eur": 0,
                    "state": {},
                }
            },
            contrarian_scores={"TEST": 0.5},
            signal_data={
                "TEST": {
                    "sleeve": "core",
                    "user_multiplier": 0.8,
                    "opp_score": 0.5,
                    "scaleout_stage": 0,
                },
                "OTHER": {
                    "sleeve": "core",
                    "user_multiplier": 0.9,
                    "opp_score": 0.6,
                },
            },
            min_trade_value=100.0,
            settings_ctx={
                "strategy_min_opp_score": 0.55,
                "max_position_pct": 25.0,
                "strategy_opportunity_addon_threshold": 0.15,
                "strategy_entry_t1_dd": -0.12,
                "strategy_entry_t2_dd": -0.20,
                "strategy_entry_t3_dd": -0.28,
                "strategy_rotation_time_stop_days": 30,
                "strategy_opportunity_cooloff_days": 15,
                "strategy_core_cooloff_days": 21,
                "strategy_same_side_cooloff_days": 10,
                "strategy_core_floor_pct": 0.05,
                "strategy_rotation_threshold": 0.8,
                "strategy_core_new_min_score": 0.0,
            },
            avg_monthly_deposit_6m=500.0,
        )

        # Verify that profits_first is True and profit_amount_eur is set
        assert rec is not None
        assert rec.profits_first is True
        assert rec.profit_amount_eur is not None and rec.profit_amount_eur > 0

    @pytest.mark.asyncio
    async def test_profit_cap_converts_local_currency_to_eur(self):
        """The profits-first cap must compare EUR-to-EUR.

        A non-EUR position's unrealized profit is in local currency; it must be
        converted to EUR (via fx_rate) before being capped against the EUR
        excess-above-target. Regression test for the currency-mixing bug.
        """
        engine = RebalanceEngine(db=MagicMock())
        engine._deposit_history = MagicMock()
        engine._deposit_history.get_rolling_6m_avg_deposit = AsyncMock(return_value=500.0)
        engine._check_cooloff_violation = AsyncMock(return_value=(False, ""))
        engine._currency = MagicMock()
        engine._currency.get_rate = AsyncMock(return_value=0.9)
        engine._currency.to_eur = AsyncMock(side_effect=lambda amt, curr: amt * 0.9)
        engine._calculate_months_to_self_correct = AsyncMock(return_value=4.0)

        # USD position: local profit = (100 - 80) * 10 = 200 USD.
        # fx_rate 0.9 (EUR per USD) → profit_amount_eur must be 180 EUR, not 200.
        rec = await engine._build_recommendation(
            symbol="USDX",
            ideal={"USDX": 0.05, "OTHER": 0.10},
            current={"USDX": 0.10},
            total_value=10000.0,
            security_data={
                "USDX": {
                    "price": 100.0,
                    "currency": "USD",
                    "fx_rate": 0.9,
                    "lot_size": 1,
                    "current_qty": 10,
                    "avg_cost": 80.0,
                    "allow_buy": 1,
                    "allow_sell": 1,
                    "trade_blocked": False,
                    "lot_class": "standard",
                    "ticket_pct": 0.0,
                    "min_ticket_eur": 0,
                    "state": {},
                }
            },
            contrarian_scores={"USDX": 0.5},
            signal_data={
                "USDX": {"sleeve": "core", "user_multiplier": 0.8, "opp_score": 0.5},
                "OTHER": {"sleeve": "core", "user_multiplier": 0.9, "opp_score": 0.6},
            },
            min_trade_value=100.0,
            settings_ctx={
                "strategy_min_opp_score": 0.55,
                "max_position_pct": 25.0,
                "strategy_opportunity_addon_threshold": 0.15,
                "strategy_entry_t1_dd": -0.12,
                "strategy_entry_t2_dd": -0.20,
                "strategy_entry_t3_dd": -0.28,
                "strategy_rotation_time_stop_days": 30,
                "strategy_opportunity_cooloff_days": 15,
                "strategy_core_cooloff_days": 21,
                "strategy_same_side_cooloff_days": 10,
                "strategy_core_floor_pct": 0.05,
                "strategy_rotation_threshold": 0.8,
                "strategy_core_new_min_score": 0.0,
            },
            avg_monthly_deposit_6m=500.0,
        )

        assert rec is not None
        assert rec.action == "sell"
        # EUR-converted profit, not the raw 200 USD local figure.
        assert rec.profit_amount_eur == pytest.approx(180.0)

    @pytest.mark.asyncio
    async def test_underwater_position_not_drift_sold(self):
        """A position trading below cost has zero profit → drift path won't sell it."""
        engine = RebalanceEngine(db=MagicMock())
        engine._deposit_history = MagicMock()
        engine._deposit_history.get_rolling_6m_avg_deposit = AsyncMock(return_value=500.0)
        engine._check_cooloff_violation = AsyncMock(return_value=(False, ""))
        engine._currency = MagicMock()
        engine._currency.get_rate = AsyncMock(return_value=1.0)
        engine._currency.to_eur = AsyncMock(side_effect=lambda amt, curr: amt)
        engine._calculate_months_to_self_correct = AsyncMock(return_value=4.0)

        rec = await engine._build_recommendation(
            symbol="LOSS",
            ideal={"LOSS": 0.05, "OTHER": 0.10},
            current={"LOSS": 0.10},
            total_value=10000.0,
            security_data={
                "LOSS": {
                    "price": 100.0,
                    "currency": "EUR",
                    "fx_rate": 1.0,
                    "lot_size": 1,
                    "current_qty": 10,
                    "avg_cost": 130.0,  # underwater
                    "allow_buy": 1,
                    "allow_sell": 1,
                    "trade_blocked": False,
                    "lot_class": "standard",
                    "ticket_pct": 0.0,
                    "min_ticket_eur": 0,
                    "state": {},
                }
            },
            contrarian_scores={"LOSS": 0.5},
            signal_data={
                "LOSS": {"sleeve": "core", "user_multiplier": 0.8, "opp_score": 0.5},
                "OTHER": {"sleeve": "core", "user_multiplier": 0.9, "opp_score": 0.6},
            },
            min_trade_value=100.0,
            settings_ctx={
                "strategy_min_opp_score": 0.55,
                "max_position_pct": 25.0,
                "strategy_opportunity_addon_threshold": 0.15,
                "strategy_entry_t1_dd": -0.12,
                "strategy_entry_t2_dd": -0.20,
                "strategy_entry_t3_dd": -0.28,
                "strategy_rotation_time_stop_days": 30,
                "strategy_opportunity_cooloff_days": 15,
                "strategy_core_cooloff_days": 21,
                "strategy_same_side_cooloff_days": 10,
                "strategy_core_floor_pct": 0.05,
                "strategy_rotation_threshold": 0.8,
                "strategy_core_new_min_score": 0.0,
            },
            avg_monthly_deposit_6m=500.0,
        )

        # Zero profit → profits-first cap forces qty to 0 → no drift sell.
        assert rec is None


class TestHighBarForRotation:
    """Tests for high bar for rotation logic."""

    @pytest.mark.asyncio
    async def test_rotation_high_conviction(self):
        """Test rotation with high conviction."""
        engine = RebalanceEngine(db=MagicMock())
        engine._deposit_history = MagicMock()
        engine._deposit_history.get_rolling_6m_avg_deposit = AsyncMock(return_value=500.0)

        with patch.object(
            engine,
            "_build_recommendation",
            new_callable=AsyncMock,
            return_value=MagicMock(
                action="sell",
                profit_amount_eur=1000.0,
                profits_first=True,
            ),
        ):
            rec = await engine._build_recommendation(
                symbol="A",
                ideal={"A": 0.05, "B": 0.10},
                current={"A": 0.10, "B": 0.05},
                total_value=10000.0,
                security_data={
                    "A": {
                        "price": 100.0,
                        "currency": "EUR",
                        "fx_rate": 1.0,
                        "lot_size": 1,
                        "current_qty": 10,
                        "avg_cost": 80.0,
                        "allow_buy": 1,
                        "allow_sell": 1,
                        "trade_blocked": False,
                        "lot_class": "standard",
                        "ticket_pct": 0.0,
                        "min_ticket_eur": 0,
                        "state": {},
                    },
                    "B": {
                        "price": 100.0,
                        "currency": "EUR",
                        "fx_rate": 1.0,
                        "lot_size": 1,
                        "current_qty": 5,
                        "avg_cost": 80.0,
                        "allow_buy": 1,
                        "allow_sell": 1,
                        "trade_blocked": False,
                        "lot_class": "standard",
                        "ticket_pct": 0.0,
                        "min_ticket_eur": 0,
                        "state": {},
                    },
                },
                contrarian_scores={"A": 0.5, "B": 0.7},
                signal_data={
                    "A": {
                        "sleeve": "core",
                        "user_multiplier": 0.8,
                        "opp_score": 0.5,
                    },
                    "B": {
                        "sleeve": "core",
                        "user_multiplier": 0.9,
                        "opp_score": 0.7,
                    },
                },
                min_trade_value=100.0,
                settings_ctx={
                    "strategy_min_opp_score": 0.55,
                    "max_position_pct": 25.0,
                    "strategy_opportunity_addon_threshold": 0.15,
                    "strategy_entry_t1_dd": -0.12,
                    "strategy_entry_t2_dd": -0.20,
                    "strategy_entry_t3_dd": -0.28,
                    "strategy_rotation_time_stop_days": 30,
                    "strategy_opportunity_cooloff_days": 15,
                    "strategy_core_cooloff_days": 21,
                    "strategy_same_side_cooloff_days": 10,
                    "strategy_core_floor_pct": 0.05,
                    "strategy_rotation_threshold": 0.8,
                },
                avg_monthly_deposit_6m=500.0,
            )

        assert rec is not None

    @pytest.mark.asyncio
    async def test_rotation_low_conviction(self):
        """Test rotation with low conviction."""
        engine = RebalanceEngine(db=MagicMock())
        engine._deposit_history = MagicMock()
        engine._deposit_history.get_rolling_6m_avg_deposit = AsyncMock(return_value=500.0)

        with patch.object(engine, "_build_recommendation", new_callable=AsyncMock, return_value=None):
            rec = await engine._build_recommendation(
                symbol="A",
                ideal={"A": 0.05, "B": 0.10},
                current={"A": 0.10, "B": 0.05},
                total_value=10000.0,
                security_data={
                    "A": {
                        "price": 100.0,
                        "currency": "EUR",
                        "fx_rate": 1.0,
                        "lot_size": 1,
                        "current_qty": 10,
                        "avg_cost": 80.0,
                        "allow_buy": 1,
                        "allow_sell": 1,
                        "trade_blocked": False,
                        "lot_class": "standard",
                        "ticket_pct": 0.0,
                        "min_ticket_eur": 0,
                        "state": {},
                    },
                    "B": {
                        "price": 100.0,
                        "currency": "EUR",
                        "fx_rate": 1.0,
                        "lot_size": 1,
                        "current_qty": 5,
                        "avg_cost": 80.0,
                        "allow_buy": 1,
                        "allow_sell": 1,
                        "trade_blocked": False,
                        "lot_class": "standard",
                        "ticket_pct": 0.0,
                        "min_ticket_eur": 0,
                        "state": {},
                    },
                },
                contrarian_scores={"A": 0.5, "B": 0.7},
                signal_data={
                    "A": {
                        "sleeve": "core",
                        "user_multiplier": 0.8,
                        "opp_score": 0.5,
                    },
                    "B": {
                        "sleeve": "core",
                        "user_multiplier": 0.6,  # Low conviction
                        "opp_score": 0.7,
                    },
                },
                min_trade_value=100.0,
                settings_ctx={
                    "strategy_min_opp_score": 0.55,
                    "max_position_pct": 25.0,
                    "strategy_opportunity_addon_threshold": 0.15,
                    "strategy_entry_t1_dd": -0.12,
                    "strategy_entry_t2_dd": -0.20,
                    "strategy_entry_t3_dd": -0.28,
                    "strategy_rotation_time_stop_days": 30,
                    "strategy_opportunity_cooloff_days": 15,
                    "strategy_core_cooloff_days": 21,
                    "strategy_same_side_cooloff_days": 10,
                    "strategy_core_floor_pct": 0.05,
                    "strategy_rotation_threshold": 0.8,
                },
                avg_monthly_deposit_6m=500.0,
            )

        assert rec is None


class TestFullDecisionLogic:
    """Tests for full decision logic integration."""

    @pytest.mark.asyncio
    async def test_extreme_contrarian_opportunity(self):
        """Test extreme contrarian opportunity (dip_score < -0.25 → trade regardless)."""
        engine = RebalanceEngine(db=MagicMock())
        engine._deposit_history = MagicMock()
        engine._deposit_history.get_rolling_6m_avg_deposit = AsyncMock(return_value=500.0)

        with patch.object(
            engine,
            "_build_recommendation",
            new_callable=AsyncMock,
            return_value=MagicMock(
                action="sell",
                profit_amount_eur=1000.0,
                profits_first=True,
            ),
        ):
            rec = await engine._build_recommendation(
                symbol="TEST",
                ideal={"TEST": 0.05},
                current={"TEST": 0.10},
                total_value=10000.0,
                security_data={
                    "TEST": {
                        "price": 100.0,
                        "currency": "EUR",
                        "fx_rate": 1.0,
                        "lot_size": 1,
                        "current_qty": 10,
                        "avg_cost": 80.0,
                        "allow_buy": 1,
                        "allow_sell": 1,
                        "trade_blocked": False,
                        "lot_class": "standard",
                        "ticket_pct": 0.0,
                        "min_ticket_eur": 0,
                        "state": {},
                    }
                },
                contrarian_scores={"TEST": -0.3},  # Extreme contrarian opportunity
                signal_data={
                    "TEST": {
                        "sleeve": "core",
                        "user_multiplier": 0.8,
                        "opp_score": -0.3,
                    }
                },
                min_trade_value=100.0,
                settings_ctx={
                    "strategy_min_opp_score": 0.55,
                    "max_position_pct": 25.0,
                    "strategy_opportunity_addon_threshold": 0.15,
                    "strategy_entry_t1_dd": -0.12,
                    "strategy_entry_t2_dd": -0.20,
                    "strategy_entry_t3_dd": -0.28,
                    "strategy_rotation_time_stop_days": 30,
                    "strategy_opportunity_cooloff_days": 15,
                    "strategy_core_cooloff_days": 21,
                    "strategy_same_side_cooloff_days": 10,
                    "strategy_core_floor_pct": 0.05,
                    "strategy_rotation_threshold": 0.8,
                },
                avg_monthly_deposit_6m=500.0,
            )

        assert rec is not None

    @pytest.mark.asyncio
    async def test_no_trade_fast_self_correction(self):
        """Test no trade when months_to_self_correct < 3."""
        engine = RebalanceEngine(db=MagicMock())
        engine._deposit_history = MagicMock()
        engine._deposit_history.get_rolling_6m_avg_deposit = AsyncMock(return_value=1000.0)

        with patch.object(engine, "_build_recommendation", new_callable=AsyncMock, return_value=None):
            rec = await engine._build_recommendation(
                symbol="TEST",
                ideal={"TEST": 0.05},
                current={"TEST": 0.10},
                total_value=10000.0,
                security_data={
                    "TEST": {
                        "price": 100.0,
                        "currency": "EUR",
                        "fx_rate": 1.0,
                        "lot_size": 1,
                        "current_qty": 10,
                        "avg_cost": 80.0,
                        "allow_buy": 1,
                        "allow_sell": 1,
                        "trade_blocked": False,
                        "lot_class": "standard",
                        "ticket_pct": 0.0,
                        "min_ticket_eur": 0,
                        "state": {},
                    }
                },
                contrarian_scores={"TEST": 0.5},
                signal_data={
                    "TEST": {
                        "sleeve": "core",
                        "user_multiplier": 0.8,
                        "opp_score": 0.5,
                    }
                },
                min_trade_value=100.0,
                settings_ctx={
                    "strategy_min_opp_score": 0.55,
                    "max_position_pct": 25.0,
                    "strategy_opportunity_addon_threshold": 0.15,
                    "strategy_entry_t1_dd": -0.12,
                    "strategy_entry_t2_dd": -0.20,
                    "strategy_entry_t3_dd": -0.28,
                    "strategy_rotation_time_stop_days": 30,
                    "strategy_opportunity_cooloff_days": 15,
                    "strategy_core_cooloff_days": 21,
                    "strategy_same_side_cooloff_days": 10,
                    "strategy_core_floor_pct": 0.05,
                    "strategy_rotation_threshold": 0.8,
                },
                avg_monthly_deposit_6m=1000.0,
            )

        assert rec is None


class TestTrancheLadderCooloff:
    """Tranche-raising opportunity buys bypass the same-side cool-off (Fix 4)."""

    def _engine(self):
        engine = RebalanceEngine(db=MagicMock())
        engine._deposit_history = MagicMock()
        engine._deposit_history.get_rolling_6m_avg_deposit = AsyncMock(return_value=500.0)
        engine._currency = MagicMock()
        engine._currency.get_rate = AsyncMock(return_value=1.0)
        engine._currency.to_eur = AsyncMock(side_effect=lambda amt, curr: amt)
        return engine

    def _settings(self):
        return {
            "strategy_min_opp_score": 0.55,
            "max_position_pct": 25.0,
            "strategy_opportunity_addon_threshold": 0.15,
            "strategy_entry_t1_dd": -0.12,
            "strategy_entry_t2_dd": -0.20,
            "strategy_entry_t3_dd": -0.28,
            "strategy_rotation_time_stop_days": 30,
            "strategy_opportunity_cooloff_days": 7,
            "strategy_core_cooloff_days": 21,
            "strategy_same_side_cooloff_days": 15,
            "strategy_core_floor_pct": 0.05,
            "strategy_rotation_threshold": 0.8,
            "strategy_core_new_min_score": 0.0,
            "strategy_coarse_max_new_lots_per_cycle": 1,
        }

    async def _build(self, engine, *, tranche_stage, dd252, opp_score=0.8):
        from datetime import datetime

        # Last trade: a same-side BUY only 3 days before the as-of date.
        three_days_ago = int(datetime(2026, 6, 7).timestamp())
        return await engine._build_recommendation(
            symbol="OPP",
            ideal={"OPP": 0.10},
            current={"OPP": 0.02},
            total_value=10000.0,
            security_data={
                "OPP": {
                    "price": 100.0,
                    "currency": "EUR",
                    "fx_rate": 1.0,
                    "lot_size": 1,
                    "current_qty": 5,
                    "avg_cost": 100.0,
                    "allow_buy": 1,
                    "allow_sell": 1,
                    "trade_blocked": False,
                    "lot_class": "standard",
                    "ticket_pct": 0.0,
                    "min_ticket_eur": 0,
                    "state": {"tranche_stage": tranche_stage},
                }
            },
            contrarian_scores={"OPP": opp_score},
            signal_data={
                "OPP": {
                    "sleeve": "opportunity",
                    "user_multiplier": 0.8,
                    "opp_score": opp_score,
                    "dd252": dd252,
                    "dd252_recent_min": dd252,
                    "cycle_turn": 0,
                }
            },
            min_trade_value=100.0,
            settings_ctx=self._settings(),
            latest_trade={"side": "BUY", "executed_at": three_days_ago},
            as_of_date="2026-06-10",
            avg_monthly_deposit_6m=500.0,
        )

    @pytest.mark.asyncio
    async def test_deeper_tranche_bypasses_same_side_cooloff(self):
        """T1 held, drawdown now at T2 → buy allowed despite recent same-side buy."""
        engine = self._engine()
        rec = await self._build(engine, tranche_stage=1, dd252=-0.22)
        assert rec is not None
        assert rec.action == "buy"

    @pytest.mark.asyncio
    async def test_same_tranche_still_blocked_by_same_side_cooloff(self):
        """Already at T2, no deeper stage → same-side cool-off still blocks the buy."""
        engine = self._engine()
        rec = await self._build(engine, tranche_stage=2, dd252=-0.22)
        assert rec is None
