"""Tests for ServiceResult response type.

These tests validate the ServiceResult generic type for service operation results.
"""

import pytest

from app.domain.responses.service import ServiceResult


class TestServiceResult:
    """Test ServiceResult generic type."""

    def test_success_result_creation(self):
        """Test creating a successful ServiceResult."""
        result = ServiceResult(success=True, data={"key": "value"})

        assert result.success is True
        assert result.data == {"key": "value"}
        assert result.error is None

    def test_error_result_creation(self):
        """Test creating an error ServiceResult."""
        result = ServiceResult(success=False, error="Something went wrong")

        assert result.success is False
        assert result.data is None
        assert result.error == "Something went wrong"

    def test_success_result_with_none_data(self):
        """Test creating a successful ServiceResult with None data."""
        result = ServiceResult(success=True, data=None)

        assert result.success is True
        assert result.data is None
        assert result.error is None

    def test_error_result_validation_requires_error_message(self):
        """Test that error ServiceResult requires error message."""
        with pytest.raises(
            ValueError, match="ServiceResult with success=False must have error message"
        ):
            ServiceResult(success=False, error=None)

    def test_is_success_returns_true_for_success(self):
        """Test is_success property returns True for successful results."""
        result = ServiceResult(success=True, data="test")

        assert result.is_success is True

    def test_is_success_returns_false_for_error(self):
        """Test is_success property returns False for error results."""
        result = ServiceResult(success=False, error="test error")

        assert result.is_success is False

    def test_is_error_returns_false_for_success(self):
        """Test is_error property returns False for successful results."""
        result = ServiceResult(success=True, data="test")

        assert result.is_error is False

    def test_is_error_returns_true_for_error(self):
        """Test is_error property returns True for error results."""
        result = ServiceResult(success=False, error="test error")

        assert result.is_error is True

    def test_service_result_with_integer_data(self):
        """Test ServiceResult with integer data type."""
        result = ServiceResult(success=True, data=42)

        assert result.success is True
        assert result.data == 42
        assert isinstance(result.data, int)

    def test_service_result_with_list_data(self):
        """Test ServiceResult with list data type."""
        result = ServiceResult(success=True, data=[1, 2, 3])

        assert result.success is True
        assert result.data == [1, 2, 3]
        assert isinstance(result.data, list)

    def test_service_result_with_dict_data(self):
        """Test ServiceResult with dictionary data type."""
        data = {"key1": "value1", "key2": 123}
        result = ServiceResult(success=True, data=data)

        assert result.success is True
        assert result.data == data
        assert isinstance(result.data, dict)

    def test_service_result_with_metadata(self):
        """Test ServiceResult with metadata."""
        result = ServiceResult(
            success=True,
            data="test",
            metadata={"processing_time": 0.5, "source": "api"},
        )

        assert result.success is True
        assert result.data == "test"
        assert result.metadata == {"processing_time": 0.5, "source": "api"}
