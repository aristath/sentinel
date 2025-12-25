"""FastAPI application entry point."""

import logging
from logging.handlers import RotatingFileHandler
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.config import settings
from app.infrastructure.database.manager import init_databases, get_db_manager, shutdown_databases
from app.api import portfolio, stocks, trades, status, allocation, cash_flows, charts, settings as settings_api
from app.jobs.scheduler import init_scheduler, start_scheduler, stop_scheduler
from app.services.tradernet import get_tradernet_client
from app.infrastructure.hardware.led_display import setup_event_subscriptions
from app.infrastructure.events import emit, SystemEvent

# Configure logging with correlation ID support and log rotation
from app.infrastructure.logging_context import CorrelationIDFilter

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
        logger.error("Missing Tradernet API credentials. Please set TRADERNET_API_KEY and TRADERNET_API_SECRET in .env file")
        raise ValueError("Missing required Tradernet API credentials")

    # Initialize database manager (creates all databases with schemas)
    db_manager = await init_databases(settings.data_dir)

    # Initialize and start scheduler
    await init_scheduler()
    start_scheduler()

    # Setup LED display event subscriptions
    setup_event_subscriptions()

    # Try to connect to Tradernet
    client = get_tradernet_client()
    if client.connect():
        logger.info("Tradernet connection established")
    else:
        logger.warning("Tradernet not connected - check credentials")

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

# Add rate limiting middleware (must be before other middleware)
from app.infrastructure.rate_limit import RateLimitMiddleware
app.add_middleware(RateLimitMiddleware)  # Uses values from config


@app.middleware("http")
async def request_context_middleware(request: Request, call_next):
    """Add correlation ID and LED indicators to requests."""
    from app.infrastructure.logging_context import set_correlation_id, clear_correlation_id

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
app.include_router(status.router, prefix="/api/status", tags=["Status"])
app.include_router(allocation.router, prefix="/api/allocation", tags=["Allocation"])
app.include_router(cash_flows.router, prefix="/api/cash-flows", tags=["Cash Flows"])
app.include_router(charts.router, prefix="/api/charts", tags=["Charts"])
app.include_router(settings_api.router, prefix="/api/settings", tags=["Settings"])


@app.get("/")
async def root():
    """Serve the dashboard."""
    return FileResponse("static/index.html")


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

    # Check database
    try:
        db_manager = get_db_manager()
        await db_manager.state.execute("SELECT 1")
        health_status["database"] = "connected"
    except Exception as e:
        health_status["database"] = f"error: {str(e)}"
        health_status["status"] = "degraded"

    # Check Tradernet
    try:
        from app.services.tradernet import get_tradernet_client
        client = get_tradernet_client()
        if client.is_connected:
            health_status["tradernet"] = "connected"
        elif client.connect():
            health_status["tradernet"] = "connected"
        else:
            health_status["tradernet"] = "disconnected"
            health_status["status"] = "degraded"
    except Exception as e:
        health_status["tradernet"] = f"error: {str(e)}"
        health_status["status"] = "degraded"

    # Check Yahoo Finance (basic connectivity test)
    try:
        import yfinance as yf
        # Quick test with a known symbol
        ticker = yf.Ticker("AAPL")
        info = ticker.info
        if info:
            health_status["yahoo_finance"] = "available"
        else:
            health_status["yahoo_finance"] = "unavailable"
            health_status["status"] = "degraded"
    except Exception as e:
        health_status["yahoo_finance"] = f"error: {str(e)}"
        health_status["status"] = "degraded"

    from fastapi import status as http_status

    # Return appropriate status code based on health
    if health_status["status"] == "healthy":
        return health_status
    else:
        from fastapi.responses import JSONResponse
        return JSONResponse(
            content=health_status,
            status_code=http_status.HTTP_503_SERVICE_UNAVAILABLE
        )
