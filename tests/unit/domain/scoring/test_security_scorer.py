"""Tests for security_scorer module.

These tests validate the main security scoring orchestrator that:
- Combines 8 scoring groups with configurable weights
- Calculates total weighted scores
- Handles edge cases and missing data
- Uses the correct default weights
"""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.modules.scoring.domain.models import (
    CalculatedSecurityScore,
    PortfolioContext,
    PrefetchedStockData,
)
from app.modules.scoring.domain.security_scorer import (
    SCORE_WEIGHTS,
    calculate_security_score,
    calculate_security_score_from_prefetched,
)


class TestScoreWeights:
    """Test SCORE_WEIGHTS configuration."""

    def test_weights_sum_to_one(self):
        """Test that default weights sum to 1.0."""
        total = sum(SCORE_WEIGHTS.values())
        assert total == pytest.approx(1.0)

    def test_all_weights_positive(self):
        """Test that all weights are positive."""
        for weight in SCORE_WEIGHTS.values():
            assert weight > 0

    def test_has_all_required_groups(self):
        """Test that all 8 scoring groups are present."""
        expected_groups = {
            "long_term",
            "fundamentals",
            "opportunity",
            "dividends",
            "short_term",
            "technicals",
            "opinion",
            "diversification",
        }
        assert set(SCORE_WEIGHTS.keys()) == expected_groups


class TestCalculateStockScore:
    """Test calculate_security_score function."""

    @pytest.mark.asyncio
    async def test_returns_calculated_stock_score(self):
        """Test that function returns CalculatedSecurityScore object."""
        # Mock all scoring group functions
        mock_result = MagicMock()
        mock_result.score = 0.7
        mock_result.sub_scores = {"test": 0.7}

        with (
            patch(
                "app.domain.scoring.security_scorer.calculate_long_term_score",
                new_callable=AsyncMock,
                return_value=mock_result,
            ),
            patch(
                "app.domain.scoring.security_scorer.calculate_fundamentals_score",
                new_callable=AsyncMock,
                return_value=mock_result,
            ),
            patch(
                "app.domain.scoring.security_scorer.calculate_opportunity_score",
                new_callable=AsyncMock,
                return_value=mock_result,
            ),
            patch(
                "app.domain.scoring.security_scorer.calculate_dividends_score",
                new_callable=AsyncMock,
                return_value=mock_result,
            ),
            patch(
                "app.domain.scoring.security_scorer.calculate_short_term_score",
                new_callable=AsyncMock,
                return_value=mock_result,
            ),
            patch(
                "app.domain.scoring.security_scorer.calculate_technicals_score",
                new_callable=AsyncMock,
                return_value=mock_result,
            ),
            patch(
                "app.domain.scoring.security_scorer.calculate_opinion_score",
                new_callable=AsyncMock,
                return_value=mock_result,
            ),
        ):
            result = await calculate_security_score(
                symbol="AAPL.US",
                daily_prices=[{"close": 100.0} for _ in range(100)],
                monthly_prices=[{"avg_adj_close": 100.0} for _ in range(24)],
                fundamentals=MagicMock(),
            )

        assert isinstance(result, CalculatedSecurityScore)
        assert result.symbol == "AAPL.US"
        assert isinstance(result.calculated_at, datetime)

    @pytest.mark.asyncio
    async def test_uses_default_weights_when_none_provided(self):
        """Test that SCORE_WEIGHTS is used when weights parameter is None."""
        mock_result = MagicMock()
        mock_result.score = 0.7
        mock_result.sub_scores = {"test": 0.7}

        with (
            patch(
                "app.domain.scoring.security_scorer.calculate_long_term_score",
                new_callable=AsyncMock,
                return_value=mock_result,
            ),
            patch(
                "app.domain.scoring.security_scorer.calculate_fundamentals_score",
                new_callable=AsyncMock,
                return_value=mock_result,
            ),
            patch(
                "app.domain.scoring.security_scorer.calculate_opportunity_score",
                new_callable=AsyncMock,
                return_value=mock_result,
            ),
            patch(
                "app.domain.scoring.security_scorer.calculate_dividends_score",
                new_callable=AsyncMock,
                return_value=mock_result,
            ),
            patch(
                "app.domain.scoring.security_scorer.calculate_short_term_score",
                new_callable=AsyncMock,
                return_value=mock_result,
            ),
            patch(
                "app.domain.scoring.security_scorer.calculate_technicals_score",
                new_callable=AsyncMock,
                return_value=mock_result,
            ),
            patch(
                "app.domain.scoring.security_scorer.calculate_opinion_score",
                new_callable=AsyncMock,
                return_value=mock_result,
            ),
        ):
            result = await calculate_security_score(
                symbol="AAPL.US",
                daily_prices=[{"close": 100.0}] * 100,
                monthly_prices=[{"avg_adj_close": 100.0}] * 24,
                fundamentals=MagicMock(),
                weights=None,  # Explicitly pass None
            )

        # 7 groups score 0.7, diversification defaults to 0.5
        # Expected: 0.7*0.92 + 0.5*0.08 = 0.644 + 0.04 = 0.684
        assert result.total_score == pytest.approx(0.684, abs=0.001)

    @pytest.mark.asyncio
    async def test_accepts_custom_weights(self):
        """Test that custom weights can be provided."""
        mock_result = MagicMock()
        mock_result.score = 0.5
        mock_result.sub_scores = {"test": 0.5}

        custom_weights = {
            "long_term": 0.50,
            "fundamentals": 0.10,
            "opportunity": 0.10,
            "dividends": 0.10,
            "short_term": 0.05,
            "technicals": 0.05,
            "opinion": 0.05,
            "diversification": 0.05,
        }

        with (
            patch(
                "app.domain.scoring.security_scorer.calculate_long_term_score",
                new_callable=AsyncMock,
                return_value=mock_result,
            ),
            patch(
                "app.domain.scoring.security_scorer.calculate_fundamentals_score",
                new_callable=AsyncMock,
                return_value=mock_result,
            ),
            patch(
                "app.domain.scoring.security_scorer.calculate_opportunity_score",
                new_callable=AsyncMock,
                return_value=mock_result,
            ),
            patch(
                "app.domain.scoring.security_scorer.calculate_dividends_score",
                new_callable=AsyncMock,
                return_value=mock_result,
            ),
            patch(
                "app.domain.scoring.security_scorer.calculate_short_term_score",
                new_callable=AsyncMock,
                return_value=mock_result,
            ),
            patch(
                "app.domain.scoring.security_scorer.calculate_technicals_score",
                new_callable=AsyncMock,
                return_value=mock_result,
            ),
            patch(
                "app.domain.scoring.security_scorer.calculate_opinion_score",
                new_callable=AsyncMock,
                return_value=mock_result,
            ),
        ):
            result = await calculate_security_score(
                symbol="AAPL.US",
                daily_prices=[{"close": 100.0}] * 100,
                monthly_prices=[{"avg_adj_close": 100.0}] * 24,
                fundamentals=MagicMock(),
                weights=custom_weights,
            )

        # All groups score 0.5, so weighted total should be 0.5
        assert result.total_score == pytest.approx(0.5)

    @pytest.mark.asyncio
    async def test_normalizes_weights_to_sum_one(self):
        """Test that weights are normalized if they don't sum to 1.0."""
        mock_result = MagicMock()
        mock_result.score = 1.0
        mock_result.sub_scores = {"test": 1.0}

        # Weights sum to 2.0 instead of 1.0
        unnormalized_weights = {
            "long_term": 0.40,
            "fundamentals": 0.30,
            "opportunity": 0.30,
            "dividends": 0.24,
            "short_term": 0.20,
            "technicals": 0.20,
            "opinion": 0.20,
            "diversification": 0.16,
        }

        with (
            patch(
                "app.domain.scoring.security_scorer.calculate_long_term_score",
                new_callable=AsyncMock,
                return_value=mock_result,
            ),
            patch(
                "app.domain.scoring.security_scorer.calculate_fundamentals_score",
                new_callable=AsyncMock,
                return_value=mock_result,
            ),
            patch(
                "app.domain.scoring.security_scorer.calculate_opportunity_score",
                new_callable=AsyncMock,
                return_value=mock_result,
            ),
            patch(
                "app.domain.scoring.security_scorer.calculate_dividends_score",
                new_callable=AsyncMock,
                return_value=mock_result,
            ),
            patch(
                "app.domain.scoring.security_scorer.calculate_short_term_score",
                new_callable=AsyncMock,
                return_value=mock_result,
            ),
            patch(
                "app.domain.scoring.security_scorer.calculate_technicals_score",
                new_callable=AsyncMock,
                return_value=mock_result,
            ),
            patch(
                "app.domain.scoring.security_scorer.calculate_opinion_score",
                new_callable=AsyncMock,
                return_value=mock_result,
            ),
        ):
            result = await calculate_security_score(
                symbol="AAPL.US",
                daily_prices=[{"close": 100.0}] * 100,
                monthly_prices=[{"avg_adj_close": 100.0}] * 24,
                fundamentals=MagicMock(),
                weights=unnormalized_weights,
            )

        # 7 groups score 1.0, diversification defaults to 0.5
        # Weights are normalized: sum=2.0, so each weight is divided by 2
        # 7 groups * 0.5 (normalized) + diversification 0.5 * 0.08 (normalized) = closer to 0.96
        # Actually: diversification uses default 0.5, so: 1.0*0.92 + 0.5*0.08 = 0.92 + 0.04 = 0.96
        assert result.total_score == pytest.approx(0.96, abs=0.01)

    @pytest.mark.asyncio
    async def test_calculates_weighted_average_correctly(self):
        """Test that weighted average is calculated correctly."""

        # Create mock results with different scores
        def create_mock_result(score):
            mock = MagicMock()
            mock.score = score
            mock.sub_scores = {"test": score}
            return mock

        with (
            patch(
                "app.domain.scoring.security_scorer.calculate_long_term_score",
                new_callable=AsyncMock,
                return_value=create_mock_result(0.8),  # 20% weight
            ),
            patch(
                "app.domain.scoring.security_scorer.calculate_fundamentals_score",
                new_callable=AsyncMock,
                return_value=create_mock_result(0.7),  # 15% weight
            ),
            patch(
                "app.domain.scoring.security_scorer.calculate_opportunity_score",
                new_callable=AsyncMock,
                return_value=create_mock_result(0.6),  # 15% weight
            ),
            patch(
                "app.domain.scoring.security_scorer.calculate_dividends_score",
                new_callable=AsyncMock,
                return_value=create_mock_result(0.5),  # 12% weight
            ),
            patch(
                "app.domain.scoring.security_scorer.calculate_short_term_score",
                new_callable=AsyncMock,
                return_value=create_mock_result(0.9),  # 10% weight
            ),
            patch(
                "app.domain.scoring.security_scorer.calculate_technicals_score",
                new_callable=AsyncMock,
                return_value=create_mock_result(0.4),  # 10% weight
            ),
            patch(
                "app.domain.scoring.security_scorer.calculate_opinion_score",
                new_callable=AsyncMock,
                return_value=create_mock_result(0.3),  # 10% weight
            ),
        ):
            result = await calculate_security_score(
                symbol="AAPL.US",
                daily_prices=[{"close": 100.0}] * 100,
                monthly_prices=[{"avg_adj_close": 100.0}] * 24,
                fundamentals=MagicMock(),
                country="United States",
                portfolio_context=PortfolioContext(
                    country_weights={},
                    industry_weights={},
                    positions={},
                    total_value=10000,
                ),
            )

        # Expected: 0.8*0.20 + 0.7*0.15 + 0.6*0.15 + 0.5*0.12 + 0.9*0.10 + 0.4*0.10 + 0.3*0.10 + 0.5*0.08
        # = 0.16 + 0.105 + 0.09 + 0.06 + 0.09 + 0.04 + 0.03 + 0.04 = 0.615
        expected = (
            0.8 * 0.20
            + 0.7 * 0.15
            + 0.6 * 0.15
            + 0.5 * 0.12
            + 0.9 * 0.10
            + 0.4 * 0.10
            + 0.3 * 0.10
            + 0.5 * 0.08
        )
        assert result.total_score == pytest.approx(expected, abs=0.001)

    @pytest.mark.asyncio
    async def test_includes_group_scores(self):
        """Test that individual group scores are included."""
        mock_result = MagicMock()
        mock_result.score = 0.7
        mock_result.sub_scores = {"test": 0.7}

        with (
            patch(
                "app.domain.scoring.security_scorer.calculate_long_term_score",
                new_callable=AsyncMock,
                return_value=mock_result,
            ),
            patch(
                "app.domain.scoring.security_scorer.calculate_fundamentals_score",
                new_callable=AsyncMock,
                return_value=mock_result,
            ),
            patch(
                "app.domain.scoring.security_scorer.calculate_opportunity_score",
                new_callable=AsyncMock,
                return_value=mock_result,
            ),
            patch(
                "app.domain.scoring.security_scorer.calculate_dividends_score",
                new_callable=AsyncMock,
                return_value=mock_result,
            ),
            patch(
                "app.domain.scoring.security_scorer.calculate_short_term_score",
                new_callable=AsyncMock,
                return_value=mock_result,
            ),
            patch(
                "app.domain.scoring.security_scorer.calculate_technicals_score",
                new_callable=AsyncMock,
                return_value=mock_result,
            ),
            patch(
                "app.domain.scoring.security_scorer.calculate_opinion_score",
                new_callable=AsyncMock,
                return_value=mock_result,
            ),
        ):
            result = await calculate_security_score(
                symbol="AAPL.US",
                daily_prices=[{"close": 100.0}] * 100,
                monthly_prices=[{"avg_adj_close": 100.0}] * 24,
                fundamentals=MagicMock(),
            )

        assert result.group_scores is not None
        assert "long_term" in result.group_scores
        assert "fundamentals" in result.group_scores
        assert "opportunity" in result.group_scores
        assert "dividends" in result.group_scores
        assert "short_term" in result.group_scores
        assert "technicals" in result.group_scores
        assert "opinion" in result.group_scores
        assert "diversification" in result.group_scores

    @pytest.mark.asyncio
    async def test_includes_sub_scores(self):
        """Test that sub-scores for each group are included."""
        mock_result = MagicMock()
        mock_result.score = 0.7
        mock_result.sub_scores = {"component1": 0.6, "component2": 0.8}

        with (
            patch(
                "app.domain.scoring.security_scorer.calculate_long_term_score",
                new_callable=AsyncMock,
                return_value=mock_result,
            ),
            patch(
                "app.domain.scoring.security_scorer.calculate_fundamentals_score",
                new_callable=AsyncMock,
                return_value=mock_result,
            ),
            patch(
                "app.domain.scoring.security_scorer.calculate_opportunity_score",
                new_callable=AsyncMock,
                return_value=mock_result,
            ),
            patch(
                "app.domain.scoring.security_scorer.calculate_dividends_score",
                new_callable=AsyncMock,
                return_value=mock_result,
            ),
            patch(
                "app.domain.scoring.security_scorer.calculate_short_term_score",
                new_callable=AsyncMock,
                return_value=mock_result,
            ),
            patch(
                "app.domain.scoring.security_scorer.calculate_technicals_score",
                new_callable=AsyncMock,
                return_value=mock_result,
            ),
            patch(
                "app.domain.scoring.security_scorer.calculate_opinion_score",
                new_callable=AsyncMock,
                return_value=mock_result,
            ),
        ):
            result = await calculate_security_score(
                symbol="AAPL.US",
                daily_prices=[{"close": 100.0}] * 100,
                monthly_prices=[{"avg_adj_close": 100.0}] * 24,
                fundamentals=MagicMock(),
            )

        assert result.sub_scores is not None
        assert "long_term" in result.sub_scores
        assert "component1" in result.sub_scores["long_term"]
        assert "component2" in result.sub_scores["long_term"]

    @pytest.mark.asyncio
    async def test_calculates_volatility_with_sufficient_data(self):
        """Test that volatility is calculated when enough daily prices exist."""
        mock_result = MagicMock()
        mock_result.score = 0.7
        mock_result.sub_scores = {"test": 0.7}

        # Create prices with known volatility pattern
        prices = [{"close": 100.0 + i * 0.5} for i in range(60)]

        with (
            patch(
                "app.domain.scoring.security_scorer.calculate_long_term_score",
                new_callable=AsyncMock,
                return_value=mock_result,
            ),
            patch(
                "app.domain.scoring.security_scorer.calculate_fundamentals_score",
                new_callable=AsyncMock,
                return_value=mock_result,
            ),
            patch(
                "app.domain.scoring.security_scorer.calculate_opportunity_score",
                new_callable=AsyncMock,
                return_value=mock_result,
            ),
            patch(
                "app.domain.scoring.security_scorer.calculate_dividends_score",
                new_callable=AsyncMock,
                return_value=mock_result,
            ),
            patch(
                "app.domain.scoring.security_scorer.calculate_short_term_score",
                new_callable=AsyncMock,
                return_value=mock_result,
            ),
            patch(
                "app.domain.scoring.security_scorer.calculate_technicals_score",
                new_callable=AsyncMock,
                return_value=mock_result,
            ),
            patch(
                "app.domain.scoring.security_scorer.calculate_opinion_score",
                new_callable=AsyncMock,
                return_value=mock_result,
            ),
        ):
            result = await calculate_security_score(
                symbol="AAPL.US",
                daily_prices=prices,
                monthly_prices=[{"avg_adj_close": 100.0}] * 24,
                fundamentals=MagicMock(),
            )

        assert result.volatility is not None
        assert result.volatility > 0

    @pytest.mark.asyncio
    async def test_volatility_none_with_insufficient_data(self):
        """Test that volatility is None when insufficient daily prices."""
        mock_result = MagicMock()
        mock_result.score = 0.7
        mock_result.sub_scores = {"test": 0.7}

        # Only 20 days of data (need at least 30)
        prices = [{"close": 100.0}] * 20

        with (
            patch(
                "app.domain.scoring.security_scorer.calculate_long_term_score",
                new_callable=AsyncMock,
                return_value=mock_result,
            ),
            patch(
                "app.domain.scoring.security_scorer.calculate_fundamentals_score",
                new_callable=AsyncMock,
                return_value=mock_result,
            ),
            patch(
                "app.domain.scoring.security_scorer.calculate_opportunity_score",
                new_callable=AsyncMock,
                return_value=mock_result,
            ),
            patch(
                "app.domain.scoring.security_scorer.calculate_dividends_score",
                new_callable=AsyncMock,
                return_value=mock_result,
            ),
            patch(
                "app.domain.scoring.security_scorer.calculate_short_term_score",
                new_callable=AsyncMock,
                return_value=mock_result,
            ),
            patch(
                "app.domain.scoring.security_scorer.calculate_technicals_score",
                new_callable=AsyncMock,
                return_value=mock_result,
            ),
            patch(
                "app.domain.scoring.security_scorer.calculate_opinion_score",
                new_callable=AsyncMock,
                return_value=mock_result,
            ),
        ):
            result = await calculate_security_score(
                symbol="AAPL.US",
                daily_prices=prices,
                monthly_prices=[{"avg_adj_close": 100.0}] * 24,
                fundamentals=MagicMock(),
            )

        assert result.volatility is None

    @pytest.mark.asyncio
    async def test_passes_parameters_to_long_term_score(self):
        """Test that parameters are passed correctly to long-term scorer."""
        mock_long_term = AsyncMock()
        mock_long_term.return_value = MagicMock(score=0.7, sub_scores={})

        mock_result = MagicMock()
        mock_result.score = 0.7
        mock_result.sub_scores = {"test": 0.7}

        with (
            patch(
                "app.domain.scoring.security_scorer.calculate_long_term_score",
                mock_long_term,
            ),
            patch(
                "app.domain.scoring.security_scorer.calculate_fundamentals_score",
                new_callable=AsyncMock,
                return_value=mock_result,
            ),
            patch(
                "app.domain.scoring.security_scorer.calculate_opportunity_score",
                new_callable=AsyncMock,
                return_value=mock_result,
            ),
            patch(
                "app.domain.scoring.security_scorer.calculate_dividends_score",
                new_callable=AsyncMock,
                return_value=mock_result,
            ),
            patch(
                "app.domain.scoring.security_scorer.calculate_short_term_score",
                new_callable=AsyncMock,
                return_value=mock_result,
            ),
            patch(
                "app.domain.scoring.security_scorer.calculate_technicals_score",
                new_callable=AsyncMock,
                return_value=mock_result,
            ),
            patch(
                "app.domain.scoring.security_scorer.calculate_opinion_score",
                new_callable=AsyncMock,
                return_value=mock_result,
            ),
        ):
            await calculate_security_score(
                symbol="AAPL.US",
                daily_prices=[{"close": 100.0}] * 100,
                monthly_prices=[{"avg_adj_close": 100.0}] * 24,
                fundamentals=MagicMock(),
                sortino_ratio=2.5,
                target_annual_return=0.15,
            )

        mock_long_term.assert_called_once()
        call_kwargs = mock_long_term.call_args[1]
        assert call_kwargs["symbol"] == "AAPL.US"
        assert call_kwargs["sortino_ratio"] == 2.5
        assert call_kwargs["target_annual_return"] == 0.15

    @pytest.mark.asyncio
    async def test_passes_parameters_to_short_term_score(self):
        """Test that pyfolio_drawdown is passed to short-term scorer."""
        mock_short_term = AsyncMock()
        mock_short_term.return_value = MagicMock(score=0.7, sub_scores={})

        mock_result = MagicMock()
        mock_result.score = 0.7
        mock_result.sub_scores = {"test": 0.7}

        with (
            patch(
                "app.domain.scoring.security_scorer.calculate_long_term_score",
                new_callable=AsyncMock,
                return_value=mock_result,
            ),
            patch(
                "app.domain.scoring.security_scorer.calculate_fundamentals_score",
                new_callable=AsyncMock,
                return_value=mock_result,
            ),
            patch(
                "app.domain.scoring.security_scorer.calculate_opportunity_score",
                new_callable=AsyncMock,
                return_value=mock_result,
            ),
            patch(
                "app.domain.scoring.security_scorer.calculate_dividends_score",
                new_callable=AsyncMock,
                return_value=mock_result,
            ),
            patch(
                "app.domain.scoring.security_scorer.calculate_short_term_score",
                mock_short_term,
            ),
            patch(
                "app.domain.scoring.security_scorer.calculate_technicals_score",
                new_callable=AsyncMock,
                return_value=mock_result,
            ),
            patch(
                "app.domain.scoring.security_scorer.calculate_opinion_score",
                new_callable=AsyncMock,
                return_value=mock_result,
            ),
        ):
            await calculate_security_score(
                symbol="AAPL.US",
                daily_prices=[{"close": 100.0}] * 100,
                monthly_prices=[{"avg_adj_close": 100.0}] * 24,
                fundamentals=MagicMock(),
                pyfolio_drawdown=-0.15,
            )

        mock_short_term.assert_called_once()
        call_kwargs = mock_short_term.call_args[1]
        assert call_kwargs["pyfolio_drawdown"] == -0.15

    @pytest.mark.asyncio
    async def test_passes_parameters_to_opportunity_score(self):
        """Test that market_avg_pe is passed to opportunity scorer."""
        mock_opportunity = AsyncMock()
        mock_opportunity.return_value = MagicMock(score=0.7, sub_scores={})

        mock_result = MagicMock()
        mock_result.score = 0.7
        mock_result.sub_scores = {"test": 0.7}

        with (
            patch(
                "app.domain.scoring.security_scorer.calculate_long_term_score",
                new_callable=AsyncMock,
                return_value=mock_result,
            ),
            patch(
                "app.domain.scoring.security_scorer.calculate_fundamentals_score",
                new_callable=AsyncMock,
                return_value=mock_result,
            ),
            patch(
                "app.domain.scoring.security_scorer.calculate_opportunity_score",
                mock_opportunity,
            ),
            patch(
                "app.domain.scoring.security_scorer.calculate_dividends_score",
                new_callable=AsyncMock,
                return_value=mock_result,
            ),
            patch(
                "app.domain.scoring.security_scorer.calculate_short_term_score",
                new_callable=AsyncMock,
                return_value=mock_result,
            ),
            patch(
                "app.domain.scoring.security_scorer.calculate_technicals_score",
                new_callable=AsyncMock,
                return_value=mock_result,
            ),
            patch(
                "app.domain.scoring.security_scorer.calculate_opinion_score",
                new_callable=AsyncMock,
                return_value=mock_result,
            ),
        ):
            await calculate_security_score(
                symbol="AAPL.US",
                daily_prices=[{"close": 100.0}] * 100,
                monthly_prices=[{"avg_adj_close": 100.0}] * 24,
                fundamentals=MagicMock(),
                market_avg_pe=22.5,
            )

        mock_opportunity.assert_called_once()
        call_kwargs = mock_opportunity.call_args[1]
        assert call_kwargs["market_avg_pe"] == 22.5

    @pytest.mark.asyncio
    async def test_passes_yahoo_symbol_to_opinion_score(self):
        """Test that yahoo_symbol is passed to opinion scorer."""
        mock_opinion = AsyncMock()
        mock_opinion.return_value = MagicMock(score=0.7, sub_scores={})

        mock_result = MagicMock()
        mock_result.score = 0.7
        mock_result.sub_scores = {"test": 0.7}

        with (
            patch(
                "app.domain.scoring.security_scorer.calculate_long_term_score",
                new_callable=AsyncMock,
                return_value=mock_result,
            ),
            patch(
                "app.domain.scoring.security_scorer.calculate_fundamentals_score",
                new_callable=AsyncMock,
                return_value=mock_result,
            ),
            patch(
                "app.domain.scoring.security_scorer.calculate_opportunity_score",
                new_callable=AsyncMock,
                return_value=mock_result,
            ),
            patch(
                "app.domain.scoring.security_scorer.calculate_dividends_score",
                new_callable=AsyncMock,
                return_value=mock_result,
            ),
            patch(
                "app.domain.scoring.security_scorer.calculate_short_term_score",
                new_callable=AsyncMock,
                return_value=mock_result,
            ),
            patch(
                "app.domain.scoring.security_scorer.calculate_technicals_score",
                new_callable=AsyncMock,
                return_value=mock_result,
            ),
            patch(
                "app.domain.scoring.security_scorer.calculate_opinion_score",
                mock_opinion,
            ),
        ):
            await calculate_security_score(
                symbol="AAPL.US",
                daily_prices=[{"close": 100.0}] * 100,
                monthly_prices=[{"avg_adj_close": 100.0}] * 24,
                fundamentals=MagicMock(),
                yahoo_symbol="AAPL",
            )

        mock_opinion.assert_called_once()
        call_kwargs = mock_opinion.call_args[1]
        assert call_kwargs["yahoo_symbol"] == "AAPL"

    @pytest.mark.asyncio
    async def test_diversification_score_with_portfolio_context(self):
        """Test that diversification is calculated with portfolio context."""
        mock_result = MagicMock()
        mock_result.score = 0.7
        mock_result.sub_scores = {"test": 0.7}

        mock_diversification = MagicMock()
        mock_diversification.score = 0.85
        mock_diversification.sub_scores = {
            "country": 0.8,
            "industry": 0.9,
            "averaging": 0.85,
        }

        portfolio_context = PortfolioContext(
            country_weights={"US": 0.5},
            industry_weights={"Consumer Electronics": -0.3},
            positions={"MSFT.US": 5000},
            total_value=10000,
        )

        with (
            patch(
                "app.domain.scoring.security_scorer.calculate_long_term_score",
                new_callable=AsyncMock,
                return_value=mock_result,
            ),
            patch(
                "app.domain.scoring.security_scorer.calculate_fundamentals_score",
                new_callable=AsyncMock,
                return_value=mock_result,
            ),
            patch(
                "app.domain.scoring.security_scorer.calculate_opportunity_score",
                new_callable=AsyncMock,
                return_value=mock_result,
            ),
            patch(
                "app.domain.scoring.security_scorer.calculate_dividends_score",
                new_callable=AsyncMock,
                return_value=mock_result,
            ),
            patch(
                "app.domain.scoring.security_scorer.calculate_short_term_score",
                new_callable=AsyncMock,
                return_value=mock_result,
            ),
            patch(
                "app.domain.scoring.security_scorer.calculate_technicals_score",
                new_callable=AsyncMock,
                return_value=mock_result,
            ),
            patch(
                "app.domain.scoring.security_scorer.calculate_opinion_score",
                new_callable=AsyncMock,
                return_value=mock_result,
            ),
            patch(
                "app.domain.scoring.security_scorer.calculate_diversification_score",
                return_value=mock_diversification,
            ) as mock_div,
        ):
            result = await calculate_security_score(
                symbol="AAPL.US",
                daily_prices=[{"close": 100.0}] * 100,
                monthly_prices=[{"avg_adj_close": 100.0}] * 24,
                fundamentals=MagicMock(),
                country="United States",
                industry="Consumer Electronics",
                portfolio_context=portfolio_context,
            )

        # Verify diversification score was called
        mock_div.assert_called_once()
        call_kwargs = mock_div.call_args[1]
        assert call_kwargs["symbol"] == "AAPL.US"
        assert call_kwargs["country"] == "United States"
        assert call_kwargs["industry"] == "Consumer Electronics"
        assert call_kwargs["portfolio_context"] == portfolio_context

        # Verify diversification score is in result
        assert result.group_scores["diversification"] == 0.85

    @pytest.mark.asyncio
    async def test_diversification_default_without_portfolio_context(self):
        """Test that diversification defaults to 0.5 without portfolio context."""
        mock_result = MagicMock()
        mock_result.score = 0.7
        mock_result.sub_scores = {"test": 0.7}

        with (
            patch(
                "app.domain.scoring.security_scorer.calculate_long_term_score",
                new_callable=AsyncMock,
                return_value=mock_result,
            ),
            patch(
                "app.domain.scoring.security_scorer.calculate_fundamentals_score",
                new_callable=AsyncMock,
                return_value=mock_result,
            ),
            patch(
                "app.domain.scoring.security_scorer.calculate_opportunity_score",
                new_callable=AsyncMock,
                return_value=mock_result,
            ),
            patch(
                "app.domain.scoring.security_scorer.calculate_dividends_score",
                new_callable=AsyncMock,
                return_value=mock_result,
            ),
            patch(
                "app.domain.scoring.security_scorer.calculate_short_term_score",
                new_callable=AsyncMock,
                return_value=mock_result,
            ),
            patch(
                "app.domain.scoring.security_scorer.calculate_technicals_score",
                new_callable=AsyncMock,
                return_value=mock_result,
            ),
            patch(
                "app.domain.scoring.security_scorer.calculate_opinion_score",
                new_callable=AsyncMock,
                return_value=mock_result,
            ),
        ):
            result = await calculate_security_score(
                symbol="AAPL.US",
                daily_prices=[{"close": 100.0}] * 100,
                monthly_prices=[{"avg_adj_close": 100.0}] * 24,
                fundamentals=MagicMock(),
                # No portfolio_context provided
            )

        # Diversification should default to 0.5
        assert result.group_scores["diversification"] == 0.5
        assert result.sub_scores["diversification"]["country"] == 0.5
        assert result.sub_scores["diversification"]["industry"] == 0.5
        assert result.sub_scores["diversification"]["averaging"] == 0.5

    @pytest.mark.asyncio
    async def test_diversification_default_without_geography(self):
        """Test that diversification defaults to 0.5 without geography."""
        mock_result = MagicMock()
        mock_result.score = 0.7
        mock_result.sub_scores = {"test": 0.7}

        portfolio_context = PortfolioContext(
            country_weights={},
            industry_weights={},
            positions={},
            total_value=10000,
        )

        with (
            patch(
                "app.domain.scoring.security_scorer.calculate_long_term_score",
                new_callable=AsyncMock,
                return_value=mock_result,
            ),
            patch(
                "app.domain.scoring.security_scorer.calculate_fundamentals_score",
                new_callable=AsyncMock,
                return_value=mock_result,
            ),
            patch(
                "app.domain.scoring.security_scorer.calculate_opportunity_score",
                new_callable=AsyncMock,
                return_value=mock_result,
            ),
            patch(
                "app.domain.scoring.security_scorer.calculate_dividends_score",
                new_callable=AsyncMock,
                return_value=mock_result,
            ),
            patch(
                "app.domain.scoring.security_scorer.calculate_short_term_score",
                new_callable=AsyncMock,
                return_value=mock_result,
            ),
            patch(
                "app.domain.scoring.security_scorer.calculate_technicals_score",
                new_callable=AsyncMock,
                return_value=mock_result,
            ),
            patch(
                "app.domain.scoring.security_scorer.calculate_opinion_score",
                new_callable=AsyncMock,
                return_value=mock_result,
            ),
        ):
            result = await calculate_security_score(
                symbol="AAPL.US",
                daily_prices=[{"close": 100.0}] * 100,
                monthly_prices=[{"avg_adj_close": 100.0}] * 24,
                fundamentals=MagicMock(),
                portfolio_context=portfolio_context,
                # No country provided
            )

        # Diversification should default to 0.5
        assert result.group_scores["diversification"] == 0.5

    @pytest.mark.asyncio
    async def test_rounds_total_score_to_three_decimals(self):
        """Test that total score is rounded to 3 decimal places."""
        mock_result = MagicMock()
        mock_result.score = 0.777777
        mock_result.sub_scores = {"test": 0.777777}

        with (
            patch(
                "app.domain.scoring.security_scorer.calculate_long_term_score",
                new_callable=AsyncMock,
                return_value=mock_result,
            ),
            patch(
                "app.domain.scoring.security_scorer.calculate_fundamentals_score",
                new_callable=AsyncMock,
                return_value=mock_result,
            ),
            patch(
                "app.domain.scoring.security_scorer.calculate_opportunity_score",
                new_callable=AsyncMock,
                return_value=mock_result,
            ),
            patch(
                "app.domain.scoring.security_scorer.calculate_dividends_score",
                new_callable=AsyncMock,
                return_value=mock_result,
            ),
            patch(
                "app.domain.scoring.security_scorer.calculate_short_term_score",
                new_callable=AsyncMock,
                return_value=mock_result,
            ),
            patch(
                "app.domain.scoring.security_scorer.calculate_technicals_score",
                new_callable=AsyncMock,
                return_value=mock_result,
            ),
            patch(
                "app.domain.scoring.security_scorer.calculate_opinion_score",
                new_callable=AsyncMock,
                return_value=mock_result,
            ),
        ):
            result = await calculate_security_score(
                symbol="AAPL.US",
                daily_prices=[{"close": 100.0}] * 100,
                monthly_prices=[{"avg_adj_close": 100.0}] * 24,
                fundamentals=MagicMock(),
            )

        # Should be rounded to 3 decimals
        # 7 groups at 0.777777, diversification at 0.5
        # Expected: 0.777777*0.92 + 0.5*0.08 = 0.715555 + 0.04 = 0.755555 -> 0.756
        assert result.total_score == 0.756

    @pytest.mark.asyncio
    async def test_rounds_volatility_to_four_decimals(self):
        """Test that volatility is rounded to 4 decimal places."""
        mock_result = MagicMock()
        mock_result.score = 0.7
        mock_result.sub_scores = {"test": 0.7}

        # Create prices with some variance
        prices = [{"close": 100.0 + i % 5} for i in range(60)]

        with (
            patch(
                "app.domain.scoring.security_scorer.calculate_long_term_score",
                new_callable=AsyncMock,
                return_value=mock_result,
            ),
            patch(
                "app.domain.scoring.security_scorer.calculate_fundamentals_score",
                new_callable=AsyncMock,
                return_value=mock_result,
            ),
            patch(
                "app.domain.scoring.security_scorer.calculate_opportunity_score",
                new_callable=AsyncMock,
                return_value=mock_result,
            ),
            patch(
                "app.domain.scoring.security_scorer.calculate_dividends_score",
                new_callable=AsyncMock,
                return_value=mock_result,
            ),
            patch(
                "app.domain.scoring.security_scorer.calculate_short_term_score",
                new_callable=AsyncMock,
                return_value=mock_result,
            ),
            patch(
                "app.domain.scoring.security_scorer.calculate_technicals_score",
                new_callable=AsyncMock,
                return_value=mock_result,
            ),
            patch(
                "app.domain.scoring.security_scorer.calculate_opinion_score",
                new_callable=AsyncMock,
                return_value=mock_result,
            ),
        ):
            result = await calculate_security_score(
                symbol="AAPL.US",
                daily_prices=prices,
                monthly_prices=[{"avg_adj_close": 100.0}] * 24,
                fundamentals=MagicMock(),
            )

        # Volatility should be a 4-decimal float
        assert result.volatility is not None
        # Check that it has at most 4 decimal places
        volatility_str = f"{result.volatility:.10f}"
        decimal_part = volatility_str.split(".")[1]
        non_zero_decimals = len(decimal_part.rstrip("0"))
        assert non_zero_decimals <= 4

    @pytest.mark.asyncio
    async def test_handles_zero_weight_sum(self):
        """Test handling when all weights sum to zero."""
        mock_result = MagicMock()
        mock_result.score = 0.7
        mock_result.sub_scores = {"test": 0.7}

        # All weights are zero
        zero_weights = {
            "long_term": 0.0,
            "fundamentals": 0.0,
            "opportunity": 0.0,
            "dividends": 0.0,
            "short_term": 0.0,
            "technicals": 0.0,
            "opinion": 0.0,
            "diversification": 0.0,
        }

        with (
            patch(
                "app.domain.scoring.security_scorer.calculate_long_term_score",
                new_callable=AsyncMock,
                return_value=mock_result,
            ),
            patch(
                "app.domain.scoring.security_scorer.calculate_fundamentals_score",
                new_callable=AsyncMock,
                return_value=mock_result,
            ),
            patch(
                "app.domain.scoring.security_scorer.calculate_opportunity_score",
                new_callable=AsyncMock,
                return_value=mock_result,
            ),
            patch(
                "app.domain.scoring.security_scorer.calculate_dividends_score",
                new_callable=AsyncMock,
                return_value=mock_result,
            ),
            patch(
                "app.domain.scoring.security_scorer.calculate_short_term_score",
                new_callable=AsyncMock,
                return_value=mock_result,
            ),
            patch(
                "app.domain.scoring.security_scorer.calculate_technicals_score",
                new_callable=AsyncMock,
                return_value=mock_result,
            ),
            patch(
                "app.domain.scoring.security_scorer.calculate_opinion_score",
                new_callable=AsyncMock,
                return_value=mock_result,
            ),
        ):
            result = await calculate_security_score(
                symbol="AAPL.US",
                daily_prices=[{"close": 100.0}] * 100,
                monthly_prices=[{"avg_adj_close": 100.0}] * 24,
                fundamentals=MagicMock(),
                weights=zero_weights,
            )

        # Should fall back to SCORE_WEIGHTS when weight_sum is 0
        # 7 groups score 0.7, diversification defaults to 0.5
        # Expected: 0.7*0.92 + 0.5*0.08 = 0.644 + 0.04 = 0.684
        assert result.total_score == pytest.approx(0.684, abs=0.001)


class TestCalculateStockScoreFromPrefetched:
    """Test calculate_security_score_from_prefetched function."""

    @pytest.mark.asyncio
    async def test_extracts_data_from_prefetched(self):
        """Test that data is correctly extracted from PrefetchedStockData."""
        prefetched = PrefetchedStockData(
            daily_prices=[{"close": 100.0}] * 100,
            monthly_prices=[{"avg_adj_close": 100.0}] * 24,
            fundamentals=MagicMock(),
        )

        mock_result = MagicMock()
        mock_result.score = 0.7
        mock_result.sub_scores = {"test": 0.7}

        with (
            patch(
                "app.domain.scoring.security_scorer.calculate_long_term_score",
                new_callable=AsyncMock,
                return_value=mock_result,
            ),
            patch(
                "app.domain.scoring.security_scorer.calculate_fundamentals_score",
                new_callable=AsyncMock,
                return_value=mock_result,
            ),
            patch(
                "app.domain.scoring.security_scorer.calculate_opportunity_score",
                new_callable=AsyncMock,
                return_value=mock_result,
            ),
            patch(
                "app.domain.scoring.security_scorer.calculate_dividends_score",
                new_callable=AsyncMock,
                return_value=mock_result,
            ),
            patch(
                "app.domain.scoring.security_scorer.calculate_short_term_score",
                new_callable=AsyncMock,
                return_value=mock_result,
            ),
            patch(
                "app.domain.scoring.security_scorer.calculate_technicals_score",
                new_callable=AsyncMock,
                return_value=mock_result,
            ),
            patch(
                "app.domain.scoring.security_scorer.calculate_opinion_score",
                new_callable=AsyncMock,
                return_value=mock_result,
            ),
        ):
            result = await calculate_security_score_from_prefetched(
                symbol="AAPL.US",
                prefetched=prefetched,
            )

        assert isinstance(result, CalculatedSecurityScore)
        assert result.symbol == "AAPL.US"

    @pytest.mark.asyncio
    async def test_passes_all_parameters_through(self):
        """Test that all parameters are passed through to calculate_security_score."""
        prefetched = PrefetchedStockData(
            daily_prices=[{"close": 100.0}] * 100,
            monthly_prices=[{"avg_adj_close": 100.0}] * 24,
            fundamentals=MagicMock(),
        )

        portfolio_context = PortfolioContext(
            country_weights={},
            industry_weights={},
            positions={},
            total_value=10000,
        )

        custom_weights = {
            "long_term": 0.30,
            "fundamentals": 0.20,
            "opportunity": 0.15,
            "dividends": 0.10,
            "short_term": 0.10,
            "technicals": 0.05,
            "opinion": 0.05,
            "diversification": 0.05,
        }

        mock_result = MagicMock()
        mock_result.score = 0.7
        mock_result.sub_scores = {"test": 0.7}

        with (
            patch(
                "app.domain.scoring.security_scorer.calculate_long_term_score",
                new_callable=AsyncMock,
                return_value=mock_result,
            ) as mock_long_term,
            patch(
                "app.domain.scoring.security_scorer.calculate_fundamentals_score",
                new_callable=AsyncMock,
                return_value=mock_result,
            ),
            patch(
                "app.domain.scoring.security_scorer.calculate_opportunity_score",
                new_callable=AsyncMock,
                return_value=mock_result,
            ) as mock_opportunity,
            patch(
                "app.domain.scoring.security_scorer.calculate_dividends_score",
                new_callable=AsyncMock,
                return_value=mock_result,
            ),
            patch(
                "app.domain.scoring.security_scorer.calculate_short_term_score",
                new_callable=AsyncMock,
                return_value=mock_result,
            ),
            patch(
                "app.domain.scoring.security_scorer.calculate_technicals_score",
                new_callable=AsyncMock,
                return_value=mock_result,
            ),
            patch(
                "app.domain.scoring.security_scorer.calculate_opinion_score",
                new_callable=AsyncMock,
                return_value=mock_result,
            ) as mock_opinion,
        ):
            await calculate_security_score_from_prefetched(
                symbol="AAPL.US",
                prefetched=prefetched,
                country="United States",
                industry="Consumer Electronics",
                portfolio_context=portfolio_context,
                yahoo_symbol="AAPL",
                target_annual_return=0.15,
                market_avg_pe=22.5,
                weights=custom_weights,
            )

        # Verify parameters were passed through
        assert mock_long_term.call_args[1]["target_annual_return"] == 0.15
        assert mock_opportunity.call_args[1]["market_avg_pe"] == 22.5
        assert mock_opinion.call_args[1]["yahoo_symbol"] == "AAPL"

    @pytest.mark.asyncio
    async def test_returns_same_result_as_direct_call(self):
        """Test that prefetched version returns same result as direct call."""
        daily_prices = [{"close": 100.0 + i * 0.1} for i in range(100)]
        monthly_prices = [{"avg_adj_close": 100.0 + i} for i in range(24)]
        fundamentals = MagicMock()

        prefetched = PrefetchedStockData(
            daily_prices=daily_prices,
            monthly_prices=monthly_prices,
            fundamentals=fundamentals,
        )

        mock_result = MagicMock()
        mock_result.score = 0.75
        mock_result.sub_scores = {"test": 0.75}

        with (
            patch(
                "app.domain.scoring.security_scorer.calculate_long_term_score",
                new_callable=AsyncMock,
                return_value=mock_result,
            ),
            patch(
                "app.domain.scoring.security_scorer.calculate_fundamentals_score",
                new_callable=AsyncMock,
                return_value=mock_result,
            ),
            patch(
                "app.domain.scoring.security_scorer.calculate_opportunity_score",
                new_callable=AsyncMock,
                return_value=mock_result,
            ),
            patch(
                "app.domain.scoring.security_scorer.calculate_dividends_score",
                new_callable=AsyncMock,
                return_value=mock_result,
            ),
            patch(
                "app.domain.scoring.security_scorer.calculate_short_term_score",
                new_callable=AsyncMock,
                return_value=mock_result,
            ),
            patch(
                "app.domain.scoring.security_scorer.calculate_technicals_score",
                new_callable=AsyncMock,
                return_value=mock_result,
            ),
            patch(
                "app.domain.scoring.security_scorer.calculate_opinion_score",
                new_callable=AsyncMock,
                return_value=mock_result,
            ),
        ):
            # Call both methods
            result_prefetched = await calculate_security_score_from_prefetched(
                symbol="AAPL.US",
                prefetched=prefetched,
            )

            result_direct = await calculate_security_score(
                symbol="AAPL.US",
                daily_prices=daily_prices,
                monthly_prices=monthly_prices,
                fundamentals=fundamentals,
            )

        # Results should be identical
        assert result_prefetched.total_score == result_direct.total_score
        assert result_prefetched.symbol == result_direct.symbol
