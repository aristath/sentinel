"""Planner API routes for portfolio recommendations and rebalancing."""

import inspect
import json
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends
from typing_extensions import Annotated

from sentinel.api.dependencies import CommonDependencies, get_common_deps
from sentinel.markets import get_open_market_symbols
from sentinel.planner import Planner
from sentinel.planner.models import LongTermPlan
from sentinel.portfolio import Portfolio
from sentinel.utils.fees import FeeCalculator

router = APIRouter(prefix="/planner", tags=["planner"])


def _serialize_recommendation(r) -> dict:
    return {
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
        "reason_code": r.reason_code,
        "sleeve": r.sleeve,
        "user_multiplier": r.user_multiplier,
        "clara_target_pct": (r.clara_target_pct * 100) if r.clara_target_pct is not None else None,
        "baseline_target_pct": (r.baseline_target_pct * 100) if r.baseline_target_pct is not None else None,
        "opportunity_target_pct": (r.opportunity_target_pct * 100 if r.opportunity_target_pct is not None else None),
        "timing_eligible": r.timing_eligible,
        "target_gap_ratio": r.target_gap_ratio,
        "is_fallback": r.is_fallback,
        "execution_rank": r.execution_rank,
    }


def _serialize_plan(plan: LongTermPlan) -> dict:
    return {
        "as_of_date": plan.as_of_date,
        "horizon_end_date": plan.horizon_end_date,
        "horizon_months": plan.horizon_months,
        "current_total_value_eur": plan.current_total_value_eur,
        "avg_monthly_net_deposit_eur": plan.avg_monthly_net_deposit_eur,
        "expected_contributions_eur": plan.expected_contributions_eur,
        "terminal_portfolio_value_eur": plan.terminal_portfolio_value_eur,
        "current_cash_eur": plan.current_cash_eur,
        "target_cash_allocation_pct": plan.target_cash_allocation * 100,
        "target_cash_value_eur": plan.target_cash_value_eur,
        "cash_gap_eur": plan.cash_gap_eur,
        "targets": [
            {
                "symbol": target.symbol,
                "clara_score": target.clara_score,
                "opportunity_score": target.opportunity_score,
                "target_allocation_pct": target.target_allocation * 100,
                "current_value_eur": target.current_value_eur,
                "target_value_eur": target.target_value_eur,
                "gap_eur": target.gap_eur,
                "model_target_allocation_pct": (
                    target.model_target_allocation * 100
                    if target.model_target_allocation is not None
                    else target.target_allocation * 100
                ),
                "model_target_value_eur": (
                    target.model_target_value_eur
                    if target.model_target_value_eur is not None
                    else target.target_value_eur
                ),
                "sell_locked": target.sell_locked,
                "current_quantity": target.current_quantity,
                "target_quantity": target.target_quantity,
                "quantity_delta": target.quantity_delta,
                "price": target.price,
                "currency": target.currency,
                "lot_size": target.lot_size,
            }
            for target in plan.targets
        ],
    }


@router.get("/recommendations")
async def get_recommendations(
    deps: Annotated[CommonDependencies, Depends(get_common_deps)],
    min_value: Optional[float] = None,
) -> dict:
    """Get trade recommendations to move toward ideal portfolio."""
    portfolio = Portfolio(
        db=deps.db,
        broker=deps.broker,
        settings=deps.settings,
        currency=deps.currency,
    )
    planner = Planner(db=deps.db, broker=deps.broker, portfolio=portfolio)

    # Use provided min_value or fall back to setting
    if min_value is None:
        min_value = await deps.settings.get("min_trade_value", default=100.0)

    open_symbols = await get_open_market_symbols(deps.broker, deps.db)
    recommendations, long_term_plan = await planner.get_recommendations_with_plan(
        min_trade_value=min_value,
        eligible_symbols=open_symbols,
    )

    schedule = await deps.db.get_job_schedule("trading:execute")
    valid_for_minutes = None
    if isinstance(schedule, dict):
        valid_for_minutes = schedule.get("interval_market_open_minutes") or schedule.get("interval_minutes")

    # Calculate summary with transaction fees
    current_cash = long_term_plan.current_cash_eur
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
    return {
        "recommendations": [_serialize_recommendation(r) for r in recommendations],
        "plan": _serialize_plan(long_term_plan),
        "summary": {
            "current_cash": current_cash,
            "total_sell_value": total_sell_value,
            "total_buy_value": total_buy_value,
            "total_fees": total_fees,
            "cash_after_plan": cash_after_plan,
            "current_total_value_eur": long_term_plan.current_total_value_eur,
            "avg_monthly_net_deposit_6m": long_term_plan.avg_monthly_net_deposit_eur,
            "projection_months": long_term_plan.horizon_months,
            "projected_contribution_eur": long_term_plan.expected_contributions_eur,
            "projected_total_value_eur": long_term_plan.terminal_portfolio_value_eur,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "valid_for_minutes": valid_for_minutes,
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
