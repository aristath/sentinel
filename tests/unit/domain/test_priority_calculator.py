"""Unit tests for priority calculator.

Note: The priority calculator has been simplified for long-term value investing.
The scoring system (scorer.py) now handles Quality, Opportunity, Analyst, and
Allocation Fit scores. The priority calculator just applies the manual multiplier.
"""

import pytest

from app.domain.services.priority_calculator import (
    PriorityCalculator,
    PriorityInput,
)


class TestPriorityCalculator:
    """Tests for simplified PriorityCalculator service."""

    def test_parse_industries(self):
        """Test industry string parsing."""
        assert PriorityCalculator.parse_industries("Technology") == ["Technology"]
        assert PriorityCalculator.parse_industries("Industrial, Defense") == [
            "Industrial",
            "Defense",
        ]
        assert PriorityCalculator.parse_industries("") == []
        assert PriorityCalculator.parse_industries(None) == []

    def test_calculate_priority_basic(self):
        """Test basic priority calculation - now just score * multiplier."""
        input_data = PriorityInput(
            symbol="AAPL",
            name="Apple Inc.",
            geography="US",
            industry="Technology",
            stock_score=0.7,  # Score already includes Quality, Opportunity, Analyst, Allocation Fit
            volatility=0.20,
            multiplier=1.0,
            quality_score=0.8,
            opportunity_score=0.6,
            allocation_fit_score=0.7,
        )

        result = PriorityCalculator.calculate_priority(input_data)

        assert result.symbol == "AAPL"
        assert result.combined_priority == pytest.approx(
            0.7, abs=0.01
        )  # score * multiplier
        assert result.quality_score == 0.8
        assert result.opportunity_score == 0.6
        assert result.allocation_fit_score == 0.7

    def test_calculate_priority_with_multiplier(self):
        """Test priority calculation with manual multiplier."""
        input_data = PriorityInput(
            symbol="AAPL",
            name="Apple Inc.",
            geography="US",
            industry="Technology",
            stock_score=0.6,
            volatility=0.20,
            multiplier=2.0,  # Double the priority
        )

        result = PriorityCalculator.calculate_priority(input_data)

        # With multiplier 2.0, priority should be 0.6 * 2.0 = 1.2
        assert result.combined_priority == pytest.approx(1.2, abs=0.01)

    def test_calculate_priorities_sorts_by_priority(self):
        """Test that calculate_priorities sorts results by priority."""
        inputs = [
            PriorityInput(
                symbol="LOW",
                name="Low Priority",
                geography="US",
                industry="Tech",
                stock_score=0.4,
                volatility=0.30,
                multiplier=1.0,
            ),
            PriorityInput(
                symbol="HIGH",
                name="High Priority",
                geography="US",
                industry="Tech",
                stock_score=0.8,
                volatility=0.15,
                multiplier=1.0,
            ),
        ]

        results = PriorityCalculator.calculate_priorities(inputs)

        # Should be sorted highest first
        assert results[0].symbol == "HIGH"
        assert results[1].symbol == "LOW"
        assert results[0].combined_priority > results[1].combined_priority
        assert results[0].combined_priority == pytest.approx(0.8, abs=0.01)
        assert results[1].combined_priority == pytest.approx(0.4, abs=0.01)
