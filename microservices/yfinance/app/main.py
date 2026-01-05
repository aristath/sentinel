"""Yahoo Finance microservice - Main FastAPI application."""

import logging
from typing import Optional

from app.config import settings
from app.health import router as health_router
from app.models import (
    AnalystData,
    BatchQuotesRequest,
    FundamentalData,
    HistoricalPricesRequest,
    HistoricalPricesResponse,
    SecurityInfo,
    ServiceResponse,
)
from app.service import get_yahoo_finance_service
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

# Configure logging
logging.basicConfig(
    level=settings.log_level,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title=f"{settings.service_name} API",
    description="Microservice wrapping yfinance for Yahoo Finance data access",
    version=settings.version,
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

# Get service instance
service = get_yahoo_finance_service()


@app.on_event("startup")
async def startup_event():
    """Startup event."""
    logger.info(f"{settings.service_name} starting up...")


@app.on_event("shutdown")
async def shutdown_event():
    """Shutdown event."""
    logger.info(f"{settings.service_name} shutting down...")


# Quote endpoints
@app.get("/api/quotes/{symbol}", response_model=ServiceResponse)
async def get_quote(
    symbol: str, yahoo_symbol: Optional[str] = Query(default=None)
) -> ServiceResponse:
    """Get current price for a symbol."""
    try:
        price = service.get_current_price(symbol, yahoo_symbol)
        if price is not None:
            return ServiceResponse(
                success=True,
                data={"symbol": symbol, "price": price},
            )
        return ServiceResponse(
            success=False,
            error=f"No price available for {symbol}",
        )
    except Exception as e:
        logger.exception(f"Error getting quote for {symbol}")
        return ServiceResponse(
            success=False,
            error=str(e),
        )


@app.post("/api/quotes/batch", response_model=ServiceResponse)
async def get_batch_quotes(request: BatchQuotesRequest) -> ServiceResponse:
    """Get current prices for multiple symbols."""
    try:
        quotes = service.get_batch_quotes(
            request.symbols, request.yahoo_overrides
        )
        return ServiceResponse(
            success=True,
            data={"quotes": quotes},
        )
    except Exception as e:
        logger.exception("Error getting batch quotes")
        return ServiceResponse(
            success=False,
            error=str(e),
        )


# Historical data endpoints
@app.post("/api/historical", response_model=ServiceResponse)
async def get_historical_prices(request: HistoricalPricesRequest) -> ServiceResponse:
    """Get historical OHLCV data."""
    try:
        prices = service.get_historical_prices(
            request.symbol,
            request.yahoo_symbol,
            request.period,
            request.interval,
        )
        return ServiceResponse(
            success=True,
            data=HistoricalPricesResponse(
                symbol=request.symbol, prices=prices
            ).dict(),
        )
    except Exception as e:
        logger.exception(f"Error getting historical prices for {request.symbol}")
        return ServiceResponse(
            success=False,
            error=str(e),
        )


@app.get("/api/historical/{symbol}", response_model=ServiceResponse)
async def get_historical_prices_get(
    symbol: str,
    yahoo_symbol: Optional[str] = Query(default=None),
    period: str = Query(default="1y"),
    interval: str = Query(default="1d"),
) -> ServiceResponse:
    """Get historical OHLCV data (GET endpoint)."""
    try:
        prices = service.get_historical_prices(symbol, yahoo_symbol, period, interval)
        return ServiceResponse(
            success=True,
            data=HistoricalPricesResponse(symbol=symbol, prices=prices).dict(),
        )
    except Exception as e:
        logger.exception(f"Error getting historical prices for {symbol}")
        return ServiceResponse(
            success=False,
            error=str(e),
        )


# Fundamental data endpoints
@app.get("/api/fundamentals/{symbol}", response_model=ServiceResponse)
async def get_fundamentals(
    symbol: str, yahoo_symbol: Optional[str] = Query(default=None)
) -> ServiceResponse:
    """Get fundamental analysis data."""
    try:
        data = service.get_fundamental_data(symbol, yahoo_symbol)
        if data:
            return ServiceResponse(
                success=True,
                data=data.dict(),
            )
        return ServiceResponse(
            success=False,
            error=f"No fundamental data available for {symbol}",
        )
    except Exception as e:
        logger.exception(f"Error getting fundamentals for {symbol}")
        return ServiceResponse(
            success=False,
            error=str(e),
        )


# Analyst data endpoints
@app.get("/api/analyst/{symbol}", response_model=ServiceResponse)
async def get_analyst_data(
    symbol: str, yahoo_symbol: Optional[str] = Query(default=None)
) -> ServiceResponse:
    """Get analyst recommendations and price targets."""
    try:
        data = service.get_analyst_data(symbol, yahoo_symbol)
        if data:
            return ServiceResponse(
                success=True,
                data=data.dict(),
            )
        return ServiceResponse(
            success=False,
            error=f"No analyst data available for {symbol}",
        )
    except Exception as e:
        logger.exception(f"Error getting analyst data for {symbol}")
        return ServiceResponse(
            success=False,
            error=str(e),
        )


# Security info endpoints
@app.get("/api/security/industry/{symbol}", response_model=ServiceResponse)
async def get_security_industry(
    symbol: str, yahoo_symbol: Optional[str] = Query(default=None)
) -> ServiceResponse:
    """Get security industry/sector."""
    try:
        data = service.get_security_industry(symbol, yahoo_symbol)
        if data:
            return ServiceResponse(
                success=True,
                data=data.dict(),
            )
        return ServiceResponse(
            success=False,
            error=f"No industry data available for {symbol}",
        )
    except Exception as e:
        logger.exception(f"Error getting industry for {symbol}")
        return ServiceResponse(
            success=False,
            error=str(e),
        )


@app.get("/api/security/country-exchange/{symbol}", response_model=ServiceResponse)
async def get_security_country_exchange(
    symbol: str, yahoo_symbol: Optional[str] = Query(default=None)
) -> ServiceResponse:
    """Get security country and exchange."""
    try:
        data = service.get_security_country_exchange(symbol, yahoo_symbol)
        if data:
            return ServiceResponse(
                success=True,
                data=data.dict(),
            )
        return ServiceResponse(
            success=False,
            error=f"No country/exchange data available for {symbol}",
        )
    except Exception as e:
        logger.exception(f"Error getting country/exchange for {symbol}")
        return ServiceResponse(
            success=False,
            error=str(e),
        )


@app.get("/api/security/info/{symbol}", response_model=ServiceResponse)
async def get_security_info(
    symbol: str, yahoo_symbol: Optional[str] = Query(default=None)
) -> ServiceResponse:
    """Get comprehensive security information."""
    try:
        data = service.get_security_info(symbol, yahoo_symbol)
        if data:
            return ServiceResponse(
                success=True,
                data=data.dict(),
            )
        return ServiceResponse(
            success=False,
            error=f"No security info available for {symbol}",
        )
    except Exception as e:
        logger.exception(f"Error getting security info for {symbol}")
        return ServiceResponse(
            success=False,
            error=str(e),
        )

