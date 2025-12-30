"""Tests for performance attribution calculations.

These tests validate performance attribution by geography and industry,
including helper functions for attributing returns and calculating annualized values.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pandas as pd
import pytest

from app.domain.models import DailyPrice, Stock


class TestAttributeReturnByCategory:
    """Test _attribute_return_by_category helper function."""

    def test_attributes_return_by_country_and_industry(self):
        """Test that returns are attributed correctly by country and industry."""
        from app.domain.analytics.attribution.performance import (
            _attribute_return_by_category,
        )

        position_values = {
            "AAPL": {"value": 1000.0, "country": "US", "industry": "Technology"},
            "MSFT": {"value": 500.0, "country": "US", "industry": "Technology"},
            "SAP": {"value": 500.0, "country": "DE", "industry": "Software"},
        }
        total_value = 2000.0
        daily_return = 0.02  # 2% return

        geo_returns = {}
        industry_returns = {}

        _attribute_return_by_category(
            position_values, total_value, daily_return, geo_returns, industry_returns
        )

        # US: (1000 + 500) / 2000 = 0.75 weight, 0.02 * 0.75 = 0.015 contribution
        # DE: 500 / 2000 = 0.25 weight, 0.02 * 0.25 = 0.005 contribution
        assert "US" in geo_returns
        assert "DE" in geo_returns
        assert sum(geo_returns["US"]) == pytest.approx(0.015, abs=0.001)
        assert sum(geo_returns["DE"]) == pytest.approx(0.005, abs=0.001)

        # Technology: (1000 + 500) / 2000 = 0.75 weight, 0.02 * 0.75 = 0.015
        # Software: 500 / 2000 = 0.25 weight, 0.02 * 0.25 = 0.005
        assert "Technology" in industry_returns
        assert "Software" in industry_returns
        assert sum(industry_returns["Technology"]) == pytest.approx(0.015, abs=0.001)
        assert sum(industry_returns["Software"]) == pytest.approx(0.005, abs=0.001)

    def test_handles_unknown_country(self):
        """Test handling of unknown country."""
        from app.domain.analytics.attribution.performance import (
            _attribute_return_by_category,
        )

        position_values = {
            "UNKNOWN": {"value": 1000.0, "country": "UNKNOWN", "industry": "Tech"},
        }
        total_value = 1000.0
        daily_return = 0.01

        geo_returns = {}
        industry_returns = {}

        _attribute_return_by_category(
            position_values, total_value, daily_return, geo_returns, industry_returns
        )

        assert "UNKNOWN" in geo_returns
        assert sum(geo_returns["UNKNOWN"]) == pytest.approx(0.01, abs=0.001)

    def test_handles_missing_industry(self):
        """Test handling of missing industry (None)."""
        from app.domain.analytics.attribution.performance import (
            _attribute_return_by_category,
        )

        position_values = {
            "STOCK": {"value": 1000.0, "country": "US", "industry": None},
        }
        total_value = 1000.0
        daily_return = 0.01

        geo_returns = {}
        industry_returns = {}

        _attribute_return_by_category(
            position_values, total_value, daily_return, geo_returns, industry_returns
        )

        assert "US" in geo_returns
        assert len(industry_returns) == 0  # None industry should not be added


class TestCalculateAnnualizedAttribution:
    """Test _calculate_annualized_attribution helper function."""

    def test_calculates_annualized_attribution_correctly(self):
        """Test that annualized attribution is calculated correctly."""
        from app.domain.analytics.attribution.performance import (
            _calculate_annualized_attribution,
        )

        # Simulate 5 days of contributions, each 0.001 (0.1%)
        # Total return = 5 * 0.001 = 0.005 (0.5%)
        # Annualized = (1 + 0.005) ** (252/5) - 1
        geo_returns = {"US": [0.001, 0.001, 0.001, 0.001, 0.001]}
        industry_returns = {"Technology": [0.001, 0.001, 0.001, 0.001, 0.001]}

        attribution = _calculate_annualized_attribution(geo_returns, industry_returns)

        assert "country" in attribution
        assert "industry" in attribution
        assert "US" in attribution["country"]
        assert "Technology" in attribution["industry"]
        # Annualized should be positive (compound growth)
        assert attribution["country"]["US"] > 0.005
        assert attribution["industry"]["Technology"] > 0.005

    def test_handles_total_return_less_than_minus_one(self):
        """Test handling when total return is <= -1."""
        from app.domain.analytics.attribution.performance import (
            _calculate_annualized_attribution,
        )

        # Total return = -1.5 (complete loss and more)
        geo_returns = {"US": [-1.5]}
        industry_returns = {}

        attribution = _calculate_annualized_attribution(geo_returns, industry_returns)

        assert attribution["country"]["US"] == -1.0  # Clamped to -1.0

    def test_handles_empty_contributions(self):
        """Test handling of empty contributions lists."""
        from app.domain.analytics.attribution.performance import (
            _calculate_annualized_attribution,
        )

        geo_returns = {"US": []}
        industry_returns = {"Tech": []}

        attribution = _calculate_annualized_attribution(geo_returns, industry_returns)

        # Empty contributions should result in 0.0
        assert attribution["country"]["US"] == 0.0
        assert attribution["industry"]["Tech"] == 0.0

    def test_handles_non_finite_values(self):
        """Test handling of non-finite annualized values."""
        from app.domain.analytics.attribution.performance import (
            _calculate_annualized_attribution,
        )

        # This would cause a calculation that might result in inf/nan
        # The function should handle it gracefully
        geo_returns = {"US": [0.0] * 252}  # Zero returns
        industry_returns = {}

        attribution = _calculate_annualized_attribution(geo_returns, industry_returns)

        assert isinstance(attribution["country"]["US"], float)
        assert attribution["country"]["US"] == 0.0


class TestGetPerformanceAttribution:
    """Test get_performance_attribution function."""

    @pytest.mark.asyncio
    async def test_returns_empty_for_empty_returns(self):
        """Test that empty returns series returns empty attribution."""
        from app.domain.analytics.attribution.performance import (
            get_performance_attribution,
        )

        returns = pd.Series(dtype=float)
        result = await get_performance_attribution(returns, "2024-01-01", "2024-01-31")

        assert result == {"country": {}, "industry": {}}

    @pytest.mark.asyncio
    async def test_returns_empty_for_empty_positions(self):
        """Test that empty positions returns empty attribution."""
        from app.domain.analytics.attribution.performance import (
            get_performance_attribution,
        )

        returns = pd.Series(
            [0.01, 0.02], index=pd.to_datetime(["2024-01-01", "2024-01-02"])
        )

        with patch(
            "app.domain.analytics.attribution.performance.reconstruct_historical_positions",
            new_callable=AsyncMock,
        ) as mock_reconstruct:
            mock_reconstruct.return_value = pd.DataFrame(
                columns=["date", "symbol", "quantity"]
            )

            result = await get_performance_attribution(
                returns, "2024-01-01", "2024-01-31"
            )

            assert result == {"country": {}, "industry": {}}

    @pytest.mark.asyncio
    async def test_calculates_attribution_correctly(self):
        """Test that attribution is calculated correctly from positions and returns."""
        from app.domain.analytics.attribution.performance import (
            get_performance_attribution,
        )

        # Mock returns
        returns = pd.Series(
            [0.01], index=pd.to_datetime(["2024-01-02"])
        )  # Single day return

        # Mock positions
        positions_df = pd.DataFrame(
            {
                "date": pd.to_datetime(["2024-01-01", "2024-01-02"]),
                "symbol": ["AAPL", "AAPL"],
                "quantity": [10, 10],
            }
        )

        # Mock stock repository
        mock_stock = Stock(
            symbol="AAPL",
            name="Apple",
            country="US",
            industry="Technology",
            isin=None,
        )
        mock_stock_repo = AsyncMock()
        mock_stock_repo.get_all.return_value = [mock_stock]

        # Mock history repository
        mock_history_repo = AsyncMock()
        mock_history_repo.get_daily_range.return_value = [
            DailyPrice(date="2024-01-02", close_price=100.0)
        ]

        with patch(
            "app.domain.analytics.attribution.performance.reconstruct_historical_positions",
            new_callable=AsyncMock,
        ) as mock_reconstruct:
            with patch(
                "app.domain.analytics.attribution.performance.StockRepository",
                return_value=mock_stock_repo,
            ):
                with patch(
                    "app.domain.analytics.attribution.performance.HistoryRepository",
                    return_value=mock_history_repo,
                ):
                    mock_reconstruct.return_value = positions_df

                    result = await get_performance_attribution(
                        returns, "2024-01-01", "2024-01-31"
                    )

                    assert "country" in result
                    assert "industry" in result
                    # Should have attributed some return to US and Technology
                    assert len(result["country"]) > 0 or len(result["industry"]) > 0

    @pytest.mark.asyncio
    async def test_skips_dates_with_no_positions(self):
        """Test that dates with no positions are skipped."""
        from app.domain.analytics.attribution.performance import (
            get_performance_attribution,
        )

        returns = pd.Series(
            [0.01, 0.02],
            index=pd.to_datetime(["2024-01-01", "2024-01-02"]),
        )

        # Positions only on 2024-01-02
        positions_df = pd.DataFrame(
            {
                "date": pd.to_datetime(["2024-01-02"]),
                "symbol": ["AAPL"],
                "quantity": [10],
            }
        )

        mock_stock_repo = AsyncMock()
        mock_stock_repo.get_all.return_value = []

        mock_history_repo = AsyncMock()
        mock_history_repo.get_daily_range.return_value = []

        with patch(
            "app.domain.analytics.attribution.performance.reconstruct_historical_positions",
            new_callable=AsyncMock,
        ) as mock_reconstruct:
            with patch(
                "app.domain.analytics.attribution.performance.StockRepository",
                return_value=mock_stock_repo,
            ):
                with patch(
                    "app.domain.analytics.attribution.performance.HistoryRepository",
                    return_value=mock_history_repo,
                ):
                    mock_reconstruct.return_value = positions_df

                    result = await get_performance_attribution(
                        returns, "2024-01-01", "2024-01-31"
                    )

                    # Should handle gracefully (may return empty if no valid prices)
                    assert isinstance(result, dict)
                    assert "country" in result
                    assert "industry" in result

    @pytest.mark.asyncio
    async def test_skips_zero_total_value(self):
        """Test that dates with zero total value are skipped."""
        from app.domain.analytics.attribution.performance import (
            get_performance_attribution,
        )

        returns = pd.Series(
            [0.01], index=pd.to_datetime(["2024-01-02"])
        )

        # Position with zero quantity
        positions_df = pd.DataFrame(
            {
                "date": pd.to_datetime(["2024-01-02"]),
                "symbol": ["AAPL"],
                "quantity": [0],  # Zero quantity
            }
        )

        mock_stock_repo = AsyncMock()
        mock_stock_repo.get_all.return_value = []

        with patch(
            "app.domain.analytics.attribution.performance.reconstruct_historical_positions",
            new_callable=AsyncMock,
        ) as mock_reconstruct:
            with patch(
                "app.domain.analytics.attribution.performance.StockRepository",
                return_value=mock_stock_repo,
            ):
                mock_reconstruct.return_value = positions_df

                result = await get_performance_attribution(
                    returns, "2024-01-01", "2024-01-31"
                )

                # Should return empty attribution (zero positions skipped)
                assert result == {"country": {}, "industry": {}}

