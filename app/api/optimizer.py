"""
Optimizer API - Provides portfolio optimization status and results.
"""

from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException

from app.application.services.optimization.portfolio_optimizer import (
    OptimizationResult,
    PortfolioOptimizer,
)
from app.domain.services.settings_service import SettingsService
from app.infrastructure.external import yahoo_finance as yahoo
from app.infrastructure.external.tradernet_client import TradernetClient
from app.repositories import (
    DividendRepository,
    PositionRepository,
    SettingsRepository,
    StockRepository,
)

router = APIRouter()

# Cache for last optimization result (in-memory, refreshed on each run)
_last_optimization_result: Optional[Dict[str, Any]] = None
_last_optimization_time: Optional[datetime] = None


@router.get("")
async def get_optimizer_status() -> Dict[str, Any]:
    """
    Get current optimizer status and last run results.

    Returns optimization settings, last run timestamp, target weights,
    and top weight adjustments needed.
    """
    settings_repo = SettingsRepository()
    settings_service = SettingsService(settings_repo)
    settings = await settings_service.get_settings()

    # Calculate min trade amount from transaction costs
    from app.application.services.rebalancing_service import calculate_min_trade_amount

    min_trade_amount = calculate_min_trade_amount(
        settings.transaction_cost_fixed, settings.transaction_cost_percent
    )

    response = {
        "settings": {
            "optimizer_blend": settings.optimizer_blend,
            "optimizer_target_return": settings.optimizer_target_return,
            "min_cash_reserve": settings.min_cash_reserve,
            "min_trade_amount": round(min_trade_amount, 2),
        },
        "last_run": None,
        "status": "ready",
    }

    if _last_optimization_result:
        response["last_run"] = _last_optimization_result
        response["last_run_time"] = (
            _last_optimization_time.isoformat() if _last_optimization_time else None
        )

    return response


@router.post("/run")
async def run_optimization() -> Dict[str, Any]:
    """
    Run portfolio optimization and return results.

    This endpoint triggers a fresh optimization calculation.
    """
    global _last_optimization_result, _last_optimization_time

    settings_repo = SettingsRepository()
    settings_service = SettingsService(settings_repo)
    settings = await settings_service.get_settings()

    stock_repo = StockRepository()
    position_repo = PositionRepository()

    # Get current portfolio data
    stocks = await stock_repo.get_all()
    if not stocks:
        raise HTTPException(status_code=400, detail="No stocks in universe")

    positions_list = await position_repo.get_all()
    positions = {p.symbol: p for p in positions_list}

    # Get current prices
    yahoo_symbols = {s.symbol: s.yahoo_symbol for s in stocks if s.yahoo_symbol}
    current_prices = yahoo.get_batch_quotes(yahoo_symbols)

    # Calculate portfolio value
    portfolio_value = sum(
        p.quantity
        * current_prices.get(
            p.symbol, p.market_value_eur / p.quantity if p.quantity > 0 else 0
        )
        for p in positions_list
    )

    # Get cash balance
    try:
        client = TradernetClient.shared()
        cash_balance = client.get_total_cash_eur()
    except Exception:
        cash_balance = 0.0

    portfolio_value += cash_balance

    # Get allocation targets
    geo_targets = await settings_repo.get_json("geography_targets", {})
    ind_targets = await settings_repo.get_json("industry_targets", {})

    # Get pending dividend bonuses (DRIP fallback)
    dividend_repo = DividendRepository()
    dividend_bonuses = await dividend_repo.get_pending_bonuses()

    # Run optimization
    optimizer = PortfolioOptimizer()
    result = await optimizer.optimize(
        stocks=stocks,
        positions=positions,
        portfolio_value=portfolio_value,
        current_prices=current_prices,
        cash_balance=cash_balance,
        blend=settings.optimizer_blend,
        target_return=settings.optimizer_target_return,
        geo_targets=geo_targets,
        ind_targets=ind_targets,
        min_cash_reserve=settings.min_cash_reserve,
        dividend_bonuses=dividend_bonuses,
    )

    # Convert result to dict for caching and response
    result_dict = _optimization_result_to_dict(result, portfolio_value)

    _last_optimization_result = result_dict
    _last_optimization_time = datetime.now()

    return {
        "success": result.success,
        "result": result_dict,
        "timestamp": _last_optimization_time.isoformat(),
    }


def _optimization_result_to_dict(
    result: OptimizationResult, portfolio_value: float
) -> Dict[str, Any]:
    """Convert OptimizationResult to a JSON-serializable dict."""
    # Get top 5 weight changes
    top_changes = []
    for wc in result.weight_changes[:5]:
        change_eur = wc.change * portfolio_value
        top_changes.append(
            {
                "symbol": wc.symbol,
                "current_pct": round(wc.current_weight * 100, 1),
                "target_pct": round(wc.target_weight * 100, 1),
                "change_pct": round(wc.change * 100, 1),
                "change_eur": round(change_eur, 0),
                "direction": "buy" if wc.change > 0 else "sell",
            }
        )

    # Determine next action
    next_action = None
    if top_changes:
        top = top_changes[0]
        action = "Buy" if top["direction"] == "buy" else "Sell"
        next_action = f"{action} {top['symbol']} ~€{abs(top['change_eur']):,.0f}"

    return {
        "success": result.success,
        "error": result.error,
        "target_return_pct": round(result.target_return * 100, 1),
        "achieved_return_pct": (
            round(result.achieved_expected_return * 100, 1)
            if result.achieved_expected_return
            else None
        ),
        "blend_used": result.blend_used,
        "fallback_used": result.fallback_used,
        "total_stocks_optimized": len(result.target_weights),
        "top_adjustments": top_changes,
        "next_action": next_action,
        "high_correlations": result.high_correlations,
        "constraints": result.constraints_summary,
    }


def update_optimization_cache(result: OptimizationResult, portfolio_value: float):
    """Update the cached optimization result (called from jobs)."""
    global _last_optimization_result, _last_optimization_time
    _last_optimization_result = _optimization_result_to_dict(result, portfolio_value)
    _last_optimization_time = datetime.now()
