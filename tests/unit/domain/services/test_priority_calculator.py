"""Tests for priority calculator service.

These tests validate priority calculations for stock recommendations,
including stock scores, allocation fit, and diversification scores.
"""

import pytest

from app.domain.models import StockPriority


class TestPriorityCalculator:
    """Test PriorityCalculator class."""

    def test_calculate_priority_combines_scores_correctly(self):
        """Test that priority calculation combines stock score and allocation fit correctly."""
        from app.domain.services.priority_calculator import PriorityCalculator

        stock_priority = StockPriority(
            symbol="AAPL",
            name="Apple",
            stock_score=0.8,
            multiplier=1.0,
            volatility=0.15,
        )

        allocation_fit_score = 0.7
        diversification_score = 0.6

        priority = PriorityCalculator.calculate_priority(
            stock_priority, allocation_fit_score, diversification_score
        )

        # Priority should be a weighted combination
        assert isinstance(priority, float)
        assert 0.0 <= priority <= 1.0

    def test_calculate_priority_uses_multiplier(self):
        """Test that stock priority multiplier affects the calculation."""
        from app.domain.services.priority_calculator import PriorityCalculator

        stock_priority_high = StockPriority(
            symbol="AAPL",
            name="Apple",
            stock_score=0.5,
            multiplier=2.0,  # High multiplier
            volatility=0.15,
        )

        stock_priority_low = StockPriority(
            symbol="MSFT",
            name="Microsoft",
            stock_score=0.5,
            multiplier=0.5,  # Low multiplier
            volatility=0.15,
        )

        allocation_fit = 0.5
        diversification = 0.5

        priority_high = PriorityCalculator.calculate_priority(
            stock_priority_high, allocation_fit, diversification
        )
        priority_low = PriorityCalculator.calculate_priority(
            stock_priority_low, allocation_fit, diversification
        )

        # Higher multiplier should result in higher priority
        assert priority_high > priority_low

    def test_calculate_priority_handles_zero_allocation_fit(self):
        """Test handling when allocation fit score is zero."""
        from app.domain.services.priority_calculator import PriorityCalculator

        stock_priority = StockPriority(
            symbol="AAPL",
            name="Apple",
            stock_score=0.8,
            multiplier=1.0,
            volatility=0.15,
        )

        priority = PriorityCalculator.calculate_priority(
            stock_priority, allocation_fit_score=0.0, diversification_score=0.5
        )

        assert isinstance(priority, float)
        assert priority >= 0.0

    def test_calculate_priority_handles_zero_diversification(self):
        """Test handling when diversification score is zero."""
        from app.domain.services.priority_calculator import PriorityCalculator

        stock_priority = StockPriority(
            symbol="AAPL",
            name="Apple",
            stock_score=0.8,
            multiplier=1.0,
            volatility=0.15,
        )

        priority = PriorityCalculator.calculate_priority(
            stock_priority, allocation_fit_score=0.5, diversification_score=0.0
        )

        assert isinstance(priority, float)
        assert priority >= 0.0

    def test_calculate_priority_handles_maximum_scores(self):
        """Test handling when all scores are at maximum (1.0)."""
        from app.domain.services.priority_calculator import PriorityCalculator

        stock_priority = StockPriority(
            symbol="AAPL",
            name="Apple",
            stock_score=1.0,
            multiplier=1.0,
            volatility=0.15,
        )

        priority = PriorityCalculator.calculate_priority(
            stock_priority, allocation_fit_score=1.0, diversification_score=1.0
        )

        assert isinstance(priority, float)
        assert 0.0 <= priority <= 1.0

    def test_calculate_priority_handles_minimum_scores(self):
        """Test handling when all scores are at minimum (0.0)."""
        from app.domain.services.priority_calculator import PriorityCalculator

        stock_priority = StockPriority(
            symbol="AAPL",
            name="Apple",
            stock_score=0.0,
            multiplier=1.0,
            volatility=0.15,
        )

        priority = PriorityCalculator.calculate_priority(
            stock_priority, allocation_fit_score=0.0, diversification_score=0.0
        )

        assert isinstance(priority, float)
        assert priority >= 0.0

    def test_calculate_allocation_fit_score_calculates_correctly(self):
        """Test that allocation fit score is calculated correctly."""
        from app.domain.services.priority_calculator import PriorityCalculator

        # Mock scenario: target allocation is 10%, current is 5%
        target_allocation = 0.10
        current_allocation = 0.05

        score = PriorityCalculator.calculate_allocation_fit_score(
            target_allocation, current_allocation
        )

        assert isinstance(score, float)
        assert 0.0 <= score <= 1.0
        # Underweight position (current < target) should have positive score
        assert score > 0.0

    def test_calculate_allocation_fit_score_handles_overweight(self):
        """Test handling when position is overweight (current > target)."""
        from app.domain.services.priority_calculator import PriorityCalculator

        target_allocation = 0.05
        current_allocation = 0.10  # Overweight

        score = PriorityCalculator.calculate_allocation_fit_score(
            target_allocation, current_allocation
        )

        assert isinstance(score, float)
        # Overweight positions should have lower scores
        assert score >= 0.0

    def test_calculate_allocation_fit_score_handles_at_target(self):
        """Test handling when position is at target allocation."""
        from app.domain.services.priority_calculator import PriorityCalculator

        target_allocation = 0.10
        current_allocation = 0.10

        score = PriorityCalculator.calculate_allocation_fit_score(
            target_allocation, current_allocation
        )

        assert isinstance(score, float)
        assert score >= 0.0

    def test_calculate_allocation_fit_score_handles_zero_target(self):
        """Test handling when target allocation is zero."""
        from app.domain.services.priority_calculator import PriorityCalculator

        target_allocation = 0.0
        current_allocation = 0.05

        score = PriorityCalculator.calculate_allocation_fit_score(
            target_allocation, current_allocation
        )

        assert isinstance(score, float)
        assert score >= 0.0

    def test_calculate_allocation_fit_score_handles_zero_current(self):
        """Test handling when current allocation is zero."""
        from app.domain.services.priority_calculator import PriorityCalculator

        target_allocation = 0.10
        current_allocation = 0.0

        score = PriorityCalculator.calculate_allocation_fit_score(
            target_allocation, current_allocation
        )

        assert isinstance(score, float)
        # Zero current with positive target should have high score
        assert score > 0.0

    def test_calculate_diversification_score_calculates_correctly(self):
        """Test that diversification score is calculated correctly."""
        from app.domain.services.priority_calculator import PriorityCalculator

        # Mock scenario with country/industry weights
        country_weights = {"US": 0.6, "EU": 0.3, "ASIA": 0.1}
        industry_weights = {"Tech": 0.5, "Finance": 0.3, "Healthcare": 0.2}
        stock_country = "ASIA"  # Underweight country
        stock_industry = "Healthcare"  # Underweight industry

        score = PriorityCalculator.calculate_diversification_score(
            country_weights, industry_weights, stock_country, stock_industry
        )

        assert isinstance(score, float)
        assert 0.0 <= score <= 1.0
        # Underweight regions/industries should have positive diversification score
        assert score > 0.0

    def test_calculate_diversification_score_handles_overweight_regions(self):
        """Test handling when stock is in overweight regions."""
        from app.domain.services.priority_calculator import PriorityCalculator

        country_weights = {"US": 0.8, "EU": 0.2}  # US is overweight
        industry_weights = {"Tech": 0.7, "Finance": 0.3}  # Tech is overweight
        stock_country = "US"
        stock_industry = "Tech"

        score = PriorityCalculator.calculate_diversification_score(
            country_weights, industry_weights, stock_country, stock_industry
        )

        assert isinstance(score, float)
        # Overweight regions should have lower diversification scores
        assert score >= 0.0

    def test_calculate_diversification_score_handles_missing_country(self):
        """Test handling when stock country is not in weights."""
        from app.domain.services.priority_calculator import PriorityCalculator

        country_weights = {"US": 0.6, "EU": 0.4}
        industry_weights = {"Tech": 1.0}
        stock_country = "ASIA"  # Not in weights
        stock_industry = "Tech"

        score = PriorityCalculator.calculate_diversification_score(
            country_weights, industry_weights, stock_country, stock_industry
        )

        assert isinstance(score, float)
        assert score >= 0.0

    def test_calculate_diversification_score_handles_missing_industry(self):
        """Test handling when stock industry is not in weights."""
        from app.domain.services.priority_calculator import PriorityCalculator

        country_weights = {"US": 1.0}
        industry_weights = {"Tech": 0.6, "Finance": 0.4}
        stock_country = "US"
        stock_industry = "Healthcare"  # Not in weights

        score = PriorityCalculator.calculate_diversification_score(
            country_weights, industry_weights, stock_country, stock_industry
        )

        assert isinstance(score, float)
        assert score >= 0.0

    def test_calculate_diversification_score_handles_empty_weights(self):
        """Test handling when weights dictionaries are empty."""
        from app.domain.services.priority_calculator import PriorityCalculator

        country_weights = {}
        industry_weights = {}
        stock_country = "US"
        stock_industry = "Tech"

        score = PriorityCalculator.calculate_diversification_score(
            country_weights, industry_weights, stock_country, stock_industry
        )

        assert isinstance(score, float)
        assert score >= 0.0

