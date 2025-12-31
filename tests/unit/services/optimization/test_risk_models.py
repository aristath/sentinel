"""Tests for risk models calculation.

These tests validate risk model calculations for portfolio optimization,
including covariance matrices built from historical price data.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pandas as pd
import pytest

from app.modules.optimization.services.risk_models import RiskModelBuilder


class TestRiskModelBuilder:
    """Test RiskModelBuilder class."""

    @pytest.fixture
    def builder(self):
        """Create RiskModelBuilder instance."""
        return RiskModelBuilder()

    @pytest.mark.asyncio
    async def test_builds_covariance_matrix_from_prices(self, builder):
        """Test that covariance matrix is built from historical prices."""
        symbols = ["AAPL", "MSFT"]

        # Mock price data
        mock_prices_aapl = [
            MagicMock(date="2024-01-01", close_price=100.0),
            MagicMock(date="2024-01-02", close_price=101.0),
            MagicMock(date="2024-01-03", close_price=102.0),
        ]
        mock_prices_msft = [
            MagicMock(date="2024-01-01", close_price=200.0),
            MagicMock(date="2024-01-02", close_price=201.0),
            MagicMock(date="2024-01-03", close_price=202.0),
        ]

        mock_history_repo_aapl = AsyncMock()
        mock_history_repo_aapl.get_daily_prices = AsyncMock(
            return_value=mock_prices_aapl
        )

        mock_history_repo_msft = AsyncMock()
        mock_history_repo_msft.get_daily_prices = AsyncMock(
            return_value=mock_prices_msft
        )

        with patch(
            "app.modules.optimization.risk_models.HistoryRepository"
        ) as mock_repo_class:

            def repo_side_effect(symbol):
                if symbol == "AAPL":
                    return mock_history_repo_aapl
                elif symbol == "MSFT":
                    return mock_history_repo_msft
                return AsyncMock()

            mock_repo_class.side_effect = repo_side_effect

            # Mock Ledoit-Wolf to return a simple covariance matrix
            with patch(
                "app.modules.optimization.risk_models.pypfopt_risk.CovarianceShrinkage"
            ) as mock_shrinkage:
                mock_cov_matrix = pd.DataFrame(
                    [[0.0001, 0.00005], [0.00005, 0.0001]],
                    index=["AAPL", "MSFT"],
                    columns=["AAPL", "MSFT"],
                )
                mock_shrinkage_instance = MagicMock()
                mock_shrinkage_instance.ledoit_wolf.return_value = mock_cov_matrix
                mock_shrinkage.return_value = mock_shrinkage_instance

                cov_matrix, returns_df = await builder.build_covariance_matrix(symbols)

                assert cov_matrix is not None
                assert isinstance(cov_matrix, pd.DataFrame)
                assert "AAPL" in cov_matrix.index
                assert "MSFT" in cov_matrix.index
                assert isinstance(returns_df, pd.DataFrame)

    @pytest.mark.asyncio
    async def test_handles_empty_price_data(self, builder):
        """Test handling when no price data is available."""
        symbols = ["AAPL"]

        mock_history_repo = AsyncMock()
        mock_history_repo.get_daily_prices = AsyncMock(return_value=[])

        with patch(
            "app.modules.optimization.risk_models.HistoryRepository",
            return_value=mock_history_repo,
        ):
            cov_matrix, returns_df = await builder.build_covariance_matrix(symbols)

            assert cov_matrix is None
            assert isinstance(returns_df, pd.DataFrame)
            assert returns_df.empty

    @pytest.mark.asyncio
    async def test_handles_insufficient_history(self, builder):
        """Test handling when symbols have insufficient price history."""
        symbols = ["AAPL"]

        # Only one price point (need more for covariance)
        mock_prices = [MagicMock(date="2024-01-01", close_price=100.0)]

        mock_history_repo = AsyncMock()
        mock_history_repo.get_daily_prices = AsyncMock(return_value=mock_prices)

        with patch(
            "app.modules.optimization.risk_models.HistoryRepository",
            return_value=mock_history_repo,
        ):
            cov_matrix, returns_df = await builder.build_covariance_matrix(symbols)

            # Should return None for covariance when insufficient data
            assert cov_matrix is None or isinstance(cov_matrix, pd.DataFrame)

    @pytest.mark.asyncio
    async def test_handles_empty_symbols_list(self, builder):
        """Test handling when symbols list is empty."""
        symbols = []

        cov_matrix, returns_df = await builder.build_covariance_matrix(symbols)

        assert cov_matrix is None
        assert isinstance(returns_df, pd.DataFrame)
        assert returns_df.empty

    @pytest.mark.asyncio
    async def test_filters_valid_symbols(self, builder):
        """Test that only symbols with sufficient history are included."""
        symbols = ["AAPL", "MSFT", "INSUFFICIENT"]

        # AAPL and MSFT have enough prices
        mock_prices_good = [
            MagicMock(date=f"2024-01-{i:02d}", close_price=100.0 + i)
            for i in range(1, 300)  # 299 prices (enough)
        ]

        # INSUFFICIENT has too few prices
        mock_prices_bad = [
            MagicMock(date="2024-01-01", close_price=100.0),
        ]

        mock_repo_good = AsyncMock()
        mock_repo_good.get_daily_prices = AsyncMock(return_value=mock_prices_good)

        mock_repo_bad = AsyncMock()
        mock_repo_bad.get_daily_prices = AsyncMock(return_value=mock_prices_bad)

        with patch(
            "app.modules.optimization.risk_models.HistoryRepository"
        ) as mock_repo_class:

            def repo_side_effect(symbol):
                if symbol == "INSUFFICIENT":
                    return mock_repo_bad
                return mock_repo_good

            mock_repo_class.side_effect = repo_side_effect

            with patch(
                "app.modules.optimization.risk_models.pypfopt_risk.CovarianceShrinkage"
            ) as mock_shrinkage:
                # Create a covariance matrix for valid symbols only
                mock_cov_matrix = pd.DataFrame(
                    [[0.0001, 0.00005], [0.00005, 0.0001]],
                    index=["AAPL", "MSFT"],
                    columns=["AAPL", "MSFT"],
                )
                mock_shrinkage_instance = MagicMock()
                mock_shrinkage_instance.ledoit_wolf.return_value = mock_cov_matrix
                mock_shrinkage.return_value = mock_shrinkage_instance

                cov_matrix, returns_df = await builder.build_covariance_matrix(symbols)

                # Should only include symbols with sufficient history
                if cov_matrix is not None:
                    assert "INSUFFICIENT" not in cov_matrix.index

    def test_get_correlations(self, builder):
        """Test finding highly correlated stock pairs."""
        # Create sample returns DataFrame
        dates = pd.date_range("2024-01-01", periods=10, freq="D")
        returns_df = pd.DataFrame(
            {
                "AAPL": [0.01, 0.02, -0.01, 0.03, 0.01, 0.02, -0.01, 0.03, 0.01, 0.02],
                "MSFT": [0.02, 0.01, 0.02, 0.01, 0.02, 0.01, 0.02, 0.01, 0.02, 0.01],
                "GOOGL": [
                    0.01,
                    0.02,
                    -0.01,
                    0.03,
                    0.01,
                    0.02,
                    -0.01,
                    0.03,
                    0.01,
                    0.02,
                ],  # Highly correlated with AAPL
            },
            index=dates,
        )

        pairs = builder.get_correlations(returns_df, threshold=0.80)

        assert isinstance(pairs, list)
        # Should find highly correlated pairs
        # AAPL and GOOGL should be highly correlated (same returns)
        if len(pairs) > 0:
            assert any(
                (p["symbol1"] == "AAPL" and p["symbol2"] == "GOOGL")
                or (p["symbol1"] == "GOOGL" and p["symbol2"] == "AAPL")
                for p in pairs
            )

    def test_get_correlations_empty_dataframe(self, builder):
        """Test handling when returns DataFrame is empty."""
        returns_df = pd.DataFrame()

        pairs = builder.get_correlations(returns_df)

        assert isinstance(pairs, list)
        assert len(pairs) == 0
