from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from sentinel.jobs.tasks import _update_strategy_state_after_execution
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
