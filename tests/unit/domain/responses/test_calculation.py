"""Tests for CalculationResult response type.

These tests validate the CalculationResult type for calculation function results.
"""

from app.domain.responses.calculation import CalculationResult


class TestCalculationResult:
    """Test CalculationResult type."""

    def test_calculation_result_creation_with_value_only(self):
        """Test creating CalculationResult with value only."""
        result = CalculationResult(value=0.11)

        assert result.value == 0.11
        assert result.success is True  # Default
        assert result.sub_components == {}
        assert result.error is None
        assert result.metadata is None

    def test_calculation_result_creation_with_all_fields(self):
        """Test creating CalculationResult with all fields."""
        result = CalculationResult(
            value=0.15,
            success=True,
            sub_components={"5y": 0.14, "10y": 0.16},
            error=None,
            metadata={"months_used": 60},
        )

        assert result.value == 0.15
        assert result.success is True
        assert result.sub_components == {"5y": 0.14, "10y": 0.16}
        assert result.error is None
        assert result.metadata == {"months_used": 60}

    def test_calculation_result_failure(self):
        """Test creating CalculationResult for failed calculation."""
        result = CalculationResult(
            value=0.0,
            success=False,
            error="insufficient_data",
            metadata={"symbol": "AAPL"},
        )

        assert result.value == 0.0
        assert result.success is False
        assert result.error == "insufficient_data"
        assert result.metadata == {"symbol": "AAPL"}

    def test_calculation_result_with_sub_components(self):
        """Test CalculationResult with sub-components breakdown."""
        result = CalculationResult(
            value=0.12,
            sub_components={
                "historical_cagr": 0.11,
                "target_return": 0.11,
                "regime_adjustment": 0.01,
            },
        )

        assert result.value == 0.12
        assert len(result.sub_components) == 3
        assert result.sub_components["historical_cagr"] == 0.11
        assert result.sub_components["target_return"] == 0.11
        assert result.sub_components["regime_adjustment"] == 0.01

    def test_calculation_result_with_metadata(self):
        """Test CalculationResult with metadata."""
        result = CalculationResult(
            value=0.10,
            metadata={"data_points": 120, "confidence": "high"},
        )

        assert result.value == 0.10
        assert result.metadata == {"data_points": 120, "confidence": "high"}

    def test_calculation_result_zero_value(self):
        """Test CalculationResult with zero value."""
        result = CalculationResult(value=0.0)

        assert result.value == 0.0
        assert result.success is True

    def test_calculation_result_negative_value(self):
        """Test CalculationResult with negative value."""
        result = CalculationResult(value=-0.05)

        assert result.value == -0.05
        assert result.success is True
