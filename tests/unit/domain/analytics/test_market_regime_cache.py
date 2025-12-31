"""Tests for market regime detection caching.

These tests validate that regime detection results are cached correctly.
CRITICAL: Tests catch real bugs that would cause cache misses or stale data.
"""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.infrastructure.external.tradernet import OHLC, Quote


def create_ohlc(timestamp: datetime, close: float) -> OHLC:
    """Helper to create OHLC data point."""
    return OHLC(
        timestamp=timestamp,
        open=close * 0.99,
        high=close * 1.01,
        low=close * 0.98,
        close=close,
        volume=1000000,
    )


def create_historical_data(
    days: int, start_price: float, trend: float = 0.0
) -> list[OHLC]:
    """Helper to create historical OHLC data."""
    data = []
    base_date = datetime.now() - timedelta(days=days)
    for i in range(days):
        price = start_price * (1 + trend * i / days)
        timestamp = base_date + timedelta(days=i)
        data.append(create_ohlc(timestamp, price))
    return data


class TestRegimeCache:
    """Test regime detection caching."""

    @pytest.mark.asyncio
    async def test_uses_cached_regime_when_available(self):
        """Test that cached regime is used when available.

        Bug caught: Cache not checked, recalculates unnecessarily.
        """
        from app.modules.analytics.domain.market_regime import detect_market_regime

        # Mock cache to return cached value
        mock_cache = AsyncMock()
        mock_cache.get_analytics = AsyncMock(return_value="bull")

        with (
            patch(
                "app.modules.analytics.domain.market_regime.get_recommendation_cache",
                return_value=mock_cache,
            ),
            patch(
                "app.modules.analytics.domain.market_regime.SettingsRepository",
                return_value=AsyncMock(),
            ),
            patch(
                "app.modules.analytics.domain.market_regime.get_tradernet_client",
                return_value=MagicMock(),
            ),
        ):
            regime = await detect_market_regime(use_cache=True)

        # Should return cached value without calling API
        assert regime == "bull"
        mock_cache.get_analytics.assert_called_once_with("market_regime")

    @pytest.mark.asyncio
    async def test_caches_regime_after_detection(self):
        """Test that regime is cached after detection.

        Bug caught: Cache not updated, subsequent calls recalculate.
        """
        from app.modules.analytics.domain.market_regime import detect_market_regime

        historical = create_historical_data(250, start_price=100.0, trend=0.0)
        current_price = 110.0

        mock_client = MagicMock()
        mock_client.is_connected = True
        mock_client.get_historical_prices = MagicMock(
            side_effect=lambda symbol, start=None, end=None: (
                historical if symbol in ("SPY.US", "QQQ.US") else []
            )
        )
        mock_client.get_quote = MagicMock(
            return_value=Quote(
                symbol="SPY.US",
                price=current_price,
                change=0.0,
                change_pct=0.0,
                volume=0,
                timestamp=datetime.now(),
            )
        )

        mock_settings_repo = AsyncMock()

        async def get_float(key, default):
            return {
                "market_regime_detection_enabled": 1.0,
                "market_regime_bull_threshold": 0.05,
                "market_regime_bear_threshold": -0.05,
            }.get(key, default)

        mock_settings_repo.get_float = AsyncMock(side_effect=get_float)

        mock_cache = AsyncMock()
        mock_cache.get_analytics = AsyncMock(return_value=None)  # Cache miss
        mock_cache.set_analytics = AsyncMock()

        with (
            patch(
                "app.modules.analytics.domain.market_regime.get_recommendation_cache",
                return_value=mock_cache,
            ),
            patch(
                "app.modules.analytics.domain.market_regime.SettingsRepository",
                return_value=mock_settings_repo,
            ),
            patch(
                "app.modules.analytics.domain.market_regime.get_tradernet_client",
                return_value=mock_client,
            ),
        ):
            await detect_market_regime(client=mock_client, use_cache=True)

        # Verify regime was cached
        mock_cache.set_analytics.assert_called_once()
        call_args = mock_cache.set_analytics.call_args
        assert call_args[0][0] == "market_regime"  # cache key
        assert call_args[0][1] in ("bull", "bear", "sideways")  # regime value
        assert call_args[1]["ttl_hours"] == 24  # 24-hour TTL

    @pytest.mark.asyncio
    async def test_bypasses_cache_when_use_cache_false(self):
        """Test that cache is bypassed when use_cache=False.

        Bug caught: Cache always used even when explicitly disabled.
        """
        from app.modules.analytics.domain.market_regime import detect_market_regime

        historical = create_historical_data(250, start_price=100.0, trend=0.0)
        current_price = 100.0

        mock_client = MagicMock()
        mock_client.is_connected = True
        mock_client.get_historical_prices = MagicMock(
            side_effect=lambda symbol, start=None, end=None: (
                historical if symbol in ("SPY.US", "QQQ.US") else []
            )
        )
        mock_client.get_quote = MagicMock(
            return_value=Quote(
                symbol="SPY.US",
                price=current_price,
                change=0.0,
                change_pct=0.0,
                volume=0,
                timestamp=datetime.now(),
            )
        )

        mock_settings_repo = AsyncMock()

        async def get_float(key, default):
            return {
                "market_regime_detection_enabled": 1.0,
                "market_regime_bull_threshold": 0.05,
                "market_regime_bear_threshold": -0.05,
            }.get(key, default)

        mock_settings_repo.get_float = AsyncMock(side_effect=get_float)

        mock_cache = AsyncMock()

        with (
            patch(
                "app.modules.analytics.domain.market_regime.get_recommendation_cache",
                return_value=mock_cache,
            ),
            patch(
                "app.modules.analytics.domain.market_regime.SettingsRepository",
                return_value=mock_settings_repo,
            ),
            patch(
                "app.modules.analytics.domain.market_regime.get_tradernet_client",
                return_value=mock_client,
            ),
        ):
            await detect_market_regime(client=mock_client, use_cache=False)

        # Verify cache was NOT accessed
        mock_cache.get_analytics.assert_not_called()
        mock_cache.set_analytics.assert_not_called()

    @pytest.mark.asyncio
    async def test_handles_cache_failure_gracefully(self):
        """Test that cache failure doesn't break regime detection.

        Bug caught: Cache error crashes regime detection.
        """
        from app.modules.analytics.domain.market_regime import detect_market_regime

        historical = create_historical_data(250, start_price=100.0, trend=0.0)
        current_price = 100.0

        mock_client = MagicMock()
        mock_client.is_connected = True
        mock_client.get_historical_prices = MagicMock(
            side_effect=lambda symbol, start=None, end=None: (
                historical if symbol in ("SPY.US", "QQQ.US") else []
            )
        )
        mock_client.get_quote = MagicMock(
            return_value=Quote(
                symbol="SPY.US",
                price=current_price,
                change=0.0,
                change_pct=0.0,
                volume=0,
                timestamp=datetime.now(),
            )
        )

        mock_settings_repo = AsyncMock()

        async def get_float(key, default):
            return {
                "market_regime_detection_enabled": 1.0,
                "market_regime_bull_threshold": 0.05,
                "market_regime_bear_threshold": -0.05,
            }.get(key, default)

        mock_settings_repo.get_float = AsyncMock(side_effect=get_float)

        # Mock cache to raise exception
        mock_cache = AsyncMock()
        mock_cache.get_analytics = AsyncMock(side_effect=Exception("Cache error"))
        mock_cache.set_analytics = AsyncMock(side_effect=Exception("Cache error"))

        with (
            patch(
                "app.modules.analytics.domain.market_regime.get_recommendation_cache",
                return_value=mock_cache,
            ),
            patch(
                "app.modules.analytics.domain.market_regime.SettingsRepository",
                return_value=mock_settings_repo,
            ),
            patch(
                "app.modules.analytics.domain.market_regime.get_tradernet_client",
                return_value=mock_client,
            ),
        ):
            # Should not raise exception, should proceed with detection
            regime = await detect_market_regime(client=mock_client, use_cache=True)
            assert regime in ("bull", "bear", "sideways")
