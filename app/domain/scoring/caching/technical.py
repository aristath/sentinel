"""
Technical Indicators - Caching layer for technical calculations.

This module provides caching wrappers around pure calculation functions.
Calculation functions are in app.domain.scoring.calculations.
"""

import logging
from typing import Optional, Tuple

import numpy as np

# Import pure calculation functions
from app.domain.scoring.calculations import (
    calculate_bollinger_bands,
    calculate_ema,
    calculate_max_drawdown,
    calculate_rsi,
    calculate_sharpe_ratio,
    calculate_volatility,
)
from app.domain.scoring.constants import (
    BOLLINGER_LENGTH,
    BOLLINGER_STD,
    EMA_LENGTH,
    RSI_LENGTH,
)

logger = logging.getLogger(__name__)


async def get_ema(
    symbol: str, closes: np.ndarray, length: int = EMA_LENGTH
) -> Optional[float]:
    """
    Get EMA value from cache or calculate it.

    Args:
        symbol: Stock symbol
        closes: Array of closing prices
        length: EMA period (default 200)

    Returns:
        Current EMA value or None if insufficient data
    """
    from app.repositories.calculations import CalculationsRepository

    calc_repo = CalculationsRepository()
    metric_name = f"EMA_{length}"

    # Check cache first
    cached = await calc_repo.get_metric(symbol, metric_name)
    if cached is not None:
        return cached

    # Calculate if not cached
    ema = calculate_ema(closes, length)
    if ema is not None:
        await calc_repo.set_metric(symbol, metric_name, ema)

    return ema


async def get_rsi(
    symbol: str, closes: np.ndarray, length: int = RSI_LENGTH
) -> Optional[float]:
    """
    Get RSI value from cache or calculate it.

    Args:
        symbol: Stock symbol
        closes: Array of closing prices
        length: RSI period (default 14)

    Returns:
        Current RSI value (0-100) or None if insufficient data
    """
    from app.repositories.calculations import CalculationsRepository

    calc_repo = CalculationsRepository()
    metric_name = f"RSI_{length}"

    # Check cache first
    cached = await calc_repo.get_metric(symbol, metric_name)
    if cached is not None:
        return cached

    # Calculate if not cached
    rsi = calculate_rsi(closes, length)
    if rsi is not None:
        await calc_repo.set_metric(symbol, metric_name, rsi)

    return rsi


async def get_bollinger_bands(
    symbol: str,
    closes: np.ndarray,
    length: int = BOLLINGER_LENGTH,
    std: float = BOLLINGER_STD,
) -> Optional[Tuple[float, float, float]]:
    """
    Get Bollinger Bands from cache or calculate them.

    Args:
        symbol: Stock symbol
        closes: Array of closing prices
        length: BB period (default 20)
        std: Standard deviation multiplier (default 2)

    Returns:
        Tuple of (lower, middle, upper) or None if insufficient data
    """
    from app.repositories.calculations import CalculationsRepository

    calc_repo = CalculationsRepository()

    # Check cache for all three components
    metrics = await calc_repo.get_metrics(symbol, ["BB_LOWER", "BB_MIDDLE", "BB_UPPER"])
    if all(v is not None for v in metrics.values()):
        return metrics["BB_LOWER"], metrics["BB_MIDDLE"], metrics["BB_UPPER"]

    # Calculate if not cached
    bands = calculate_bollinger_bands(closes, length, std)
    if bands is not None:
        lower, middle, upper = bands
        await calc_repo.set_metrics(
            symbol,
            {
                "BB_LOWER": lower,
                "BB_MIDDLE": middle,
                "BB_UPPER": upper,
            },
        )

    return bands


async def get_sharpe_ratio(
    symbol: str, closes: np.ndarray, risk_free_rate: float = 0.0
) -> Optional[float]:
    """
    Get Sharpe ratio from cache or calculate it.

    Args:
        symbol: Stock symbol
        closes: Array of closing prices
        risk_free_rate: Risk-free rate (default 0)

    Returns:
        Annualized Sharpe ratio or None if insufficient data
    """
    from app.repositories.calculations import CalculationsRepository

    calc_repo = CalculationsRepository()

    # Check cache first
    cached = await calc_repo.get_metric(symbol, "SHARPE")
    if cached is not None:
        return cached

    # Calculate if not cached
    sharpe = calculate_sharpe_ratio(closes, risk_free_rate)
    if sharpe is not None:
        await calc_repo.set_metric(symbol, "SHARPE", sharpe)

    return sharpe


async def get_max_drawdown(symbol: str, closes: np.ndarray) -> Optional[float]:
    """
    Get max drawdown from cache or calculate it.

    Args:
        symbol: Stock symbol
        closes: Array of closing prices

    Returns:
        Maximum drawdown as negative percentage (e.g., -0.20 = 20% drawdown)
        or None if insufficient data
    """
    from app.repositories.calculations import CalculationsRepository

    calc_repo = CalculationsRepository()

    # Check cache first
    cached = await calc_repo.get_metric(symbol, "MAX_DRAWDOWN")
    if cached is not None:
        return cached

    # Calculate if not cached
    mdd = calculate_max_drawdown(closes)
    if mdd is not None:
        await calc_repo.set_metric(symbol, "MAX_DRAWDOWN", mdd)

    return mdd


async def get_52_week_high(symbol: str, highs: np.ndarray) -> float:
    """
    Get 52-week high price from cache or calculate it.

    Args:
        symbol: Stock symbol
        highs: Array of high prices (at least 252 days for full year)

    Returns:
        52-week high price
    """
    from app.repositories.calculations import CalculationsRepository

    calc_repo = CalculationsRepository()

    # Check cache first
    cached = await calc_repo.get_metric(symbol, "HIGH_52W")
    if cached is not None:
        return cached

    # Calculate if not cached
    high_52w = _calculate_52_week_high(highs)
    await calc_repo.set_metric(symbol, "HIGH_52W", high_52w)

    return high_52w


def _calculate_52_week_high(highs: np.ndarray) -> float:
    """
    Calculate 52-week high price (internal function).

    Args:
        highs: Array of high prices (at least 252 days for full year)

    Returns:
        52-week high price
    """
    if len(highs) >= 252:
        return float(max(highs[-252:]))
    return float(max(highs))


async def get_52_week_low(symbol: str, lows: np.ndarray) -> float:
    """
    Get 52-week low price from cache or calculate it.

    Args:
        symbol: Stock symbol
        lows: Array of low prices (at least 252 days for full year)

    Returns:
        52-week low price
    """
    from app.repositories.calculations import CalculationsRepository

    calc_repo = CalculationsRepository()

    # Check cache first
    cached = await calc_repo.get_metric(symbol, "LOW_52W")
    if cached is not None:
        return cached

    # Calculate if not cached
    low_52w = _calculate_52_week_low(lows)
    await calc_repo.set_metric(symbol, "LOW_52W", low_52w)

    return low_52w


def _calculate_52_week_low(lows: np.ndarray) -> float:
    """
    Calculate 52-week low price (internal function).

    Args:
        lows: Array of low prices (at least 252 days for full year)

    Returns:
        52-week low price
    """
    if len(lows) >= 252:
        return float(min(lows[-252:]))
    return float(min(lows))


def calculate_distance_from_ma(current_price: float, ma_value: float) -> float:
    """
    Calculate percentage distance from moving average.

    Args:
        current_price: Current price
        ma_value: Moving average value

    Returns:
        Percentage distance (positive = above, negative = below)
    """
    if ma_value <= 0:
        return 0.0

    return (current_price - ma_value) / ma_value
