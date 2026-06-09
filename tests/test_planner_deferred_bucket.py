"""Tests for the deferred-trades bucket: DB CRUD, reconciliation, and planner wiring."""

import os
import tempfile
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio

from sentinel.database import Database
from sentinel.planner.models import TradeRecommendation
from sentinel.planner.rebalance import RebalanceEngine


def _buy(symbol, value_delta_eur):
    """Minimal buy recommendation for deferred-buy tests."""
    return TradeRecommendation(
        symbol=symbol,
        action="buy",
        current_allocation=0.0,
        target_allocation=0.1,
        allocation_delta=0.1,
        current_value_eur=0.0,
        target_value_eur=value_delta_eur,
        value_delta_eur=value_delta_eur,
        quantity=1,
        price=value_delta_eur,
        currency="EUR",
        lot_size=1,
        contrarian_score=0.5,
        priority=1.0,
        reason="buy",
    )


@pytest_asyncio.fixture
async def temp_db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    db = Database(path)
    await db.connect()
    yield db
    await db.close()
    db.remove_from_cache()
    for ext in ("", "-wal", "-shm"):
        target = path + ext
        if os.path.exists(target):
            os.remove(target)


# --------------------------------------------------------------------------- #
# DB CRUD (single canonical implementation in BaseDatabase)
# --------------------------------------------------------------------------- #


class TestPendingTradesCRUD:
    @pytest.mark.asyncio
    async def test_add_and_get(self, temp_db):
        await temp_db.add_pending_trade("AAPL:sell", "AAPL", "sell", 250.0, "patience")
        rows = await temp_db.get_pending_trades()
        assert len(rows) == 1
        row = rows[0]
        assert row["trade_key"] == "AAPL:sell"
        assert row["symbol"] == "AAPL"
        assert row["action"] == "sell"
        assert row["target_amount_eur"] == 250.0
        assert row["reason"] == "patience"
        assert row["created_at"] > 0
        assert row["last_evaluated"] == row["created_at"]

    @pytest.mark.asyncio
    async def test_remove(self, temp_db):
        await temp_db.add_pending_trade("AAPL:sell", "AAPL", "sell", 250.0, "patience")
        await temp_db.remove_pending_trade("AAPL:sell")
        assert await temp_db.get_pending_trades() == []

    @pytest.mark.asyncio
    async def test_update_refreshes_fields_and_preserves_created_at(self, temp_db):
        await temp_db.add_pending_trade("AAPL:buy", "AAPL", "buy", 250.0, "deferred: old")
        created_at = (await temp_db.get_pending_trades())[0]["created_at"]

        # Force an earlier timestamp so the bump is observable.
        await temp_db.conn.execute(
            "UPDATE pending_trades SET last_evaluated = ? WHERE trade_key = ?",
            (created_at - 100, "AAPL:buy"),
        )
        await temp_db.conn.commit()

        await temp_db.update_pending_trade("AAPL:buy", 999.0, "reserved: fresh")
        row = (await temp_db.get_pending_trades())[0]
        assert row["created_at"] == created_at  # unchanged — records how long it's waited
        assert row["last_evaluated"] >= created_at  # bumped forward
        assert row["target_amount_eur"] == 999.0  # refreshed
        assert row["reason"] == "reserved: fresh"  # refreshed


# --------------------------------------------------------------------------- #
# _build_deferred_buys: a wanted buy dropped by the cash constraint is deferred
# --------------------------------------------------------------------------- #


class TestBuildDeferredBuys:
    def test_dropped_buy_is_deferred(self):
        buys_before = {"AAPL": _buy("AAPL", 1500.0)}
        buys_after: set[str] = set()  # cash constraint dropped it
        deferred = RebalanceEngine._build_deferred_buys(buys_before, buys_after, avg_monthly_deposit_6m=500.0)
        assert len(deferred) == 1
        entry = deferred[0]
        assert entry["symbol"] == "AAPL"
        assert entry["action"] == "buy"
        assert entry["target_amount_eur"] == 1500.0
        # 1500 / 500 = ~3.0 months of deposits to fund it
        assert "3.0mo" in entry["reason"]

    def test_surviving_buy_is_not_deferred(self):
        buys_before = {"AAPL": _buy("AAPL", 1500.0)}
        buys_after = {"AAPL"}  # survived (possibly scaled) — executes this cycle
        deferred = RebalanceEngine._build_deferred_buys(buys_before, buys_after, avg_monthly_deposit_6m=500.0)
        assert deferred == []

    def test_reserved_target_labeled_reserved(self):
        # The allocator's actual reserve target is labeled "reserved".
        buys_before = {"AAPL": _buy("AAPL", 1000.0)}
        deferred = RebalanceEngine._build_deferred_buys(
            buys_before, set(), avg_monthly_deposit_6m=500.0, reserved_symbol="AAPL"
        )
        assert deferred[0]["reason"].startswith("reserved:")

    def test_non_target_labeled_deferred_even_when_cheap(self):
        # In eager mode (no reserve target), even a cheap, soon-fundable buy is plainly
        # "deferred" — the engine deployed cash, it isn't saving for this one.
        buys_before = {"AAPL": _buy("AAPL", 100.0)}  # 100/500 = 0.2mo, but not the reserved target
        deferred = RebalanceEngine._build_deferred_buys(
            buys_before, set(), avg_monthly_deposit_6m=500.0, reserved_symbol=None
        )
        assert deferred[0]["reason"].startswith("deferred:")

    def test_only_the_target_among_many_is_reserved(self):
        buys_before = {"AAPL": _buy("AAPL", 2000.0), "MSFT": _buy("MSFT", 300.0)}
        deferred = RebalanceEngine._build_deferred_buys(
            buys_before, set(), avg_monthly_deposit_6m=500.0, reserved_symbol="AAPL"
        )
        by_symbol = {d["symbol"]: d["reason"] for d in deferred}
        assert by_symbol["AAPL"].startswith("reserved:")
        assert by_symbol["MSFT"].startswith("deferred:")

    def test_mixed_only_dropped_are_deferred(self):
        buys_before = {"AAPL": _buy("AAPL", 1500.0), "MSFT": _buy("MSFT", 800.0)}
        buys_after = {"AAPL"}  # MSFT dropped, AAPL survived
        deferred = RebalanceEngine._build_deferred_buys(buys_before, buys_after, avg_monthly_deposit_6m=500.0)
        assert [d["symbol"] for d in deferred] == ["MSFT"]

    def test_no_deposit_history_omits_month_estimate(self):
        buys_before = {"AAPL": _buy("AAPL", 1500.0)}
        deferred = RebalanceEngine._build_deferred_buys(buys_before, set(), avg_monthly_deposit_6m=0.0)
        assert "mo of deposits" not in deferred[0]["reason"]
        assert "insufficient cash" in deferred[0]["reason"]


# --------------------------------------------------------------------------- #
# _reconcile_pending_trades
# --------------------------------------------------------------------------- #


def _engine_with_async_db(existing_rows):
    db = MagicMock()
    db.get_pending_trades = AsyncMock(return_value=existing_rows)
    db.add_pending_trade = AsyncMock()
    db.remove_pending_trade = AsyncMock()
    db.update_pending_trade = AsyncMock()
    return RebalanceEngine(db=db), db


class TestReconcilePendingTrades:
    @pytest.mark.asyncio
    async def test_adds_new_deferral(self):
        engine, db = _engine_with_async_db(existing_rows=[])
        await engine._reconcile_pending_trades(
            [{"symbol": "AAPL", "action": "buy", "target_amount_eur": 1500.0, "reason": "insufficient cash"}]
        )
        db.add_pending_trade.assert_awaited_once_with("AAPL:buy", "AAPL", "buy", 1500.0, "insufficient cash")
        db.update_pending_trade.assert_not_awaited()
        db.remove_pending_trade.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_refreshes_existing_deferral(self):
        engine, db = _engine_with_async_db(existing_rows=[{"trade_key": "AAPL:buy"}])
        await engine._reconcile_pending_trades(
            [{"symbol": "AAPL", "action": "buy", "target_amount_eur": 999.0, "reason": "still waiting"}]
        )
        # Already parked → refresh amount/reason + bump timestamp, don't re-insert.
        db.update_pending_trade.assert_awaited_once_with("AAPL:buy", 999.0, "still waiting")
        db.add_pending_trade.assert_not_awaited()
        db.remove_pending_trade.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_removes_resolved_deferral(self):
        # "MSFT:buy" was parked last cycle but isn't deferred now → it executed or is no longer wanted.
        engine, db = _engine_with_async_db(existing_rows=[{"trade_key": "MSFT:buy"}])
        await engine._reconcile_pending_trades([])
        db.remove_pending_trade.assert_awaited_once_with("MSFT:buy")
        db.add_pending_trade.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_skips_non_async_db(self):
        # A plain MagicMock returns a non-awaitable — reconcile must bail without touching the db.
        db = MagicMock()
        engine = RebalanceEngine(db=db)
        await engine._reconcile_pending_trades(
            [{"symbol": "AAPL", "action": "buy", "target_amount_eur": 1.0, "reason": "x"}]
        )
        db.add_pending_trade.assert_not_called()
        db.remove_pending_trade.assert_not_called()


# --------------------------------------------------------------------------- #
# Reserve-for-target: hold cash for a close, wanted buy instead of frittering on
# lesser buys — but still take a legitimately great trade.
# --------------------------------------------------------------------------- #


def _full_buy(symbol, value, price, score, priority):
    return TradeRecommendation(
        symbol=symbol,
        action="buy",
        current_allocation=0.0,
        target_allocation=0.1,
        allocation_delta=0.1,
        current_value_eur=0.0,
        target_value_eur=value,
        value_delta_eur=value,
        quantity=max(1, int(value / price)),
        price=price,
        currency="EUR",
        lot_size=1,
        contrarian_score=score,
        priority=priority,
        reason="buy",
    )


def _reserve_engine(cash, avg_deposit):
    engine = RebalanceEngine(db=MagicMock())
    engine._settings = MagicMock()
    settings = {
        "transaction_fee_fixed": 0.0,
        "transaction_fee_percent": 0.0,
        "strategy_reserve_margin_pct": 0.30,
        "strategy_reserve_max_months": 3,
        "strategy_reserve_great_opp_score": 0.75,
        "strategy_max_funding_sells_per_cycle": 2,
        "strategy_max_funding_turnover_pct": 0.12,
    }
    engine._settings.get = AsyncMock(side_effect=lambda key, default=None: settings.get(key, default))
    engine._portfolio = MagicMock()
    engine._portfolio.total_cash_eur = AsyncMock(return_value=cash)
    engine._portfolio.total_value = AsyncMock(return_value=10000.0)
    engine._currency = MagicMock()
    engine._currency.get_rate = AsyncMock(return_value=1.0)
    engine._currency.to_eur = AsyncMock(side_effect=lambda amt, curr: amt)
    engine._generate_deficit_sells = AsyncMock(return_value=[])
    engine._deposit_history = MagicMock()
    engine._deposit_history.get_rolling_6m_avg_deposit = AsyncMock(return_value=avg_deposit)
    return engine


# A = top-priority target (expensive, unaffordable, ordinary score)
# C = affordable lesser buy   D = weakest (gets conviction-trimmed away)
# Top-20% of a 3-name universe = the single highest-conviction name.
_C_TOP_CONVICTION = {"A": 0.40, "C": 0.90, "D": 0.20}  # C is the highest-conviction name
_C_LOW_CONVICTION = {"A": 0.90, "C": 0.50, "D": 0.20}  # A is highest; C is not top-20%


def _buys(c_score=0.5):
    return [
        _full_buy("A", 2000.0, 2000.0, 0.5, priority=5.0),
        _full_buy("C", 300.0, 300.0, c_score, priority=3.0),
        _full_buy("D", 300.0, 300.0, 0.5, priority=1.0),
    ]


class TestReserveForTarget:
    @pytest.mark.asyncio
    async def test_reserve_holds_cash_when_no_great_trade(self):
        # Target A is ~2 months away → reserve. C's score (0.5) misses the bar → buy nothing.
        engine = _reserve_engine(cash=400.0, avg_deposit=1100.0)
        result = await engine._apply_cash_constraint(
            _buys(c_score=0.5), min_trade_value=100.0, symbol_convictions=_C_TOP_CONVICTION
        )
        assert [r for r in result if r.action == "buy"] == []
        assert engine._reserved_target_symbol == "A"  # reserving for the top-priority target

    @pytest.mark.asyncio
    async def test_reserve_takes_great_score_and_top_conviction(self):
        # C is a deep dip (0.85 ≥ 0.75) AND the top-conviction name → take it, still reserve for A.
        engine = _reserve_engine(cash=400.0, avg_deposit=1100.0)
        result = await engine._apply_cash_constraint(
            _buys(c_score=0.85), min_trade_value=100.0, symbol_convictions=_C_TOP_CONVICTION
        )
        bought = {r.symbol for r in result if r.action == "buy"}
        assert bought == {"C"}
        assert engine._reserved_target_symbol == "A"

    @pytest.mark.asyncio
    async def test_reserve_skips_great_score_but_low_conviction(self):
        # C is a deep dip (0.85) but NOT a top-20% conviction name → not "great" → hold cash.
        engine = _reserve_engine(cash=400.0, avg_deposit=1100.0)
        result = await engine._apply_cash_constraint(
            _buys(c_score=0.85), min_trade_value=100.0, symbol_convictions=_C_LOW_CONVICTION
        )
        assert [r for r in result if r.action == "buy"] == []
        assert engine._reserved_target_symbol == "A"

    @pytest.mark.asyncio
    async def test_far_target_falls_back_to_eager(self):
        # Tiny deposits → A is >3 months away → don't reserve; deploy eagerly into affordable C.
        engine = _reserve_engine(cash=400.0, avg_deposit=100.0)
        result = await engine._apply_cash_constraint(
            _buys(c_score=0.5), min_trade_value=100.0, symbol_convictions=_C_LOW_CONVICTION
        )
        bought = {r.symbol for r in result if r.action == "buy"}
        assert bought == {"C"}
        assert engine._reserved_target_symbol is None  # eager mode — nothing reserved
