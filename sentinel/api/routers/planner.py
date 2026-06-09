"""Planner API routes for portfolio recommendations and rebalancing."""

import inspect
import json
from typing import Optional

from fastapi import APIRouter, Depends
from typing_extensions import Annotated

from sentinel.api.dependencies import CommonDependencies, get_common_deps
from sentinel.planner import Planner
from sentinel.portfolio import Portfolio
from sentinel.utils.fees import FeeCalculator

router = APIRouter(prefix="/planner", tags=["planner"])


@router.get("/recommendations")
async def get_recommendations(
    deps: Annotated[CommonDependencies, Depends(get_common_deps)],
    min_value: Optional[float] = None,
) -> dict:
    """Get trade recommendations to move toward ideal portfolio."""
    planner = Planner()
    portfolio = Portfolio()

    # Use provided min_value or fall back to setting
    if min_value is None:
        min_value = await deps.settings.get("min_trade_value", default=100.0)

    recommendations = await planner.get_recommendations(
        min_trade_value=min_value,
    )

    # Calculate summary with transaction fees
    current_cash = await portfolio.total_cash_eur()
    fee_calc = FeeCalculator()
    trades = [{"action": r.action, "value_eur": abs(r.value_delta_eur)} for r in recommendations]
    fee_summary = await fee_calc.calculate_batch(trades)

    total_sell_value = fee_summary["total_sell_value"]
    total_buy_value = fee_summary["total_buy_value"]
    total_fees = fee_summary["total_fees"]
    sell_fees = fee_summary["sell_fees"]
    buy_fees = fee_summary["buy_fees"]

    # Cash after plan: start + sells - sell_fees - buys - buy_fees
    cash_after_plan = current_cash + total_sell_value - sell_fees - total_buy_value - buy_fees

    # Deferred trades: buys the planner wants but can't fund this cycle without a bad
    # sell — parked to wait for deposits to accumulate enough cash. Reconciled by
    # get_recommendations above, so the bucket is fresh here.
    pending_getter = getattr(deps.db, "get_pending_trades", None)
    deferred: list[dict] = []
    if callable(pending_getter):
        maybe_rows = pending_getter()
        if inspect.isawaitable(maybe_rows):
            deferred = [
                {
                    "symbol": row["symbol"],
                    "action": row["action"],
                    "target_amount_eur": row["target_amount_eur"],
                    "reason": row["reason"],
                    # "reserved" = the allocator is actively holding cash for this exact buy;
                    # otherwise it's a plain deferral. Carried in the reason prefix set by the planner.
                    "reserved": str(row["reason"] or "").startswith("reserved:"),
                    "created_at": row["created_at"],
                    "last_evaluated": row["last_evaluated"],
                }
                for row in await maybe_rows
            ]

    return {
        "recommendations": [
            {
                "symbol": r.symbol,
                "action": r.action,
                "current_allocation_pct": r.current_allocation * 100,
                "target_allocation_pct": r.target_allocation * 100,
                "allocation_delta_pct": r.allocation_delta * 100,
                "current_value_eur": r.current_value_eur,
                "target_value_eur": r.target_value_eur,
                "value_delta_eur": r.value_delta_eur,
                "quantity": r.quantity,
                "price": r.price,
                "currency": r.currency,
                "lot_size": r.lot_size,
                "contrarian_score": r.contrarian_score,
                "priority": r.priority,
                "reason": r.reason,
                "sleeve": r.sleeve,
                "user_multiplier": r.user_multiplier,
                "clara_target_pct": (r.clara_target_pct * 100) if r.clara_target_pct is not None else None,
                "baseline_target_pct": (r.baseline_target_pct * 100) if r.baseline_target_pct is not None else None,
                "opportunity_target_pct": (
                    r.opportunity_target_pct * 100 if r.opportunity_target_pct is not None else None
                ),
            }
            for r in recommendations
        ],
        "deferred": deferred,
        "summary": {
            "current_cash": current_cash,
            "total_sell_value": total_sell_value,
            "total_buy_value": total_buy_value,
            "total_fees": total_fees,
            "cash_after_plan": cash_after_plan,
        },
    }


@router.get("/ideal")
async def get_ideal_portfolio(
    deps: Annotated[CommonDependencies, Depends(get_common_deps)],
) -> dict:
    """Get the calculated ideal portfolio allocations."""
    planner = Planner()
    ideal = await planner.calculate_ideal_portfolio()
    current = await planner.get_current_allocations()
    decomposition = None
    cache_getter = getattr(deps.db, "cache_get", None)
    if callable(cache_getter):
        cached = cache_getter("planner:allocation_decomposition")
        if inspect.isawaitable(cached):
            cached = await cached
        if isinstance(cached, (str, bytes, bytearray)):
            decomposition = json.loads(cached)

    return {
        "ideal": {k: v * 100 for k, v in ideal.items()},
        "current": {k: v * 100 for k, v in current.items()},
        "allocation_decomposition": decomposition,
    }


@router.get("/summary")
async def get_rebalance_summary() -> dict:
    """Get summary of portfolio alignment with ideal allocations."""
    planner = Planner()
    return await planner.get_rebalance_summary()
