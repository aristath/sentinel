"""Market regime detection based on 200-day moving averages.

Classifies market conditions as bull, bear, or sideways based on the average
distance of SPY and QQQ from their 200-day moving averages.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional

from app.infrastructure.external.tradernet import TradernetClient, get_tradernet_client
from app.infrastructure.recommendation_cache import get_recommendation_cache
from app.repositories import SettingsRepository

logger = logging.getLogger(__name__)

# Market indices for regime detection
SPY_SYMBOL = "SPY.US"
QQQ_SYMBOL = "QQQ.US"

# Number of days for moving average calculation
MA_PERIOD = 200

# Cache key for regime detection
REGIME_CACHE_KEY = "market_regime"
REGIME_CACHE_TTL_HOURS = 24  # Update daily


def _calculate_200_day_ma(historical_data: list) -> Optional[float]:
    """
    Calculate 200-day moving average from historical OHLC data.

    Args:
        historical_data: List of OHLC objects with close prices

    Returns:
        200-day MA or None if insufficient data
    """
    if not historical_data or len(historical_data) < MA_PERIOD:
        return None

    # Sort by timestamp (oldest first)
    sorted_data = sorted(historical_data, key=lambda x: x.timestamp)

    # Get last 200 days
    last_200 = sorted_data[-MA_PERIOD:]

    # Calculate average of close prices
    total = sum(candle.close for candle in last_200)
    return total / MA_PERIOD


def _calculate_distance_from_ma(current_price: float, ma: float) -> Optional[float]:
    """
    Calculate distance from moving average as percentage.

    Args:
        current_price: Current price
        ma: Moving average value

    Returns:
        Distance as decimal (e.g., 0.05 = 5% above MA, -0.05 = 5% below MA)
        Returns None if ma is zero or invalid
    """
    if ma == 0.0 or ma is None:
        return None

    return (current_price - ma) / ma


async def detect_market_regime(
    client: Optional[TradernetClient] = None, use_cache: bool = True
) -> str:
    """
    Detect current market regime based on SPY and QQQ 200-day moving averages.

    Classifies market as:
    - Bull: Average distance > bull_threshold (default 5%)
    - Bear: Average distance < bear_threshold (default -5%)
    - Sideways: Between thresholds

    Args:
        client: Optional TradernetClient (uses singleton if not provided)
        use_cache: Whether to use cached result (default: True)

    Returns:
        Market regime string: "bull", "bear", or "sideways"
    """
    if client is None:
        client = get_tradernet_client()

    try:
        # Get settings
        settings_repo = SettingsRepository()
        enabled = await settings_repo.get_float("market_regime_detection_enabled", 1.0)
        if enabled == 0.0:
            logger.info(
                "Market regime detection is disabled, returning sideways as default"
            )
            return "sideways"

        # Check cache first (if enabled)
        if use_cache:
            cache = get_recommendation_cache()
            cached_regime = await cache.get_analytics(REGIME_CACHE_KEY)
            if cached_regime is not None:
                logger.debug(f"Market regime cache HIT: {cached_regime}")
                return cached_regime

        bull_threshold = await settings_repo.get_float(
            "market_regime_bull_threshold", 0.05
        )
        bear_threshold = await settings_repo.get_float(
            "market_regime_bear_threshold", -0.05
        )

        # Ensure client is connected
        if not client.is_connected:
            if not client.connect():
                logger.warning(
                    "Failed to connect to Tradernet for regime detection, returning sideways"
                )
                return "sideways"

        # Get historical data for SPY (200+ days needed)
        end_date = datetime.now()
        start_date = end_date - timedelta(days=MA_PERIOD + 50)  # Extra buffer

        spy_data = client.get_historical_prices(
            SPY_SYMBOL, start=start_date, end=end_date
        )
        qqq_data = client.get_historical_prices(
            QQQ_SYMBOL, start=start_date, end=end_date
        )

        if not spy_data or len(spy_data) < MA_PERIOD:
            logger.warning(
                f"Insufficient SPY data for regime detection ({len(spy_data) if spy_data else 0} days)"
            )
            return "sideways"

        qqq_available = bool(qqq_data and len(qqq_data) >= MA_PERIOD)
        if not qqq_available:
            logger.warning(
                f"Insufficient QQQ data for regime detection ({len(qqq_data) if qqq_data else 0} days)"
            )
            # Use only SPY if QQQ is unavailable

        # Calculate 200-day MAs
        spy_ma = _calculate_200_day_ma(spy_data)
        if spy_ma is None:
            logger.warning("Failed to calculate SPY 200-day MA")
            return "sideways"

        qqq_ma = _calculate_200_day_ma(qqq_data) if qqq_available else None

        # Get current prices
        spy_quote = client.get_quote(SPY_SYMBOL)
        if not spy_quote:
            logger.warning("Failed to get SPY quote")
            return "sideways"

        qqq_quote = client.get_quote(QQQ_SYMBOL) if qqq_data else None

        # Calculate distances from MA
        spy_distance = _calculate_distance_from_ma(spy_quote.price, spy_ma)
        if spy_distance is None:
            logger.warning("Failed to calculate SPY distance from MA")
            return "sideways"

        qqq_distance = None
        if qqq_ma and qqq_quote:
            qqq_distance = _calculate_distance_from_ma(qqq_quote.price, qqq_ma)

        # Average the distances (use SPY only if QQQ unavailable)
        if qqq_distance is not None:
            avg_distance = (spy_distance + qqq_distance) / 2.0
        else:
            avg_distance = spy_distance
            logger.info("Using SPY only for regime detection (QQQ unavailable)")

        # Classify regime (>= for bull, <= for bear ensures boundary values classify correctly)
        if avg_distance >= bull_threshold:
            regime = "bull"
        elif avg_distance <= bear_threshold:
            regime = "bear"
        else:
            regime = "sideways"

        qqq_str = f"{qqq_distance:.3f}" if qqq_distance is not None else "N/A"
        logger.info(
            f"Market regime detected: {regime} (avg_distance={avg_distance:.3f}, "
            f"SPY={spy_distance:.3f}, QQQ={qqq_str})"
        )

        # Cache the result (if caching enabled)
        if use_cache:
            try:
                cache = get_recommendation_cache()
                await cache.set_analytics(
                    REGIME_CACHE_KEY, regime, ttl_hours=REGIME_CACHE_TTL_HOURS
                )
                logger.debug(f"Cached market regime: {regime}")
            except Exception as e:
                logger.warning(f"Failed to cache market regime: {e}")

        return regime

    except Exception as e:
        logger.error(f"Failed to detect market regime: {e}", exc_info=True)
        return "sideways"  # Safe default
