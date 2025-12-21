"""FastAPI application entry point."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.config import settings
from app.database import init_db
from app.api import portfolio, stocks, trades, status, allocation
from app.jobs.scheduler import init_scheduler, start_scheduler, stop_scheduler
from app.services.tradernet import get_tradernet_client
from app.led.display import get_led_display

# Configure logging
logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup and shutdown events."""
    # Startup
    logger.info("Starting Arduino Trader...")
    await init_db()

    # Initialize and start scheduler
    init_scheduler()
    start_scheduler()

    # Try to connect to LED display
    display = get_led_display()
    if display.connect():
        logger.info("LED display connected")
        # Check wifi and show appropriate state
        if display.check_wifi():
            display.set_system_status("ok")
        else:
            display.show_no_wifi()
    else:
        logger.warning("LED display not connected")

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
    display.disconnect()


app = FastAPI(
    title=settings.app_name,
    description="Automated trading system for Arduino Uno Q",
    version="0.1.0",
    lifespan=lifespan,
)


@app.middleware("http")
async def led_request_indicator(request: Request, call_next):
    """Flash RGB LEDs on web requests to show activity."""
    display = get_led_display()
    if display.is_connected:
        # Flash cyan on RGB LEDs (doesn't interrupt matrix display)
        display.flash_web_request()

    response = await call_next(request)
    return response


# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Include API routers
app.include_router(portfolio.router, prefix="/api/portfolio", tags=["Portfolio"])
app.include_router(stocks.router, prefix="/api/stocks", tags=["Stocks"])
app.include_router(trades.router, prefix="/api/trades", tags=["Trades"])
app.include_router(status.router, prefix="/api/status", tags=["Status"])
app.include_router(allocation.router, prefix="/api/allocation", tags=["Allocation"])


@app.get("/")
async def root():
    """Serve the dashboard."""
    return FileResponse("static/index.html")


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy", "app": settings.app_name}
