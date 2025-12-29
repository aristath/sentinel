"""Technical data calculator for rebalancing operations.

Calculates technical indicators (volatility, EMA distance) for portfolio positions.
"""

import logging
from typing import Dict, List

import empyrical
import numpy as np
import pandas as pd
import pandas_ta as ta

from app.domain.scoring import TechnicalData
from app.infrastructure.database.manager import DatabaseManager

logger = logging.getLogger(__name__)


def _get_fallback_technical_data() -> TechnicalData:
    """Return fallback technical data with default values."""
    return TechnicalData(
        current_volatility=0.20,
        historical_volatility=0.20,
        distance_from_ma_200=0.0,
    )


def _calculate_current_volatility(closes: np.ndarray) -> float:
    """Calculate current volatility from last 60 days."""
    if len(closes) < 60:
        return 0.20

    recent_returns = np.diff(closes[-60:]) / closes[-60:-1]
    current_vol = float(empyrical.annual_volatility(recent_returns))
    if not np.isfinite(current_vol) or current_vol < 0:
        return 0.20
    return current_vol


def _calculate_historical_volatility(closes: np.ndarray) -> float:
    """Calculate historical volatility from all available data."""
    returns = np.diff(closes) / closes[:-1]
    historical_vol = float(empyrical.annual_volatility(returns))
    if not np.isfinite(historical_vol) or historical_vol < 0:
        return 0.20
    return historical_vol


def _calculate_ema_distance(closes: np.ndarray, closes_series: pd.Series) -> float:
    """Calculate distance from 200-day EMA."""
    if len(closes) < 200:
        return 0.0

    ema_200 = ta.ema(closes_series, length=200)
    if ema_200 is not None and len(ema_200) > 0 and not pd.isna(ema_200.iloc[-1]):
        ema_value = float(ema_200.iloc[-1].item())
    else:
        ema_value = float(np.mean(closes[-200:]))

    current_price = float(closes[-1])
    return (current_price - ema_value) / ema_value if ema_value > 0 else 0.0


async def _process_symbol_technical_data(
    symbol: str, db_manager: DatabaseManager
) -> TechnicalData:
    """Calculate technical data for a single symbol."""
    try:
        history_db = await db_manager.history(symbol)
        rows = await history_db.fetchall(
            """
            SELECT date, close_price FROM daily_prices
            ORDER BY date DESC LIMIT 400
            """,
        )

        if len(rows) < 60:
            return _get_fallback_technical_data()

        closes = np.array([row["close_price"] for row in reversed(rows)])
        closes_series = pd.Series(closes)

        if np.any(closes <= 0):
            logger.warning(
                f"Zero/negative prices detected for {symbol}, using fallback values"
            )
            return _get_fallback_technical_data()

        current_vol = _calculate_current_volatility(closes)
        historical_vol = _calculate_historical_volatility(closes)
        distance = _calculate_ema_distance(closes, closes_series)

        return TechnicalData(
            current_volatility=current_vol,
            historical_volatility=historical_vol,
            distance_from_ma_200=distance,
        )

    except (ValueError, ZeroDivisionError) as e:
        logger.warning(f"Invalid data for {symbol}: {e}")
        return _get_fallback_technical_data()
    except Exception as e:
        logger.error(
            f"Unexpected error getting technical data for {symbol}: {e}",
            exc_info=True,
        )
        return _get_fallback_technical_data()


async def get_technical_data_for_positions(
    symbols: List[str],
    db_manager: DatabaseManager,
) -> Dict[str, TechnicalData]:
    """Calculate technical indicators for instability detection.

    Uses per-symbol history databases to calculate:
    - Current volatility (last 60 days)
    - Historical volatility (last 365 days)
    - Distance from 200-day MA

    Args:
        symbols: List of stock symbols to calculate technical data for
        db_manager: Database manager for accessing history databases

    Returns:
        Dictionary mapping symbol to TechnicalData object
    """
    result: Dict[str, TechnicalData] = {}

    for symbol in symbols:
        result[symbol] = await _process_symbol_technical_data(symbol, db_manager)

    return result
