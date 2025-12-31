"""Tests for priority calculator service.

These tests validate priority calculations for security recommendations,
including security score multiplication and sorting.
"""

import pytest

from app.modules.universe.domain.priority_calculator import (
    PriorityCalculator,
    PriorityInput,
    PriorityResult,
)


class TestParseIndustries:
    """Test parse_industries method."""

    def test_parses_single_industry(self):
        """Test parsing a single industry string."""
        result = PriorityCalculator.parse_industries("Technology")
        assert result == ["Technology"]

    def test_parses_multiple_industries(self):
        """Test parsing a comma-separated string of industries."""
        result = PriorityCalculator.parse_industries("Industrial, Defense, Aerospace")
        assert result == ["Industrial", "Defense", "Aerospace"]

    def test_handles_leading_trailing_spaces(self):
        """Test handling of spaces around commas and industry names."""
        result = PriorityCalculator.parse_industries("  Tech , Finance ")
        assert result == ["Tech", "Finance"]

    def test_handles_empty_string(self):
        """Test handling of an empty input string."""
        result = PriorityCalculator.parse_industries("")
        assert result == []

    def test_handles_none_input(self):
        """Test handling of None input."""
        result = PriorityCalculator.parse_industries(None)
        assert result == []

    def test_handles_string_with_only_spaces(self):
        """Test handling of a string containing only spaces."""
        result = PriorityCalculator.parse_industries("   ,  ")
        assert result == []


class TestCalculatePriority:
    """Test calculate_priority method."""

    def test_calculates_priority_with_multiplier(self):
        """Test that priority is calculated as stock_score * multiplier."""
        input_data = PriorityInput(
            symbol="AAPL",
            name="Apple",
            security_score=0.75,
            multiplier=1.5,
        )

        result = PriorityCalculator.calculate_priority(input_data)

        assert isinstance(result, PriorityResult)
        assert result.symbol == "AAPL"
        assert result.name == "Apple"
        assert result.security_score == 0.75
        assert result.multiplier == 1.5
        assert result.combined_priority == pytest.approx(0.75 * 1.5, abs=0.0001)
        assert result.combined_priority == pytest.approx(1.125, abs=0.0001)

    def test_rounds_combined_priority_to_4_decimal_places(self):
        """Test that combined_priority is rounded to 4 decimal places."""
        input_data = PriorityInput(
            symbol="AAPL",
            name="Apple",
            security_score=0.333333,
            multiplier=1.5,
        )

        result = PriorityCalculator.calculate_priority(input_data)

        # Should be rounded to 4 decimal places
        # 0.333333 * 1.5 = 0.4999995, should round to 0.5000
        assert result.combined_priority == pytest.approx(0.5000, abs=0.0001)

    def test_preserves_optional_fields(self):
        """Test that optional fields are preserved in the result."""
        input_data = PriorityInput(
            symbol="AAPL",
            name="Apple",
            security_score=0.75,
            multiplier=1.0,
            country="US",
            industry="Technology",
            volatility=0.15,
            quality_score=0.8,
            opportunity_score=0.7,
            allocation_fit_score=0.6,
        )

        result = PriorityCalculator.calculate_priority(input_data)

        assert result.country == "US"
        assert result.industry == "Technology"
        assert result.volatility == 0.15
        assert result.quality_score == 0.8
        assert result.opportunity_score == 0.7
        assert result.allocation_fit_score == 0.6

    def test_handles_none_optional_fields(self):
        """Test handling when optional fields are None."""
        input_data = PriorityInput(
            symbol="AAPL",
            name="Apple",
            security_score=0.75,
            multiplier=1.0,
        )

        result = PriorityCalculator.calculate_priority(input_data)

        assert result.country is None
        assert result.industry is None
        assert result.volatility is None
        assert result.quality_score is None
        assert result.opportunity_score is None
        assert result.allocation_fit_score is None

    def test_handles_zero_stock_score(self):
        """Test handling when stock_score is zero."""
        input_data = PriorityInput(
            symbol="AAPL",
            name="Apple",
            security_score=0.0,
            multiplier=1.5,
        )

        result = PriorityCalculator.calculate_priority(input_data)

        assert result.combined_priority == 0.0

    def test_handles_zero_multiplier(self):
        """Test handling when multiplier is zero."""
        input_data = PriorityInput(
            symbol="AAPL",
            name="Apple",
            security_score=0.75,
            multiplier=0.0,
        )

        result = PriorityCalculator.calculate_priority(input_data)

        assert result.combined_priority == 0.0

    def test_handles_maximum_values(self):
        """Test handling when stock_score and multiplier are at maximum."""
        input_data = PriorityInput(
            symbol="AAPL",
            name="Apple",
            security_score=1.0,
            multiplier=2.0,  # Maximum reasonable multiplier
        )

        result = PriorityCalculator.calculate_priority(input_data)

        assert result.combined_priority == 2.0


class TestCalculatePriorities:
    """Test calculate_priorities method."""

    def test_calculates_priorities_for_multiple_stocks(self):
        """Test that priorities are calculated for multiple securities."""
        inputs = [
            PriorityInput(
                symbol="AAPL",
                name="Apple",
                security_score=0.8,
                multiplier=1.0,
            ),
            PriorityInput(
                symbol="MSFT",
                name="Microsoft",
                security_score=0.7,
                multiplier=1.0,
            ),
        ]

        results = PriorityCalculator.calculate_priorities(inputs)

        assert len(results) == 2
        assert all(isinstance(r, PriorityResult) for r in results)
        assert results[0].symbol == "AAPL"  # Higher score first
        assert results[1].symbol == "MSFT"

    def test_sorts_by_combined_priority_descending(self):
        """Test that results are sorted by combined_priority in descending order."""
        inputs = [
            PriorityInput(
                symbol="LOW",
                name="Low Priority",
                security_score=0.5,
                multiplier=1.0,  # combined = 0.5
            ),
            PriorityInput(
                symbol="HIGH",
                name="High Priority",
                security_score=0.8,
                multiplier=1.5,  # combined = 1.2
            ),
            PriorityInput(
                symbol="MED",
                name="Medium Priority",
                security_score=0.6,
                multiplier=1.0,  # combined = 0.6
            ),
        ]

        results = PriorityCalculator.calculate_priorities(inputs)

        assert len(results) == 3
        assert results[0].symbol == "HIGH"  # Highest priority first
        assert results[1].symbol == "MED"
        assert results[2].symbol == "LOW"

    def test_handles_empty_input_list(self):
        """Test handling when input list is empty."""
        results = PriorityCalculator.calculate_priorities([])

        assert results == []

    def test_handles_single_input(self):
        """Test handling when input list has only one item."""
        inputs = [
            PriorityInput(
                symbol="AAPL",
                name="Apple",
                security_score=0.75,
                multiplier=1.0,
            )
        ]

        results = PriorityCalculator.calculate_priorities(inputs)

        assert len(results) == 1
        assert results[0].symbol == "AAPL"
        assert results[0].combined_priority == pytest.approx(0.75, abs=0.0001)

    def test_preserves_all_input_fields(self):
        """Test that all input fields are preserved in results."""
        inputs = [
            PriorityInput(
                symbol="AAPL",
                name="Apple",
                security_score=0.75,
                multiplier=1.5,
                country="US",
                industry="Technology",
                volatility=0.15,
                quality_score=0.8,
                opportunity_score=0.7,
                allocation_fit_score=0.6,
            )
        ]

        results = PriorityCalculator.calculate_priorities(inputs)

        assert len(results) == 1
        result = results[0]
        assert result.symbol == "AAPL"
        assert result.name == "Apple"
        assert result.country == "US"
        assert result.industry == "Technology"
        assert result.volatility == 0.15
        assert result.quality_score == 0.8
        assert result.opportunity_score == 0.7
        assert result.allocation_fit_score == 0.6
