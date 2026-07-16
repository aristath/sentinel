"""Tests for the new patience-first rebalance philosophy."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from sentinel.planner import RebalanceEngine


@pytest.fixture
def _make_engine():
    """Factory to create an engine with proper settings_ctx."""

    def _create():
        db = MagicMock()
        engine = RebalanceEngine(db=db)
        engine._broker = MagicMock()
        engine._settings = MagicMock()
        engine._settings.get = AsyncMock(
            side_effect=lambda key, default=None: {
                "strategy_min_opp_score": 0.55,
                "max_position_pct": 25.0,
                "strategy_opportunity_addon_threshold": 0.15,
                "strategy_entry_t1_dd": -0.12,
                "strategy_entry_t2_dd": -0.20,
                "strategy_entry_t3_dd": -0.28,
                "strategy_rotation_time_stop_days": 30,
                "strategy_core_cooloff_days": 21,
                "strategy_opportunity_cooloff_days": 15,
                "strategy_same_side_cooloff_days": 10,
                "strategy_core_timing_min_score": 0.0,
                "min_trade_value": 250.0,
            }.get(key, default)
        )
        engine._portfolio = MagicMock()
        engine._currency = MagicMock()
        engine._currency.get_rate = AsyncMock(return_value=1.0)
        engine._currency.to_eur = AsyncMock(side_effect=lambda amt, curr: amt)
        engine._deposit_history = MagicMock()
        engine._deposit_history.get_rolling_6m_avg_deposit = AsyncMock(return_value=500.0)
        return engine

    return _create


class TestNewRebalancePhilosophy:
    """Tests for the new patience-first rebalance philosophy."""

    @pytest.mark.asyncio
    async def test_overweight_core_is_not_sold_without_a_selected_buy(self, _make_engine):
        """An overweight target holding is funding inventory, not a standalone order."""
        engine = _make_engine()

        # Mock all dependencies
        engine._get_price = MagicMock(return_value=100.0)
        engine._check_cooloff_violation = AsyncMock(return_value=(False, ""))
        engine._check_price_anomaly = MagicMock(return_value=(False, ""))
        engine._currency.get_rate = AsyncMock(return_value=1.0)
        engine._currency.to_eur = AsyncMock(side_effect=lambda amt, curr: amt)

        # Create security data dictionary
        security_data = {
            "ASML.EU": {
                "price": 100.0,
                "currency": "EUR",
                "lot_size": 1,
                "current_qty": 20,
                "avg_cost": 80.0,
                "allow_sell": 1,
                "state": {},
            }
        }

        rec = await engine._build_recommendation(
            symbol="ASML.EU",
            ideal={"ASML.EU": 0.03, "BUYME": 0.10},
            current={"ASML.EU": 0.20},
            total_value=10000.0,
            security_data=security_data,
            contrarian_scores={"ASML.EU": 0.0},
            signal_data={
                "ASML.EU": {"scaleout_stage": 0, "sleeve": "core", "opp_score": 0.0, "user_multiplier": 0.5},
                "BUYME": {"sleeve": "core", "opp_score": 0.6, "user_multiplier": 0.9},
            },
            min_trade_value=100.0,
            settings_ctx={
                "strategy_core_cooloff_days": 21,
                "strategy_same_side_cooloff_days": 10,
                "strategy_opportunity_cooloff_days": 15,
                "strategy_core_timing_min_score": 0.0,
                "max_position_pct": 25.0,
                "min_trade_value": 100.0,
                "strategy_min_opp_score": 0.55,
                "strategy_opportunity_addon_threshold": 0.15,
                "strategy_entry_t1_dd": -0.12,
                "strategy_entry_t2_dd": -0.20,
                "strategy_entry_t3_dd": -0.28,
                "strategy_rotation_time_stop_days": 30,
            },
            latest_trade=None,
            as_of_date=datetime.now(timezone.utc).isoformat(),
        )

        assert rec is None

    @pytest.mark.asyncio
    async def test_overweight_position_does_not_create_an_orphan_sell(self, _make_engine):
        """Funding sells are produced by cash planning only after a buy is selected."""
        engine = _make_engine()

        # Mock all dependencies
        engine._get_price = MagicMock(return_value=100.0)
        engine._check_cooloff_violation = AsyncMock(return_value=(False, ""))
        engine._check_price_anomaly = MagicMock(return_value=(False, ""))
        engine._currency.get_rate = AsyncMock(return_value=1.0)
        engine._currency.to_eur = AsyncMock(side_effect=lambda amt, curr: amt)

        # Create security data dictionary
        security_data = {
            "TSM.US": {
                "price": 100.0,
                "currency": "USD",
                "lot_size": 1,
                "current_qty": 20,
                "avg_cost": 80.0,
                "allow_sell": 1,
                "state": {},
            }
        }

        rec = await engine._build_recommendation(
            symbol="TSM.US",
            ideal={"TSM.US": 0.10, "BUYME": 0.10},
            current={"TSM.US": 0.28},
            total_value=10000.0,
            security_data=security_data,
            contrarian_scores={"TSM.US": 0.0},
            signal_data={
                "TSM.US": {"scaleout_stage": 0, "sleeve": "core", "opp_score": 0.0, "user_multiplier": 0.5},
                "BUYME": {"sleeve": "core", "opp_score": 0.6, "user_multiplier": 0.9},
            },
            min_trade_value=100.0,
            settings_ctx={
                "strategy_core_cooloff_days": 21,
                "strategy_same_side_cooloff_days": 10,
                "strategy_opportunity_cooloff_days": 15,
                "strategy_core_timing_min_score": 0.0,
                "max_position_pct": 25.0,
                "min_trade_value": 100.0,
                "strategy_min_opp_score": 0.55,
                "strategy_opportunity_addon_threshold": 0.15,
                "strategy_entry_t1_dd": -0.12,
                "strategy_entry_t2_dd": -0.20,
                "strategy_entry_t3_dd": -0.28,
                "strategy_rotation_time_stop_days": 30,
            },
            latest_trade=None,
            as_of_date=datetime.now(timezone.utc).isoformat(),
        )

        assert rec is None
