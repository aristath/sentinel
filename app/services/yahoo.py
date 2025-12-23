"""Yahoo Finance service for analyst data and fundamentals."""

import logging
from contextlib import contextmanager
from datetime import datetime
from typing import Optional
from dataclasses import dataclass

import yfinance as yf

from app.infrastructure.events import emit, SystemEvent

logger = logging.getLogger(__name__)


@contextmanager
def _led_api_call():
    """Context manager to emit events during API calls for LED indication."""
    emit(SystemEvent.API_CALL_START)
    try:
        yield
    finally:
        emit(SystemEvent.API_CALL_END)


@dataclass
class AnalystData:
    """Analyst recommendation data."""
    symbol: str
    recommendation: str  # strongBuy, buy, hold, sell, strongSell
    target_price: float
    current_price: float
    upside_pct: float
    num_analysts: int
    recommendation_score: float  # 0-1 normalized score


@dataclass
class FundamentalData:
    """Fundamental analysis data."""
    symbol: str
    pe_ratio: Optional[float]
    forward_pe: Optional[float]
    peg_ratio: Optional[float]
    price_to_book: Optional[float]
    revenue_growth: Optional[float]
    earnings_growth: Optional[float]
    profit_margin: Optional[float]
    operating_margin: Optional[float]
    roe: Optional[float]
    debt_to_equity: Optional[float]
    current_ratio: Optional[float]
    market_cap: Optional[float]
    dividend_yield: Optional[float]
    five_year_avg_dividend_yield: Optional[float]  # For DRIP scoring


@dataclass
class HistoricalPrice:
    """Historical price data."""
    date: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int
    adj_close: float


def get_yahoo_symbol(tradernet_symbol: str, yahoo_override: str = None) -> str:
    """
    Convert Tradernet symbol format to Yahoo Finance format.

    Uses explicit override if provided, otherwise applies conventions:
    - US stocks (.US): Strip suffix (AAPL.US -> AAPL)
    - Greek stocks (.GR): Convert to Athens (.GR -> .AT)
    - Other suffixes: Keep as-is

    Args:
        tradernet_symbol: Symbol in Tradernet format
        yahoo_override: Explicit Yahoo symbol (used for Asian stocks with different formats)

    Returns:
        Yahoo Finance compatible symbol
    """
    if yahoo_override:
        return yahoo_override

    symbol = tradernet_symbol.upper()

    # US stocks: strip .US suffix
    if symbol.endswith(".US"):
        return symbol[:-3]

    # Greek stocks: .GR -> .AT (Athens Exchange)
    if symbol.endswith(".GR"):
        return symbol[:-3] + ".AT"

    return symbol


# Removed _normalize_symbol() - use get_yahoo_symbol() instead


def get_analyst_data(symbol: str, yahoo_symbol: str = None) -> Optional[AnalystData]:
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
            current_price = info.get("currentPrice") or info.get("regularMarketPrice", 0) or 0

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


def get_fundamental_data(symbol: str, yahoo_symbol: str = None) -> Optional[FundamentalData]:
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
    symbol: str,
    yahoo_symbol: str = None,
    period: str = "1y"
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
            result.append(HistoricalPrice(
                date=date.to_pydatetime(),
                open=float(row["Open"]),
                high=float(row["High"]),
                low=float(row["Low"]),
                close=float(row["Close"]),
                volume=int(row["Volume"]),
                adj_close=float(row.get("Adj Close", row["Close"])),
            ))

        return result
    except Exception as e:
        logger.error(f"Failed to get historical prices for {symbol}: {e}")
        return []


def get_current_price(symbol: str, yahoo_symbol: str = None, max_retries: int = None) -> Optional[float]:
    """
    Get current stock price with retry logic.

    Args:
        symbol: Stock symbol (Tradernet format)
        yahoo_symbol: Optional explicit Yahoo symbol override
        max_retries: Maximum number of retry attempts (default: from config)

    Returns:
        Current price or None if all retries fail
    """
    import time
    from app.config import settings
    
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
                    wait_time = settings.price_fetch_retry_delay_base * (2 ** attempt)  # Exponential backoff
                    logger.warning(f"Price fetch returned invalid value for {symbol}, retrying in {wait_time}s...")
                    time.sleep(wait_time)
        except Exception as e:
            if attempt < max_retries - 1:
                wait_time = settings.price_fetch_retry_delay_base * (2 ** attempt)  # Exponential backoff
                logger.warning(f"Failed to get current price for {symbol} (attempt {attempt + 1}/{max_retries}): {e}. Retrying in {wait_time}s...")
                time.sleep(wait_time)
            else:
                logger.error(f"Failed to get current price for {symbol} after {max_retries} attempts: {e}")
    
    return None


def get_stock_industry(symbol: str, yahoo_symbol: str = None) -> Optional[str]:
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
            if any(term in industry_lower for term in [
                "technology", "software", "semiconductor", "internet",
                "computer", "electronic", "telecom"
            ]):
                return "Technology"

            # Healthcare
            if any(term in industry_lower for term in [
                "health", "medical", "pharma", "biotech", "drug"
            ]):
                return "Healthcare"

            # Finance
            if any(term in industry_lower for term in [
                "bank", "financial", "insurance", "capital", "asset"
            ]):
                return "Finance"

            # Consumer
            if any(term in industry_lower for term in [
                "consumer", "retail", "food", "beverage", "apparel",
                "luxury", "entertainment", "media"
            ]):
                return "Consumer"

            # Industrial
            if any(term in industry_lower for term in [
                "industrial", "aerospace", "defense", "machinery",
                "construction", "transport", "auto"
            ]):
                return "Industrial"

            # Energy (map to Industrial for now)
            if any(term in industry_lower for term in [
                "energy", "oil", "gas", "utilities", "power"
            ]):
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
            data = yf.download(
                tickers=" ".join(yf_symbols),
                period="1d",
                progress=False,
                threads=True
            )

            if not data.empty:
                # Handle single vs multiple symbols
                if len(yf_symbols) == 1:
                    yf_sym = yf_symbols[0]
                    orig_sym = symbol_map[yf_sym]
                    result[orig_sym] = float(data["Close"].iloc[-1])
                else:
                    for yf_sym in yf_symbols:
                        orig_sym = symbol_map[yf_sym]
                        if yf_sym in data["Close"].columns:
                            price = data["Close"][yf_sym].iloc[-1]
                            if not pd.isna(price):
                                result[orig_sym] = float(price)

    except Exception as e:
        logger.error(f"Failed to get batch quotes: {e}")

    return result


# Import pandas for batch quotes
try:
    import pandas as pd
except ImportError:
    pd = None
