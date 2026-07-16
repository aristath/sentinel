from dataclasses import asdict
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from sentinel.jobs.tasks import (
    SUBMITTED_TRADE_STATE_KEY,
    _reconcile_submitted_trade,
    _update_strategy_state_after_execution,
)
from sentinel.planner.models import TradeRecommendation


def _rec(**kwargs) -> TradeRecommendation:
    base: dict[str, Any] = dict(
        symbol="AAPL.US",
        action="buy",
        current_allocation=0.0,
        target_allocation=0.1,
        allocation_delta=0.1,
        current_value_eur=0.0,
        target_value_eur=1000.0,
        value_delta_eur=1000.0,
        quantity=1,
        price=100.0,
        currency="USD",
        lot_size=1,
        contrarian_score=0.7,
        priority=1.0,
        reason="test",
        reason_code="entry_t1",
        sleeve="opportunity",
    )
    base.update(kwargs)
    return TradeRecommendation(**base)


@pytest.mark.asyncio
async def test_strategy_state_updated_on_entry_buy():
    db = MagicMock()
    db.get_strategy_state = AsyncMock(return_value=None)
    db.upsert_strategy_state = AsyncMock()

    await _update_strategy_state_after_execution(db, _rec())

    assert db.upsert_strategy_state.await_count == 1
    args = db.upsert_strategy_state.await_args
    assert args.args[0] == "AAPL.US"
    assert args.kwargs["tranche_stage"] == 1
    assert args.kwargs["sleeve"] == "opportunity"


@pytest.mark.asyncio
async def test_fallback_buy_resets_persistent_wait_window():
    db = MagicMock()
    db.get_strategy_state = AsyncMock(return_value=None)
    db.upsert_strategy_state = AsyncMock()
    db.delete_planner_state = AsyncMock()
    db.set_planner_state = AsyncMock()

    await _update_strategy_state_after_execution(db, _rec(is_fallback=True))

    db.delete_planner_state.assert_awaited_once_with("fallback_wait_started_at")
    db.set_planner_state.assert_not_awaited()


@pytest.mark.asyncio
async def test_submitted_trade_updates_state_only_after_broker_fill():
    rec = _rec()
    db = MagicMock()
    db.get_planner_state = AsyncMock(
        return_value={
            "order_id": "123",
            "submitted_at": 1_700_000_000,
            "recommendation": asdict(rec),
        }
    )
    db.get_trades = AsyncMock(
        return_value=[
            {
                "symbol": rec.symbol,
                "side": "BUY",
                "quantity": 1.0,
                "price": 97.5,
                "executed_at": 1_700_000_100,
                "raw_data": {"order_id": 123},
            }
        ]
    )
    db.get_strategy_state = AsyncMock(return_value=None)
    db.upsert_strategy_state = AsyncMock()
    db.delete_planner_state = AsyncMock()

    assert await _reconcile_submitted_trade(db) is True

    assert db.upsert_strategy_state.await_args.kwargs["last_entry_price"] == 97.5
    assert db.upsert_strategy_state.await_args.kwargs["last_entry_ts"] == 1_700_000_100
    db.delete_planner_state.assert_any_await(SUBMITTED_TRADE_STATE_KEY)


@pytest.mark.asyncio
async def test_strategy_state_rotation_resets_tranche():
    db = MagicMock()
    db.get_strategy_state = AsyncMock(return_value={"tranche_stage": 3, "scaleout_stage": 2, "sleeve": "opportunity"})
    db.upsert_strategy_state = AsyncMock()

    rec = _rec(
        action="sell",
        allocation_delta=-0.1,
        value_delta_eur=-500.0,
        reason_code="exit_momentum",
    )
    await _update_strategy_state_after_execution(db, rec)

    args = db.upsert_strategy_state.await_args
    assert args.kwargs["tranche_stage"] == 0
    assert args.kwargs["scaleout_stage"] == 0
