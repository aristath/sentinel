"""
Sentinel Web API - FastAPI entry point.

Usage:
    uvicorn sentinel.app:app --host 0.0.0.0 --port 8000
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles

# API routers
# API routers
from sentinel.api.routers import (
    allocation_router,
    led_router,
    portfolio_router,
    prices_router,
    scores_router,
    securities_router,
    settings_router,
    targets_router,
    unified_router,
)
from sentinel.api.routers.settings import set_led_controller
from sentinel.backtester import (
    BacktestConfig,
    Backtester,
    BacktestProgress,
    BacktestResult,
    get_active_backtest,
    set_active_backtest,
)
from sentinel.broker import Broker
from sentinel.cache import Cache
from sentinel.currency import Currency
from sentinel.database import Database
from sentinel.jobs import get_status, reschedule, run_now
from sentinel.jobs import init as init_jobs
from sentinel.jobs import stop as stop_jobs
from sentinel.jobs.market import BrokerMarketChecker
from sentinel.portfolio import Portfolio
from sentinel.security import Security
from sentinel.settings import Settings
from sentinel.utils.fees import FeeCalculator
from sentinel.version import VERSION

logger = logging.getLogger(__name__)

# Global instances
_scheduler = None  # APScheduler instance
_led_controller = None
_led_task: asyncio.Task | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize services on startup, cleanup on shutdown."""
    global _scheduler, _led_controller, _led_task

    # Startup
    db = Database()
    await db.connect()

    settings = Settings()
    await settings.init_defaults()

    broker = Broker()
    await broker.connect()

    # Sync exchange rates on startup
    currency = Currency()
    await currency.sync_rates()
    logger.info("Exchange rates synced")

    # Check if we need to sync historical prices
    await _sync_missing_prices(db, broker)

    # Initialize job system components
    from sentinel.analyzer import Analyzer
    from sentinel.ml_monitor import MLMonitor
    from sentinel.ml_retrainer import MLRetrainer
    from sentinel.planner import Planner
    from sentinel.regime_hmm import RegimeDetector

    portfolio = Portfolio()
    analyzer = Analyzer()
    detector = RegimeDetector()
    planner = Planner()
    retrainer = MLRetrainer()
    monitor = MLMonitor()
    cache = Cache("motion")

    # Seed default job schedules before starting scheduler
    await db.seed_default_job_schedules()

    # Initialize market checker
    market_checker = BrokerMarketChecker(broker)
    await market_checker.refresh()

    # Initialize APScheduler-based job system
    _scheduler = await init_jobs(
        db,
        broker,
        portfolio,
        analyzer,
        detector,
        planner,
        retrainer,
        monitor,
        cache,
        market_checker,
    )
    logger.info("Job scheduler started")

    # Start LED controller (checks setting internally, no-op if disabled)
    from sentinel.led import LEDController

    _led_controller = LEDController()
    set_led_controller(_led_controller)
    _led_task = asyncio.create_task(_led_controller.start())

    yield

    # Shutdown
    await stop_jobs()
    logger.info("Job scheduler stopped")

    if _led_controller:
        _led_controller.stop()
    if _led_task:
        _led_task.cancel()
        try:
            await _led_task
        except asyncio.CancelledError:
            pass

    await db.close()


async def _sync_missing_prices(db: Database, broker: Broker):
    """Sync historical prices for securities that don't have price data."""
    # Get all positions (these are the securities we care about)
    positions = await db.get_all_positions()
    if not positions:
        logger.info("No positions to sync prices for")
        return

    symbols = [p["symbol"] for p in positions]

    # Check which symbols are missing price data
    missing = []
    for symbol in symbols:
        cursor = await db.conn.execute("SELECT COUNT(*) as cnt FROM prices WHERE symbol = ?", (symbol,))
        row = await cursor.fetchone()
        if row is None or row["cnt"] < 100:  # Less than 100 days of data
            missing.append(symbol)

    if not missing:
        logger.info(f"All {len(symbols)} securities have price data")
        return

    logger.info(f"Syncing historical prices for {len(missing)} securities: {missing}")

    # Fetch in bulk
    prices_data = await broker.get_historical_prices_bulk(missing, years=10)

    # Save to database
    for symbol, prices in prices_data.items():
        if prices:
            await db.save_prices(symbol, prices)
            logger.info(f"Saved {len(prices)} prices for {symbol}")

    logger.info("Historical price sync complete")


app = FastAPI(
    title="Sentinel",
    description="Long-term portfolio management system",
    version=VERSION,
    lifespan=lifespan,
)

# CORS for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routers
app.include_router(settings_router, prefix="/api")
app.include_router(led_router, prefix="/api")
app.include_router(portfolio_router, prefix="/api")
app.include_router(targets_router, prefix="/api")
app.include_router(allocation_router, prefix="/api")
app.include_router(securities_router, prefix="/api")
app.include_router(prices_router, prefix="/api")
app.include_router(scores_router, prefix="/api")
app.include_router(unified_router, prefix="/api")

# -----------------------------------------------------------------------------
# The following routes have been moved to sentinel/api/routers/:
# - Settings API -> settings_router
# - LED Display API -> led_router
# -----------------------------------------------------------------------------

# -----------------------------------------------------------------------------
# Settings API (MOVED to sentinel/api/routers/settings.py)
# -----------------------------------------------------------------------------
# NOTE: The following handlers are now in settings_router:
# - GET /api/settings
# - PUT /api/settings/{key}
# NOTE: The following handlers are now in led_router:
# - GET /api/led/status
# - PUT /api/led/enabled
# - POST /api/led/refresh


# -----------------------------------------------------------------------------
# Settings API
# -----------------------------------------------------------------------------


# MOVED to sentinel/api/routers/settings.py
# @app.get("/api/settings")
# async def get_settings():
#     """Get all settings."""
#     settings = Settings()
#     return await settings.all()


# MOVED to sentinel/api/routers/settings.py
# @app.put("/api/settings/{key}")
# async def set_setting(key: str, value: dict):
#     """Set a setting value."""
#     settings = Settings()
#     await settings.set(key, value.get("value"))
#     return {"status": "ok"}


# -----------------------------------------------------------------------------
# LED Display API (MOVED to sentinel/api/routers/settings.py)
# -----------------------------------------------------------------------------


# MOVED to sentinel/api/routers/settings.py
# @app.get("/api/led/status")
# async def get_led_status():
#     """Get LED display status and settings."""
#     settings = Settings()
#     enabled = await settings.get("led_display_enabled", False)
#     return {
#         "enabled": enabled,
#         "running": _led_controller.is_running if _led_controller else False,
#         "trade_count": _led_controller.trade_count if _led_controller else 0,
#     }


# MOVED to sentinel/api/routers/settings.py
# @app.put("/api/led/enabled")
# async def set_led_enabled(data: dict):
#     """Enable or disable LED display."""
#     settings = Settings()
#     enabled = data.get("enabled", False)
#     await settings.set("led_display_enabled", enabled)
#     return {"enabled": enabled}


# MOVED to sentinel/api/routers/settings.py
# @app.post("/api/led/refresh")
# async def refresh_led_display():
#     """Force an immediate LED display refresh."""
#     if not _led_controller or not _led_controller.is_running:
#         return {"status": "not_running"}
#     await _led_controller.force_refresh()
#     return {"status": "refreshed", "trade_count": _led_controller.trade_count}


# -----------------------------------------------------------------------------
# Exchange Rates API
# -----------------------------------------------------------------------------


@app.get("/api/exchange-rates")
async def get_exchange_rates():
    """Get all exchange rates to EUR."""
    currency = Currency()
    return await currency.get_rates()


@app.post("/api/exchange-rates/sync")
async def sync_exchange_rates():
    """Sync exchange rates from Tradernet API."""
    currency = Currency()
    rates = await currency.sync_rates()
    return rates


@app.put("/api/exchange-rates/{curr}")
async def set_exchange_rate(curr: str, data: dict):
    """Manually set exchange rate for a currency to EUR."""
    currency = Currency()
    await currency.set_rate(curr, data.get("rate", 1.0))
    return {"status": "ok"}


# -----------------------------------------------------------------------------
# Markets API
# -----------------------------------------------------------------------------


@app.get("/api/markets/status")
async def get_markets_status():
    """Get market status for markets that have securities in our universe."""
    import json as _json

    db = Database()
    broker = Broker()

    # Get all active securities and extract their market IDs from metadata
    securities = await db.get_all_securities(active_only=True)

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


# -----------------------------------------------------------------------------
# Meta API
# -----------------------------------------------------------------------------


@app.get("/api/meta/categories")
async def get_categories():
    """Get distinct categories from securities in the database."""
    db = Database()
    return await db.get_categories()

    # -----------------------------------------------------------------------------
    # Portfolio API
    # -----------------------------------------------------------------------------

    # MOVED to sentinel/api/routers/portfolio.py
    # @app.get("/api/portfolio")
    # async def get_portfolio():
    """Get current portfolio state."""
    currency = Currency()

    portfolio = Portfolio()
    positions = await portfolio.positions()
    total = await portfolio.total_value()
    allocations = await portfolio.get_allocations()

    # Get security names and add EUR-converted values to each position
    db = Database()

    # Batch-fetch all securities for name lookups
    all_securities = await db.get_all_securities(active_only=False)
    securities_map = {s["symbol"]: s for s in all_securities}

    from sentinel.utils.positions import PositionCalculator

    pos_calc = PositionCalculator(currency_converter=currency)

    for pos in positions:
        symbol = pos["symbol"]
        price = pos.get("current_price", 0)
        qty = pos.get("quantity", 0)
        avg_cost = pos.get("avg_cost", 0)
        pos_currency = pos.get("currency", "EUR")

        pos["value_local"] = await pos_calc.calculate_value_local(qty, price)
        pos["value_eur"] = await pos_calc.calculate_value_eur(qty, price, pos_currency)

        profit_pct, _ = pos_calc.calculate_profit(qty, price, avg_cost)
        pos["profit_pct"] = profit_pct

        # Get security name
        sec = securities_map.get(symbol)
        if sec:
            pos["name"] = sec.get("name", symbol)

    # Get cash balances from portfolio (stored in DB)
    cash = await portfolio.get_cash_balances()

    # Calculate total cash in EUR
    total_cash_eur = await portfolio.total_cash_eur()

    # Calculate total value including cash
    total_eur = total + total_cash_eur

    return {
        "positions": positions,
        "total_value": total,
        "total_value_eur": total_eur,
        "cash": cash,
        "total_cash_eur": total_cash_eur,
        "allocations": allocations,
    }

    # MOVED to sentinel/api/routers/portfolio.py
    # @app.post("/api/portfolio/sync")
    # async def sync_portfolio():
    """Sync portfolio from broker."""
    portfolio = Portfolio()
    await portfolio.sync()
    return {"status": "ok"}

    # MOVED to sentinel/api/routers/portfolio.py
    # @app.get("/api/portfolio/allocations")
    # async def get_allocations():
    """Get current vs target allocations."""
    portfolio = Portfolio()
    current = await portfolio.get_allocations()
    targets = await portfolio.get_target_allocations()
    deviations = await portfolio.deviation_from_targets()

    return {
        "current": current,
        "targets": targets,
        "deviations": deviations,
    }

    # MOVED to sentinel/api/routers/portfolio.py
    # @app.get("/api/portfolio/pnl-history")
    # async def get_portfolio_pnl_history(period: str = "1Y"): ...

    # MOVED to sentinel/api/routers/portfolio.py
    # async def _backfill_portfolio_snapshots(db: Database, currency) -> None: ...

    # -----------------------------------------------------------------------------
    # Securities API
    # -----------------------------------------------------------------------------

    # MOVED to sentinel/api/routers/securities.py
    # @app.get("/api/securities")
    # async def get_securities():
    """Get all securities in universe."""
    db = Database()
    return await db.get_all_securities(active_only=False)

    # MOVED to sentinel/api/routers/securities.py
    # @app.post("/api/securities")
    # async def add_security(data: dict): ...

    # MOVED to sentinel/api/routers/securities.py
    # @app.delete("/api/securities/{symbol}")
    # async def delete_security(symbol: str, sell_position: bool = True): ...

    # MOVED to sentinel/api/routers/securities.py
    # @app.get("/api/securities/aliases")
    # async def get_all_aliases():
    """Get aliases for all securities (for companion news/sentiment app)."""
    db = Database()
    securities = await db.get_all_securities(active_only=True)
    return [
        {
            "symbol": sec["symbol"],
            "name": sec.get("name"),
            "aliases": sec.get("aliases"),
        }
        for sec in securities
    ]

    # MOVED to sentinel/api/routers/securities.py
    # @app.get("/api/securities/{symbol}")
    # async def get_security(symbol: str):
    """Get a specific security."""
    security = Security(symbol)
    if not await security.exists():
        raise HTTPException(status_code=404, detail="Security not found")
    await security.load()
    return {
        "symbol": security.symbol,
        "name": security.name,
        "currency": security.currency,
        "geography": security.geography,
        "industry": security.industry,
        "aliases": security.aliases,
        "quantity": security.quantity,
        "current_price": security.current_price,
        "score": await security.get_score(),
    }

    # MOVED to sentinel/api/routers/securities.py
    # @app.put("/api/securities/{symbol}")
    # async def update_security(symbol: str, data: dict): ...

    # MOVED to sentinel/api/routers/securities.py
    # @app.get("/api/unified")
    # async def get_unified_view(period: str = "1Y"): ...

    # MOVED to sentinel/api/routers/securities.py
    # @app.get("/api/securities/{symbol}/prices")
    # async def get_prices(symbol: str, days: int = 365): ...

    # MOVED to sentinel/api/routers/securities.py
    # @app.post("/api/securities/{symbol}/sync-prices")
    # async def sync_prices(symbol: str, days: int = 365): ...

    # MOVED to sentinel/api/routers/securities.py
    # @app.post("/api/prices/sync-all")
    # async def sync_all_prices():
    """Sync historical prices for all securities with positions."""
    db = Database()
    broker = Broker()
    await _sync_missing_prices(db, broker)
    return {"status": "ok"}

    # MOVED to sentinel/api/routers/securities.py
    # @app.post("/api/scores/calculate")
    # async def calculate_scores():
    """Calculate scores for all securities."""
    from sentinel.analyzer import Analyzer

    analyzer = Analyzer()
    count = await analyzer.update_scores()
    return {"calculated": count}


# -----------------------------------------------------------------------------
# Trading API
# -----------------------------------------------------------------------------


@app.get("/api/trades")
async def get_trades(
    symbol: Optional[str] = None,
    side: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
):
    """
    Get trade history with optional filters.

    Query params:
        symbol: Filter by security symbol
        side: Filter by 'BUY' or 'SELL'
        start_date: Filter trades on or after (YYYY-MM-DD)
        end_date: Filter trades on or before (YYYY-MM-DD)
        limit: Max trades to return (default 100)
        offset: Number to skip for pagination

    Returns:
        trades: List of trade objects
        count: Number of trades in this response
        total: Total number of trades matching filters (for pagination)
    """
    db = Database()
    trades = await db.get_trades(
        symbol=symbol,
        side=side,
        start_date=start_date,
        end_date=end_date,
        limit=limit,
        offset=offset,
    )

    # Get total count for pagination (without limit/offset)
    total = await db.get_trades_count(
        symbol=symbol,
        side=side,
        start_date=start_date,
        end_date=end_date,
    )

    return {"trades": trades, "count": len(trades), "total": total}


@app.post("/api/trades/sync")
async def sync_trades_endpoint():
    """Trigger manual sync of trades from broker."""
    from sentinel.jobs import run_now

    result = await run_now("sync:trades")
    return result


@app.get("/api/cashflows")
async def get_cashflows():
    """
    Get aggregated cash flow summary from database.

    Returns:
        deposits: Total deposits in EUR
        withdrawals: Total withdrawals in EUR (positive number)
        dividends: Total dividends received in EUR
        taxes: Total taxes paid in EUR (positive number)
        fees: Total trading fees in EUR (positive number)
        net_deposits: deposits - withdrawals
        total_profit: Current portfolio value + cash - net_deposits
    """
    db = Database()
    currency = Currency()

    # Get aggregated cash flows from database
    summary = await db.get_cash_flow_summary()

    # Convert each type/currency combination to EUR
    deposits_eur = 0.0
    withdrawals_eur = 0.0
    dividends_eur = 0.0
    taxes_eur = 0.0

    for type_id, currencies in summary.items():
        for curr, total in currencies.items():
            amount_eur = await currency.to_eur(total, curr)

            if type_id == "card":
                deposits_eur += amount_eur
            elif type_id == "card_payout":
                withdrawals_eur += abs(amount_eur)
            elif type_id == "dividend":
                dividends_eur += amount_eur
            elif type_id == "tax":
                taxes_eur += abs(amount_eur)

    # Get trading fees efficiently (aggregated query)
    fees_by_currency = await db.get_total_fees()
    fees_eur = 0.0
    for curr, total in fees_by_currency.items():
        fees_eur += await currency.to_eur(total, curr)

    # Get portfolio value for total profit calculation
    portfolio_obj = Portfolio()
    total_value = await portfolio_obj.total_value()
    cash_balances = await portfolio_obj.get_cash_balances()

    # Calculate total cash in EUR
    total_cash_eur = 0.0
    for curr, amount in cash_balances.items():
        total_cash_eur += await currency.to_eur(amount, curr)

    net_deposits = deposits_eur - withdrawals_eur
    # Total profit = current value - what we put in (net deposits)
    # Note: dividends and fees are already reflected in cash balance
    total_profit = (total_value + total_cash_eur) - net_deposits

    return {
        "deposits": round(deposits_eur, 2),
        "withdrawals": round(withdrawals_eur, 2),
        "dividends": round(dividends_eur, 2),
        "taxes": round(taxes_eur, 2),
        "fees": round(fees_eur, 2),
        "net_deposits": round(net_deposits, 2),
        "total_profit": round(total_profit, 2),
    }


@app.post("/api/cashflows/sync")
async def sync_cashflows_endpoint():
    """Trigger manual sync of cash flows from broker."""
    from sentinel.jobs import run_now

    result = await run_now("sync:cashflows")
    return result


@app.post("/api/securities/{symbol}/buy")
async def buy_security(symbol: str, quantity: int):
    """Buy a security."""
    security = Security(symbol)
    await security.load()
    order_id = await security.buy(quantity)
    if not order_id:
        raise HTTPException(status_code=400, detail="Buy order failed")
    return {"order_id": order_id}


@app.post("/api/securities/{symbol}/sell")
async def sell_security(symbol: str, quantity: int):
    """Sell a security."""
    security = Security(symbol)
    await security.load()
    order_id = await security.sell(quantity)
    if not order_id:
        raise HTTPException(status_code=400, detail="Sell order failed")
    return {"order_id": order_id}

    # -----------------------------------------------------------------------------
    # Allocation Targets API
    # -----------------------------------------------------------------------------

    # MOVED to sentinel/api/routers/portfolio.py
    # @app.get("/api/allocation-targets")
    # async def get_allocation_targets():
    """Get all allocation targets."""
    db = Database()
    targets = await db.get_allocation_targets()
    return {
        "geography": [t for t in targets if t["type"] == "geography"],
        "industry": [t for t in targets if t["type"] == "industry"],
    }

    # MOVED to sentinel/api/routers/portfolio.py
    # @app.put("/api/allocation-targets/{target_type}/{name}")
    # async def set_allocation_target(target_type: str, name: str, data: dict): ...

    # MOVED to sentinel/api/routers/portfolio.py
    # @app.get("/api/allocation/current")
    # async def get_allocation_current():
    """Get current allocation data formatted for radar charts."""
    portfolio = Portfolio()
    current = await portfolio.get_allocations()
    targets = await portfolio.get_target_allocations()

    # Format geography allocations
    geography = []
    all_geos = set(current.get("by_geography", {}).keys()) | set(targets.get("geography", {}).keys())
    for geo in sorted(all_geos):
        current_pct = current.get("by_geography", {}).get(geo, 0) * 100
        target_pct = targets.get("geography", {}).get(geo, 0) * 100
        geography.append(
            {
                "name": geo,
                "current_pct": current_pct,
                "target_pct": target_pct,
            }
        )

    # Format industry allocations
    industry = []
    all_inds = set(current.get("by_industry", {}).keys()) | set(targets.get("industry", {}).keys())
    for ind in sorted(all_inds):
        current_pct = current.get("by_industry", {}).get(ind, 0) * 100
        target_pct = targets.get("industry", {}).get(ind, 0) * 100
        industry.append(
            {
                "name": ind,
                "current_pct": current_pct,
                "target_pct": target_pct,
            }
        )

    return {
        "geography": geography,
        "industry": industry,
        "alerts": [],  # TODO: implement concentration alerts if needed
    }

    # MOVED to sentinel/api/routers/portfolio.py
    # @app.get("/api/allocation/targets")
    # async def get_allocation_targets_formatted():
    """Get allocation targets as {geography: {name: weight}, industry: {name: weight}}."""
    db = Database()
    targets = await db.get_allocation_targets()

    geography = {}
    industry = {}
    for t in targets:
        if t["type"] == "geography":
            geography[t["name"]] = t["weight"]
        elif t["type"] == "industry":
            industry[t["name"]] = t["weight"]

    return {"geography": geography, "industry": industry}

    # MOVED to sentinel/api/routers/portfolio.py
    # @app.get("/api/allocation/available-geographies")
    # async def get_available_geographies():
    """Get available geographies from securities and allocation_targets only (no defaults)."""
    db = Database()
    # Only from securities + allocation_targets, NOT defaults
    existing = await db.get_categories()
    targets = await db.get_allocation_targets()
    target_geos = {t["name"] for t in targets if t["type"] == "geography"}
    geographies = sorted(set(existing["geographies"]) | target_geos)
    return {"geographies": geographies}

    # MOVED to sentinel/api/routers/portfolio.py
    # @app.get("/api/allocation/available-industries")
    # async def get_available_industries():
    """Get available industries from securities and allocation_targets only (no defaults)."""
    db = Database()
    # Only from securities + allocation_targets, NOT defaults
    existing = await db.get_categories()
    targets = await db.get_allocation_targets()
    target_inds = {t["name"] for t in targets if t["type"] == "industry"}
    industries = sorted(set(existing["industries"]) | target_inds)
    return {"industries": industries}

    # MOVED to sentinel/api/routers/portfolio.py
    # @app.put("/api/allocation/targets/geography")
    # async def save_geography_targets(data: dict): ...

    # MOVED to sentinel/api/routers/portfolio.py
    # @app.put("/api/allocation/targets/industry")
    # async def save_industry_targets(data: dict): ...

    # MOVED to sentinel/api/routers/portfolio.py
    # @app.delete("/api/allocation/targets/geography/{name}")
    # async def delete_geography_target(name: str): ...

    # MOVED to sentinel/api/routers/portfolio.py
    # @app.delete("/api/allocation/targets/industry/{name}")
    # async def delete_industry_target(name: str): ...

    # -----------------------------------------------------------------------------
    # Scores API
    # -----------------------------------------------------------------------------

    # MOVED to sentinel/api/routers/securities.py
    # @app.get("/api/scores")
    # async def get_scores():
    """Get all security scores."""
    db = Database()
    cursor = await db.conn.execute("SELECT symbol, score, components, calculated_at FROM scores ORDER BY score DESC")
    rows = await cursor.fetchall()
    return [dict(row) for row in rows]


# -----------------------------------------------------------------------------
# Planner API
# -----------------------------------------------------------------------------


@app.get("/api/planner/recommendations")
async def get_recommendations(min_value: Optional[float] = None):
    """Get trade recommendations to move toward ideal portfolio."""
    from sentinel.planner import Planner
    from sentinel.portfolio import Portfolio
    from sentinel.settings import Settings

    planner = Planner()
    portfolio = Portfolio()
    settings = Settings()

    # Use provided min_value or fall back to setting
    if min_value is None:
        min_value = await settings.get("min_trade_value", default=100.0)

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
                "expected_return": r.expected_return,
                "priority": r.priority,
                "reason": r.reason,
            }
            for r in recommendations
        ],
        "summary": {
            "current_cash": current_cash,
            "total_sell_value": total_sell_value,
            "total_buy_value": total_buy_value,
            "total_fees": total_fees,
            "cash_after_plan": cash_after_plan,
        },
    }


@app.get("/api/planner/ideal")
async def get_ideal_portfolio():
    """Get the calculated ideal portfolio allocations."""
    from sentinel.planner import Planner

    planner = Planner()
    ideal = await planner.calculate_ideal_portfolio()
    current = await planner.get_current_allocations()

    return {
        "ideal": {k: v * 100 for k, v in ideal.items()},
        "current": {k: v * 100 for k, v in current.items()},
    }


@app.get("/api/planner/summary")
async def get_rebalance_summary():
    """Get summary of portfolio alignment with ideal allocations."""
    from sentinel.planner import Planner

    planner = Planner()
    return await planner.get_rebalance_summary()


# -----------------------------------------------------------------------------
# Jobs API
# -----------------------------------------------------------------------------


@app.get("/api/jobs")
async def get_jobs():
    """Get current job, upcoming jobs and recent job history."""
    status = await get_status()
    return status


@app.post("/api/jobs/{job_type:path}/run")
async def run_job_endpoint(job_type: str):
    """Manually trigger a job by type. Executes immediately."""
    result = await run_now(job_type)
    if result.get("status") == "failed" and "Unknown job type" in result.get("error", ""):
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@app.post("/api/jobs/refresh-all")
async def refresh_all():
    """Reset last_run timestamp to 0 for all jobs and reschedule."""
    db = Database()
    await db.conn.execute("UPDATE job_schedules SET last_run = 0")
    await db.conn.commit()
    schedules = await db.get_job_schedules()
    for s in schedules:
        await reschedule(s["job_type"], db)
    return {"status": "ok", "message": "All jobs rescheduled"}


# -----------------------------------------------------------------------------
# Job Schedules API
# -----------------------------------------------------------------------------

MARKET_TIMING_LABELS = {
    0: "Any time",
    1: "After market close",
    2: "During market open",
    3: "All markets closed",
}


@app.get("/api/jobs/schedules")
async def get_job_schedules():
    """Get all job schedule configurations with status info."""
    db = Database()
    schedules = await db.get_job_schedules()

    # Get next run times from APScheduler
    next_run_times = {}
    if _scheduler:
        for job in _scheduler.get_jobs():
            if job.next_run_time:
                next_run_times[job.id] = job.next_run_time.isoformat()

    # Enrich with runtime info
    result = []
    for s in schedules:
        job_type = s["job_type"]

        # Get most recent execution (not just successful ones)
        history = await db.get_job_history_for_type(job_type, limit=1)
        if history:
            last_run = datetime.fromtimestamp(history[0]["executed_at"]).isoformat()
            last_status = history[0]["status"]
        else:
            last_run = None
            last_status = None

        result.append(
            {
                "job_type": s["job_type"],
                "interval_minutes": s["interval_minutes"],
                "interval_market_open_minutes": s.get("interval_market_open_minutes"),
                "market_timing": s["market_timing"],
                "market_timing_label": MARKET_TIMING_LABELS.get(s["market_timing"], "Unknown"),
                "description": s.get("description"),
                "category": s.get("category"),
                "last_run": last_run,
                "last_status": last_status,
                "next_run": next_run_times.get(job_type),
            }
        )

    return {"schedules": result}


@app.put("/api/jobs/schedules/{job_type:path}")
async def update_job_schedule(job_type: str, data: dict):
    """Update a job's schedule configuration."""
    db = Database()

    # Check if job_type exists
    existing = await db.get_job_schedule(job_type)
    if not existing:
        raise HTTPException(status_code=404, detail=f"Unknown job type: {job_type}")

    # Validate interval_minutes
    if "interval_minutes" in data:
        val = data["interval_minutes"]
        if not isinstance(val, int) or val < 1 or val > 10080:
            raise HTTPException(status_code=400, detail="interval_minutes must be between 1 and 10080")

    # Validate interval_market_open_minutes
    if "interval_market_open_minutes" in data:
        val = data["interval_market_open_minutes"]
        if val is not None and (not isinstance(val, int) or val < 1 or val > 10080):
            raise HTTPException(status_code=400, detail="interval_market_open_minutes must be between 1 and 10080")

    # Validate market_timing
    if "market_timing" in data:
        val = data["market_timing"]
        if not isinstance(val, int) or val < 0 or val > 3:
            raise HTTPException(status_code=400, detail="market_timing must be 0, 1, 2, or 3")

    await db.upsert_job_schedule(
        job_type,
        interval_minutes=data.get("interval_minutes"),
        interval_market_open_minutes=data.get("interval_market_open_minutes"),
        market_timing=data.get("market_timing"),
    )

    # Reschedule the job in APScheduler
    await reschedule(job_type, db)

    return {"status": "ok"}


@app.get("/api/jobs/history")
async def get_job_history(job_type: str | None = None, limit: int = 50):
    """Get job execution history."""
    db = Database()

    if job_type:
        history = await db.get_job_history_for_type(job_type, limit=limit)
    else:
        history = await db.get_job_history(limit=limit)

    return {"history": history}


# -----------------------------------------------------------------------------
# Cache Management
# -----------------------------------------------------------------------------


@app.get("/api/cache/stats")
async def get_cache_stats():
    """Get statistics for all caches."""
    return Cache.get_all_stats()


@app.post("/api/cache/clear")
async def clear_cache(name: str | None = None):
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


# -----------------------------------------------------------------------------
# Backtest API
# -----------------------------------------------------------------------------


@app.get("/api/backtest/run")
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
):
    """
    Run a backtest simulation via Server-Sent Events (SSE).

    Returns events:
    - progress: {current_date, progress_pct, portfolio_value, status, phase, current_item, items_done, items_total}
    - result: Full backtest results when complete
    - error: Error message if something goes wrong
    """
    import json
    from dataclasses import asdict

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


@app.post("/api/backtest/cancel")
async def cancel_backtest():
    """Cancel a running backtest."""
    backtest = get_active_backtest()
    if backtest:
        backtest.cancel()
        return {"status": "ok", "message": "Backtest cancellation requested"}
    return {"status": "ok", "message": "No active backtest to cancel"}


# -----------------------------------------------------------------------------
# Advanced Analytics API
# -----------------------------------------------------------------------------


@app.get("/api/analytics/regime/{symbol}")
async def get_regime_status(symbol: str):
    """Get current regime for a security."""
    from sentinel.regime_hmm import RegimeDetector

    detector = RegimeDetector()
    regime = await detector.detect_current_regime(symbol)
    history = await detector.get_regime_history(symbol, days=90)
    return {"current": regime, "history": history}


@app.get("/api/analytics/regimes")
async def get_all_regimes():
    """Get current regimes for all active securities."""
    from sentinel.regime_hmm import RegimeDetector

    db = Database()
    detector = RegimeDetector()

    securities = await db.get_all_securities(active_only=True)
    results = {}
    for sec in securities:
        regime = await detector.detect_current_regime(sec["symbol"])
        results[sec["symbol"]] = regime
    return results


# -----------------------------------------------------------------------------
# Backup API
# -----------------------------------------------------------------------------


@app.post("/api/backup/run")
async def run_backup():
    """Trigger an immediate R2 backup."""
    result = await run_now("backup:r2")
    return result


@app.get("/api/backup/status")
async def get_backup_status():
    """List recent backups from R2."""
    settings = Settings()
    account_id = await settings.get("r2_account_id", "")
    access_key = await settings.get("r2_access_key", "")
    secret_key = await settings.get("r2_secret_key", "")
    bucket_name = await settings.get("r2_bucket_name", "")

    if not all([account_id, access_key, secret_key, bucket_name]):
        return {"configured": False, "backups": []}

    try:
        from sentinel.jobs.tasks import _get_r2_client

        client = _get_r2_client(account_id, access_key, secret_key)
        response = client.list_objects_v2(Bucket=bucket_name, Prefix="backups/")
        contents = response.get("Contents", [])

        backups = sorted(
            [
                {
                    "key": obj["Key"],
                    "size_bytes": obj.get("Size", 0),
                    "last_modified": obj["LastModified"].isoformat() if obj.get("LastModified") else None,
                }
                for obj in contents
            ],
            key=lambda x: x["last_modified"] or "",
            reverse=True,
        )

        return {"configured": True, "backups": backups}
    except Exception as e:
        return {"configured": True, "backups": [], "error": str(e)}


# -----------------------------------------------------------------------------
# Health Check
# -----------------------------------------------------------------------------


@app.get("/api/pulse/labels")
async def get_pulse_labels():
    """Return geographies and industries from active securities for Pulse classification."""
    db = Database()
    return await db.get_categories(active_only=True)


@app.get("/api/version")
async def version():
    """Return the application version."""
    return {"version": VERSION}


@app.get("/api/health")
async def health():
    """Health check endpoint."""
    broker = Broker()
    settings = Settings()
    trading_mode = await settings.get("trading_mode", "research")
    return {
        "status": "healthy",
        "broker_connected": broker.connected,
        "trading_mode": trading_mode,
    }


# -----------------------------------------------------------------------------
# ML Prediction API Endpoints (Per-Symbol Models)
# -----------------------------------------------------------------------------


@app.get("/api/ml/status")
async def get_ml_status():
    """Get ML system status."""
    from sentinel.database import Database

    db = Database()
    await db.connect()

    # Count securities with ML enabled
    cursor = await db.conn.execute("SELECT COUNT(*) as count FROM securities WHERE ml_enabled = 1 AND active = 1")
    enabled_row = await cursor.fetchone()
    securities_ml_enabled = enabled_row["count"] if enabled_row else 0

    # Count symbols with trained models
    cursor = await db.conn.execute("SELECT COUNT(*) as count FROM ml_models")
    total_models_row = await cursor.fetchone()
    symbols_with_models = total_models_row["count"] if total_models_row else 0

    # Count total training samples
    cursor = await db.conn.execute("SELECT COUNT(*) as count FROM ml_training_samples")
    total_samples_row = await cursor.fetchone()
    total_samples = total_samples_row["count"] if total_samples_row else 0

    # Get aggregate metrics across all models
    cursor = await db.conn.execute(
        """SELECT AVG(validation_rmse) as avg_rmse,
                  AVG(validation_mae) as avg_mae,
                  AVG(validation_r2) as avg_r2,
                  SUM(training_samples) as total_trained_samples
           FROM ml_models"""
    )
    metrics_row = await cursor.fetchone()

    aggregate_metrics = None
    if metrics_row and metrics_row["avg_rmse"] is not None:
        aggregate_metrics = {
            "avg_validation_rmse": metrics_row["avg_rmse"],
            "avg_validation_mae": metrics_row["avg_mae"],
            "avg_validation_r2": metrics_row["avg_r2"],
            "total_trained_samples": metrics_row["total_trained_samples"],
        }

    # Get list of ML-enabled securities with their settings
    cursor = await db.conn.execute(
        """SELECT symbol, ml_blend_ratio FROM securities
           WHERE ml_enabled = 1 AND active = 1"""
    )
    ml_securities = await cursor.fetchall()

    return {
        "securities_ml_enabled": securities_ml_enabled,
        "symbols_with_models": symbols_with_models,
        "total_training_samples": total_samples,
        "aggregate_metrics": aggregate_metrics,
        "ml_securities": [{"symbol": row["symbol"], "blend_ratio": row["ml_blend_ratio"]} for row in ml_securities],
    }


@app.post("/api/ml/retrain")
async def trigger_retraining():
    """Manually trigger ML model retraining for all ML-enabled symbols."""
    from sentinel.database import Database
    from sentinel.ml_retrainer import MLRetrainer

    db = Database()
    await db.connect()

    # Get symbols with ML enabled
    cursor = await db.conn.execute("SELECT symbol FROM securities WHERE ml_enabled = 1 AND active = 1")
    rows = await cursor.fetchall()

    if not rows:
        return {"status": "skipped", "reason": "No securities have ML enabled"}

    retrainer = MLRetrainer()
    results = {}
    trained = 0
    skipped = 0

    for row in rows:
        symbol = row["symbol"]
        result = await retrainer.retrain_symbol(symbol)
        if result:
            results[symbol] = result
            trained += 1
        else:
            results[symbol] = {"status": "skipped", "reason": "Insufficient data"}
            skipped += 1

    return {
        "status": "completed",
        "symbols_trained": trained,
        "symbols_skipped": skipped,
        "results": results,
    }


@app.post("/api/ml/retrain/{symbol}")
async def trigger_retraining_symbol(symbol: str):
    """Manually trigger ML model retraining for a specific symbol."""
    from sentinel.ml_retrainer import MLRetrainer

    retrainer = MLRetrainer()
    result = await retrainer.retrain_symbol(symbol)

    if result is None:
        return {"status": "skipped", "symbol": symbol, "reason": "Insufficient training data"}

    return {"status": "trained", "symbol": symbol, **result}


@app.get("/api/ml/performance")
async def get_ml_performance():
    """Get ML model performance metrics and report for ML-enabled securities."""
    from sentinel.database import Database
    from sentinel.ml_monitor import MLMonitor

    db = Database()
    await db.connect()

    # Get symbols with ML enabled
    cursor = await db.conn.execute("SELECT symbol FROM securities WHERE ml_enabled = 1 AND active = 1")
    rows = await cursor.fetchall()

    if not rows:
        return {
            "metrics": {"status": "skipped", "reason": "No securities have ML enabled"},
            "report": "No ML-enabled securities to monitor.",
        }

    monitor = MLMonitor()
    all_metrics = {}

    for row in rows:
        symbol = row["symbol"]
        result = await monitor.track_symbol_performance(symbol)
        if result:
            all_metrics[symbol] = result

    report = await monitor.generate_report()

    return {
        "metrics": all_metrics,
        "report": report,
    }


@app.get("/api/ml/models")
async def list_ml_models():
    """List all per-symbol ML models."""
    from sentinel.database import Database

    db = Database()
    await db.connect()

    query = """
        SELECT symbol, training_samples, validation_rmse,
               validation_mae, validation_r2, last_trained_at
        FROM ml_models
        ORDER BY last_trained_at DESC
    """
    cursor = await db.conn.execute(query)
    models = await cursor.fetchall()

    return {
        "models": [
            {
                "symbol": m["symbol"],
                "training_samples": m["training_samples"],
                "validation_rmse": m["validation_rmse"],
                "validation_mae": m["validation_mae"],
                "validation_r2": m["validation_r2"],
                "last_trained_at": m["last_trained_at"],
            }
            for m in models
        ]
    }


@app.get("/api/ml/models/{symbol}")
async def get_ml_model(symbol: str):
    """Get ML model details for a specific symbol."""
    from sentinel.database import Database
    from sentinel.ml_ensemble import EnsembleBlender

    db = Database()
    await db.connect()

    # Get model record
    cursor = await db.conn.execute("SELECT * FROM ml_models WHERE symbol = ?", (symbol,))
    model_row = await cursor.fetchone()

    if not model_row:
        return {"error": f"No model found for {symbol}"}

    # Check if model files exist
    model_exists = EnsembleBlender.model_exists(symbol)

    # Get sample count for this symbol
    cursor = await db.conn.execute("SELECT COUNT(*) as count FROM ml_training_samples WHERE symbol = ?", (symbol,))
    sample_row = await cursor.fetchone()

    return {
        "symbol": model_row["symbol"],
        "training_samples": model_row["training_samples"],
        "validation_rmse": model_row["validation_rmse"],
        "validation_mae": model_row["validation_mae"],
        "validation_r2": model_row["validation_r2"],
        "last_trained_at": model_row["last_trained_at"],
        "model_files_exist": model_exists,
        "available_samples": sample_row["count"] if sample_row else 0,
    }


@app.get("/api/ml/train/{symbol}/stream")
async def train_symbol_stream(symbol: str):
    """Train ML model for a symbol with SSE progress updates."""
    import json

    from starlette.responses import StreamingResponse

    from sentinel.database import Database
    from sentinel.ml_retrainer import MLRetrainer
    from sentinel.ml_trainer import TrainingDataGenerator
    from sentinel.settings import Settings

    async def generate():
        db = Database()
        await db.connect()
        settings = Settings()

        try:
            # Step 1: Check if symbol exists
            yield f"data: {json.dumps({'step': 1, 'total': 5, 'message': 'Checking symbol...', 'progress': 0})}\n\n"
            security = await db.get_security(symbol)
            if not security:
                yield f"data: {json.dumps({'error': 'Symbol not found'})}\n\n"
                return

            # Step 2: Generate training samples
            evt = json.dumps({"step": 2, "total": 5, "message": "Generating training samples...", "progress": 20})
            yield f"data: {evt}\n\n"
            trainer = TrainingDataGenerator()
            horizon_days = await settings.get("ml_prediction_horizon_days", 14)
            lookback_years = await settings.get("ml_training_lookback_years", 8)

            samples_df = await trainer.generate_training_data_for_symbol(
                symbol,
                lookback_years=lookback_years,
                prediction_horizon_days=horizon_days,
            )
            sample_count = len(samples_df) if samples_df is not None else 0
            msg = f"Generated {sample_count} samples"
            yield f"data: {json.dumps({'step': 2, 'total': 5, 'message': msg, 'progress': 40})}\n\n"

            # Step 3: Check minimum samples
            evt = json.dumps({"step": 3, "total": 5, "message": "Checking data sufficiency...", "progress": 50})
            yield f"data: {evt}\n\n"
            min_samples = await settings.get("ml_min_samples_per_symbol", 100)
            if sample_count < min_samples:
                err_msg = f"Insufficient samples: {sample_count} < {min_samples} required"
                yield f"data: {json.dumps({'error': err_msg})}\n\n"
                return

            # Step 4: Train model
            evt = json.dumps({"step": 4, "total": 5, "message": "Training neural network + XGBoost...", "progress": 60})
            yield f"data: {evt}\n\n"
            retrainer = MLRetrainer()
            metrics = await retrainer.retrain_symbol(symbol)

            if not metrics:
                yield f"data: {json.dumps({'error': 'Training failed'})}\n\n"
                return

            rmse_msg = f"RMSE: {metrics['validation_rmse']:.4f}"
            evt = json.dumps({"step": 4, "total": 5, "message": rmse_msg, "progress": 90})
            yield f"data: {evt}\n\n"

            # Step 5: Done
            evt = json.dumps(
                {"step": 5, "total": 5, "message": "Model saved", "progress": 100, "complete": True, "metrics": metrics}
            )
            yield f"data: {evt}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


@app.delete("/api/ml/training-data/{symbol}")
async def delete_training_data(symbol: str):
    """Delete all training data and model for a symbol."""
    import shutil

    from sentinel.database import Database

    db = Database()
    await db.connect()

    # Delete training samples
    await db.conn.execute("DELETE FROM ml_training_samples WHERE symbol = ?", (symbol,))

    # Delete predictions
    await db.conn.execute("DELETE FROM ml_predictions WHERE symbol = ?", (symbol,))

    # Delete model record
    await db.conn.execute("DELETE FROM ml_models WHERE symbol = ?", (symbol,))

    # Delete performance tracking
    await db.conn.execute("DELETE FROM ml_performance_tracking WHERE symbol = ?", (symbol,))

    await db.conn.commit()

    # Delete model files
    from sentinel.paths import DATA_DIR

    model_path = DATA_DIR / "ml_models" / symbol
    if model_path.exists():
        shutil.rmtree(model_path)

    return {"status": "deleted", "symbol": symbol}


@app.get("/api/ml/training-status/{symbol}")
async def get_training_status(symbol: str):
    """Get ML training status for a symbol."""
    from sentinel.database import Database
    from sentinel.ml_ensemble import EnsembleBlender

    db = Database()
    await db.connect()

    # Get sample count
    cursor = await db.conn.execute("SELECT COUNT(*) as count FROM ml_training_samples WHERE symbol = ?", (symbol,))
    row = await cursor.fetchone()
    sample_count = row["count"] if row else 0

    # Get model info
    cursor = await db.conn.execute("SELECT * FROM ml_models WHERE symbol = ?", (symbol,))
    model_row = await cursor.fetchone()

    # Check if model files exist
    model_exists = EnsembleBlender.model_exists(symbol)

    return {
        "symbol": symbol,
        "sample_count": sample_count,
        "model_exists": model_exists,
        "model_info": dict(model_row) if model_row else None,
    }


# -----------------------------------------------------------------------------
# ML Reset API
# -----------------------------------------------------------------------------


@app.post("/api/ml/reset-and-retrain")
async def reset_and_retrain():
    """Reset all ML data and retrain all models from scratch.

    This endpoint:
    1. Deletes all aggregate price series (_AGG_*)
    2. Clears ML training data tables
    3. Removes model files
    4. Recomputes aggregates
    5. Regenerates training samples
    6. Retrains all models

    The operation runs in the background and returns immediately.
    Returns 409 Conflict if a reset is already in progress.
    """
    from sentinel.ml_reset import is_reset_in_progress

    if is_reset_in_progress():
        raise HTTPException(
            status_code=409,
            detail="A reset operation is already in progress",
        )

    asyncio.create_task(_run_reset_and_retrain())
    return {"status": "started", "message": "Reset and retrain started in background"}


@app.get("/api/ml/reset-status")
async def get_ml_reset_status():
    """Get the current status of the ML reset operation.

    Returns:
        - running: bool - whether a reset is in progress
        - current_step: int - current step number (1-6)
        - total_steps: int - total number of steps (6)
        - step_name: str - name of the current step
        - details: str - additional details about current progress
    """
    from sentinel.ml_reset import get_reset_status

    return get_reset_status()


async def _run_reset_and_retrain():
    """Background task to run the full reset and retrain pipeline."""
    from sentinel.ml_reset import MLResetManager, set_active_reset

    manager = MLResetManager()
    set_active_reset(manager)
    try:
        result = await manager.reset_all()
        logger.info(f"ML reset and retrain completed: {result}")
    except Exception as e:
        logger.error(f"ML reset and retrain failed: {e}")
    finally:
        set_active_reset(None)


# -----------------------------------------------------------------------------
# Static Files (Web UI)
# -----------------------------------------------------------------------------

web_dir = Path(__file__).parent.parent / "web" / "dist"

if web_dir.exists():
    from fastapi.responses import FileResponse

    # Serve static assets
    app.mount("/assets", StaticFiles(directory=str(web_dir / "assets")), name="assets")

    # Catch-all for client-side routing - serve index.html
    @app.get("/{path:path}")
    async def serve_spa(path: str):
        """Serve index.html for all non-API routes (SPA support)."""
        file_path = web_dir / path
        if file_path.exists() and file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(web_dir / "index.html")
