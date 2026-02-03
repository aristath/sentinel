"""System API routes for health, cache, backtest, and utility endpoints."""

import json
from dataclasses import asdict
from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from typing_extensions import Annotated

from sentinel.api.dependencies import CommonDependencies, get_common_deps
from sentinel.backtester import (
    BacktestConfig,
    Backtester,
    BacktestProgress,
    BacktestResult,
    get_active_backtest,
    set_active_backtest,
)
from sentinel.cache import Cache
from sentinel.currency import Currency
from sentinel.version import VERSION

router = APIRouter(tags=["system"])
cache_router = APIRouter(prefix="/cache", tags=["cache"])
backtest_router = APIRouter(prefix="/backtest", tags=["backtest"])
exchange_rates_router = APIRouter(prefix="/exchange-rates", tags=["exchange-rates"])
markets_router = APIRouter(prefix="/markets", tags=["markets"])
meta_router = APIRouter(prefix="/meta", tags=["meta"])
pulse_router = APIRouter(prefix="/pulse", tags=["pulse"])


@router.get("/health")
async def health(
    deps: Annotated[CommonDependencies, Depends(get_common_deps)],
) -> dict[str, Any]:
    """Health check endpoint."""
    broker = deps.broker
    trading_mode = await deps.settings.get("trading_mode", "research")
    return {
        "status": "healthy",
        "broker_connected": broker.connected,
        "trading_mode": trading_mode,
    }


@router.get("/version")
async def version() -> dict[str, str]:
    """Return the application version."""
    return {"version": VERSION}


# Cache router endpoints


@cache_router.get("/stats")
async def get_cache_stats() -> dict:
    """Get statistics for all caches."""
    return Cache.get_all_stats()


@cache_router.post("/clear")
async def clear_cache(name: str | None = None) -> dict:
    """
    Clear cache entries.

    Args:
        name: Specific cache name to clear (e.g., 'motion'), or None for all caches
    """
    if name:
        cache = Cache(name)
        cleared = cache.clear()
        return {"cleared": {name: cleared}}
    else:
        cleared = Cache.clear_all()
        return {"cleared": cleared}


# Backtest router endpoints


@backtest_router.get("/run")
async def run_backtest(
    start_date: str,
    end_date: str,
    initial_capital: float = 10000.0,
    monthly_deposit: float = 0.0,
    rebalance_frequency: str = "weekly",
    use_existing_universe: bool = True,
    pick_random: bool = True,
    random_count: int = 10,
    symbols: str = "",  # Comma-separated
) -> StreamingResponse:
    """
    Run a backtest simulation via Server-Sent Events (SSE).

    Returns events:
    - progress: {current_date, progress_pct, portfolio_value, status, phase, current_item, items_done, items_total}
    - result: Full backtest results when complete
    - error: Error message if something goes wrong
    """
    # Parse comma-separated symbols
    symbols_list = [s.strip() for s in symbols.split(",") if s.strip()] if symbols else []

    config = BacktestConfig(
        start_date=start_date,
        end_date=end_date,
        initial_capital=initial_capital,
        monthly_deposit=monthly_deposit,
        rebalance_frequency=rebalance_frequency,
        use_existing_universe=use_existing_universe,
        pick_random=pick_random,
        random_count=random_count,
        symbols=symbols_list,
    )

    backtester = Backtester(config)
    set_active_backtest(backtester)

    async def event_generator():
        try:
            async for update in backtester.run():
                if isinstance(update, BacktestProgress):
                    event_data = {
                        "current_date": update.current_date,
                        "progress_pct": update.progress_pct,
                        "portfolio_value": update.portfolio_value,
                        "status": update.status,
                        "message": update.message,
                        "phase": update.phase,
                        "current_item": update.current_item,
                        "items_done": update.items_done,
                        "items_total": update.items_total,
                    }
                    yield f"event: progress\ndata: {json.dumps(event_data)}\n\n"

                    if update.status in ("error", "cancelled"):
                        break

                elif isinstance(update, BacktestResult):
                    # Convert result to JSON-serializable format
                    result_data = {
                        "config": asdict(update.config),
                        "snapshots": [
                            {
                                "date": s.date,
                                "total_value": s.total_value,
                                "cash": s.cash,
                                "positions_value": s.positions_value,
                            }
                            for s in update.snapshots
                        ],
                        "trades": [
                            {
                                "date": t.date,
                                "symbol": t.symbol,
                                "action": t.action,
                                "quantity": t.quantity,
                                "price": t.price,
                                "value": t.value,
                            }
                            for t in update.trades
                        ],
                        "initial_value": update.initial_value,
                        "final_value": update.final_value,
                        "total_deposits": update.total_deposits,
                        "total_return": update.total_return,
                        "total_return_pct": update.total_return_pct,
                        "cagr": update.cagr,
                        "max_drawdown": update.max_drawdown,
                        "sharpe_ratio": update.sharpe_ratio,
                        "security_performance": [
                            {
                                "symbol": sp.symbol,
                                "name": sp.name,
                                "total_invested": sp.total_invested,
                                "total_sold": sp.total_sold,
                                "final_value": sp.final_value,
                                "total_return": sp.total_return,
                                "return_pct": sp.return_pct,
                                "num_buys": sp.num_buys,
                                "num_sells": sp.num_sells,
                            }
                            for sp in update.security_performance
                        ],
                    }
                    yield f"event: result\ndata: {json.dumps(result_data)}\n\n"

        except Exception as e:
            error_data = {"message": str(e)}
            yield f"event: error\ndata: {json.dumps(error_data)}\n\n"
        finally:
            set_active_backtest(None)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@backtest_router.post("/cancel")
async def cancel_backtest() -> dict:
    """Cancel a running backtest."""
    backtest = get_active_backtest()
    if backtest:
        backtest.cancel()
        return {"status": "ok", "message": "Backtest cancellation requested"}
    return {"status": "ok", "message": "No active backtest to cancel"}


# Exchange rates router endpoints


@exchange_rates_router.get("")
async def get_exchange_rates() -> dict:
    """Get all exchange rates to EUR."""
    currency = Currency()
    return await currency.get_rates()


@exchange_rates_router.post("/sync")
async def sync_exchange_rates() -> dict:
    """Sync exchange rates from Tradernet API."""
    currency = Currency()
    rates = await currency.sync_rates()
    return rates


@exchange_rates_router.put("/{curr}")
async def set_exchange_rate(curr: str, data: dict) -> dict:
    """Manually set exchange rate for a currency to EUR."""
    currency = Currency()
    await currency.set_rate(curr, data.get("rate", 1.0))
    return {"status": "ok"}


# Markets router endpoints


@markets_router.get("/status")
async def get_markets_status(
    deps: Annotated[CommonDependencies, Depends(get_common_deps)],
) -> dict:
    """Get market status for markets that have securities in our universe."""
    import json as _json

    broker = deps.broker

    # Get all active securities and extract their market IDs from metadata
    securities = await deps.db.get_all_securities(active_only=True)

    market_ids_needed = set()
    for sec in securities:
        data = sec.get("data")
        if data:
            try:
                sec_data = _json.loads(data) if isinstance(data, str) else data
                mkt_id = sec_data.get("mrkt", {}).get("mkt_id")
                if mkt_id is not None:
                    market_ids_needed.add(str(mkt_id))
            except (_json.JSONDecodeError, KeyError, TypeError, ValueError):
                pass

    # Get market status from broker
    market_data = await broker.get_market_status("*")
    if not market_data:
        return {"markets": [], "any_open": False}

    # Filter to only markets that have securities in our universe
    markets_list = market_data.get("m", [])
    filtered_markets = []
    seen = set()
    for m in markets_list:
        mkt_id = str(m.get("i", ""))
        market_name = m.get("n2", mkt_id)
        if mkt_id in market_ids_needed and market_name not in seen:
            seen.add(market_name)
            filtered_markets.append(
                {
                    "name": market_name,
                    "status": m.get("s", "UNKNOWN"),
                    "is_open": m.get("s") == "OPEN",
                }
            )

    any_open = any(m["is_open"] for m in filtered_markets)

    return {
        "markets": filtered_markets,
        "any_open": any_open,
    }


# Meta router endpoints


@meta_router.get("/categories")
async def get_categories(
    deps: Annotated[CommonDependencies, Depends(get_common_deps)],
) -> dict:
    """Get distinct categories from securities in the database."""
    return await deps.db.get_categories()


# Pulse router endpoints


@pulse_router.get("/labels")
async def get_pulse_labels(
    deps: Annotated[CommonDependencies, Depends(get_common_deps)],
) -> dict:
    """Return geographies and industries from active securities for Pulse classification."""
    return await deps.db.get_categories(active_only=True)
