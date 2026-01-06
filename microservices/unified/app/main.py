"""Unified microservice - Main FastAPI application."""

import logging
from contextlib import asynccontextmanager

from app.config import settings
from app.health import router as health_router
from app.routers import pypfopt, tradernet, yfinance
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Configure logging
logging.basicConfig(
    level=settings.log_level,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown events."""
    # Startup
    logger.info(f"{settings.service_name} starting up on port {settings.port}...")
    yield
    # Shutdown
    logger.info(f"{settings.service_name} shutting down...")


# Create FastAPI app
app = FastAPI(
    title=f"{settings.service_name} API",
    description=(
        "Unified microservice combining PyPFOpt, Tradernet, and YFinance services"
    ),
    version=settings.version,
    lifespan=lifespan,
)

# CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include health router
app.include_router(health_router)

# Include service routers with prefixes
app.include_router(pypfopt.router, prefix="/api/pypfopt", tags=["pypfopt"])
app.include_router(tradernet.router, prefix="/api/tradernet", tags=["tradernet"])
app.include_router(yfinance.router, prefix="/api/yfinance", tags=["yfinance"])
