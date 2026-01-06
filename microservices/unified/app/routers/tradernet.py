"""Tradernet router for unified microservice."""

import logging
from datetime import datetime
from typing import Optional

from app.models.tradernet_models import (
    BatchQuotesRequest,
    PlaceOrderRequest,
    ServiceResponse,
)
from app.services.tradernet_service import get_tradernet_service
from fastapi import APIRouter, Query, Request

logger = logging.getLogger(__name__)

router = APIRouter()

# Get service instance
service = get_tradernet_service()


def get_credentials(request: Request) -> tuple[Optional[str], Optional[str]]:
    """Extract API credentials from request headers.

    Args:
        request: FastAPI request object

    Returns:
        Tuple of (api_key, api_secret) or (None, None) if not provided
    """
    api_key = request.headers.get("X-Tradernet-API-Key")
    api_secret = request.headers.get("X-Tradernet-API-Secret")
    return api_key, api_secret


# Trading endpoints
@router.post("/api/trading/place-order", response_model=ServiceResponse)
async def place_order(
    request: PlaceOrderRequest, http_request: Request
) -> ServiceResponse:
    """Execute a trade order."""
    try:
        api_key, api_secret = get_credentials(http_request)
        result = service.place_order(
            symbol=request.symbol,
            side=request.side,
            quantity=request.quantity,
            api_key=api_key,
            api_secret=api_secret,
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


@router.get("/api/trading/pending-orders", response_model=ServiceResponse)
async def get_pending_orders(request: Request) -> ServiceResponse:
    """Get all pending/active orders."""
    try:
        api_key, api_secret = get_credentials(request)
        orders = service.get_pending_orders(api_key=api_key, api_secret=api_secret)
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


@router.get("/api/trading/pending-orders/{symbol}", response_model=ServiceResponse)
async def check_pending_order(symbol: str, request: Request) -> ServiceResponse:
    """Check if symbol has any pending orders."""
    try:
        api_key, api_secret = get_credentials(request)
        has_pending = service.has_pending_order_for_symbol(
            symbol, api_key=api_key, api_secret=api_secret
        )
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


@router.get("/api/trading/pending-totals", response_model=ServiceResponse)
async def get_pending_totals(request: Request) -> ServiceResponse:
    """Get total value of pending BUY orders by currency."""
    try:
        api_key, api_secret = get_credentials(request)
        totals = service.get_pending_order_totals(
            api_key=api_key, api_secret=api_secret
        )
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
@router.get("/api/portfolio/positions", response_model=ServiceResponse)
async def get_portfolio_positions(request: Request) -> ServiceResponse:
    """Get current portfolio positions."""
    try:
        api_key, api_secret = get_credentials(request)
        positions = service.get_portfolio(api_key=api_key, api_secret=api_secret)
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


@router.get("/api/portfolio/cash-balances", response_model=ServiceResponse)
async def get_cash_balances(request: Request) -> ServiceResponse:
    """Get cash balances in all currencies."""
    try:
        api_key, api_secret = get_credentials(request)
        balances = service.get_cash_balances(api_key=api_key, api_secret=api_secret)
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


@router.get("/api/portfolio/cash-total-eur", response_model=ServiceResponse)
async def get_cash_total_eur(request: Request) -> ServiceResponse:
    """Get total cash balance in EUR."""
    try:
        api_key, api_secret = get_credentials(request)
        total = service.get_total_cash_eur(api_key=api_key, api_secret=api_secret)
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
@router.get("/api/transactions/cash-movements", response_model=ServiceResponse)
async def get_cash_movements(request: Request) -> ServiceResponse:
    """Get withdrawal history."""
    try:
        api_key, api_secret = get_credentials(request)
        movements = service.get_cash_movements(api_key=api_key, api_secret=api_secret)
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


@router.get("/api/transactions/cash-flows", response_model=ServiceResponse)
async def get_cash_flows(
    request: Request,
    limit: int = Query(default=1000, ge=1, le=5000),
) -> ServiceResponse:
    """Get all cash flow transactions."""
    try:
        api_key, api_secret = get_credentials(request)
        transactions = service.get_all_cash_flows(
            limit=limit, api_key=api_key, api_secret=api_secret
        )
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


@router.get("/api/transactions/executed-trades", response_model=ServiceResponse)
async def get_executed_trades(
    request: Request,
    limit: int = Query(default=500, ge=1, le=1000),
) -> ServiceResponse:
    """Get executed trade history."""
    try:
        api_key, api_secret = get_credentials(request)
        trades = service.get_executed_trades(
            limit=limit, api_key=api_key, api_secret=api_secret
        )
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
@router.get("/api/market-data/quote/{symbol:path}", response_model=ServiceResponse)
async def get_quote(symbol: str, request: Request) -> ServiceResponse:
    """Get current quote for a symbol.

    Uses :path converter to allow symbols with slashes (e.g., HKD/EUR).
    """
    try:
        api_key, api_secret = get_credentials(request)
        quote = service.get_quote(symbol, api_key=api_key, api_secret=api_secret)
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


@router.post("/api/market-data/quotes", response_model=ServiceResponse)
async def get_quotes(
    request: BatchQuotesRequest, http_request: Request
) -> ServiceResponse:
    """Get quotes for multiple symbols."""
    try:
        api_key, api_secret = get_credentials(http_request)
        quotes = service.get_quotes_raw(
            request.symbols, api_key=api_key, api_secret=api_secret
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


@router.get("/api/market-data/historical/{symbol:path}", response_model=ServiceResponse)
async def get_historical(
    symbol: str,
    request: Request,
    start: Optional[str] = Query(default=None, description="Start date YYYY-MM-DD"),
    end: Optional[str] = Query(default=None, description="End date YYYY-MM-DD"),
) -> ServiceResponse:
    """Get historical OHLC data."""
    try:
        api_key, api_secret = get_credentials(request)
        # Parse dates
        start_dt = datetime.strptime(start, "%Y-%m-%d") if start else None
        end_dt = datetime.strptime(end, "%Y-%m-%d") if end else None

        candles = service.get_historical_prices(
            symbol, start=start_dt, end=end_dt, api_key=api_key, api_secret=api_secret
        )
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
@router.get("/api/securities/find", response_model=ServiceResponse)
async def find_symbol(
    request: Request,
    symbol: str = Query(..., description="Symbol or ISIN to search"),
    exchange: Optional[str] = Query(default=None, description="Exchange filter"),
) -> ServiceResponse:
    """Find security by symbol or ISIN."""
    try:
        api_key, api_secret = get_credentials(request)
        result = service.find_symbol(
            symbol, exchange=exchange, api_key=api_key, api_secret=api_secret
        )
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


@router.get("/api/securities/info/{symbol}", response_model=ServiceResponse)
async def get_security_info(symbol: str, request: Request) -> ServiceResponse:
    """Get security metadata (lot size, etc.)."""
    try:
        api_key, api_secret = get_credentials(request)
        info = service.get_security_info(symbol, api_key=api_key, api_secret=api_secret)
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
