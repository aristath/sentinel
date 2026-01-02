"""Tradernet microservice - Main FastAPI application."""

import logging
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.health import router as health_router
from app.models import (
    BatchQuotesRequest,
    PlaceOrderRequest,
    ServiceResponse,
)
from app.service import get_tradernet_service

# Configure logging
logging.basicConfig(
    level=settings.log_level,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title=f"{settings.service_name} API",
    description="Microservice wrapping Tradernet SDK for portfolio management operations",
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
service = get_tradernet_service()


@app.on_event("startup")
async def startup_event():
    """Startup event - connect to Tradernet."""
    logger.info(f"{settings.service_name} starting up...")
    if service.connect():
        logger.info("Successfully connected to Tradernet API")
    else:
        logger.warning("Failed to connect to Tradernet API - check credentials")


@app.on_event("shutdown")
async def shutdown_event():
    """Shutdown event."""
    logger.info(f"{settings.service_name} shutting down...")


# Trading endpoints
@app.post("/api/trading/place-order", response_model=ServiceResponse)
async def place_order(request: PlaceOrderRequest) -> ServiceResponse:
    """Execute a trade order."""
    try:
        result = service.place_order(
            symbol=request.symbol,
            side=request.side,
            quantity=request.quantity,
        )

        if result:
            return ServiceResponse(
                success=True,
                data=result.dict(),
            )

        return ServiceResponse(
            success=False,
            error="Order execution failed",
        )
    except Exception as e:
        logger.exception("Error placing order")
        return ServiceResponse(
            success=False,
            error=str(e),
        )


@app.get("/api/trading/pending-orders", response_model=ServiceResponse)
async def get_pending_orders() -> ServiceResponse:
    """Get all pending/active orders."""
    try:
        orders = service.get_pending_orders()
        return ServiceResponse(
            success=True,
            data={"orders": [o.dict() for o in orders]},
        )
    except Exception as e:
        logger.exception("Error getting pending orders")
        return ServiceResponse(
            success=False,
            error=str(e),
        )


@app.get("/api/trading/pending-orders/{symbol}", response_model=ServiceResponse)
async def check_pending_order(symbol: str) -> ServiceResponse:
    """Check if symbol has any pending orders."""
    try:
        has_pending = service.has_pending_order_for_symbol(symbol)
        return ServiceResponse(
            success=True,
            data={
                "has_pending": has_pending,
                "symbol": symbol,
            },
        )
    except Exception as e:
        logger.exception(f"Error checking pending order for {symbol}")
        return ServiceResponse(
            success=False,
            error=str(e),
        )


@app.get("/api/trading/pending-totals", response_model=ServiceResponse)
async def get_pending_totals() -> ServiceResponse:
    """Get total value of pending BUY orders by currency."""
    try:
        totals = service.get_pending_order_totals()
        return ServiceResponse(
            success=True,
            data={"totals": totals},
        )
    except Exception as e:
        logger.exception("Error getting pending order totals")
        return ServiceResponse(
            success=False,
            error=str(e),
        )


# Portfolio endpoints
@app.get("/api/portfolio/positions", response_model=ServiceResponse)
async def get_portfolio_positions() -> ServiceResponse:
    """Get current portfolio positions."""
    try:
        positions = service.get_portfolio()
        return ServiceResponse(
            success=True,
            data={"positions": [p.dict() for p in positions]},
        )
    except Exception as e:
        logger.exception("Error getting portfolio positions")
        return ServiceResponse(
            success=False,
            error=str(e),
        )


@app.get("/api/portfolio/cash-balances", response_model=ServiceResponse)
async def get_cash_balances() -> ServiceResponse:
    """Get cash balances in all currencies."""
    try:
        balances = service.get_cash_balances()
        return ServiceResponse(
            success=True,
            data={"balances": [b.dict() for b in balances]},
        )
    except Exception as e:
        logger.exception("Error getting cash balances")
        return ServiceResponse(
            success=False,
            error=str(e),
        )


@app.get("/api/portfolio/cash-total-eur", response_model=ServiceResponse)
async def get_cash_total_eur() -> ServiceResponse:
    """Get total cash balance in EUR."""
    try:
        total = service.get_total_cash_eur()
        return ServiceResponse(
            success=True,
            data={"total_eur": total},
        )
    except Exception as e:
        logger.exception("Error getting total cash in EUR")
        return ServiceResponse(
            success=False,
            error=str(e),
        )


# Transaction endpoints
@app.get("/api/transactions/cash-movements", response_model=ServiceResponse)
async def get_cash_movements() -> ServiceResponse:
    """Get withdrawal history."""
    try:
        movements = service.get_cash_movements()
        return ServiceResponse(
            success=True,
            data=movements,
        )
    except Exception as e:
        logger.exception("Error getting cash movements")
        return ServiceResponse(
            success=False,
            error=str(e),
        )


@app.get("/api/transactions/cash-flows", response_model=ServiceResponse)
async def get_cash_flows(
    limit: int = Query(default=1000, ge=1, le=5000)
) -> ServiceResponse:
    """Get all cash flow transactions."""
    try:
        transactions = service.get_all_cash_flows(limit=limit)
        return ServiceResponse(
            success=True,
            data={"transactions": [t.dict() for t in transactions]},
        )
    except Exception as e:
        logger.exception("Error getting cash flows")
        return ServiceResponse(
            success=False,
            error=str(e),
        )


@app.get("/api/transactions/executed-trades", response_model=ServiceResponse)
async def get_executed_trades(
    limit: int = Query(default=500, ge=1, le=1000)
) -> ServiceResponse:
    """Get executed trade history."""
    try:
        trades = service.get_executed_trades(limit=limit)
        return ServiceResponse(
            success=True,
            data={"trades": [t.dict() for t in trades]},
        )
    except Exception as e:
        logger.exception("Error getting executed trades")
        return ServiceResponse(
            success=False,
            error=str(e),
        )


# Market data endpoints
@app.get("/api/market-data/quote/{symbol}", response_model=ServiceResponse)
async def get_quote(symbol: str) -> ServiceResponse:
    """Get current quote for a symbol."""
    try:
        quote = service.get_quote(symbol)
        if quote:
            return ServiceResponse(
                success=True,
                data=quote.dict(),
            )

        return ServiceResponse(
            success=False,
            error=f"No quote available for {symbol}",
        )
    except Exception as e:
        logger.exception(f"Error getting quote for {symbol}")
        return ServiceResponse(
            success=False,
            error=str(e),
        )


@app.post("/api/market-data/quotes", response_model=ServiceResponse)
async def get_quotes(request: BatchQuotesRequest) -> ServiceResponse:
    """Get quotes for multiple symbols."""
    try:
        quotes = service.get_quotes_raw(request.symbols)
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


@app.get("/api/market-data/historical/{symbol}", response_model=ServiceResponse)
async def get_historical(
    symbol: str,
    start: Optional[str] = Query(default=None, description="Start date YYYY-MM-DD"),
    end: Optional[str] = Query(default=None, description="End date YYYY-MM-DD"),
) -> ServiceResponse:
    """Get historical OHLC data."""
    try:
        # Parse dates
        start_dt = datetime.strptime(start, "%Y-%m-%d") if start else None
        end_dt = datetime.strptime(end, "%Y-%m-%d") if end else None

        candles = service.get_historical_prices(symbol, start=start_dt, end=end_dt)
        return ServiceResponse(
            success=True,
            data={
                "symbol": symbol,
                "candles": [c.dict() for c in candles],
            },
        )
    except ValueError as e:
        return ServiceResponse(
            success=False,
            error=f"Invalid date format: {str(e)}",
        )
    except Exception as e:
        logger.exception(f"Error getting historical data for {symbol}")
        return ServiceResponse(
            success=False,
            error=str(e),
        )


# Security lookup endpoints
@app.get("/api/securities/find", response_model=ServiceResponse)
async def find_symbol(
    symbol: str = Query(..., description="Symbol or ISIN to search"),
    exchange: Optional[str] = Query(default=None, description="Exchange filter"),
) -> ServiceResponse:
    """Find security by symbol or ISIN."""
    try:
        result = service.find_symbol(symbol, exchange=exchange)
        return ServiceResponse(
            success=True,
            data=result,
        )
    except Exception as e:
        logger.exception(f"Error finding symbol {symbol}")
        return ServiceResponse(
            success=False,
            error=str(e),
        )


@app.get("/api/securities/info/{symbol}", response_model=ServiceResponse)
async def get_security_info(symbol: str) -> ServiceResponse:
    """Get security metadata (lot size, etc.)."""
    try:
        info = service.get_security_info(symbol)
        if info:
            return ServiceResponse(
                success=True,
                data=info,
            )

        return ServiceResponse(
            success=False,
            error=f"No info available for {symbol}",
        )
    except Exception as e:
        logger.exception(f"Error getting security info for {symbol}")
        return ServiceResponse(
            success=False,
            error=str(e),
        )
