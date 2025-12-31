"""FastAPI application entry point."""

import logging
from contextlib import asynccontextmanager
from logging.handlers import RotatingFileHandler

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api import charts
from app.api import settings as settings_api
from app.config import settings
from app.core.database.manager import get_db_manager, init_databases, shutdown_databases
from app.core.events import SystemEvent, emit

# Configure logging with correlation ID support and log rotation
from app.core.logging import CorrelationIDFilter

# Import event modules to register event subscriptions
from app.infrastructure import recommendation_events  # noqa: F401
from app.infrastructure.external.tradernet import get_tradernet_client
from app.jobs.scheduler import init_scheduler, start_scheduler, stop_scheduler
from app.modules.allocation.api import allocation
from app.modules.cash_flows.api import cash_flows
from app.modules.optimization.api import optimizer
from app.modules.planning import events as planner_events  # noqa: F401
from app.modules.planning.api import planner, recommendations
from app.modules.portfolio.api import portfolio
from app.modules.system.api import status
from app.modules.trading.api import trades
from app.modules.universe.api import stocks

# Log format with correlation ID
log_format = logging.Formatter(
    "%(asctime)s - [%(correlation_id)s] - %(name)s - %(levelname)s - %(message)s"
)

# Console handler (for systemd/docker logs)
console_handler = logging.StreamHandler()
console_handler.setFormatter(log_format)
console_handler.addFilter(CorrelationIDFilter())

# File handler with rotation (5MB per file, keep 3 backups = 20MB max)
log_dir = settings.data_dir / "logs"
log_dir.mkdir(parents=True, exist_ok=True)
file_handler = RotatingFileHandler(
    log_dir / "arduino-trader.log",
    maxBytes=5 * 1024 * 1024,  # 5MB
    backupCount=3,
    encoding="utf-8",
)
file_handler.setFormatter(log_format)
file_handler.addFilter(CorrelationIDFilter())

logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    handlers=[console_handler, file_handler],
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup and shutdown events."""
    # Startup
    logger.info("Starting Arduino Trader...")

    # Clean up stale lock files from previous crashes
    lock_dir = settings.data_dir / "locks"
    if lock_dir.exists():
        for lock_file in lock_dir.glob("*.lock"):
            try:
                lock_file.unlink()
                logger.info(f"Cleaned up stale lock file: {lock_file.name}")
            except Exception as e:
                logger.warning(f"Failed to clean up lock file {lock_file.name}: {e}")

    # Validate required configuration
    if not settings.tradernet_api_key or not settings.tradernet_api_secret:
        logger.error(
            "Missing Tradernet API credentials. Please set TRADERNET_API_KEY and TRADERNET_API_SECRET in .env file"
        )
        raise ValueError("Missing required Tradernet API credentials")

    # Initialize database manager (creates all databases with schemas)
    await init_databases(settings.data_dir)

    # Initialize and start scheduler
    await init_scheduler()
    start_scheduler()

    # Try to connect to Tradernet
    client = get_tradernet_client()
    if client.connect():
        logger.info("Tradernet connection established")
    else:
        logger.warning("Tradernet not connected - check credentials")

    # Initialize display with startup message
    from app.modules.display.services.display_service import set_text

    set_text("SYSTEM STARTING...")
    logger.info("Display initialized with startup message")

    # Trigger initial display update in background
    async def update_display_on_startup():
        try:
            from app.modules.display.services.display_updater_service import (
                update_display_ticker,
            )

            await update_display_ticker()
            logger.info("Display updated on startup")
        except Exception as e:
            logger.warning(f"Failed to update display on startup: {e}")

    import asyncio

    asyncio.create_task(update_display_on_startup())

    yield

    # Shutdown
    logger.info("Shutting down Arduino Trader...")
    stop_scheduler()
    await shutdown_databases()


app = FastAPI(
    title=settings.app_name,
    description="Automated trading system for Arduino Uno Q",
    version="0.1.0",
    lifespan=lifespan,
)

from app.core.middleware import RateLimitMiddleware  # noqa: E402

# Add rate limiting middleware (must be before other middleware)
app.add_middleware(RateLimitMiddleware)  # Uses values from config


@app.middleware("http")
async def request_context_middleware(request: Request, call_next):
    """Add correlation ID and LED indicators to requests."""
    from app.core.logging import clear_correlation_id, set_correlation_id

    # Set correlation ID for this request
    correlation_id = set_correlation_id()

    # Flash LED 2 on web requests (skip LED polling to avoid feedback loop)
    if not request.url.path.startswith("/api/status/led"):
        emit(SystemEvent.WEB_REQUEST)

    try:
        response = await call_next(request)
        response.headers["X-Correlation-ID"] = correlation_id
        return response
    finally:
        clear_correlation_id()


# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Include API routers
app.include_router(portfolio.router, prefix="/api/portfolio", tags=["Portfolio"])
app.include_router(stocks.router, prefix="/api/stocks", tags=["Stocks"])
app.include_router(trades.router, prefix="/api/trades", tags=["Trades"])
app.include_router(
    recommendations.router,
    prefix="/api/trades/recommendations",
    tags=["Recommendations"],
)
app.include_router(status.router, prefix="/api/status", tags=["Status"])
app.include_router(allocation.router, prefix="/api/allocation", tags=["Allocation"])
app.include_router(cash_flows.router, prefix="/api/cash-flows", tags=["Cash Flows"])
app.include_router(charts.router, prefix="/api/charts", tags=["Charts"])
app.include_router(settings_api.router, prefix="/api/settings", tags=["Settings"])
app.include_router(optimizer.router, prefix="/api/optimizer", tags=["Optimizer"])
app.include_router(planner.router, prefix="/api/planner", tags=["Planner"])


@app.get("/")
async def root():
    """Serve the dashboard."""
    return FileResponse("static/index.html")


async def _check_database_health() -> tuple[str, bool]:
    """Check database connectivity."""
    try:
        db_manager = get_db_manager()
        await db_manager.state.execute("SELECT 1")
        return "connected", False
    except Exception as e:
        return f"error: {str(e)}", True


def _check_tradernet_health() -> tuple[str, bool]:
    """Check Tradernet API connectivity."""
    try:
        from app.infrastructure.external.tradernet import get_tradernet_client

        client = get_tradernet_client()
        if client.is_connected or client.connect():
            return "connected", False
        else:
            return "disconnected", True
    except Exception as e:
        return f"error: {str(e)}", True


def _check_yahoo_finance_health() -> tuple[str, bool]:
    """Check Yahoo Finance API connectivity."""
    try:
        import yfinance as yf

        ticker = yf.Ticker("AAPL")
        info = ticker.info
        if info:
            return "available", False
        else:
            return "unavailable", True
    except Exception as e:
        return f"error: {str(e)}", True


@app.get("/health")
async def health():
    """
    Health check endpoint with external service status.

    Returns:
        - status: Overall health status
        - app: Application name
        - database: Database connectivity status
        - tradernet: Tradernet API connectivity status
        - yahoo_finance: Yahoo Finance API status (basic check)
    """
    health_status = {
        "status": "healthy",
        "app": settings.app_name,
        "database": "unknown",
        "tradernet": "unknown",
        "yahoo_finance": "unknown",
    }

    db_status, db_degraded = await _check_database_health()
    health_status["database"] = db_status
    if db_degraded:
        health_status["status"] = "degraded"

    tradernet_status, tradernet_degraded = _check_tradernet_health()
    health_status["tradernet"] = tradernet_status
    if tradernet_degraded:
        health_status["status"] = "degraded"

    yahoo_status, yahoo_degraded = _check_yahoo_finance_health()
    health_status["yahoo_finance"] = yahoo_status
    if yahoo_degraded:
        health_status["status"] = "degraded"

    from fastapi import status as http_status

    if health_status["status"] == "healthy":
        return health_status
    else:
        from fastapi.responses import JSONResponse

        return JSONResponse(
            content=health_status, status_code=http_status.HTTP_503_SERVICE_UNAVAILABLE
        )
