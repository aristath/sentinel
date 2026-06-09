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
                "strategy_core_floor_pct": 0.05,
                "strategy_core_new_min_score": 0.0,
                "min_trade_value": 250.0,
                "strategy_core_target_pct": 80.0,
                "strategy_opportunity_target_pct": 20.0,
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
    async def test_core_floor_protection(self, _make_engine):
        """Test that core floor only blocks sells when position is ABOVE floor."""
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

        # Test core floor protection with position ABOVE floor (20% > 5%)
        # excess = 1700 EUR, deposits = 500/mo → months_to_self_correct = 3.4 > 3
        rec = await engine._build_recommendation(
            symbol="ASML.EU",
            ideal={"ASML.EU": 0.03},
            current={"ASML.EU": 0.20},
            total_value=10000.0,
            security_data=security_data,
            contrarian_scores={"ASML.EU": -0.30},
            signal_data={"ASML.EU": {"scaleout_stage": 0, "sleeve": "core", "opp_score": -0.30}},
            min_trade_value=100.0,
            settings_ctx={
                "strategy_core_floor_pct": 0.05,
                "strategy_core_cooloff_days": 21,
                "strategy_same_side_cooloff_days": 10,
                "strategy_opportunity_cooloff_days": 15,
                "strategy_core_new_min_score": 0.0,
                "max_position_pct": 25.0,
                "min_trade_value": 100.0,
                "strategy_min_opp_score": 0.55,
                "strategy_opportunity_addon_threshold": 0.15,
                "strategy_entry_t1_dd": -0.12,
                "strategy_entry_t2_dd": -0.20,
                "strategy_entry_t3_dd": -0.28,
                "strategy_rotation_time_stop_days": 30,
                "strategy_rotation_threshold": 0.8,
            },
            latest_trade=None,
            as_of_date=datetime.now(timezone.utc).isoformat(),
        )

        # Should recommend sell since position is above floor and excess takes > 3 months to self-correct
        assert rec is not None
        assert rec.action == "sell"
        # 20 shares at 100 EUR = 2000 EUR (20%), target 300 EUR (3%), excess 1700 EUR
        # max_sell = min(profit, excess) = min(400, 1700) = 400 EUR → 4 shares
        assert rec.quantity == 4

    @pytest.mark.asyncio
    async def test_deficit_sell_calculation(self, _make_engine):
        """Test that deficit sells only liquidate excess above target."""
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

        # Test with position that has excess above target
        # Total value: 10000 EUR, position: 2800 EUR (28%), target: 1000 EUR (10%)
        # excess = 1800 EUR, deposits = 500/mo → months_to_self_correct = 3.6 > 3
        rec = await engine._build_recommendation(
            symbol="TSM.US",
            ideal={"TSM.US": 0.10},
            current={"TSM.US": 0.28},
            total_value=10000.0,
            security_data=security_data,
            contrarian_scores={"TSM.US": -0.30},
            signal_data={"TSM.US": {"scaleout_stage": 0, "sleeve": "core", "opp_score": -0.30}},
            min_trade_value=100.0,
            settings_ctx={
                "strategy_core_floor_pct": 0.05,
                "strategy_core_cooloff_days": 21,
                "strategy_same_side_cooloff_days": 10,
                "strategy_opportunity_cooloff_days": 15,
                "strategy_core_new_min_score": 0.0,
                "max_position_pct": 25.0,
                "min_trade_value": 100.0,
                "strategy_min_opp_score": 0.55,
                "strategy_opportunity_addon_threshold": 0.15,
                "strategy_entry_t1_dd": -0.12,
                "strategy_entry_t2_dd": -0.20,
                "strategy_entry_t3_dd": -0.28,
                "strategy_rotation_time_stop_days": 30,
                "strategy_rotation_threshold": 0.8,
            },
            latest_trade=None,
            as_of_date=datetime.now(timezone.utc).isoformat(),
        )

        # Should recommend sell of only 4 shares (excess above target, capped by profit)
        # current_qty=20 at 100 USD, avg_cost 80 → profit = 20*20 = 400 EUR
        # excess = 1800 EUR, max_sell = min(400, 1800) = 400 EUR → 4 shares
        assert rec is not None
        assert rec.action == "sell"
        assert rec.quantity == 4  # Only sell profit-capped amount, not entire excess
