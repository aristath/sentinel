"""Tests for RiskModelBuilder.

These tests verify the covariance matrix calculation which is CRITICAL
for portfolio optimization risk assessment.
"""

from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pandas as pd
import pytest

from app.application.services.optimization.risk_models import RiskModelBuilder
from app.domain.scoring.constants import (
    COVARIANCE_MIN_HISTORY,
)


def create_mock_price_history(
    symbol: str,
    days: int,
    base_price: float = 100.0,
    volatility: float = 0.02,
) -> list:
    """Create mock price history for testing."""
    prices = []
    current_price = base_price
    start_date = date.today() - timedelta(days=days)

    for i in range(days):
        # Simple random walk
        change = np.random.normal(0, volatility)
        current_price *= 1 + change
        mock_price = MagicMock()
        mock_price.date = start_date + timedelta(days=i)
        mock_price.close_price = current_price
        prices.append(mock_price)

    return prices


class TestRiskModelBuilderCovarianceMatrix:
    """Test covariance matrix building."""

    @pytest.mark.asyncio
    async def test_build_covariance_matrix_returns_dataframe(self):
        """Test that build_covariance_matrix returns a valid DataFrame."""
        builder = RiskModelBuilder()

        # Create mock price data
        np.random.seed(42)  # For reproducibility
        symbols = ["AAPL", "GOOGL", "MSFT"]

        with patch.object(builder, "_fetch_prices") as mock_fetch:
            # Create price DataFrame with enough history
            dates = pd.date_range(
                end=date.today(), periods=COVARIANCE_MIN_HISTORY + 10, freq="D"
            )
            data = {
                "AAPL": 100 + np.cumsum(np.random.normal(0, 2, len(dates))),
                "GOOGL": 150 + np.cumsum(np.random.normal(0, 3, len(dates))),
                "MSFT": 200 + np.cumsum(np.random.normal(0, 2.5, len(dates))),
            }
            mock_fetch.return_value = pd.DataFrame(data, index=dates)

            cov_matrix, returns_df = await builder.build_covariance_matrix(symbols)

            assert cov_matrix is not None
            assert isinstance(cov_matrix, pd.DataFrame)
            assert list(cov_matrix.columns) == symbols
            assert list(cov_matrix.index) == symbols

    @pytest.mark.asyncio
    async def test_covariance_matrix_is_symmetric(self):
        """Test that the covariance matrix is symmetric."""
        builder = RiskModelBuilder()
        np.random.seed(42)
        symbols = ["AAPL", "GOOGL", "MSFT"]

        with patch.object(builder, "_fetch_prices") as mock_fetch:
            dates = pd.date_range(
                end=date.today(), periods=COVARIANCE_MIN_HISTORY + 10, freq="D"
            )
            data = {
                "AAPL": 100 + np.cumsum(np.random.normal(0, 2, len(dates))),
                "GOOGL": 150 + np.cumsum(np.random.normal(0, 3, len(dates))),
                "MSFT": 200 + np.cumsum(np.random.normal(0, 2.5, len(dates))),
            }
            mock_fetch.return_value = pd.DataFrame(data, index=dates)

            cov_matrix, _ = await builder.build_covariance_matrix(symbols)

            # Check symmetry
            assert cov_matrix is not None
            for i, sym1 in enumerate(symbols):
                for j, sym2 in enumerate(symbols):
                    assert cov_matrix.loc[sym1, sym2] == pytest.approx(
                        cov_matrix.loc[sym2, sym1], rel=1e-10
                    )

    @pytest.mark.asyncio
    async def test_covariance_matrix_positive_diagonal(self):
        """Test that covariance matrix has positive diagonal (variances)."""
        builder = RiskModelBuilder()
        np.random.seed(42)
        symbols = ["AAPL", "GOOGL", "MSFT"]

        with patch.object(builder, "_fetch_prices") as mock_fetch:
            dates = pd.date_range(
                end=date.today(), periods=COVARIANCE_MIN_HISTORY + 10, freq="D"
            )
            data = {
                "AAPL": 100 + np.cumsum(np.random.normal(0, 2, len(dates))),
                "GOOGL": 150 + np.cumsum(np.random.normal(0, 3, len(dates))),
                "MSFT": 200 + np.cumsum(np.random.normal(0, 2.5, len(dates))),
            }
            mock_fetch.return_value = pd.DataFrame(data, index=dates)

            cov_matrix, _ = await builder.build_covariance_matrix(symbols)

            # Diagonal elements (variances) must be positive
            assert cov_matrix is not None
            for symbol in symbols:
                assert cov_matrix.loc[symbol, symbol] > 0

    @pytest.mark.asyncio
    async def test_returns_none_when_empty_price_data(self):
        """Test that None is returned when no price data is available."""
        builder = RiskModelBuilder()

        with patch.object(builder, "_fetch_prices") as mock_fetch:
            mock_fetch.return_value = pd.DataFrame()

            cov_matrix, returns_df = await builder.build_covariance_matrix(
                ["AAPL", "GOOGL"]
            )

            assert cov_matrix is None
            assert returns_df.empty

    @pytest.mark.asyncio
    async def test_returns_none_when_only_one_valid_symbol(self):
        """Test that None is returned when only one symbol has valid data."""
        builder = RiskModelBuilder()
        np.random.seed(42)

        with patch.object(builder, "_fetch_prices") as mock_fetch:
            # Only AAPL has enough history
            dates = pd.date_range(
                end=date.today(), periods=COVARIANCE_MIN_HISTORY + 10, freq="D"
            )
            data = {
                "AAPL": 100 + np.cumsum(np.random.normal(0, 2, len(dates))),
                "GOOGL": [np.nan] * (len(dates) - 10)
                + list(150 + np.cumsum(np.random.normal(0, 3, 10))),
            }
            mock_fetch.return_value = pd.DataFrame(data, index=dates)

            cov_matrix, _ = await builder.build_covariance_matrix(["AAPL", "GOOGL"])

            assert cov_matrix is None


class TestRiskModelBuilderMinimumHistory:
    """Test minimum history requirements."""

    @pytest.mark.asyncio
    async def test_returns_none_with_insufficient_history(self):
        """Test that None is returned when history is below minimum."""
        builder = RiskModelBuilder()
        np.random.seed(42)
        symbols = ["AAPL", "GOOGL"]

        with patch.object(builder, "_fetch_prices") as mock_fetch:
            # Only 30 days, need at least COVARIANCE_MIN_HISTORY (60)
            dates = pd.date_range(end=date.today(), periods=30, freq="D")
            data = {
                "AAPL": 100 + np.cumsum(np.random.normal(0, 2, len(dates))),
                "GOOGL": 150 + np.cumsum(np.random.normal(0, 3, len(dates))),
            }
            mock_fetch.return_value = pd.DataFrame(data, index=dates)

            cov_matrix, returns_df = await builder.build_covariance_matrix(symbols)

            # After pct_change().dropna(), we lose one row
            # With 30 days, we get 29 returns, which is below 60
            assert cov_matrix is None

    @pytest.mark.asyncio
    async def test_works_with_exactly_minimum_history(self):
        """Test that it works with exactly the minimum required history."""
        builder = RiskModelBuilder()
        np.random.seed(42)
        symbols = ["AAPL", "GOOGL"]

        with patch.object(builder, "_fetch_prices") as mock_fetch:
            # Need COVARIANCE_MIN_HISTORY + 1 days to get COVARIANCE_MIN_HISTORY returns
            dates = pd.date_range(
                end=date.today(), periods=COVARIANCE_MIN_HISTORY + 1, freq="D"
            )
            data = {
                "AAPL": 100 + np.cumsum(np.random.normal(0, 2, len(dates))),
                "GOOGL": 150 + np.cumsum(np.random.normal(0, 3, len(dates))),
            }
            mock_fetch.return_value = pd.DataFrame(data, index=dates)

            cov_matrix, returns_df = await builder.build_covariance_matrix(symbols)

            assert cov_matrix is not None
            assert len(returns_df) == COVARIANCE_MIN_HISTORY


class TestRiskModelBuilderFilterValidSymbols:
    """Test symbol filtering based on data availability."""

    def test_filter_valid_symbols_excludes_insufficient_data(self):
        """Test that symbols with insufficient data are excluded."""
        builder = RiskModelBuilder()

        dates = pd.date_range(end=date.today(), periods=100, freq="D")
        data = {
            "AAPL": [100.0] * 100,  # Full data
            "GOOGL": [np.nan] * 50 + [150.0] * 50,  # Only 50 points
            "MSFT": [200.0] * 100,  # Full data
        }
        prices_df = pd.DataFrame(data, index=dates)

        valid = builder._filter_valid_symbols(prices_df)

        # GOOGL only has 50 data points, below COVARIANCE_MIN_HISTORY (60)
        assert "AAPL" in valid
        assert "MSFT" in valid
        assert "GOOGL" not in valid

    def test_filter_valid_symbols_keeps_sufficient_data(self):
        """Test that symbols with sufficient data are kept."""
        builder = RiskModelBuilder()

        dates = pd.date_range(end=date.today(), periods=100, freq="D")
        data = {
            "AAPL": [100.0] * 100,
            "GOOGL": [150.0] * 100,
            "MSFT": [200.0] * 100,
        }
        prices_df = pd.DataFrame(data, index=dates)

        valid = builder._filter_valid_symbols(prices_df)

        assert len(valid) == 3
        assert set(valid) == {"AAPL", "GOOGL", "MSFT"}


class TestRiskModelBuilderCorrelations:
    """Test high correlation detection."""

    def test_get_correlations_finds_high_correlations(self):
        """Test that highly correlated pairs are detected."""
        builder = RiskModelBuilder()
        np.random.seed(42)

        # Create returns where AAPL and MSFT are highly correlated
        n_days = 100
        base_returns = np.random.normal(0, 0.02, n_days)

        returns_df = pd.DataFrame(
            {
                "AAPL": base_returns + np.random.normal(0, 0.001, n_days),
                "MSFT": base_returns + np.random.normal(0, 0.001, n_days),  # Similar
                "GOOGL": np.random.normal(0, 0.02, n_days),  # Independent
            }
        )

        pairs = builder.get_correlations(returns_df, threshold=0.80)

        # AAPL and MSFT should be highly correlated
        assert len(pairs) >= 1
        high_corr_pair = pairs[0]
        assert {high_corr_pair["symbol1"], high_corr_pair["symbol2"]} == {
            "AAPL",
            "MSFT",
        }
        assert abs(high_corr_pair["correlation"]) >= 0.80

    def test_get_correlations_returns_empty_for_low_correlations(self):
        """Test that no pairs are returned when correlations are low."""
        builder = RiskModelBuilder()
        np.random.seed(42)

        # Create independent returns
        n_days = 100
        returns_df = pd.DataFrame(
            {
                "AAPL": np.random.normal(0, 0.02, n_days),
                "MSFT": np.random.normal(0, 0.02, n_days),
                "GOOGL": np.random.normal(0, 0.02, n_days),
            }
        )

        pairs = builder.get_correlations(returns_df, threshold=0.95)

        # With independent random returns, correlations should be low
        # The threshold of 0.95 should filter out all pairs
        assert len(pairs) == 0

    def test_get_correlations_empty_dataframe(self):
        """Test that empty list is returned for empty DataFrame."""
        builder = RiskModelBuilder()

        pairs = builder.get_correlations(pd.DataFrame(), threshold=0.80)

        assert pairs == []

    def test_get_correlations_sorted_by_absolute_value(self):
        """Test that pairs are sorted by absolute correlation (descending)."""
        builder = RiskModelBuilder()
        np.random.seed(42)

        # Create returns with varying correlations
        n_days = 100
        base1 = np.random.normal(0, 0.02, n_days)
        base2 = np.random.normal(0, 0.02, n_days)

        returns_df = pd.DataFrame(
            {
                "A": base1,
                "B": base1 + np.random.normal(0, 0.002, n_days),  # ~0.99 corr with A
                "C": base2,
                "D": base2 + np.random.normal(0, 0.005, n_days),  # ~0.95 corr with C
            }
        )

        pairs = builder.get_correlations(returns_df, threshold=0.80)

        # Check sorting - first pair should have highest absolute correlation
        if len(pairs) >= 2:
            assert abs(pairs[0]["correlation"]) >= abs(pairs[1]["correlation"])

    def test_get_correlations_custom_threshold(self):
        """Test that custom threshold is respected."""
        builder = RiskModelBuilder()
        np.random.seed(42)

        n_days = 100
        base = np.random.normal(0, 0.02, n_days)

        returns_df = pd.DataFrame(
            {
                "A": base,
                "B": base + np.random.normal(0, 0.01, n_days),  # ~0.9 correlation
            }
        )

        # With 0.95 threshold
        pairs_high = builder.get_correlations(returns_df, threshold=0.95)

        # With 0.50 threshold
        pairs_low = builder.get_correlations(returns_df, threshold=0.50)

        # Lower threshold should find more pairs (or same)
        assert len(pairs_low) >= len(pairs_high)


class TestRiskModelBuilderLedoitWolfShrinkage:
    """Test Ledoit-Wolf shrinkage application."""

    @pytest.mark.asyncio
    async def test_uses_ledoit_wolf_shrinkage(self):
        """Test that Ledoit-Wolf shrinkage is applied to covariance matrix."""
        builder = RiskModelBuilder()
        np.random.seed(42)
        symbols = ["AAPL", "GOOGL", "MSFT"]

        with patch.object(builder, "_fetch_prices") as mock_fetch:
            dates = pd.date_range(
                end=date.today(), periods=COVARIANCE_MIN_HISTORY + 10, freq="D"
            )
            data = {
                "AAPL": 100 + np.cumsum(np.random.normal(0, 2, len(dates))),
                "GOOGL": 150 + np.cumsum(np.random.normal(0, 3, len(dates))),
                "MSFT": 200 + np.cumsum(np.random.normal(0, 2.5, len(dates))),
            }
            mock_fetch.return_value = pd.DataFrame(data, index=dates)

            with patch(
                "app.application.services.optimization.risk_models.pypfopt_risk"
            ) as mock_pypfopt:
                # Create a mock return value for ledoit_wolf
                mock_cov = pd.DataFrame(
                    np.eye(3) * 0.001,
                    index=symbols,
                    columns=symbols,
                )
                mock_shrinkage = MagicMock()
                mock_shrinkage.ledoit_wolf.return_value = mock_cov
                mock_pypfopt.CovarianceShrinkage.return_value = mock_shrinkage

                cov_matrix, _ = await builder.build_covariance_matrix(symbols)

                # Verify CovarianceShrinkage was called
                mock_pypfopt.CovarianceShrinkage.assert_called_once()
                mock_shrinkage.ledoit_wolf.assert_called_once()


class TestRiskModelBuilderFetchPrices:
    """Test price fetching functionality."""

    @pytest.mark.asyncio
    async def test_fetch_prices_creates_dataframe(self):
        """Test that _fetch_prices creates a proper DataFrame."""
        builder = RiskModelBuilder()

        with patch(
            "app.application.services.optimization.risk_models.HistoryRepository"
        ) as MockRepo:
            # Setup mock
            mock_repo_instance = AsyncMock()
            MockRepo.return_value = mock_repo_instance

            # Create mock price data
            prices = []
            for i in range(10):
                mock_price = MagicMock()
                mock_price.date = date.today() - timedelta(days=10 - i)
                mock_price.close_price = 100.0 + i
                prices.append(mock_price)

            mock_repo_instance.get_daily_prices.return_value = prices

            result = await builder._fetch_prices(["AAPL"], lookback_days=30)

            assert isinstance(result, pd.DataFrame)
            assert "AAPL" in result.columns
            assert len(result) == 10

    @pytest.mark.asyncio
    async def test_fetch_prices_handles_missing_data(self):
        """Test that _fetch_prices handles symbols with no data."""
        builder = RiskModelBuilder()

        with patch(
            "app.application.services.optimization.risk_models.HistoryRepository"
        ) as MockRepo:
            mock_repo_instance = AsyncMock()
            MockRepo.return_value = mock_repo_instance

            # First symbol has data, second doesn't
            async def mock_get_prices(limit):
                symbol = MockRepo.call_args[0][0]
                if symbol == "AAPL":
                    prices = []
                    for i in range(10):
                        mock_price = MagicMock()
                        mock_price.date = date.today() - timedelta(days=10 - i)
                        mock_price.close_price = 100.0 + i
                        prices.append(mock_price)
                    return prices
                return []

            mock_repo_instance.get_daily_prices = mock_get_prices

            result = await builder._fetch_prices(["AAPL", "NODATA"], lookback_days=30)

            assert "AAPL" in result.columns
            # NODATA should not be in columns since it had no data
            assert "NODATA" not in result.columns

    @pytest.mark.asyncio
    async def test_fetch_prices_handles_exceptions(self):
        """Test that _fetch_prices handles exceptions gracefully."""
        builder = RiskModelBuilder()

        with patch(
            "app.application.services.optimization.risk_models.HistoryRepository"
        ) as MockRepo:
            mock_repo_instance = AsyncMock()
            MockRepo.return_value = mock_repo_instance

            # Raise exception for all symbols
            mock_repo_instance.get_daily_prices.side_effect = Exception("DB error")

            result = await builder._fetch_prices(["AAPL", "GOOGL"], lookback_days=30)

            assert result.empty


class TestRiskModelBuilderIntegration:
    """Integration tests for RiskModelBuilder."""

    @pytest.mark.asyncio
    async def test_full_pipeline_covariance_to_correlations(self):
        """Test full pipeline from prices to correlations."""
        builder = RiskModelBuilder()
        np.random.seed(42)
        symbols = ["AAPL", "GOOGL", "MSFT"]

        with patch.object(builder, "_fetch_prices") as mock_fetch:
            # Create correlated price data
            n_days = COVARIANCE_MIN_HISTORY + 20
            dates = pd.date_range(end=date.today(), periods=n_days, freq="D")

            # AAPL and MSFT will be correlated
            base = np.cumsum(np.random.normal(0, 2, n_days))
            data = {
                "AAPL": 100 + base,
                "MSFT": 200 + base * 1.5 + np.random.normal(0, 1, n_days),
                "GOOGL": 150 + np.cumsum(np.random.normal(0, 3, n_days)),
            }
            mock_fetch.return_value = pd.DataFrame(data, index=dates)

            # Build covariance matrix
            cov_matrix, returns_df = await builder.build_covariance_matrix(symbols)

            # Get correlations
            correlations = builder.get_correlations(returns_df, threshold=0.70)

            # Verify outputs
            assert cov_matrix is not None
            assert not returns_df.empty
            # AAPL and MSFT should be in the correlated pairs
            if len(correlations) > 0:
                symbols_in_pairs = set()
                for pair in correlations:
                    symbols_in_pairs.add(pair["symbol1"])
                    symbols_in_pairs.add(pair["symbol2"])
                assert "AAPL" in symbols_in_pairs or "MSFT" in symbols_in_pairs

    @pytest.mark.asyncio
    async def test_handles_forward_fill_for_holidays(self):
        """Test that forward fill handles missing dates (holidays)."""
        builder = RiskModelBuilder()
        np.random.seed(42)

        with patch.object(builder, "_fetch_prices") as mock_fetch:
            # Create data with some NaN values (simulating holidays)
            n_days = COVARIANCE_MIN_HISTORY + 10
            dates = pd.date_range(end=date.today(), periods=n_days, freq="D")

            prices_aapl = 100 + np.cumsum(np.random.normal(0, 2, n_days))
            prices_googl = 150 + np.cumsum(np.random.normal(0, 3, n_days))

            # Insert some NaN values
            prices_aapl[10] = np.nan
            prices_aapl[20] = np.nan
            prices_googl[15] = np.nan

            data = {
                "AAPL": prices_aapl,
                "GOOGL": prices_googl,
            }
            mock_fetch.return_value = pd.DataFrame(data, index=dates)

            # Should still work due to forward fill
            cov_matrix, returns_df = await builder.build_covariance_matrix(
                ["AAPL", "GOOGL"]
            )

            assert cov_matrix is not None
            # Returns should not have NaN after ffill
            assert not returns_df.isna().any().any()
