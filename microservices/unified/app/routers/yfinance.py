"""YFinance router for unified microservice."""

import logging
from typing import Optional

from app.models.yfinance_models import (
    BatchQuotesRequest,
    HistoricalPricesRequest,
    HistoricalPricesResponse,
    ServiceResponse,
)
from app.services.yfinance_service import get_yahoo_finance_service
from fastapi import APIRouter, Query

logger = logging.getLogger(__name__)

router = APIRouter()

# Get service instance
service = get_yahoo_finance_service()


# Quote endpoints
@router.get("/api/quotes/{symbol}", response_model=ServiceResponse)
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


@router.post("/api/quotes/batch", response_model=ServiceResponse)
async def get_batch_quotes(request: BatchQuotesRequest) -> ServiceResponse:
    """Get current prices for multiple symbols."""
    try:
        quotes = service.get_batch_quotes(request.symbols, request.yahoo_overrides)
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
@router.post("/api/historical", response_model=ServiceResponse)
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
            data=HistoricalPricesResponse(symbol=request.symbol, prices=prices).dict(),
        )
    except Exception as e:
        logger.exception(f"Error getting historical prices for {request.symbol}")
        return ServiceResponse(
            success=False,
            error=str(e),
        )


@router.get("/api/historical/{symbol}", response_model=ServiceResponse)
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
@router.get("/api/fundamentals/{symbol}", response_model=ServiceResponse)
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
@router.get("/api/analyst/{symbol}", response_model=ServiceResponse)
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
@router.get("/api/security/industry/{symbol}", response_model=ServiceResponse)
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


@router.get("/api/security/country-exchange/{symbol}", response_model=ServiceResponse)
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


@router.get("/api/security/info/{symbol}", response_model=ServiceResponse)
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


@router.get("/api/security/lookup-ticker/{isin}", response_model=ServiceResponse)
async def lookup_ticker_from_isin(isin: str) -> ServiceResponse:
    """Lookup ticker symbol from ISIN."""
    try:
        ticker = service.lookup_ticker_from_isin(isin)
        if ticker:
            return ServiceResponse(
                success=True,
                data={"isin": isin, "ticker": ticker},
            )
        return ServiceResponse(
            success=False,
            error=f"No ticker found for ISIN {isin}",
        )
    except Exception as e:
        logger.exception(f"Error looking up ticker for ISIN {isin}")
        return ServiceResponse(
            success=False,
            error=str(e),
        )


@router.get("/api/security/quote-name/{symbol}", response_model=ServiceResponse)
async def get_quote_name(
    symbol: str, yahoo_symbol: Optional[str] = Query(default=None)
) -> ServiceResponse:
    """Get security name (longName or shortName)."""
    try:
        name = service.get_quote_name(symbol, yahoo_symbol)
        if name:
            return ServiceResponse(
                success=True,
                data={"symbol": symbol, "name": name},
            )
        return ServiceResponse(
            success=False,
            error=f"No name available for {symbol}",
        )
    except Exception as e:
        logger.exception(f"Error getting quote name for {symbol}")
        return ServiceResponse(
            success=False,
            error=str(e),
        )


@router.get("/api/security/quote-type/{symbol}", response_model=ServiceResponse)
async def get_quote_type(
    symbol: str, yahoo_symbol: Optional[str] = Query(default=None)
) -> ServiceResponse:
    """Get quote type from Yahoo Finance."""
    try:
        quote_type = service.get_quote_type(symbol, yahoo_symbol)
        if quote_type:
            return ServiceResponse(
                success=True,
                data={"symbol": symbol, "quote_type": quote_type},
            )
        return ServiceResponse(
            success=False,
            error=f"No quote type available for {symbol}",
        )
    except Exception as e:
        logger.exception(f"Error getting quote type for {symbol}")
        return ServiceResponse(
            success=False,
            error=str(e),
        )
