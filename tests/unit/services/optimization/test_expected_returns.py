"""Tests for ExpectedReturnsCalculator.

These tests verify the expected return calculation formula which is CRITICAL
for portfolio optimization and affects all trade recommendations.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.application.services.optimization.expected_returns import (
    ExpectedReturnsCalculator,
)
from app.domain.scoring.constants import (
    EXPECTED_RETURN_MAX,
    EXPECTED_RETURN_MIN,
    EXPECTED_RETURNS_CAGR_WEIGHT,
    EXPECTED_RETURNS_SCORE_WEIGHT,
)


class TestExpectedReturnsFormula:
    """Test the expected returns calculation formula."""

    @pytest.mark.asyncio
    async def test_basic_expected_return_calculation(self):
        """Test basic expected return calculation with all components."""
        mock_calc_repo = AsyncMock()
        mock_calc_repo.get_metrics.return_value = {
            "CAGR_5Y": 0.10,  # 10% CAGR
            "DIVIDEND_YIELD": 0.02,  # 2% dividend
        }

        mock_score_repo = AsyncMock()
        mock_score = MagicMock()
        mock_score.total_score = 0.7  # Good score
        mock_score_repo.get_by_symbol.return_value = mock_score

        mock_stock_repo = AsyncMock()
        mock_stock = MagicMock()
        mock_stock.priority_multiplier = 1.0  # No multiplier
        mock_stock_repo.get_by_symbol.return_value = mock_stock

        calculator = ExpectedReturnsCalculator(
            calc_repo=mock_calc_repo,
            score_repo=mock_score_repo,
            stock_repo=mock_stock_repo,
        )

        result = await calculator._calculate_single(
            symbol="AAPL",
            target_return=0.11,
            dividend_bonus=0.0,
        )

        # Expected calculation:
        # total_return_cagr = 0.10 + 0.02 = 0.12
        # score_factor = 0.7 / 0.5 = 1.4
        # base = 0.12 * 0.7 + 0.11 * 1.4 * 0.3 = 0.084 + 0.0462 = 0.1302
        assert result is not None
        assert result > 0
        # Should be around 13% based on the calculation
        assert 0.10 < result < 0.20

    @pytest.mark.asyncio
    async def test_expected_return_with_dividend_bonus(self):
        """Test that dividend bonus is added correctly."""
        mock_calc_repo = AsyncMock()
        mock_calc_repo.get_metrics.return_value = {"CAGR_5Y": 0.08}

        mock_score_repo = AsyncMock()
        mock_score = MagicMock()
        mock_score.total_score = 0.5
        mock_score_repo.get_by_symbol.return_value = mock_score

        mock_stock_repo = AsyncMock()
        mock_stock = MagicMock()
        mock_stock.priority_multiplier = 1.0
        mock_stock_repo.get_by_symbol.return_value = mock_stock

        calculator = ExpectedReturnsCalculator(
            calc_repo=mock_calc_repo,
            score_repo=mock_score_repo,
            stock_repo=mock_stock_repo,
        )

        # Calculate without bonus
        result_no_bonus = await calculator._calculate_single(
            symbol="AAPL",
            target_return=0.11,
            dividend_bonus=0.0,
        )

        # Calculate with 5% bonus
        result_with_bonus = await calculator._calculate_single(
            symbol="AAPL",
            target_return=0.11,
            dividend_bonus=0.05,
        )

        # Bonus should add 5% to the result
        assert result_with_bonus is not None
        assert result_no_bonus is not None
        assert result_with_bonus == pytest.approx(result_no_bonus + 0.05, rel=0.01)

    @pytest.mark.asyncio
    async def test_expected_return_with_priority_multiplier(self):
        """Test that priority multiplier affects the return."""
        mock_calc_repo = AsyncMock()
        mock_calc_repo.get_metrics.return_value = {"CAGR_5Y": 0.10}

        mock_score_repo = AsyncMock()
        mock_score = MagicMock()
        mock_score.total_score = 0.5
        mock_score_repo.get_by_symbol.return_value = mock_score

        mock_stock_repo = AsyncMock()
        calculator = ExpectedReturnsCalculator(
            calc_repo=mock_calc_repo,
            score_repo=mock_score_repo,
            stock_repo=mock_stock_repo,
        )

        # Test with 1.0 multiplier
        mock_stock = MagicMock()
        mock_stock.priority_multiplier = 1.0
        mock_stock_repo.get_by_symbol.return_value = mock_stock

        result_1x = await calculator._calculate_single(
            symbol="AAPL", target_return=0.11, dividend_bonus=0.0
        )

        # Test with 1.5 multiplier (high priority stock)
        mock_stock.priority_multiplier = 1.5
        mock_stock_repo.get_by_symbol.return_value = mock_stock

        result_1_5x = await calculator._calculate_single(
            symbol="AAPL", target_return=0.11, dividend_bonus=0.0
        )

        # Higher multiplier should give higher return
        assert result_1_5x > result_1x

    @pytest.mark.asyncio
    async def test_expected_return_clamped_to_max(self):
        """Test that expected return is clamped to maximum (30%)."""
        mock_calc_repo = AsyncMock()
        mock_calc_repo.get_metrics.return_value = {
            "CAGR_5Y": 0.50,  # Unrealistically high CAGR
            "DIVIDEND_YIELD": 0.10,
        }

        mock_score_repo = AsyncMock()
        mock_score = MagicMock()
        mock_score.total_score = 1.0  # Maximum score
        mock_score_repo.get_by_symbol.return_value = mock_score

        mock_stock_repo = AsyncMock()
        mock_stock = MagicMock()
        mock_stock.priority_multiplier = 2.0  # High multiplier
        mock_stock_repo.get_by_symbol.return_value = mock_stock

        calculator = ExpectedReturnsCalculator(
            calc_repo=mock_calc_repo,
            score_repo=mock_score_repo,
            stock_repo=mock_stock_repo,
        )

        result = await calculator._calculate_single(
            symbol="AAPL",
            target_return=0.11,
            dividend_bonus=0.10,  # Another 10% bonus
        )

        # Should be clamped to max
        assert result == EXPECTED_RETURN_MAX

    @pytest.mark.asyncio
    async def test_expected_return_clamped_to_min(self):
        """Test that expected return is clamped to minimum (-10%)."""
        mock_calc_repo = AsyncMock()
        mock_calc_repo.get_metrics.return_value = {
            "CAGR_5Y": -0.30,  # Very negative CAGR (declining company)
        }

        mock_score_repo = AsyncMock()
        mock_score = MagicMock()
        mock_score.total_score = 0.1  # Very low score
        mock_score_repo.get_by_symbol.return_value = mock_score

        mock_stock_repo = AsyncMock()
        mock_stock = MagicMock()
        mock_stock.priority_multiplier = 1.0
        mock_stock_repo.get_by_symbol.return_value = mock_stock

        calculator = ExpectedReturnsCalculator(
            calc_repo=mock_calc_repo,
            score_repo=mock_score_repo,
            stock_repo=mock_stock_repo,
        )

        result = await calculator._calculate_single(
            symbol="AAPL",
            target_return=0.11,
            dividend_bonus=0.0,
        )

        # Should be clamped to min
        assert result >= EXPECTED_RETURN_MIN


class TestExpectedReturnsDataHandling:
    """Test handling of missing or incomplete data."""

    @pytest.mark.asyncio
    async def test_returns_none_when_no_cagr(self):
        """Test that None is returned when no CAGR data exists."""
        mock_calc_repo = AsyncMock()
        mock_calc_repo.get_metrics.return_value = {}  # No CAGR data

        mock_score_repo = AsyncMock()
        mock_stock_repo = AsyncMock()

        calculator = ExpectedReturnsCalculator(
            calc_repo=mock_calc_repo,
            score_repo=mock_score_repo,
            stock_repo=mock_stock_repo,
        )

        result = await calculator._calculate_single(
            symbol="AAPL",
            target_return=0.11,
            dividend_bonus=0.0,
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_uses_10y_cagr_as_fallback(self):
        """Test that 10Y CAGR is used when 5Y is not available."""
        mock_calc_repo = AsyncMock()
        mock_calc_repo.get_metrics.return_value = {
            "CAGR_10Y": 0.08,  # Only 10Y available
        }

        mock_score_repo = AsyncMock()
        mock_score = MagicMock()
        mock_score.total_score = 0.5
        mock_score_repo.get_by_symbol.return_value = mock_score

        mock_stock_repo = AsyncMock()
        mock_stock = MagicMock()
        mock_stock.priority_multiplier = 1.0
        mock_stock_repo.get_by_symbol.return_value = mock_stock

        calculator = ExpectedReturnsCalculator(
            calc_repo=mock_calc_repo,
            score_repo=mock_score_repo,
            stock_repo=mock_stock_repo,
        )

        result = await calculator._calculate_single(
            symbol="AAPL",
            target_return=0.11,
            dividend_bonus=0.0,
        )

        # Should work with 10Y CAGR
        assert result is not None
        assert result > 0

    @pytest.mark.asyncio
    async def test_uses_default_score_when_missing(self):
        """Test that default score of 0.5 is used when score is missing."""
        mock_calc_repo = AsyncMock()
        mock_calc_repo.get_metrics.return_value = {"CAGR_5Y": 0.10}

        mock_score_repo = AsyncMock()
        mock_score_repo.get_by_symbol.return_value = None  # No score

        mock_stock_repo = AsyncMock()
        mock_stock = MagicMock()
        mock_stock.priority_multiplier = 1.0
        mock_stock_repo.get_by_symbol.return_value = mock_stock

        calculator = ExpectedReturnsCalculator(
            calc_repo=mock_calc_repo,
            score_repo=mock_score_repo,
            stock_repo=mock_stock_repo,
        )

        result = await calculator._calculate_single(
            symbol="AAPL",
            target_return=0.11,
            dividend_bonus=0.0,
        )

        # Should work with default score
        assert result is not None


class TestExpectedReturnsBulkCalculation:
    """Test bulk calculation of expected returns."""

    @pytest.mark.asyncio
    async def test_calculate_expected_returns_for_multiple_symbols(self):
        """Test calculating returns for multiple symbols."""
        mock_calc_repo = AsyncMock()
        mock_calc_repo.get_metrics.return_value = {"CAGR_5Y": 0.10}

        mock_score_repo = AsyncMock()
        mock_score = MagicMock()
        mock_score.total_score = 0.6
        mock_score_repo.get_by_symbol.return_value = mock_score

        mock_stock_repo = AsyncMock()
        mock_stock = MagicMock()
        mock_stock.priority_multiplier = 1.0
        mock_stock_repo.get_by_symbol.return_value = mock_stock

        calculator = ExpectedReturnsCalculator(
            calc_repo=mock_calc_repo,
            score_repo=mock_score_repo,
            stock_repo=mock_stock_repo,
        )

        symbols = ["AAPL", "GOOGL", "MSFT"]
        result = await calculator.calculate_expected_returns(
            symbols=symbols,
            target_return=0.11,
        )

        # Should have returns for all symbols
        assert len(result) == 3
        assert "AAPL" in result
        assert "GOOGL" in result
        assert "MSFT" in result

    @pytest.mark.asyncio
    async def test_calculate_expected_returns_skips_symbols_without_data(self):
        """Test that symbols without CAGR data are skipped."""
        mock_calc_repo = AsyncMock()

        # First symbol has data, second doesn't
        async def mock_get_metrics(symbol, metrics):
            if symbol == "AAPL":
                return {"CAGR_5Y": 0.10}
            return {}

        mock_calc_repo.get_metrics = mock_get_metrics

        mock_score_repo = AsyncMock()
        mock_score = MagicMock()
        mock_score.total_score = 0.5
        mock_score_repo.get_by_symbol.return_value = mock_score

        mock_stock_repo = AsyncMock()
        mock_stock = MagicMock()
        mock_stock.priority_multiplier = 1.0
        mock_stock_repo.get_by_symbol.return_value = mock_stock

        calculator = ExpectedReturnsCalculator(
            calc_repo=mock_calc_repo,
            score_repo=mock_score_repo,
            stock_repo=mock_stock_repo,
        )

        symbols = ["AAPL", "NEWSTOCK"]
        result = await calculator.calculate_expected_returns(
            symbols=symbols,
            target_return=0.11,
        )

        # Only AAPL should be in results
        assert len(result) == 1
        assert "AAPL" in result
        assert "NEWSTOCK" not in result

    @pytest.mark.asyncio
    async def test_calculate_expected_returns_with_dividend_bonuses(self):
        """Test that dividend bonuses are applied per-symbol."""
        mock_calc_repo = AsyncMock()
        mock_calc_repo.get_metrics.return_value = {"CAGR_5Y": 0.10}

        mock_score_repo = AsyncMock()
        mock_score = MagicMock()
        mock_score.total_score = 0.5
        mock_score_repo.get_by_symbol.return_value = mock_score

        mock_stock_repo = AsyncMock()
        mock_stock = MagicMock()
        mock_stock.priority_multiplier = 1.0
        mock_stock_repo.get_by_symbol.return_value = mock_stock

        calculator = ExpectedReturnsCalculator(
            calc_repo=mock_calc_repo,
            score_repo=mock_score_repo,
            stock_repo=mock_stock_repo,
        )

        symbols = ["AAPL", "GOOGL"]
        dividend_bonuses = {"AAPL": 0.05}  # 5% bonus for AAPL only

        result = await calculator.calculate_expected_returns(
            symbols=symbols,
            target_return=0.11,
            dividend_bonuses=dividend_bonuses,
        )

        # AAPL should have higher return due to bonus
        assert result["AAPL"] > result["GOOGL"]


class TestGetSymbolsWithData:
    """Test the data availability filter."""

    @pytest.mark.asyncio
    async def test_filters_to_symbols_with_cagr(self):
        """Test that only symbols with CAGR data are returned."""
        mock_calc_repo = AsyncMock()

        async def mock_get_metrics(symbol, metrics):
            if symbol in ["AAPL", "MSFT"]:
                return {"CAGR_5Y": 0.10}
            return {}

        mock_calc_repo.get_metrics = mock_get_metrics

        mock_score_repo = AsyncMock()
        mock_stock_repo = AsyncMock()
        calculator = ExpectedReturnsCalculator(
            calc_repo=mock_calc_repo,
            score_repo=mock_score_repo,
            stock_repo=mock_stock_repo,
        )

        symbols = ["AAPL", "GOOGL", "MSFT"]
        result = await calculator.get_symbols_with_data(symbols)

        assert len(result) == 2
        assert "AAPL" in result
        assert "MSFT" in result
        assert "GOOGL" not in result
