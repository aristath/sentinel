"""Yahoo Finance data fetching functions.

Handles fetching analyst data, fundamentals, prices, and industry information.
"""

import logging
import time
from contextlib import contextmanager
from typing import Optional

import yfinance as yf

from app.config import settings
from app.infrastructure.events import SystemEvent, emit
from app.infrastructure.external.yahoo.models import (
    AnalystData,
    FundamentalData,
    HistoricalPrice,
)
from app.infrastructure.external.yahoo.symbol_converter import get_yahoo_symbol

logger = logging.getLogger(__name__)


@contextmanager
def _led_api_call():
    """Context manager to emit events during API calls for LED indication."""
    emit(SystemEvent.API_CALL_START)
    try:
        yield
    finally:
        emit(SystemEvent.API_CALL_END)


def get_analyst_data(symbol: str, yahoo_symbol: Optional[str] = None) -> Optional[AnalystData]:
    """
    Get analyst recommendations and price targets.

    Args:
        symbol: Stock symbol (Tradernet format)
        yahoo_symbol: Optional explicit Yahoo symbol override

    Returns:
        AnalystData if available, None otherwise
    """
    yf_symbol = get_yahoo_symbol(symbol, yahoo_symbol)

    try:
        with _led_api_call():
            ticker = yf.Ticker(yf_symbol)
            info = ticker.info

            # Get recommendation
            recommendation = info.get("recommendationKey", "hold")

            # Get price targets
            target_price = info.get("targetMeanPrice", 0) or 0
            current_price = (
                info.get("currentPrice") or info.get("regularMarketPrice", 0) or 0
            )

            # Calculate upside
            upside_pct = 0.0
            if current_price > 0 and target_price > 0:
                upside_pct = ((target_price - current_price) / current_price) * 100

            # Number of analysts
            num_analysts = info.get("numberOfAnalystOpinions", 0) or 0

            # Convert recommendation to score (0-1)
            rec_scores = {
                "strongBuy": 1.0,
                "buy": 0.8,
                "hold": 0.5,
                "sell": 0.2,
                "strongSell": 0.0,
            }
            recommendation_score = rec_scores.get(recommendation, 0.5)

            return AnalystData(
                symbol=symbol,
                recommendation=recommendation,
                target_price=target_price,
                current_price=current_price,
                upside_pct=upside_pct,
                num_analysts=num_analysts,
                recommendation_score=recommendation_score,
            )
    except Exception as e:
        logger.error(f"Failed to get analyst data for {symbol}: {e}")
        return None


def get_fundamental_data(
    symbol: str, yahoo_symbol: Optional[str] = None
) -> Optional[FundamentalData]:
    """
    Get fundamental analysis data.

    Args:
        symbol: Stock symbol (Tradernet format)
        yahoo_symbol: Optional explicit Yahoo symbol override

    Returns:
        FundamentalData if available, None otherwise
    """
    yf_symbol = get_yahoo_symbol(symbol, yahoo_symbol)

    try:
        with _led_api_call():
            ticker = yf.Ticker(yf_symbol)
            info = ticker.info

            return FundamentalData(
                symbol=symbol,
                pe_ratio=info.get("trailingPE"),
                forward_pe=info.get("forwardPE"),
                peg_ratio=info.get("pegRatio"),
                price_to_book=info.get("priceToBook"),
                revenue_growth=info.get("revenueGrowth"),
                earnings_growth=info.get("earningsGrowth"),
                profit_margin=info.get("profitMargins"),
                operating_margin=info.get("operatingMargins"),
                roe=info.get("returnOnEquity"),
                debt_to_equity=info.get("debtToEquity"),
                current_ratio=info.get("currentRatio"),
                market_cap=info.get("marketCap"),
                dividend_yield=info.get("dividendYield"),
                five_year_avg_dividend_yield=info.get("fiveYearAvgDividendYield"),
            )
    except Exception as e:
        logger.error(f"Failed to get fundamental data for {symbol}: {e}")
        return None


def get_historical_prices(
    symbol: str, yahoo_symbol: Optional[str] = None, period: str = "1y"
) -> list[HistoricalPrice]:
    """
    Get historical price data.

    Args:
        symbol: Stock symbol (Tradernet format)
        yahoo_symbol: Optional explicit Yahoo symbol override
        period: Time period (1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max)

    Returns:
        List of HistoricalPrice objects
    """
    yf_symbol = get_yahoo_symbol(symbol, yahoo_symbol)

    try:
        ticker = yf.Ticker(yf_symbol)
        hist = ticker.history(period=period)

        result = []
        for date, row in hist.iterrows():
            result.append(
                HistoricalPrice(
                    date=date.to_pydatetime(),
                    open=float(row["Open"]),
                    high=float(row["High"]),
                    low=float(row["Low"]),
                    close=float(row["Close"]),
                    volume=int(row["Volume"]),
                    adj_close=float(row.get("Adj Close", row["Close"])),
                )
            )

        return result
    except Exception as e:
        logger.error(f"Failed to get historical prices for {symbol}: {e}")
        return []


def get_current_price(
    symbol: str, yahoo_symbol: Optional[str] = None, max_retries: Optional[int] = None
) -> Optional[float]:
    """
    Get current stock price with retry logic.

    Args:
        symbol: Stock symbol (Tradernet format)
        yahoo_symbol: Optional explicit Yahoo symbol override
        max_retries: Maximum number of retry attempts (default: from config)

    Returns:
        Current price or None if all retries fail
    """
    if max_retries is None:
        max_retries = settings.price_fetch_max_retries

    yf_symbol = get_yahoo_symbol(symbol, yahoo_symbol)

    for attempt in range(max_retries):
        try:
            with _led_api_call():
                ticker = yf.Ticker(yf_symbol)
                info = ticker.info
                price = info.get("currentPrice") or info.get("regularMarketPrice")
                if price and price > 0:
                    return price
                # If price is 0 or None, retry
                if attempt < max_retries - 1:
                    wait_time = settings.price_fetch_retry_delay_base * (
                        2**attempt
                    )  # Exponential backoff
                    logger.warning(
                        f"Price fetch returned invalid value for {symbol}, retrying in {wait_time}s..."
                    )
                    time.sleep(wait_time)
        except Exception as e:
            if attempt < max_retries - 1:
                wait_time = settings.price_fetch_retry_delay_base * (
                    2**attempt
                )  # Exponential backoff
                logger.warning(
                    f"Failed to get current price for {symbol} (attempt {attempt + 1}/{max_retries}): {e}. Retrying in {wait_time}s..."
                )
                time.sleep(wait_time)
            else:
                logger.error(
                    f"Failed to get current price for {symbol} after {max_retries} attempts: {e}"
                )

    return None


def get_stock_industry(symbol: str, yahoo_symbol: Optional[str] = None) -> Optional[str]:
    """
    Get stock industry/sector from Yahoo Finance.

    Args:
        symbol: Stock symbol (Tradernet format)
        yahoo_symbol: Optional explicit Yahoo symbol override

    Returns:
        Industry name or None
    """
    yf_symbol = get_yahoo_symbol(symbol, yahoo_symbol)

    try:
        ticker = yf.Ticker(yf_symbol)
        info = ticker.info

        # Try industry first, then sector
        industry = info.get("industry") or info.get("sector")

        # Normalize common industry names to our categories
        if industry:
            industry_lower = industry.lower()

            # Technology
            if any(
                term in industry_lower
                for term in [
                    "technology",
                    "software",
                    "semiconductor",
                    "internet",
                    "computer",
                    "electronic",
                    "telecom",
                ]
            ):
                return "Technology"

            # Healthcare
            if any(
                term in industry_lower
                for term in ["health", "medical", "pharma", "biotech", "drug"]
            ):
                return "Healthcare"

            # Finance
            if any(
                term in industry_lower
                for term in ["bank", "financial", "insurance", "capital", "asset"]
            ):
                return "Finance"

            # Consumer
            if any(
                term in industry_lower
                for term in [
                    "consumer",
                    "retail",
                    "food",
                    "beverage",
                    "apparel",
                    "luxury",
                    "entertainment",
                    "media",
                ]
            ):
                return "Consumer"

            # Industrial
            if any(
                term in industry_lower
                for term in [
                    "industrial",
                    "aerospace",
                    "defense",
                    "machinery",
                    "construction",
                    "transport",
                    "auto",
                ]
            ):
                return "Industrial"

            # Energy (map to Industrial for now)
            if any(
                term in industry_lower
                for term in ["energy", "oil", "gas", "utilities", "power"]
            ):
                return "Energy"

        return industry  # Return original if no match

    except Exception as e:
        logger.error(f"Failed to get industry for {symbol}: {e}")
        return None


def get_batch_quotes(symbol_yahoo_map: dict[str, Optional[str]]) -> dict[str, float]:
    """
    Get current prices for multiple symbols efficiently.

    Args:
        symbol_yahoo_map: Dict mapping Tradernet symbol to Yahoo symbol override
                          (None values use convention-based derivation)

    Returns:
        Dict mapping Tradernet symbol to current price
    """
    result = {}

    # Convert symbols using overrides where provided
    yf_symbols = []
    symbol_map = {}  # yf_symbol -> tradernet_symbol
    for tradernet_sym, yahoo_override in symbol_yahoo_map.items():
        yf_sym = get_yahoo_symbol(tradernet_sym, yahoo_override)
        yf_symbols.append(yf_sym)
        symbol_map[yf_sym] = tradernet_sym

    try:
        with _led_api_call():
            # Use yfinance download for batch efficiency
            # Use period="5d" to handle markets with different trading schedules
            # (e.g., Christmas Eve: Asian markets open, US/EU closed)
            data = yf.download(
                tickers=" ".join(yf_symbols),
                period="5d",
                progress=False,
                threads=True,
                auto_adjust=True,
            )

            if not data.empty:
                # Handle single vs multiple symbols
                if len(yf_symbols) == 1:
                    yf_sym = yf_symbols[0]
                    orig_sym = symbol_map[yf_sym]
                    # Get last non-NaN value
                    close_series = data["Close"].dropna()
                    if len(close_series) > 0:
                        result[orig_sym] = float(close_series.iloc[-1])
                else:
                    for yf_sym in yf_symbols:
                        orig_sym = symbol_map[yf_sym]
                        if yf_sym in data["Close"].columns:
                            # Get last non-NaN value for this symbol
                            close_series = data["Close"][yf_sym].dropna()
                            if len(close_series) > 0:
                                result[orig_sym] = float(close_series.iloc[-1])

    except Exception as e:
        logger.error(f"Failed to get batch quotes: {e}")

    return result
