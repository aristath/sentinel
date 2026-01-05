"""Yahoo Finance microservice - Starlette example (for comparison).

This is an example showing how the service would look using Starlette instead of FastAPI.
This file is for reference only - not used in production.
"""

import json
import logging
from datetime import datetime
from typing import Optional

from app.config import settings
from app.service import get_yahoo_finance_service
from starlette.applications import Starlette
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

# Configure logging
logging.basicConfig(
    level=settings.log_level,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Get service instance
service = get_yahoo_finance_service()


# Helper function for standard responses
def success_response(data: dict) -> JSONResponse:
    """Create a success response."""
    return JSONResponse(
        {
            "success": True,
            "data": data,
            "timestamp": datetime.utcnow().isoformat(),
        }
    )


def error_response(error: str, status_code: int = 200) -> JSONResponse:
    """Create an error response."""
    return JSONResponse(
        {
            "success": False,
            "error": error,
            "timestamp": datetime.utcnow().isoformat(),
        },
        status_code=status_code,
    )


# Health check endpoint
async def health_check(request: Request) -> JSONResponse:
    """Health check endpoint."""
    return JSONResponse(
        {
            "status": "healthy",
            "service": settings.service_name,
            "version": settings.version,
            "timestamp": datetime.utcnow().isoformat(),
        }
    )


# Quote endpoints
async def get_quote(request: Request) -> JSONResponse:
    """Get current price for a symbol."""
    try:
        symbol = request.path_params["symbol"]
        yahoo_symbol = request.query_params.get("yahoo_symbol")

        price = service.get_current_price(symbol, yahoo_symbol)
        if price is not None:
            return success_response({"symbol": symbol, "price": price})
        return error_response(f"No price available for {symbol}")
    except Exception as e:
        logger.exception(f"Error getting quote for {symbol}")
        return error_response(str(e))


async def get_batch_quotes(request: Request) -> JSONResponse:
    """Get current prices for multiple symbols."""
    try:
        body = await request.json()
        symbols = body.get("symbols", [])
        yahoo_overrides = body.get("yahoo_overrides")

        if not symbols:
            return error_response("symbols field is required", status_code=400)

        quotes = service.get_batch_quotes(symbols, yahoo_overrides)
        return success_response({"quotes": quotes})
    except json.JSONDecodeError:
        return error_response("Invalid JSON in request body", status_code=400)
    except Exception as e:
        logger.exception("Error getting batch quotes")
        return error_response(str(e))


# Historical data endpoints
async def get_historical_prices_post(request: Request) -> JSONResponse:
    """Get historical OHLCV data (POST endpoint)."""
    try:
        body = await request.json()
        symbol = body.get("symbol")
        yahoo_symbol = body.get("yahoo_symbol")
        period = body.get("period", "1y")
        interval = body.get("interval", "1d")

        if not symbol:
            return error_response("symbol field is required", status_code=400)

        prices = service.get_historical_prices(symbol, yahoo_symbol, period, interval)

        # Convert Pydantic models to dict for JSON serialization
        prices_dict = [price.dict() if hasattr(price, "dict") else price for price in prices]

        return success_response(
            {
                "symbol": symbol,
                "prices": prices_dict,
            }
        )
    except json.JSONDecodeError:
        return error_response("Invalid JSON in request body", status_code=400)
    except Exception as e:
        logger.exception(f"Error getting historical prices")
        return error_response(str(e))


async def get_historical_prices_get(request: Request) -> JSONResponse:
    """Get historical OHLCV data (GET endpoint)."""
    try:
        symbol = request.path_params["symbol"]
        yahoo_symbol = request.query_params.get("yahoo_symbol")
        period = request.query_params.get("period", "1y")
        interval = request.query_params.get("interval", "1d")

        prices = service.get_historical_prices(symbol, yahoo_symbol, period, interval)

        # Convert Pydantic models to dict for JSON serialization
        prices_dict = [price.dict() if hasattr(price, "dict") else price for price in prices]

        return success_response(
            {
                "symbol": symbol,
                "prices": prices_dict,
            }
        )
    except Exception as e:
        logger.exception(f"Error getting historical prices for {symbol}")
        return error_response(str(e))


# Fundamental data endpoints
async def get_fundamentals(request: Request) -> JSONResponse:
    """Get fundamental analysis data."""
    try:
        symbol = request.path_params["symbol"]
        yahoo_symbol = request.query_params.get("yahoo_symbol")

        data = service.get_fundamental_data(symbol, yahoo_symbol)
        if data:
            return success_response(data.dict() if hasattr(data, "dict") else data)
        return error_response(f"No fundamental data available for {symbol}")
    except Exception as e:
        logger.exception(f"Error getting fundamentals for {symbol}")
        return error_response(str(e))


# Analyst data endpoints
async def get_analyst_data(request: Request) -> JSONResponse:
    """Get analyst recommendations and price targets."""
    try:
        symbol = request.path_params["symbol"]
        yahoo_symbol = request.query_params.get("yahoo_symbol")

        data = service.get_analyst_data(symbol, yahoo_symbol)
        if data:
            return success_response(data.dict() if hasattr(data, "dict") else data)
        return error_response(f"No analyst data available for {symbol}")
    except Exception as e:
        logger.exception(f"Error getting analyst data for {symbol}")
        return error_response(str(e))


# Security info endpoints
async def get_security_industry(request: Request) -> JSONResponse:
    """Get security industry/sector."""
    try:
        symbol = request.path_params["symbol"]
        yahoo_symbol = request.query_params.get("yahoo_symbol")

        data = service.get_security_industry(symbol, yahoo_symbol)
        if data:
            return success_response(data.dict() if hasattr(data, "dict") else data)
        return error_response(f"No industry data available for {symbol}")
    except Exception as e:
        logger.exception(f"Error getting industry for {symbol}")
        return error_response(str(e))


async def get_security_country_exchange(request: Request) -> JSONResponse:
    """Get security country and exchange."""
    try:
        symbol = request.path_params["symbol"]
        yahoo_symbol = request.query_params.get("yahoo_symbol")

        data = service.get_security_country_exchange(symbol, yahoo_symbol)
        if data:
            return success_response(data.dict() if hasattr(data, "dict") else data)
        return error_response(f"No country/exchange data available for {symbol}")
    except Exception as e:
        logger.exception(f"Error getting country/exchange for {symbol}")
        return error_response(str(e))


async def get_security_info(request: Request) -> JSONResponse:
    """Get comprehensive security information."""
    try:
        symbol = request.path_params["symbol"]
        yahoo_symbol = request.query_params.get("yahoo_symbol")

        data = service.get_security_info(symbol, yahoo_symbol)
        if data:
            return success_response(data.dict() if hasattr(data, "dict") else data)
        return error_response(f"No security info available for {symbol}")
    except Exception as e:
        logger.exception(f"Error getting security info for {symbol}")
        return error_response(str(e))


# Define routes
routes = [
    Route("/health", health_check, methods=["GET"]),
    Route("/api/quotes/{symbol}", get_quote, methods=["GET"]),
    Route("/api/quotes/batch", get_batch_quotes, methods=["POST"]),
    Route("/api/historical", get_historical_prices_post, methods=["POST"]),
    Route("/api/historical/{symbol}", get_historical_prices_get, methods=["GET"]),
    Route("/api/fundamentals/{symbol}", get_fundamentals, methods=["GET"]),
    Route("/api/analyst/{symbol}", get_analyst_data, methods=["GET"]),
    Route("/api/security/industry/{symbol}", get_security_industry, methods=["GET"]),
    Route(
        "/api/security/country-exchange/{symbol}",
        get_security_country_exchange,
        methods=["GET"],
    ),
    Route("/api/security/info/{symbol}", get_security_info, methods=["GET"]),
]

# Create Starlette app
app = Starlette(
    routes=routes,
    debug=False,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Startup/shutdown events (if needed)
@app.on_event("startup")
async def startup_event():
    """Startup event."""
    logger.info(f"{settings.service_name} starting up...")


@app.on_event("shutdown")
async def shutdown_event():
    """Shutdown event."""
    logger.info(f"{settings.service_name} shutting down...")

