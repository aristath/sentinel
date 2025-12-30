"""Tests for position risk metrics calculations.

These tests validate risk metric calculations for individual stock positions,
including volatility, Sharpe ratio, Sortino ratio, and max drawdown.
"""

from unittest.mock import AsyncMock, patch

import pytest

from app.domain.models import DailyPrice


@pytest.fixture
def mock_history_repo():
    """Mock HistoryRepository."""
    repo = AsyncMock()
    repo.get_daily_range.return_value = []
    return repo


@pytest.fixture
def mock_recommendation_cache():
    """Mock RecommendationCache."""
    cache = AsyncMock()
    cache.get_analytics.return_value = None  # No cached data by default
    return cache


class TestGetPositionRiskMetrics:
    """Test get_position_risk_metrics function."""

    @pytest.mark.asyncio
    async def test_returns_cached_metrics_if_available(self, mock_recommendation_cache):
        """Test that cached metrics are returned if available."""
        from app.domain.analytics.position.risk import get_position_risk_metrics

        cached_metrics = {
            "sortino_ratio": 1.5,
            "sharpe_ratio": 1.2,
            "volatility": 0.15,
            "max_drawdown": -0.10,
        }
        mock_recommendation_cache.get_analytics.return_value = cached_metrics

        with patch(
            "app.domain.analytics.position.risk.get_recommendation_cache",
            return_value=mock_recommendation_cache,
        ):
            result = await get_position_risk_metrics("AAPL", "2024-01-01", "2024-01-31")

            assert result == cached_metrics
            mock_recommendation_cache.get_analytics.assert_called_once_with("risk:AAPL")

    @pytest.mark.asyncio
    async def test_returns_zero_metrics_for_insufficient_data(self):
        """Test that zero metrics are returned when there's insufficient price data."""
        from app.domain.analytics.position.risk import get_position_risk_metrics

        mock_history_repo = AsyncMock()
        mock_history_repo.get_daily_range.return_value = []  # No price data

        mock_cache = AsyncMock()
        mock_cache.get_analytics.return_value = None

        with patch(
            "app.domain.analytics.position.risk.get_recommendation_cache",
            return_value=mock_cache,
        ):
            with patch(
                "app.domain.analytics.position.risk.HistoryRepository",
                return_value=mock_history_repo,
            ):
                result = await get_position_risk_metrics(
                    "AAPL", "2024-01-01", "2024-01-31"
                )

                assert result == {
                    "sortino_ratio": 0.0,
                    "sharpe_ratio": 0.0,
                    "volatility": 0.0,
                    "max_drawdown": 0.0,
                }

    @pytest.mark.asyncio
    async def test_returns_zero_metrics_for_single_price_point(self):
        """Test that zero metrics are returned when only one price point is available."""
        from app.domain.analytics.position.risk import get_position_risk_metrics

        prices = [DailyPrice(date="2024-01-01", close_price=100.0)]

        mock_history_repo = AsyncMock()
        mock_history_repo.get_daily_range.return_value = prices

        mock_cache = AsyncMock()
        mock_cache.get_analytics.return_value = None

        with patch(
            "app.domain.analytics.position.risk.get_recommendation_cache",
            return_value=mock_cache,
        ):
            with patch(
                "app.domain.analytics.position.risk.HistoryRepository",
                return_value=mock_history_repo,
            ):
                result = await get_position_risk_metrics(
                    "AAPL", "2024-01-01", "2024-01-31"
                )

                assert result == {
                    "sortino_ratio": 0.0,
                    "sharpe_ratio": 0.0,
                    "volatility": 0.0,
                    "max_drawdown": 0.0,
                }

    @pytest.mark.asyncio
    async def test_calculates_metrics_correctly(self):
        """Test that risk metrics are calculated correctly from price data."""
        from app.domain.analytics.position.risk import get_position_risk_metrics

        # Create sample price data (simple upward trend)
        prices = [
            DailyPrice(date="2024-01-01", close_price=100.0),
            DailyPrice(date="2024-01-02", close_price=101.0),
            DailyPrice(date="2024-01-03", close_price=102.0),
            DailyPrice(date="2024-01-04", close_price=103.0),
            DailyPrice(date="2024-01-05", close_price=104.0),
        ]

        mock_history_repo = AsyncMock()
        mock_history_repo.get_daily_range.return_value = prices

        mock_cache = AsyncMock()
        mock_cache.get_analytics.return_value = None

        with patch(
            "app.domain.analytics.position.risk.get_recommendation_cache",
            return_value=mock_cache,
        ):
            with patch(
                "app.domain.analytics.position.risk.HistoryRepository",
                return_value=mock_history_repo,
            ):
                result = await get_position_risk_metrics(
                    "AAPL", "2024-01-01", "2024-01-31"
                )

                assert isinstance(result, dict)
                assert all(
                    key in result
                    for key in [
                        "sortino_ratio",
                        "sharpe_ratio",
                        "volatility",
                        "max_drawdown",
                    ]
                )
                assert result["volatility"] >= 0.0
                # Metrics should be finite numbers (or 0.0)
                assert all(isinstance(v, (int, float)) for v in result.values())

                # Should cache the result
                mock_cache.set_analytics.assert_called_once()
                call_args = mock_cache.set_analytics.call_args
                assert call_args[0][0] == "risk:AAPL"
                assert call_args[0][1] == result
                assert call_args[1]["ttl_hours"] == 72

    @pytest.mark.asyncio
    async def test_handles_empty_returns_series(self):
        """Test handling when returns series is empty after pct_change."""
        from app.domain.analytics.position.risk import get_position_risk_metrics

        # Prices with same values (no returns)
        prices = [
            DailyPrice(date="2024-01-01", close_price=100.0),
            DailyPrice(date="2024-01-02", close_price=100.0),
        ]

        mock_history_repo = AsyncMock()
        mock_history_repo.get_daily_range.return_value = prices

        mock_cache = AsyncMock()
        mock_cache.get_analytics.return_value = None

        with patch(
            "app.domain.analytics.position.risk.get_recommendation_cache",
            return_value=mock_cache,
        ):
            with patch(
                "app.domain.analytics.position.risk.HistoryRepository",
                return_value=mock_history_repo,
            ):
                result = await get_position_risk_metrics(
                    "AAPL", "2024-01-01", "2024-01-31"
                )

                assert result == {
                    "sortino_ratio": 0.0,
                    "sharpe_ratio": 0.0,
                    "volatility": 0.0,
                    "max_drawdown": 0.0,
                }

    @pytest.mark.asyncio
    async def test_handles_non_finite_metrics(self):
        """Test handling when empyrical returns non-finite values."""
        from app.domain.analytics.position.risk import get_position_risk_metrics

        prices = [
            DailyPrice(date="2024-01-01", close_price=100.0),
            DailyPrice(date="2024-01-02", close_price=101.0),
        ]

        mock_history_repo = AsyncMock()
        mock_history_repo.get_daily_range.return_value = prices

        mock_cache = AsyncMock()
        mock_cache.get_analytics.return_value = None

        with patch(
            "app.domain.analytics.position.risk.get_recommendation_cache",
            return_value=mock_cache,
        ):
            with patch(
                "app.domain.analytics.position.risk.HistoryRepository",
                return_value=mock_history_repo,
            ):
                # Mock empyrical to return inf/nan values
                with patch("empyrical.annual_volatility", return_value=float("inf")):
                    with patch("empyrical.sharpe_ratio", return_value=float("nan")):
                        with patch(
                            "empyrical.sortino_ratio", return_value=float("inf")
                        ):
                            with patch(
                                "empyrical.max_drawdown", return_value=float("nan")
                            ):
                                result = await get_position_risk_metrics(
                                    "AAPL", "2024-01-01", "2024-01-31"
                                )

                                # Non-finite values should be converted to 0.0
                                assert result == {
                                    "sortino_ratio": 0.0,
                                    "sharpe_ratio": 0.0,
                                    "volatility": 0.0,
                                    "max_drawdown": 0.0,
                                }

    @pytest.mark.asyncio
    async def test_handles_exceptions_gracefully(self):
        """Test that exceptions during calculation return zero metrics."""
        from app.domain.analytics.position.risk import get_position_risk_metrics

        mock_history_repo = AsyncMock()
        mock_history_repo.get_daily_range.side_effect = Exception("DB error")

        mock_cache = AsyncMock()
        mock_cache.get_analytics.return_value = None

        with patch(
            "app.domain.analytics.position.risk.get_recommendation_cache",
            return_value=mock_cache,
        ):
            with patch(
                "app.domain.analytics.position.risk.HistoryRepository",
                return_value=mock_history_repo,
            ):
                result = await get_position_risk_metrics(
                    "AAPL", "2024-01-01", "2024-01-31"
                )

                assert result == {
                    "sortino_ratio": 0.0,
                    "sharpe_ratio": 0.0,
                    "volatility": 0.0,
                    "max_drawdown": 0.0,
                }
