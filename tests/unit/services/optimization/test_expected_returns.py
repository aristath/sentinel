"""Tests for expected returns calculation.

These tests validate expected returns calculations for portfolio optimization,
including CAGR-based returns, score adjustments, and regime handling.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.application.services.optimization.expected_returns import (
    ExpectedReturnsCalculator,
)


class TestExpectedReturnsCalculator:
    """Test ExpectedReturnsCalculator class."""

    @pytest.fixture
    def mock_calc_repo(self):
        """Mock CalculationsRepository."""
        repo = AsyncMock()
        return repo

    @pytest.fixture
    def mock_score_repo(self):
        """Mock ScoreRepository."""
        repo = AsyncMock()
        return repo

    @pytest.fixture
    def mock_stock_repo(self):
        """Mock StockRepository."""
        repo = AsyncMock()
        return repo

    @pytest.fixture
    def calculator(self, mock_calc_repo, mock_score_repo, mock_stock_repo):
        """Create ExpectedReturnsCalculator with mocked dependencies."""
        return ExpectedReturnsCalculator(
            calc_repo=mock_calc_repo,
            score_repo=mock_score_repo,
            stock_repo=mock_stock_repo,
        )

    @pytest.mark.asyncio
    async def test_calculates_returns_with_cagr_and_score(
        self, calculator, mock_calc_repo, mock_score_repo, mock_stock_repo
    ):
        """Test that expected returns are calculated from CAGR and score."""
        symbols = ["AAPL"]

        # Mock CAGR data
        mock_calc_repo.get_metrics = AsyncMock(
            return_value={
                "CAGR_5Y": 0.12,  # 12% CAGR
                "DIVIDEND_YIELD": 0.02,  # 2% dividend yield
            }
        )

        # Mock score
        mock_score = MagicMock()
        mock_score.total_score = 0.75  # 75% score
        mock_score_repo.get_by_symbol = AsyncMock(return_value=mock_score)

        # Mock stock
        mock_stock = MagicMock()
        mock_stock.priority_multiplier = 1.0
        mock_stock_repo.get_by_symbol = AsyncMock(return_value=mock_stock)

        # Mock market indicators
        with (
            patch(
                "app.modules.optimization.expected_returns.market_indicators.get_vix",
                new_callable=AsyncMock,
            ) as mock_vix,
            patch(
                "app.modules.optimization.expected_returns.market_indicators.get_treasury_yields",
                new_callable=AsyncMock,
            ) as mock_yields,
            patch(
                "app.modules.optimization.expected_returns.market_indicators.get_market_pe",
                new_callable=AsyncMock,
            ) as mock_pe,
        ):
            mock_vix.return_value = None
            mock_yields.return_value = None
            mock_pe.return_value = None

            result = await calculator.calculate_expected_returns(symbols)

            assert isinstance(result, dict)
            assert "AAPL" in result
            assert isinstance(result["AAPL"], float)
            # Expected return should be positive
            assert result["AAPL"] > 0

    @pytest.mark.asyncio
    async def test_handles_missing_cagr_data(self, calculator, mock_calc_repo):
        """Test handling when CAGR data is missing."""
        symbols = ["AAPL"]

        # Mock missing CAGR
        mock_calc_repo.get_metrics = AsyncMock(return_value={})

        with (
            patch(
                "app.modules.optimization.expected_returns.market_indicators.get_vix",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch(
                "app.modules.optimization.expected_returns.market_indicators.get_treasury_yields",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch(
                "app.modules.optimization.expected_returns.market_indicators.get_market_pe",
                new_callable=AsyncMock,
                return_value=None,
            ),
        ):
            result = await calculator.calculate_expected_returns(symbols)

            # Should skip symbols without CAGR
            assert "AAPL" not in result or len(result) == 0

    @pytest.mark.asyncio
    async def test_handles_empty_symbols_list(self, calculator):
        """Test handling when symbols list is empty."""
        symbols = []

        with (
            patch(
                "app.modules.optimization.expected_returns.market_indicators.get_vix",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch(
                "app.modules.optimization.expected_returns.market_indicators.get_treasury_yields",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch(
                "app.modules.optimization.expected_returns.market_indicators.get_market_pe",
                new_callable=AsyncMock,
                return_value=None,
            ),
        ):
            result = await calculator.calculate_expected_returns(symbols)

            assert isinstance(result, dict)
            assert len(result) == 0

    @pytest.mark.asyncio
    async def test_applies_regime_adjustment(
        self, calculator, mock_calc_repo, mock_score_repo, mock_stock_repo
    ):
        """Test that bear regime reduces expected returns."""
        symbols = ["AAPL"]

        mock_calc_repo.get_metrics = AsyncMock(
            return_value={
                "CAGR_5Y": 0.12,
                "DIVIDEND_YIELD": 0.02,
            }
        )

        mock_score = MagicMock()
        mock_score.total_score = 0.75
        mock_score_repo.get_by_symbol = AsyncMock(return_value=mock_score)

        mock_stock = MagicMock()
        mock_stock.priority_multiplier = 1.0
        mock_stock_repo.get_by_symbol = AsyncMock(return_value=mock_stock)

        with (
            patch(
                "app.modules.optimization.expected_returns.market_indicators.get_vix",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch(
                "app.modules.optimization.expected_returns.market_indicators.get_treasury_yields",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch(
                "app.modules.optimization.expected_returns.market_indicators.get_market_pe",
                new_callable=AsyncMock,
                return_value=None,
            ),
        ):
            # Test default regime
            result_default = await calculator.calculate_expected_returns(
                symbols, regime=None
            )

            # Test bear regime (should reduce returns by ~25%)
            result_bear = await calculator.calculate_expected_returns(
                symbols, regime="bear"
            )

            assert "AAPL" in result_default
            assert "AAPL" in result_bear
            # Bear regime should have lower expected return
            assert result_bear["AAPL"] < result_default["AAPL"]

    @pytest.mark.asyncio
    async def test_applies_dividend_bonus(
        self, calculator, mock_calc_repo, mock_score_repo, mock_stock_repo
    ):
        """Test that dividend bonuses are added to expected returns."""
        symbols = ["AAPL"]

        mock_calc_repo.get_metrics = AsyncMock(
            return_value={
                "CAGR_5Y": 0.12,
                "DIVIDEND_YIELD": 0.02,
            }
        )

        mock_score = MagicMock()
        mock_score.total_score = 0.75
        mock_score_repo.get_by_symbol = AsyncMock(return_value=mock_score)

        mock_stock = MagicMock()
        mock_stock.priority_multiplier = 1.0
        mock_stock_repo.get_by_symbol = AsyncMock(return_value=mock_stock)

        with (
            patch(
                "app.modules.optimization.expected_returns.market_indicators.get_vix",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch(
                "app.modules.optimization.expected_returns.market_indicators.get_treasury_yields",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch(
                "app.modules.optimization.expected_returns.market_indicators.get_market_pe",
                new_callable=AsyncMock,
                return_value=None,
            ),
        ):
            # Without dividend bonus
            result_no_bonus = await calculator.calculate_expected_returns(symbols)

            # With dividend bonus
            dividend_bonuses = {"AAPL": 0.01}  # 1% bonus
            result_with_bonus = await calculator.calculate_expected_returns(
                symbols, dividend_bonuses=dividend_bonuses
            )

            assert "AAPL" in result_no_bonus
            assert "AAPL" in result_with_bonus
            # With bonus should be higher
            assert result_with_bonus["AAPL"] > result_no_bonus["AAPL"]

    @pytest.mark.asyncio
    async def test_get_symbols_with_data(self, calculator, mock_calc_repo):
        """Test filtering symbols to those with CAGR data."""
        symbols = ["AAPL", "MSFT", "UNKNOWN"]

        async def get_metrics_side_effect(symbol, metrics):
            if symbol == "AAPL":
                return {"CAGR_5Y": 0.12}
            elif symbol == "MSFT":
                return {"CAGR_10Y": 0.10}
            else:
                return {}  # No CAGR for UNKNOWN

        mock_calc_repo.get_metrics = AsyncMock(side_effect=get_metrics_side_effect)

        result = await calculator.get_symbols_with_data(symbols)

        assert "AAPL" in result
        assert "MSFT" in result
        assert "UNKNOWN" not in result
        assert len(result) == 2
