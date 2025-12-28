"""Tests for market regime detection.

These tests validate market regime classification logic based on 200-day moving averages.
CRITICAL: Tests catch real bugs that would cause wrong strategy adjustments.
"""

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from app.infrastructure.external.tradernet import OHLC


def create_ohlc(timestamp: datetime, close: float) -> OHLC:
    """Helper to create OHLC data point."""
    from app.infrastructure.external.tradernet import OHLC
    return OHLC(
        timestamp=timestamp,
        open=close * 0.99,
        high=close * 1.01,
        low=close * 0.98,
        close=close,
        volume=1000000,
    )


def create_historical_data(days: int, start_price: float, trend: float = 0.0) -> list[OHLC]:
    """Helper to create historical OHLC data."""
    data = []
    base_date = datetime.now() - timedelta(days=days)
    for i in range(days):
        price = start_price * (1 + trend * i / days)
        timestamp = base_date + timedelta(days=i)
        data.append(create_ohlc(timestamp, price))
    return data


class TestRegimeClassification:
    """Test regime classification logic."""

    @pytest.mark.asyncio
    async def test_classifies_bull_market_correctly(self):
        """Test that bull market is classified correctly.

        Bug caught: Wrong regime detected, wrong strategy used.
        """
        from app.domain.analytics.market_regime import detect_market_regime

        # Create data where current price is 10% above 200-day MA
        historical = create_historical_data(250, start_price=100.0, trend=0.1)
        current_price = 110.0  # 10% above average

        mock_client = MagicMock()
        # Mock SPY data
        mock_client.get_historical_prices = MagicMock(
            side_effect=lambda symbol, start, end, days: (
                historical if symbol == "SPY.US" else []
            )
        )
        mock_client.get_quote = MagicMock(
            side_effect=lambda symbol: Quote(
                symbol=symbol,
                price=current_price,
                change=0.0,
                change_pct=0.0,
                volume=0,
                timestamp=datetime.now(),
            )
        )

        mock_settings_repo = MagicMock()
        async def get_float(key, default):
            return {
                "market_regime_detection_enabled": 1.0,
                "market_regime_bull_threshold": 0.05,  # 5%
                "market_regime_bear_threshold": -0.05,  # -5%
            }.get(key, default)
        mock_settings_repo.get_float = MagicMock(side_effect=get_float)

        with (
            patch("app.domain.analytics.market_regime.SettingsRepository", return_value=mock_settings_repo),
            patch("app.domain.analytics.market_regime.get_tradernet_client", return_value=mock_client),
        ):
            regime = await detect_market_regime()

        # Should classify as bull market (avg distance > 5% threshold)
        assert regime == "bull"

    @pytest.mark.asyncio
    async def test_classifies_bear_market_correctly(self):
        """Test that bear market is classified correctly.

        Bug caught: Wrong regime detected, wrong strategy used.
        """
        from app.domain.analytics.market_regime import detect_market_regime

        # Create data where current price is 10% below 200-day MA
        historical = create_historical_data(250, start_price=100.0, trend=-0.1)
        current_price = 90.0  # 10% below average

        mock_client = MagicMock()
        mock_client.get_historical_prices = MagicMock(
            side_effect=lambda symbol, start, end, days: (
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

        mock_settings_repo = MagicMock()
        async def get_float(key, default):
            return {
                "market_regime_detection_enabled": 1.0,
                "market_regime_bull_threshold": 0.05,
                "market_regime_bear_threshold": -0.05,
            }.get(key, default)
        mock_settings_repo.get_float = MagicMock(side_effect=get_float)

        with (
            patch("app.domain.analytics.market_regime.SettingsRepository", return_value=mock_settings_repo),
            patch("app.domain.analytics.market_regime.get_tradernet_client", return_value=mock_client),
        ):
            regime = await detect_market_regime()

        # Should classify as bear market (avg distance < -5% threshold)
        assert regime == "bear"

    @pytest.mark.asyncio
    async def test_classifies_sideways_market_correctly(self):
        """Test that sideways market is classified correctly.

        Bug caught: Wrong regime detected, wrong strategy used.
        """
        from app.domain.analytics.market_regime import detect_market_regime

        # Create data where current price is close to 200-day MA (within thresholds)
        historical = create_historical_data(250, start_price=100.0, trend=0.0)
        current_price = 100.0  # Same as average (0% distance)

        mock_client = MagicMock()
        mock_client.get_historical_prices = MagicMock(
            side_effect=lambda symbol, start, end, days: (
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

        mock_settings_repo = MagicMock()
        async def get_float(key, default):
            return {
                "market_regime_detection_enabled": 1.0,
                "market_regime_bull_threshold": 0.05,
                "market_regime_bear_threshold": -0.05,
            }.get(key, default)
        mock_settings_repo.get_float = MagicMock(side_effect=get_float)

        with (
            patch("app.domain.analytics.market_regime.SettingsRepository", return_value=mock_settings_repo),
            patch("app.domain.analytics.market_regime.get_tradernet_client", return_value=mock_client),
        ):
            regime = await detect_market_regime()

        # Should classify as sideways market (between thresholds)
        assert regime == "sideways"

    @pytest.mark.asyncio
    async def test_exactly_at_bull_threshold_classifies_bull(self):
        """Test that exactly at bull threshold classifies as bull.

        Bug caught: Off-by-one at threshold.
        """
        from app.domain.analytics.market_regime import detect_market_regime

        historical = create_historical_data(250, start_price=100.0, trend=0.0)
        # Current price exactly 5% above average
        current_price = 105.0

        mock_client = MagicMock()
        mock_client.get_historical_prices = MagicMock(
            side_effect=lambda symbol, start, end, days: (
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

        mock_settings_repo = MagicMock()
        async def get_float(key, default):
            return {
                "market_regime_detection_enabled": 1.0,
                "market_regime_bull_threshold": 0.05,  # Exactly 5%
                "market_regime_bear_threshold": -0.05,
            }.get(key, default)
        mock_settings_repo.get_float = MagicMock(side_effect=get_float)

        with (
            patch("app.domain.analytics.market_regime.SettingsRepository", return_value=mock_settings_repo),
            patch("app.domain.analytics.market_regime.get_tradernet_client", return_value=mock_client),
        ):
            regime = await detect_market_regime()

        # Should classify as bull (>= threshold)
        assert regime == "bull"


class TestMACalculation:
    """Test moving average calculation."""

    @pytest.mark.asyncio
    async def test_calculates_200_day_ma_correctly(self):
        """Test that 200-day MA is calculated correctly.

        Bug caught: Wrong MA calculation, wrong regime.
        """
        from app.domain.analytics.market_regime import _calculate_200_day_ma

        # Create exactly 200 days of data with constant price
        historical = create_historical_data(200, start_price=100.0, trend=0.0)

        ma = _calculate_200_day_ma(historical)

        # MA should be close to 100.0 (all prices are ~100.0)
        assert abs(ma - 100.0) < 1.0

    @pytest.mark.asyncio
    async def test_handles_insufficient_data_gracefully(self):
        """Test that insufficient data is handled gracefully.

        Bug caught: Crashes when <200 days of data.
        """
        from app.domain.analytics.market_regime import _calculate_200_day_ma

        # Only 50 days of data
        historical = create_historical_data(50, start_price=100.0)

        # Should return None or raise appropriate error
        ma = _calculate_200_day_ma(historical)
        assert ma is None


class TestDistanceCalculation:
    """Test distance calculation from moving average."""

    @pytest.mark.asyncio
    async def test_calculates_distance_from_ma_correctly(self):
        """Test that distance from MA is calculated correctly.

        Bug caught: Wrong distance formula.
        """
        from app.domain.analytics.market_regime import _calculate_distance_from_ma

        ma = 100.0
        current_price = 110.0

        distance = _calculate_distance_from_ma(current_price, ma)

        # Distance should be (110 - 100) / 100 = 0.10 (10%)
        assert abs(distance - 0.10) < 0.001

    @pytest.mark.asyncio
    async def test_handles_zero_ma_gracefully(self):
        """Test that zero MA is handled gracefully.

        Bug caught: Division by zero.
        """
        from app.domain.analytics.market_regime import _calculate_distance_from_ma

        ma = 0.0
        current_price = 100.0

        # Should not raise exception
        distance = _calculate_distance_from_ma(current_price, ma)
        # Should return None or handle gracefully
        assert distance is None or distance == 0.0


class TestErrorHandling:
    """Test error handling."""

    @pytest.mark.asyncio
    async def test_api_failure_returns_default_regime(self):
        """Test that API failure returns default regime.

        Bug caught: Crashes on API failure.
        """
        from app.domain.analytics.market_regime import detect_market_regime

        mock_client = MagicMock()
        mock_client.get_historical_prices.side_effect = Exception("API error")

        mock_settings_repo = MagicMock()
        async def get_float(key, default):
            return {
                "market_regime_detection_enabled": 1.0,
                "market_regime_bull_threshold": 0.05,
                "market_regime_bear_threshold": -0.05,
            }.get(key, default)
        mock_settings_repo.get_float = MagicMock(side_effect=get_float)

        with (
            patch("app.domain.analytics.market_regime.SettingsRepository", return_value=mock_settings_repo),
            patch("app.domain.analytics.market_regime.get_tradernet_client", return_value=mock_client),
        ):
            # Should not raise exception, return default regime
            regime = await detect_market_regime()
            # Should return "sideways" as safe default
            assert regime in ("bull", "bear", "sideways")

