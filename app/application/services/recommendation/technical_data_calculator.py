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
        try:
            history_db = await db_manager.history(symbol)
            rows = await history_db.fetchall(
                """
                SELECT date, close_price FROM daily_prices
                ORDER BY date DESC LIMIT 400
                """,
            )

            if len(rows) < 60:
                result[symbol] = TechnicalData(
                    current_volatility=0.20,
                    historical_volatility=0.20,
                    distance_from_ma_200=0.0,
                )
                continue

            closes = np.array([row["close_price"] for row in reversed(rows)])
            closes_series = pd.Series(closes)

            if np.any(closes <= 0):
                logger.warning(
                    f"Zero/negative prices detected for {symbol}, using fallback values"
                )
                result[symbol] = TechnicalData(
                    current_volatility=0.20,
                    historical_volatility=0.20,
                    distance_from_ma_200=0.0,
                )
                continue

            # Current volatility (last 60 days) using empyrical
            if len(closes) >= 60:
                recent_returns = np.diff(closes[-60:]) / closes[-60:-1]
                current_vol = float(empyrical.annual_volatility(recent_returns))
                if not np.isfinite(current_vol) or current_vol < 0:
                    current_vol = 0.20
            else:
                current_vol = 0.20

            # Historical volatility using empyrical
            returns = np.diff(closes) / closes[:-1]
            historical_vol = float(empyrical.annual_volatility(returns))
            if not np.isfinite(historical_vol) or historical_vol < 0:
                historical_vol = 0.20

            # Distance from 200-day EMA using pandas-ta
            if len(closes) >= 200:
                ema_200 = ta.ema(closes_series, length=200)
                if (
                    ema_200 is not None
                    and len(ema_200) > 0
                    and not pd.isna(ema_200.iloc[-1])
                ):
                    ema_value = float(ema_200.iloc[-1])
                else:
                    ema_value = float(np.mean(closes[-200:]))
                current_price = float(closes[-1])
                distance = (
                    (current_price - ema_value) / ema_value if ema_value > 0 else 0.0
                )
            else:
                distance = 0.0

            result[symbol] = TechnicalData(
                current_volatility=current_vol,
                historical_volatility=historical_vol,
                distance_from_ma_200=distance,
            )

        except (ValueError, ZeroDivisionError) as e:
            logger.warning(f"Invalid data for {symbol}: {e}")
            result[symbol] = TechnicalData(
                current_volatility=0.20,
                historical_volatility=0.20,
                distance_from_ma_200=0.0,
            )
        except Exception as e:
            logger.error(
                f"Unexpected error getting technical data for {symbol}: {e}",
                exc_info=True,
            )
            result[symbol] = TechnicalData(
                current_volatility=0.20,
                historical_volatility=0.20,
                distance_from_ma_200=0.0,
            )

    return result
