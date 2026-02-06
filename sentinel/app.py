"""
Sentinel Web API - FastAPI entry point.

Usage:
    uvicorn sentinel.app:app --host 0.0.0.0 --port 8000
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

# API routers
from sentinel.api.routers import (
    allocation_router,
    backtest_router,
    backup_router,
    cache_router,
    cashflows_router,
    exchange_rates_router,
    internal_ml_router,
    jobs_router,
    led_router,
    markets_router,
    meta_router,
    planner_router,
    portfolio_router,
    prices_router,
    pulse_router,
    scores_router,
    securities_router,
    set_scheduler,
    settings_router,
    system_router,
    targets_router,
    trading_actions_router,
    trading_router,
    unified_router,
)
from sentinel.api.routers.settings import set_led_controller
from sentinel.broker import Broker
from sentinel.cache import Cache
from sentinel.currency import Currency
from sentinel.database import Database
from sentinel.jobs import init as init_jobs
from sentinel.jobs import stop as stop_jobs
from sentinel.jobs.market import BrokerMarketChecker
from sentinel.portfolio import Portfolio
from sentinel.settings import Settings
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
    from sentinel.planner import Planner

    portfolio = Portfolio()
    analyzer = Analyzer()
    planner = Planner()
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
        planner,
        cache,
        market_checker,
    )
    logger.info("Job scheduler started")

    # Pass scheduler to jobs router for schedule management
    set_scheduler(_scheduler)

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
app.include_router(trading_router, prefix="/api")
app.include_router(cashflows_router, prefix="/api")
app.include_router(trading_actions_router, prefix="/api")
app.include_router(planner_router, prefix="/api")
app.include_router(jobs_router, prefix="/api")
app.include_router(internal_ml_router, prefix="/api")
app.include_router(backup_router, prefix="/api")
app.include_router(system_router, prefix="/api")
app.include_router(cache_router, prefix="/api")
app.include_router(backtest_router, prefix="/api")
app.include_router(exchange_rates_router, prefix="/api")
app.include_router(markets_router, prefix="/api")
app.include_router(meta_router, prefix="/api")
app.include_router(pulse_router, prefix="/api")

# -----------------------------------------------------------------------------
# Static Files (Web UI)
# -----------------------------------------------------------------------------

web_dir = Path(__file__).parent.parent / "web" / "dist"

if web_dir.exists():
    from fastapi.responses import FileResponse, JSONResponse

    # Serve static assets
    app.mount("/assets", StaticFiles(directory=str(web_dir / "assets")), name="assets")

    # Catch-all for client-side routing - serve index.html
    @app.get("/{path:path}")
    async def serve_spa(path: str):
        """Serve index.html for all non-API routes (SPA support)."""
        # API paths must return API 404, not SPA HTML.
        if path.startswith("api/"):
            return JSONResponse(status_code=404, content={"detail": "Not Found"})
        file_path = web_dir / path
        if file_path.exists() and file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(web_dir / "index.html")
