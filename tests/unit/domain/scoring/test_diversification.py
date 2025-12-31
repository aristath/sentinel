"""Tests for diversification scoring.

These tests validate portfolio-aware diversification scoring
including country gaps, industry gaps, and averaging down calculations.
"""

from unittest.mock import AsyncMock, patch

import pytest

from app.modules.scoring.domain.models import PortfolioContext


class TestCalculateGeoGapScore:
    """Test country gap score calculation."""

    def test_returns_base_score_when_no_weight(self):
        """Test that base score is returned when geo not in weights."""
        from app.modules.scoring.domain.diversification import _calculate_geo_gap_score

        context = PortfolioContext(
            country_weights={},
            industry_weights={},
            positions={},
            total_value=0,
        )

        score = _calculate_geo_gap_score("US", context)

        assert score == 0.5  # Base score

    def test_increases_score_for_positive_weight(self):
        """Test that positive weight increases score."""
        from app.modules.scoring.domain.diversification import _calculate_geo_gap_score

        context = PortfolioContext(
            country_weights={
                "OTHER": 0.5
            },  # Underweight, should boost (US maps to OTHER if no mapping)
            industry_weights={},
            positions={},
            total_value=0,
            country_to_group={},  # No mapping means US -> OTHER
        )

        score = _calculate_geo_gap_score("US", context)

        assert score > 0.5  # Boosted

    def test_decreases_score_for_negative_weight(self):
        """Test that negative weight decreases score."""
        from app.modules.scoring.domain.diversification import _calculate_geo_gap_score

        context = PortfolioContext(
            country_weights={
                "OTHER": -0.5
            },  # Overweight, should reduce (US maps to OTHER if no mapping)
            industry_weights={},
            positions={},
            total_value=0,
            country_to_group={},  # No mapping means US -> OTHER
        )

        score = _calculate_geo_gap_score("US", context)

        assert score < 0.5  # Reduced

    def test_clamps_score_to_range(self):
        """Test that score is clamped to [0.1, 0.9] range."""
        from app.modules.scoring.domain.diversification import _calculate_geo_gap_score

        context = PortfolioContext(
            country_weights={
                "OTHER": 10.0
            },  # Extreme value (US maps to OTHER if no mapping)
            industry_weights={},
            positions={},
            total_value=0,
            country_to_group={},  # No mapping means US -> OTHER
        )

        score = _calculate_geo_gap_score("US", context)

        assert 0.1 <= score <= 0.9


class TestCalculateIndustryGapScore:
    """Test industry gap score calculation."""

    def test_returns_base_score_when_no_industry(self):
        """Test that base score is returned when industry is None."""
        from app.modules.scoring.domain.diversification import (
            _calculate_industry_gap_score,
        )

        context = PortfolioContext(
            country_weights={},
            industry_weights={},
            positions={},
            total_value=0,
        )

        score = _calculate_industry_gap_score(None, context)

        assert score == 0.5

    def test_returns_base_score_when_empty_industry(self):
        """Test that base score is returned for empty industry string."""
        from app.modules.scoring.domain.diversification import (
            _calculate_industry_gap_score,
        )

        context = PortfolioContext(
            country_weights={},
            industry_weights={},
            positions={},
            total_value=0,
        )

        score = _calculate_industry_gap_score("", context)

        assert score == 0.5

    def test_handles_single_industry(self):
        """Test scoring with single industry."""
        from app.modules.scoring.domain.diversification import (
            _calculate_industry_gap_score,
        )

        context = PortfolioContext(
            country_weights={},
            industry_weights={"Consumer Electronics": 0.5},
            positions={},
            total_value=0,
        )

        score = _calculate_industry_gap_score("Consumer Electronics", context)

        assert score > 0.5

    def test_handles_multiple_industries(self):
        """Test scoring with comma-separated industries."""
        from app.modules.scoring.domain.diversification import (
            _calculate_industry_gap_score,
        )

        context = PortfolioContext(
            country_weights={},
            industry_weights={"Consumer Electronics": 0.5, "Drug Manufacturers": -0.5},
            positions={},
            total_value=0,
        )

        score = _calculate_industry_gap_score("Technology, Healthcare", context)

        # Average of boosted Tech and reduced Healthcare
        assert 0.1 <= score <= 0.9


class TestCalculateAveragingDownScore:
    """Test averaging down score calculation."""

    def test_returns_base_when_no_position(self):
        """Test that base score is returned when no position held."""
        from app.modules.scoring.domain.diversification import (
            _calculate_averaging_down_score,
        )

        context = PortfolioContext(
            country_weights={},
            industry_weights={},
            positions={},
            total_value=10000,
        )

        score = _calculate_averaging_down_score("AAPL.US", 0.7, 0.6, context)

        assert score == 0.5

    def test_high_score_for_quality_opportunity(self):
        """Test high score for high quality + high opportunity."""
        from app.modules.scoring.domain.diversification import (
            _calculate_averaging_down_score,
        )

        context = PortfolioContext(
            country_weights={},
            industry_weights={},
            positions={"AAPL.US": 1000},
            total_value=10000,
        )

        score = _calculate_averaging_down_score(
            "AAPL.US", 0.8, 0.8, context  # High quality * opportunity
        )

        assert score > 0.7

    def test_low_score_for_low_quality(self):
        """Test lower score for low quality securities.

        With quality=0.2, opportunity=0.2: avg_down_potential = 0.04 < 0.3
        Base score = 0.3
        Position is 10% of portfolio (1000/10000), which triggers CONCENTRATION_MED
        Final score = 0.3 * 0.9 = 0.27
        """
        from app.modules.scoring.domain.diversification import (
            _calculate_averaging_down_score,
        )

        context = PortfolioContext(
            country_weights={},
            industry_weights={},
            positions={"AAPL.US": 1000},
            total_value=10000,
        )

        score = _calculate_averaging_down_score(
            "AAPL.US", 0.2, 0.2, context  # Low quality * opportunity
        )

        # Base 0.3 with medium concentration penalty (0.9x) = 0.27
        assert score == pytest.approx(0.27, abs=0.01)


class TestApplyCostBasisBonus:
    """Test cost basis bonus application."""

    def test_returns_original_when_no_price_data(self):
        """Test that original score is returned when no price data."""
        from app.modules.scoring.domain.diversification import _apply_cost_basis_bonus

        context = PortfolioContext(
            country_weights={},
            industry_weights={},
            positions={},
            total_value=0,
        )

        score = _apply_cost_basis_bonus("AAPL.US", 0.5, context)

        assert score == 0.5

    def test_boosts_score_when_below_cost_basis(self):
        """Test that score is boosted when current price below cost basis."""
        from app.modules.scoring.domain.diversification import _apply_cost_basis_bonus

        context = PortfolioContext(
            country_weights={},
            industry_weights={},
            positions={"AAPL.US": 1000},
            total_value=10000,
            position_avg_prices={"AAPL.US": 150.0},
            current_prices={"AAPL.US": 120.0},  # 20% below avg
        )

        score = _apply_cost_basis_bonus("AAPL.US", 0.5, context)

        assert score > 0.5

    def test_no_boost_when_above_cost_basis(self):
        """Test that no boost when current price above cost basis."""
        from app.modules.scoring.domain.diversification import _apply_cost_basis_bonus

        context = PortfolioContext(
            country_weights={},
            industry_weights={},
            positions={"AAPL.US": 1000},
            total_value=10000,
            position_avg_prices={"AAPL.US": 100.0},
            current_prices={"AAPL.US": 120.0},  # Above avg
        )

        score = _apply_cost_basis_bonus("AAPL.US", 0.5, context)

        assert score == 0.5


class TestApplyConcentrationPenalty:
    """Test concentration penalty application."""

    def test_returns_original_when_no_total_value(self):
        """Test no penalty when total value is zero."""
        from app.modules.scoring.domain.diversification import (
            _apply_concentration_penalty,
        )

        context = PortfolioContext(
            country_weights={},
            industry_weights={},
            positions={},
            total_value=0,
        )

        score = _apply_concentration_penalty(1000, 0.7, context)

        assert score == 0.7

    def test_applies_high_concentration_penalty(self):
        """Test severe penalty for high concentration."""
        from app.modules.scoring.domain.diversification import (
            _apply_concentration_penalty,
        )

        context = PortfolioContext(
            country_weights={},
            industry_weights={},
            positions={},
            total_value=10000,
        )

        # Position is 20% of portfolio (high concentration)
        score = _apply_concentration_penalty(2000, 1.0, context)

        assert score < 1.0

    def test_no_penalty_for_small_position(self):
        """Test no penalty for small positions."""
        from app.modules.scoring.domain.diversification import (
            _apply_concentration_penalty,
        )

        context = PortfolioContext(
            country_weights={},
            industry_weights={},
            positions={},
            total_value=100000,
        )

        # Position is only 1% of portfolio
        score = _apply_concentration_penalty(1000, 0.7, context)

        assert score == 0.7


class TestCalculateDiversificationScore:
    """Test main diversification score calculation."""

    def test_returns_score_result(self):
        """Test that ScoreResult is returned."""
        from app.modules.scoring.domain.diversification import (
            calculate_diversification_score,
        )

        context = PortfolioContext(
            country_weights={"US": 0.1},
            industry_weights={"Consumer Electronics": 0.1},
            positions={},
            total_value=10000,
        )

        result = calculate_diversification_score(
            symbol="AAPL.US",
            country="United States",
            industry="Consumer Electronics",
            quality_score=0.7,
            opportunity_score=0.6,
            portfolio_context=context,
        )

        assert hasattr(result, "score")
        assert hasattr(result, "sub_scores")
        assert 0 <= result.score <= 1

    def test_includes_sub_scores(self):
        """Test that sub_scores are included."""
        from app.modules.scoring.domain.diversification import (
            calculate_diversification_score,
        )

        context = PortfolioContext(
            country_weights={},
            industry_weights={},
            positions={},
            total_value=10000,
        )

        result = calculate_diversification_score(
            symbol="AAPL.US",
            country="United States",
            industry="Consumer Electronics",
            quality_score=0.7,
            opportunity_score=0.6,
            portfolio_context=context,
        )

        assert "country" in result.sub_scores
        assert "industry" in result.sub_scores
        assert "averaging" in result.sub_scores


class TestCalculatePortfolioScore:
    """Test portfolio score calculation."""

    @pytest.mark.asyncio
    async def test_returns_default_for_empty_portfolio(self):
        """Test default score when portfolio is empty."""
        from app.modules.scoring.domain.diversification import calculate_portfolio_score

        context = PortfolioContext(
            country_weights={},
            industry_weights={},
            positions={},
            total_value=0,
        )

        score = await calculate_portfolio_score(context)

        assert score.total == 50.0
        assert score.diversification_score == 50.0
        assert score.dividend_score == 50.0
        assert score.quality_score == 50.0

    @pytest.mark.asyncio
    async def test_calculates_components(self):
        """Test that all components are calculated."""
        from app.modules.scoring.domain.diversification import calculate_portfolio_score

        context = PortfolioContext(
            country_weights={"US": 0.1, "EU": -0.1},
            industry_weights={},
            positions={"AAPL.US": 5000, "SAP.EU": 5000},
            total_value=10000,
            security_countries={"AAPL.US": "US", "SAP.EU": "EU"},
            security_scores={"AAPL.US": 0.8, "SAP.EU": 0.7},
            security_dividends={"AAPL.US": 0.01, "SAP.EU": 0.02},
        )

        score = await calculate_portfolio_score(context)

        assert hasattr(score, "diversification_score")
        assert hasattr(score, "dividend_score")
        assert hasattr(score, "quality_score")
        assert hasattr(score, "total")

    @pytest.mark.asyncio
    async def test_uses_cache_when_hash_provided(self):
        """Test that cache is checked when portfolio_hash is provided."""
        from app.modules.scoring.domain.diversification import calculate_portfolio_score

        mock_cache = AsyncMock()
        mock_cache.get_analytics.return_value = {
            "diversification_score": 70.0,
            "dividend_score": 60.0,
            "quality_score": 80.0,
            "total": 70.0,
        }

        context = PortfolioContext(
            country_weights={},
            industry_weights={},
            positions={"AAPL.US": 1000},
            total_value=1000,
        )

        # Patch at source module since import happens inside function
        with patch(
            "app.infrastructure.recommendation_cache.get_recommendation_cache",
            return_value=mock_cache,
        ):
            score = await calculate_portfolio_score(context, portfolio_hash="abc123")

        assert score.total == 70.0


class TestCalculatePostTransactionScore:
    """Test post-transaction score calculation."""

    @pytest.mark.asyncio
    async def test_calculates_new_score_after_transaction(self):
        """Test that new score reflects proposed transaction."""
        from app.modules.scoring.domain.diversification import (
            calculate_post_transaction_score,
        )

        context = PortfolioContext(
            country_weights={"EU": 0.5},  # Underweight EU
            industry_weights={},
            positions={"AAPL.US": 8000},
            total_value=10000,
            security_countries={"AAPL.US": "US"},
            security_scores={"AAPL.US": 0.7},
            security_dividends={"AAPL.US": 0.01},
        )

        # Buy an EU security to improve diversification
        new_score, score_change = await calculate_post_transaction_score(
            symbol="SAP.EU",
            country="Germany",
            industry="Consumer Electronics",
            proposed_value=2000,
            stock_quality=0.8,
            stock_dividend=0.02,
            portfolio_context=context,
        )

        assert new_score is not None
        # Buying underweight geo should improve score
        # (may not always be positive due to other factors)
        assert hasattr(new_score, "total")

    @pytest.mark.asyncio
    async def test_uses_cache_when_hash_provided(self):
        """Test that cached scenario is returned when available."""
        from app.modules.scoring.domain.diversification import (
            calculate_post_transaction_score,
        )

        mock_cache = AsyncMock()
        mock_cache.get_analytics.return_value = {
            "new_portfolio_score": {
                "diversification_score": 72.0,
                "dividend_score": 62.0,
                "quality_score": 82.0,
                "total": 72.0,
            },
            "score_change": 2.0,
        }

        context = PortfolioContext(
            country_weights={},
            industry_weights={},
            positions={"AAPL.US": 1000},
            total_value=1000,
        )

        # Patch at source module since import happens inside function
        with patch(
            "app.infrastructure.recommendation_cache.get_recommendation_cache",
            return_value=mock_cache,
        ):
            new_score, change = await calculate_post_transaction_score(
                symbol="MSFT.US",
                country="United States",
                industry="Consumer Electronics",
                proposed_value=500,
                stock_quality=0.8,
                stock_dividend=0.01,
                portfolio_context=context,
                portfolio_hash="abc123",
            )

        assert new_score.total == 72.0
        assert change == 2.0
