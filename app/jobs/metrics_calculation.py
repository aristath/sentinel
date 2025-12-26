"""
Metrics Calculation Job - Batch calculate and store raw metrics for all active stocks.

This job pre-calculates expensive metrics (RSI, EMA, Sharpe, CAGR, etc.) and stores
them in calculations.db with appropriate TTLs. This improves scoring performance
by avoiding redundant calculations.
"""

import logging

import numpy as np

from app.domain.scoring.caching import (
    get_52_week_high,
    get_52_week_low,
    get_bollinger_bands,
    get_ema,
    get_max_drawdown,
    get_rsi,
    get_sharpe_ratio,
)
from app.domain.scoring.calculations import calculate_cagr
from app.repositories.calculations import CalculationsRepository
from app.repositories.history import HistoryRepository
from app.repositories.stock import StockRepository

logger = logging.getLogger(__name__)


async def _calculate_technical_indicators(
    symbol: str, closes_array: np.ndarray, highs_array: np.ndarray, lows_array: np.ndarray
) -> tuple[int, Optional[float], Optional[float], Optional[tuple]]:
    """Calculate technical indicators and return count and key values."""
    metrics_count = 0

    rsi = await get_rsi(symbol, closes_array)
    if rsi is not None:
        metrics_count += 1

    ema_200 = await get_ema(symbol, closes_array, length=200)
    if ema_200 is not None:
        metrics_count += 1

    ema_50 = await get_ema(symbol, closes_array, length=50)
    if ema_50 is not None:
        metrics_count += 1

    bands = await get_bollinger_bands(symbol, closes_array)
    if bands is not None:
        metrics_count += 3  # Lower, Middle, Upper

    sharpe = await get_sharpe_ratio(symbol, closes_array)
    if sharpe is not None:
        metrics_count += 1

    max_dd = await get_max_drawdown(symbol, closes_array)
    if max_dd is not None:
        metrics_count += 1

    high_52w = await get_52_week_high(symbol, highs_array)
    if high_52w is not None:
        metrics_count += 1

    low_52w = await get_52_week_low(symbol, lows_array)
    if low_52w is not None:
        metrics_count += 1

    return metrics_count, ema_200, high_52w, bands


async def _calculate_cagr_metrics(
    calc_repo, symbol: str, monthly_prices: list
) -> int:
    """Calculate CAGR metrics if monthly data is available."""
    if not monthly_prices or len(monthly_prices) < 12:
        return 0

    metrics_count = 0
    monthly_dicts = [
        {"year_month": p.year_month, "avg_adj_close": p.avg_adj_close}
        for p in monthly_prices
    ]

    cagr_5y = calculate_cagr(monthly_dicts, 60)
    if cagr_5y is not None:
        await calc_repo.set_metric(symbol, "CAGR_5Y", cagr_5y)
        metrics_count += 1

    if len(monthly_prices) > 60:
        cagr_10y = calculate_cagr(monthly_dicts, len(monthly_dicts))
        if cagr_10y is not None:
            await calc_repo.set_metric(symbol, "CAGR_10Y", cagr_10y)
            metrics_count += 1

    return metrics_count


async def _calculate_momentum_metrics(calc_repo, symbol: str, closes: list) -> int:
    """Calculate momentum metrics."""
    if len(closes) < 30:
        return 0

    metrics_count = 0
    current = closes[-1]
    price_30d = closes[-30] if len(closes) >= 30 else closes[0]
    momentum_30d = (current - price_30d) / price_30d if price_30d > 0 else 0
    await calc_repo.set_metric(symbol, "MOMENTUM_30D", momentum_30d)
    metrics_count += 1

    if len(closes) >= 90:
        price_90d = closes[-90]
        momentum_90d = (current - price_90d) / price_90d if price_90d > 0 else 0
        await calc_repo.set_metric(symbol, "MOMENTUM_90D", momentum_90d)
        metrics_count += 1

    return metrics_count


async def _calculate_distance_metrics(
    calc_repo, symbol: str, closes: list, ema_200: Optional[float], high_52w: Optional[float]
) -> int:
    """Calculate distance metrics."""
    metrics_count = 0
    current_price = closes[-1]

    if high_52w:
        distance_from_52w = (high_52w - current_price) / high_52w if high_52w > 0 else 0
        await calc_repo.set_metric(symbol, "DISTANCE_FROM_52W_HIGH", distance_from_52w)
        metrics_count += 1

    if ema_200:
        distance_from_ema = (current_price - ema_200) / ema_200 if ema_200 > 0 else 0
        await calc_repo.set_metric(symbol, "DISTANCE_FROM_EMA_200", distance_from_ema)
        metrics_count += 1

    return metrics_count


async def _calculate_bollinger_position(
    calc_repo, symbol: str, closes: list, bands: Optional[tuple]
) -> int:
    """Calculate Bollinger Band position metric."""
    if not bands or not closes:
        return 0

    lower, middle, upper = bands
    current_price = closes[-1]
    if upper > lower:
        bb_position = (current_price - lower) / (upper - lower)
        bb_position = max(0.0, min(1.0, bb_position))
        await calc_repo.set_metric(symbol, "BB_POSITION", bb_position)
        return 1

    return 0


async def calculate_all_metrics_for_symbol(symbol: str) -> int:
    """
    Calculate and store all metrics for a single symbol.

    Returns:
        Number of metrics calculated
    """
    calc_repo = CalculationsRepository()
    history_repo = HistoryRepository(symbol)
    metrics_calculated = 0

    try:
        daily_prices = await history_repo.get_daily_prices(limit=365)
        monthly_prices = await history_repo.get_monthly_prices(limit=120)

        if not daily_prices or len(daily_prices) < 20:
            logger.debug(f"Insufficient data for {symbol}, skipping metrics")
            return 0

        closes = [p.close_price for p in daily_prices]
        highs = [p.high_price for p in daily_prices]
        lows = [p.low_price for p in daily_prices]
        closes_array = np.array(closes)
        highs_array = np.array(highs)
        lows_array = np.array(lows)

        tech_count, ema_200, high_52w, bands = await _calculate_technical_indicators(
            symbol, closes_array, highs_array, lows_array
        )
        metrics_calculated += tech_count

        cagr_count = await _calculate_cagr_metrics(calc_repo, symbol, monthly_prices)
        metrics_calculated += cagr_count

        momentum_count = await _calculate_momentum_metrics(calc_repo, symbol, closes)
        metrics_calculated += momentum_count

        distance_count = await _calculate_distance_metrics(
            calc_repo, symbol, closes, ema_200, high_52w
        )
        metrics_calculated += distance_count

        bb_count = await _calculate_bollinger_position(calc_repo, symbol, closes, bands)
        metrics_calculated += bb_count

        logger.debug(f"Calculated {metrics_calculated} metrics for {symbol}")

    except Exception as e:
        logger.error(f"Error calculating metrics for {symbol}: {e}", exc_info=True)

    return metrics_calculated


async def calculate_metrics_for_all_stocks() -> dict:
    """
    Calculate metrics for all active stocks.

    Returns:
        Dict with statistics: {"processed": int, "total_metrics": int, "errors": int}
    """
    stock_repo = StockRepository()
    active_stocks = await stock_repo.get_active_stocks()

    stats = {
        "processed": 0,
        "total_metrics": 0,
        "errors": 0,
    }

    logger.info(f"Calculating metrics for {len(active_stocks)} active stocks")

    for stock in active_stocks:
        try:
            metrics_count = await calculate_all_metrics_for_symbol(stock.symbol)
            stats["processed"] += 1
            stats["total_metrics"] += metrics_count
        except Exception as e:
            logger.error(f"Error processing {stock.symbol}: {e}", exc_info=True)
            stats["errors"] += 1

    logger.info(
        f"Metrics calculation complete: {stats['processed']} stocks, "
        f"{stats['total_metrics']} metrics, {stats['errors']} errors"
    )

    return stats
