"""Tests for uncovered code paths in planner package."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from sentinel.planner import RebalanceEngine
from sentinel.planner.rebalance_cash import _load_latest_trades
from sentinel.planner.rebalance_rules import get_forced_opportunity_exit


@pytest.fixture
def _make_engine():
    """Factory to create an engine with proper settings_ctx."""

    def _create():
        db = MagicMock()
        engine = RebalanceEngine(db=db)
        engine._broker = MagicMock()
        engine._settings = MagicMock()
        engine._settings.get = AsyncMock(side_effect=lambda key, default=None: default)
        engine._portfolio = MagicMock()
        engine._currency = MagicMock()
        engine._currency.get_rate = AsyncMock(return_value=1.0)
        engine._currency.to_eur = AsyncMock(side_effect=lambda amt, curr: amt)
        return engine

    return _create


@pytest.fixture
def _settings_ctx():
    """Default settings_ctx for tests."""
    return {
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
    }


class TestRebalanceEngineCoverage:
    """Tests for uncovered RebalanceEngine paths."""

    @pytest.mark.asyncio
    async def test_check_price_anomaly(self, _make_engine):
        """Test price anomaly detection."""
        engine = _make_engine()

        # Normal price history
        hist_rows = [
            {"close": 100.0, "date": "2023-01-01"},
            {"close": 101.0, "date": "2023-01-02"},
            {"close": 102.0, "date": "2023-01-03"},
        ]

        # Test normal price
        is_anomaly, reason = engine._check_price_anomaly(price=103.0, hist_rows=hist_rows, symbol="AAPL.US")
        assert not is_anomaly
        assert reason == ""

    @pytest.mark.asyncio
    async def test_get_forced_opportunity_exit(self):
        """Test forced opportunity exit logic."""

        # Test T1 exit (10% gain)
        result = get_forced_opportunity_exit(
            signal={"entry_t1_dd": -0.12, "entry_t2_dd": -0.20, "lot_size": 1},
            state={"scaleout_stage": 0},  # Set scaleout_stage in state
            current_qty=10,
            price=110.0,  # 10% gain
            avg_cost=100.0,
            as_of_date="2023-01-01",
            time_stop_days=30,
        )
        assert result is not None
        assert result["reason_code"] == "scaleout_10"
        assert result["quantity"] == 3  # 30% of 10

        # Test T2 exit (18.1% gain with scaleout_stage=1)
        result = get_forced_opportunity_exit(
            signal={"entry_t1_dd": -0.12, "entry_t2_dd": -0.20, "lot_size": 1},
            state={"scaleout_stage": 1},  # Set scaleout_stage in state
            current_qty=10,
            price=118.1,  # 18.1% gain
            avg_cost=100.0,
            as_of_date="2023-01-01",
            time_stop_days=30,
        )
        assert result is not None
        assert result["reason_code"] == "scaleout_18"

        # Test no exit (5% gain)
        result = get_forced_opportunity_exit(
            signal={"entry_t1_dd": -0.12, "entry_t2_dd": -0.20, "lot_size": 1},
            state={"scaleout_stage": 0},  # Set scaleout_stage in state
            current_qty=10,
            price=105.0,  # 5% gain
            avg_cost=100.0,
            as_of_date="2023-01-01",
            time_stop_days=30,
        )
        assert result is None


class TestRebalanceCashCoverage:
    """Tests for uncovered rebalance_cash paths."""

    @pytest.mark.asyncio
    async def test_load_latest_trades(self, _make_engine):
        """Test _load_latest_trades helper."""
        engine = _make_engine()

        # Mock DB response
        mock_trades = {
            "ASML.EU": {
                "symbol": "ASML.EU",
                "executed_at": "2023-01-15T12:00:00Z",
                "action": "buy",
                "quantity": 1,
                "price": 1000.0,
            }
        }
        engine._db.get_latest_trades_for_symbols = AsyncMock(return_value=mock_trades)

        # Test loading trades
        trades = await _load_latest_trades(engine=engine, symbols=["ASML.EU", "TSM.US"])

        assert "ASML.EU" in trades
        assert trades["ASML.EU"]["action"] == "buy"
        assert "TSM.US" not in trades


class TestPreferencesCoverage:
    """Tests for uncovered preferences.py paths."""

    def test_normalize_weights_edge_cases(self):
        """Test normalize_weights error handling."""
        from sentinel.planner.preferences import normalize_weights

        # Test empty dict
        result = normalize_weights({})
        assert result == {}

        # Test all zero/negative values
        result = normalize_weights({"A": 0, "B": -1, "C": 0})
        assert result == {}

        # Test mixed valid/invalid
        result = normalize_weights({"A": 1, "B": "invalid", "C": 2})
        assert result == {"A": 1 / 3, "C": 2 / 3}

    def test_normalize_weights_all_invalid(self):
        """Test normalize_weights with all invalid values."""
        from sentinel.planner.preferences import normalize_weights

        result = normalize_weights({"A": "invalid", "B": None, "C": float("nan")})
        assert result == {}

    def test_decayed_user_multiplier_edge_cases(self):
        """Test decayed_user_multiplier error handling."""
        from sentinel.planner.preferences import decayed_user_multiplier

        # Test with neutral multiplier
        result = decayed_user_multiplier(0.5)
        assert result == 0.5

        # Test with extreme values
        result = decayed_user_multiplier(1.0)
        assert 0.5 < result < 1.0

        result = decayed_user_multiplier(0.0)
        assert 0.0 < result < 0.5
