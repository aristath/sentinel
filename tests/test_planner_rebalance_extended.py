"""Tests for rebalance.py — missing _build_recommendation paths, cool-off, and context helpers."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from sentinel.planner import RebalanceEngine


class TestCheckPriceAnomaly:
    """Tests for _check_price_anomaly and _check_price_anomaly_closes."""

    @pytest.mark.asyncio
    async def test_zero_price_no_anomaly(self):
        engine = RebalanceEngine(db=MagicMock())
        blocked, reason = engine._check_price_anomaly(0.0, [], "TEST")
        assert blocked is False
        assert reason == ""

    @pytest.mark.asyncio
    async def test_empty_history_no_anomaly(self):
        engine = RebalanceEngine(db=MagicMock())
        blocked, reason = engine._check_price_anomaly(100.0, [], "TEST")
        assert blocked is False
        assert reason == ""

    @pytest.mark.asyncio
    async def test_price_anomaly_closes_zero_price(self):
        engine = RebalanceEngine(db=MagicMock())
        blocked, reason = engine._check_price_anomaly_closes(0.0, [100.0, 101.0], "TEST")
        assert blocked is False

    @pytest.mark.asyncio
    async def test_price_anomaly_closes_empty_closes(self):
        engine = RebalanceEngine(db=MagicMock())
        blocked, reason = engine._check_price_anomaly_closes(100.0, [], "TEST")
        assert blocked is False


class TestCheckCooloffViolation:
    """Tests for _check_cooloff_violation — many paths missing."""

    @pytest.mark.asyncio
    async def test_zero_cooloff_days_allowed(self):
        engine = RebalanceEngine(db=MagicMock())
        is_blocked, _ = await engine._check_cooloff_violation("TEST", "buy", cooloff_days=0, same_side_cooloff_days=0)
        assert is_blocked is False

    @pytest.mark.asyncio
    async def test_no_trade_history_allowed(self):
        db = MagicMock()
        db.get_trades = AsyncMock(return_value=[])
        engine = RebalanceEngine(db=db)
        engine._db = db
        is_blocked, _ = await engine._check_cooloff_violation("TEST", "buy", cooloff_days=21, same_side_cooloff_days=15)
        assert is_blocked is False

    @pytest.mark.asyncio
    async def test_cooloff_not_yet_passed(self):
        db = MagicMock()
        recent = datetime.now(timezone.utc).timestamp() - 5 * 86400  # 5 days ago
        db.get_trades = AsyncMock(return_value=[{"side": "BUY", "executed_at": recent}])
        engine = RebalanceEngine(db=db)
        engine._db = db
        is_blocked, _ = await engine._check_cooloff_violation(
            "TEST", "sell", cooloff_days=21, same_side_cooloff_days=15
        )
        assert is_blocked is True

    @pytest.mark.asyncio
    async def test_cooloff_passed_allows_trade(self):
        db = MagicMock()
        old = datetime.now(timezone.utc).timestamp() - 30 * 86400  # 30 days ago
        db.get_trades = AsyncMock(return_value=[{"side": "BUY", "executed_at": old}])
        engine = RebalanceEngine(db=db)
        engine._db = db
        is_blocked, _ = await engine._check_cooloff_violation(
            "TEST", "sell", cooloff_days=21, same_side_cooloff_days=15
        )
        assert is_blocked is False

    @pytest.mark.asyncio
    async def test_same_side_cooloff_blocks_repeat_buy(self):
        db = MagicMock()
        recent = datetime.now(timezone.utc).timestamp() - 10 * 86400  # 10 days ago
        db.get_trades = AsyncMock(return_value=[{"side": "BUY", "executed_at": recent}])
        engine = RebalanceEngine(db=db)
        engine._db = db
        is_blocked, _ = await engine._check_cooloff_violation("TEST", "buy", cooloff_days=0, same_side_cooloff_days=15)
        assert is_blocked is True

    @pytest.mark.asyncio
    async def test_same_side_cooloff_passed_allows_repeat_buy(self):
        db = MagicMock()
        old = datetime.now(timezone.utc).timestamp() - 20 * 86400  # 20 days ago
        db.get_trades = AsyncMock(return_value=[{"side": "BUY", "executed_at": old}])
        engine = RebalanceEngine(db=db)
        engine._db = db
        is_blocked, _ = await engine._check_cooloff_violation("TEST", "buy", cooloff_days=0, same_side_cooloff_days=15)
        assert is_blocked is False

    @pytest.mark.asyncio
    async def test_same_side_cooloff_blocks_repeat_sell(self):
        db = MagicMock()
        recent = datetime.now(timezone.utc).timestamp() - 5 * 86400
        db.get_trades = AsyncMock(return_value=[{"side": "SELL", "executed_at": recent}])
        engine = RebalanceEngine(db=db)
        engine._db = db
        is_blocked, _ = await engine._check_cooloff_violation("TEST", "sell", cooloff_days=0, same_side_cooloff_days=15)
        assert is_blocked is True

    @pytest.mark.asyncio
    async def test_opposite_side_cooloff_after_buy(self):
        """Buying after a sell triggers opposite-side cool-off."""
        db = MagicMock()
        recent = datetime.now(timezone.utc).timestamp() - 10 * 86400
        db.get_trades = AsyncMock(return_value=[{"side": "SELL", "executed_at": recent}])
        engine = RebalanceEngine(db=db)
        engine._db = db
        is_blocked, _ = await engine._check_cooloff_violation("TEST", "buy", cooloff_days=21, same_side_cooloff_days=0)
        assert is_blocked is True

    @pytest.mark.asyncio
    async def test_latest_trade_param_used(self):
        """When latest_trade is provided, it's used instead of DB query."""
        engine = RebalanceEngine(db=MagicMock())
        recent = datetime.now(timezone.utc).timestamp() - 5 * 86400
        latest_trade = {"side": "BUY", "executed_at": recent}
        is_blocked, _ = await engine._check_cooloff_violation(
            "TEST",
            "sell",
            cooloff_days=21,
            same_side_cooloff_days=15,
            latest_trade=latest_trade,
        )
        assert is_blocked is True

    @pytest.mark.asyncio
    async def test_as_of_date_scoping(self):
        """as_of_date parameter scopes the 'current date' for cool-off checks."""
        engine = RebalanceEngine(db=MagicMock())
        # Trade was 5 days before as_of_date
        trade_date = datetime(2025, 1, 10)
        latest_trade = {"side": "BUY", "executed_at": int(trade_date.timestamp())}
        is_blocked, _ = await engine._check_cooloff_violation(
            "TEST",
            "sell",
            cooloff_days=21,
            same_side_cooloff_days=15,
            latest_trade=latest_trade,
            as_of_date="2025-01-15",
        )
        assert is_blocked is True  # only 5 days, needs 21

    @pytest.mark.asyncio
    async def test_as_of_date_after_cooloff(self):
        trade_date = datetime(2024, 12, 1)
        latest_trade = {"side": "BUY", "executed_at": int(trade_date.timestamp())}
        engine = RebalanceEngine(db=MagicMock())
        is_blocked, _ = await engine._check_cooloff_violation(
            "TEST",
            "sell",
            cooloff_days=21,
            same_side_cooloff_days=15,
            latest_trade=latest_trade,
            as_of_date="2025-01-15",
        )
        assert is_blocked is False  # 45 days, needs 21


class TestGetPositionsForContext:
    """Tests for _get_positions_for_context."""

    @pytest.mark.asyncio
    async def test_live_positions_no_as_of_date(self):
        db = MagicMock()
        db.get_all_positions = AsyncMock(
            return_value=[
                {"symbol": "A", "quantity": 10, "current_price": 100.0},
            ]
        )
        engine = RebalanceEngine(db=db)
        positions = await engine._get_positions_for_context(as_of_date=None, securities_map={})
        assert len(positions) == 1
        assert positions[0]["symbol"] == "A"

    @pytest.mark.asyncio
    async def test_snapshot_positions_with_as_of_date(self):
        db = MagicMock()
        db.get_portfolio_snapshot_as_of = AsyncMock(
            return_value={
                "data": {
                    "positions": {
                        "A": {"quantity": 10},
                        "B": {"quantity": 0},  # zero quantity skipped
                    },
                }
            }
        )
        db.get_all_positions = AsyncMock(return_value=[])
        engine = RebalanceEngine(db=db)
        positions = await engine._get_positions_for_context(
            as_of_date="2025-01-15",
            securities_map={"A": {"currency": "EUR"}, "B": {"currency": "EUR"}},
        )
        assert len(positions) == 1
        assert positions[0]["symbol"] == "A"
        assert positions[0]["quantity"] == 10.0

    @pytest.mark.asyncio
    async def test_empty_snapshot(self):
        db = MagicMock()
        db.get_portfolio_snapshot_as_of = AsyncMock(return_value=None)
        db.get_all_positions = AsyncMock(return_value=[{"symbol": "A", "quantity": 10}])
        engine = RebalanceEngine(db=db)
        positions = await engine._get_positions_for_context(
            as_of_date="2025-01-15",
            securities_map={"A": {"currency": "EUR"}},
        )
        # None snapshot (non-simulation) returns empty list
        assert positions == []

    @pytest.mark.asyncio
    async def test_snapshot_no_positions_key(self):
        db = MagicMock()
        db.get_portfolio_snapshot_as_of = AsyncMock(return_value={"data": {}})
        db.get_all_positions = AsyncMock(return_value=[{"symbol": "A", "quantity": 10}])
        engine = RebalanceEngine(db=db)
        positions = await engine._get_positions_for_context(
            as_of_date="2025-01-15",
            securities_map={},
        )
        assert positions == []

    @pytest.mark.asyncio
    async def test_simulation_database_uses_positions(self):
        db = MagicMock()
        db.__class__.__name__ = "SimulationDatabase"
        db.get_portfolio_snapshot_as_of = AsyncMock(return_value=None)
        db.get_all_positions = AsyncMock(return_value=[{"symbol": "A", "quantity": 5}])
        engine = RebalanceEngine(db=db)
        positions = await engine._get_positions_for_context(
            as_of_date="2025-01-15",
            securities_map={},
        )
        # Simulation DB falls back to get_all_positions
        assert len(positions) == 1


class TestGetCashBalancesForContext:
    """Tests for _get_cash_balances_for_context."""

    @pytest.mark.asyncio
    async def test_live_cash_no_as_of_date(self):
        portfolio = MagicMock()
        portfolio.get_cash_balances = AsyncMock(return_value={"EUR": 1000.0, "USD": 500.0})
        engine = RebalanceEngine(portfolio=portfolio)
        balances = await engine._get_cash_balances_for_context(as_of_date=None)
        assert balances == {"EUR": 1000.0, "USD": 500.0}

    @pytest.mark.asyncio
    async def test_snapshot_cash_with_as_of_date(self):
        db = MagicMock()
        db.get_portfolio_snapshot_as_of = AsyncMock(return_value={"data": {"cash_eur": 2500.0}})
        portfolio = MagicMock()
        portfolio.get_cash_balances = AsyncMock(return_value={"EUR": 100.0})
        engine = RebalanceEngine(db=db, portfolio=portfolio)
        balances = await engine._get_cash_balances_for_context(as_of_date="2025-01-15")
        assert balances == {"EUR": 2500.0}

    @pytest.mark.asyncio
    async def test_empty_snapshot_returns_zero_cash(self):
        db = MagicMock()
        db.get_portfolio_snapshot_as_of = AsyncMock(return_value=None)
        portfolio = MagicMock()
        portfolio.get_cash_balances = AsyncMock(return_value={"EUR": 100.0})
        engine = RebalanceEngine(db=db, portfolio=portfolio)
        balances = await engine._get_cash_balances_for_context(as_of_date="2025-01-15")
        # None snapshot (non-simulation) returns zero cash, not portfolio cash
        assert balances == {"EUR": 0.0}

    @pytest.mark.asyncio
    async def test_simulation_database_uses_portfolio(self):
        db = MagicMock()
        db.__class__.__name__ = "SimulationDatabase"
        db.get_portfolio_snapshot_as_of = AsyncMock(return_value=None)
        portfolio = MagicMock()
        portfolio.get_cash_balances = AsyncMock(return_value={"EUR": 500.0})
        engine = RebalanceEngine(db=db, portfolio=portfolio)
        balances = await engine._get_cash_balances_for_context(as_of_date="2025-01-15")
        assert balances == {"EUR": 500.0}


class TestBuildRecommendationPaths:
    """Tests for specific _build_recommendation code paths."""

    @pytest.fixture
    def _make_engine(self):
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
            engine._deposit_history = MagicMock()
            engine._deposit_history.get_rolling_6m_avg_deposit = AsyncMock(return_value=500.0)
            return engine

        return _create

    @pytest.fixture
    def _settings_ctx(self):
        """Default settings_ctx for _build_recommendation tests."""
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
        }

    @pytest.mark.asyncio
    async def test_no_security_data_returns_none(self, _make_engine, _settings_ctx):
        engine = _make_engine()
        rec = await engine._build_recommendation(
            symbol="NONEXISTENT",
            ideal={"NONEXISTENT": 0.1},
            current={"NONEXISTENT": 0.0},
            total_value=10000.0,
            security_data={},
            contrarian_scores={},
            signal_data={},
            min_trade_value=100.0,
            settings_ctx=_settings_ctx,
        )
        assert rec is None

    @pytest.mark.asyncio
    async def test_zero_price_returns_none(self, _make_engine, _settings_ctx):
        engine = _make_engine()
        rec = await engine._build_recommendation(
            symbol="ZERO",
            ideal={"ZERO": 0.1},
            current={"ZERO": 0.0},
            total_value=10000.0,
            security_data={
                "ZERO": {
                    "price": 0.0,
                    "currency": "EUR",
                    "fx_rate": 1.0,
                    "lot_size": 1,
                    "current_qty": 0,
                    "avg_cost": 0,
                    "allow_buy": 1,
                    "allow_sell": 1,
                    "trade_blocked": False,
                    "lot_class": "standard",
                    "ticket_pct": 0.0,
                    "min_ticket_eur": 0,
                    "state": {},
                }
            },
            contrarian_scores={},
            signal_data={"ZERO": {"sleeve": "core"}},
            min_trade_value=100.0,
            settings_ctx=_settings_ctx,
        )
        assert rec is None

    @pytest.mark.asyncio
    async def test_trade_blocked_returns_none(self, _make_engine, _settings_ctx):
        engine = _make_engine()
        rec = await engine._build_recommendation(
            symbol="BLOCKED",
            ideal={"BLOCKED": 0.1},
            current={"BLOCKED": 0.0},
            total_value=10000.0,
            security_data={
                "BLOCKED": {
                    "price": 100.0,
                    "currency": "EUR",
                    "fx_rate": 1.0,
                    "lot_size": 1,
                    "current_qty": 0,
                    "avg_cost": 0,
                    "allow_buy": 1,
                    "allow_sell": 1,
                    "trade_blocked": True,
                    "block_reason": "price anomaly",
                    "lot_class": "standard",
                    "ticket_pct": 0.0,
                    "min_ticket_eur": 0,
                    "state": {},
                }
            },
            contrarian_scores={},
            signal_data={"BLOCKED": {"sleeve": "core"}},
            min_trade_value=100.0,
            settings_ctx=_settings_ctx,
        )
        assert rec is None

    @pytest.mark.asyncio
    async def test_no_delta_returns_none(self, _make_engine, _settings_ctx):
        engine = _make_engine()
        rec = await engine._build_recommendation(
            symbol="ALIGNED",
            ideal={"ALIGNED": 0.1},
            current={"ALIGNED": 0.1},
            total_value=10000.0,
            security_data={
                "ALIGNED": {
                    "price": 100.0,
                    "currency": "EUR",
                    "fx_rate": 1.0,
                    "lot_size": 1,
                    "current_qty": 10,
                    "avg_cost": 90.0,
                    "allow_buy": 1,
                    "allow_sell": 1,
                    "trade_blocked": False,
                    "lot_class": "standard",
                    "ticket_pct": 0.0,
                    "min_ticket_eur": 0,
                    "state": {},
                }
            },
            contrarian_scores={},
            signal_data={"ALIGNED": {"sleeve": "core"}},
            min_trade_value=100.0,
            settings_ctx=_settings_ctx,
        )
        assert rec is None

    @pytest.mark.asyncio
    async def test_cannot_buy_returns_none(self, _make_engine, _settings_ctx):
        engine = _make_engine()
        rec = await engine._build_recommendation(
            symbol="NOBUY",
            ideal={"NOBUY": 0.1},
            current={"NOBUY": 0.0},
            total_value=10000.0,
            security_data={
                "NOBUY": {
                    "price": 100.0,
                    "currency": "EUR",
                    "fx_rate": 1.0,
                    "lot_size": 1,
                    "current_qty": 0,
                    "avg_cost": 0,
                    "allow_buy": 0,
                    "allow_sell": 1,
                    "trade_blocked": False,
                    "lot_class": "standard",
                    "ticket_pct": 0.0,
                    "min_ticket_eur": 0,
                    "state": {},
                }
            },
            contrarian_scores={},
            signal_data={"NOBUY": {"sleeve": "core"}},
            min_trade_value=100.0,
            settings_ctx=_settings_ctx,
        )
        assert rec is None

    @pytest.mark.asyncio
    async def test_cannot_sell_returns_none(self, _make_engine, _settings_ctx):
        engine = _make_engine()
        rec = await engine._build_recommendation(
            symbol="NOSELL",
            ideal={"NOSELL": 0.0},
            current={"NOSELL": 0.1},
            total_value=10000.0,
            security_data={
                "NOSELL": {
                    "price": 100.0,
                    "currency": "EUR",
                    "fx_rate": 1.0,
                    "lot_size": 1,
                    "current_qty": 10,
                    "avg_cost": 90.0,
                    "allow_buy": 1,
                    "allow_sell": 0,
                    "trade_blocked": False,
                    "lot_class": "standard",
                    "ticket_pct": 0.0,
                    "min_ticket_eur": 0,
                    "state": {},
                }
            },
            contrarian_scores={},
            signal_data={"NOSELL": {"sleeve": "core"}},
            min_trade_value=100.0,
            settings_ctx=_settings_ctx,
        )
        assert rec is None

    @pytest.mark.asyncio
    async def test_quantity_below_lot_size_returns_none(self, _make_engine, _settings_ctx):
        engine = _make_engine()
        rec = await engine._build_recommendation(
            symbol="SMALL",
            ideal={"SMALL": 0.001},
            current={"SMALL": 0.0},
            total_value=100.0,
            security_data={
                "SMALL": {
                    "price": 100.0,
                    "currency": "EUR",
                    "fx_rate": 1.0,
                    "lot_size": 1,
                    "current_qty": 0,
                    "avg_cost": 0,
                    "allow_buy": 1,
                    "allow_sell": 1,
                    "trade_blocked": False,
                    "lot_class": "standard",
                    "ticket_pct": 0.0,
                    "min_ticket_eur": 0,
                    "state": {},
                }
            },
            contrarian_scores={},
            signal_data={"SMALL": {"sleeve": "core", "clara_target_pct": 0.001}},
            min_trade_value=100.0,
            settings_ctx=_settings_ctx,
        )
        assert rec is None

    @pytest.mark.asyncio
    async def test_value_below_min_trade_returns_none(self, _make_engine, _settings_ctx):
        engine = _make_engine()
        rec = await engine._build_recommendation(
            symbol="TINY",
            ideal={"TINY": 0.001},
            current={"TINY": 0.0},
            total_value=100.0,
            security_data={
                "TINY": {
                    "price": 10.0,
                    "currency": "EUR",
                    "fx_rate": 1.0,
                    "lot_size": 1,
                    "current_qty": 0,
                    "avg_cost": 0,
                    "allow_buy": 1,
                    "allow_sell": 1,
                    "trade_blocked": False,
                    "lot_class": "standard",
                    "ticket_pct": 0.0,
                    "min_ticket_eur": 0,
                    "state": {},
                }
            },
            contrarian_scores={},
            signal_data={"TINY": {"sleeve": "core", "clara_target_pct": 0.001}},
            min_trade_value=500.0,
            settings_ctx=_settings_ctx,
        )
        assert rec is None

    @pytest.mark.asyncio
    async def test_buy_reason_code_rebalance_buy(self, _make_engine, _settings_ctx):
        engine = _make_engine()
        rec = await engine._build_recommendation(
            symbol="CORE_BUY",
            ideal={"CORE_BUY": 0.1},
            current={"CORE_BUY": 0.05},
            total_value=10000.0,
            security_data={
                "CORE_BUY": {
                    "price": 100.0,
                    "currency": "EUR",
                    "fx_rate": 1.0,
                    "lot_size": 1,
                    "current_qty": 5,
                    "avg_cost": 90.0,
                    "allow_buy": 1,
                    "allow_sell": 1,
                    "trade_blocked": False,
                    "lot_class": "standard",
                    "ticket_pct": 0.0,
                    "min_ticket_eur": 0,
                    "state": {},
                }
            },
            contrarian_scores={},
            signal_data={"CORE_BUY": {"sleeve": "core"}},
            min_trade_value=100.0,
            settings_ctx=_settings_ctx,
        )
        assert rec is not None
        assert rec.action == "buy"
        assert rec.reason_code == "rebalance_buy"

    @pytest.mark.asyncio
    async def test_sell_reason_code_rebalance_sell(self, _make_engine, _settings_ctx):
        engine = _make_engine()
        # A core overweight only sells when a higher-conviction rotation
        # candidate exists — provide one (BUYME) so the drift-sell proceeds.
        rec = await engine._build_recommendation(
            symbol="CORE_SELL",
            ideal={"CORE_SELL": 0.03, "BUYME": 0.10},
            current={"CORE_SELL": 0.20},
            total_value=10000.0,
            security_data={
                "CORE_SELL": {
                    "price": 100.0,
                    "currency": "EUR",
                    "fx_rate": 1.0,
                    "lot_size": 1,
                    "current_qty": 20,
                    "avg_cost": 90.0,
                    "allow_buy": 1,
                    "allow_sell": 1,
                    "trade_blocked": False,
                    "lot_class": "standard",
                    "ticket_pct": 0.0,
                    "min_ticket_eur": 0,
                    "state": {},
                }
            },
            contrarian_scores={},
            signal_data={
                "CORE_SELL": {"sleeve": "core", "opp_score": 0.0, "user_multiplier": 0.5},
                "BUYME": {"sleeve": "core", "opp_score": 0.6, "user_multiplier": 0.9},
            },
            min_trade_value=100.0,
            settings_ctx={
                **_settings_ctx,
                "strategy_rotation_threshold": 0.8,
            },
        )
        assert rec is not None
        assert rec.action == "sell"
        assert rec.reason_code == "rebalance_sell"
