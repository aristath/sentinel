"""Tests for RecommendationStatus value object.

These tests validate the RecommendationStatus enum and its status checking functionality.
"""

import pytest

from app.domain.value_objects.recommendation_status import RecommendationStatus


class TestRecommendationStatus:
    """Test RecommendationStatus enum."""

    def test_recommendation_status_enum_values(self):
        """Test that RecommendationStatus enum has expected values."""
        assert RecommendationStatus.PENDING.value == "pending"
        assert RecommendationStatus.ACCEPTED.value == "accepted"
        assert RecommendationStatus.EXECUTED.value == "executed"
        assert RecommendationStatus.REJECTED.value == "rejected"
        assert RecommendationStatus.DISMISSED.value == "dismissed"

    def test_from_string_with_valid_status(self):
        """Test from_string with valid status strings."""
        assert RecommendationStatus.from_string("pending") == RecommendationStatus.PENDING
        assert RecommendationStatus.from_string("accepted") == RecommendationStatus.ACCEPTED
        assert RecommendationStatus.from_string("executed") == RecommendationStatus.EXECUTED
        assert RecommendationStatus.from_string("rejected") == RecommendationStatus.REJECTED
        assert RecommendationStatus.from_string("dismissed") == RecommendationStatus.DISMISSED

    def test_from_string_case_insensitive(self):
        """Test that from_string is case-insensitive."""
        assert RecommendationStatus.from_string("PENDING") == RecommendationStatus.PENDING
        assert RecommendationStatus.from_string("Pending") == RecommendationStatus.PENDING
        assert RecommendationStatus.from_string("pending") == RecommendationStatus.PENDING
        assert RecommendationStatus.from_string("EXECUTED") == RecommendationStatus.EXECUTED

    def test_from_string_with_invalid_status(self):
        """Test that from_string raises ValueError for invalid statuses."""
        with pytest.raises(ValueError, match="Invalid recommendation status"):
            RecommendationStatus.from_string("INVALID")

        with pytest.raises(ValueError):
            RecommendationStatus.from_string("")

        with pytest.raises(ValueError):
            RecommendationStatus.from_string("UNKNOWN")

    def test_from_string_with_none(self):
        """Test that from_string raises ValueError for None."""
        with pytest.raises(ValueError):
            RecommendationStatus.from_string(None)

    def test_is_final_with_final_statuses(self):
        """Test is_final method with final statuses."""
        assert RecommendationStatus.EXECUTED.is_final() is True
        assert RecommendationStatus.REJECTED.is_final() is True
        assert RecommendationStatus.DISMISSED.is_final() is True

    def test_is_final_with_non_final_statuses(self):
        """Test is_final method with non-final statuses."""
        assert RecommendationStatus.PENDING.is_final() is False
        assert RecommendationStatus.ACCEPTED.is_final() is False

    def test_recommendation_status_str_representation(self):
        """Test that RecommendationStatus enum values have correct string representation."""
        assert str(RecommendationStatus.PENDING) == "RecommendationStatus.PENDING"
        assert str(RecommendationStatus.EXECUTED) == "RecommendationStatus.EXECUTED"

    def test_recommendation_status_equality(self):
        """Test RecommendationStatus enum equality."""
        assert RecommendationStatus.PENDING == RecommendationStatus.PENDING
        assert RecommendationStatus.EXECUTED == RecommendationStatus.EXECUTED
        assert RecommendationStatus.PENDING != RecommendationStatus.EXECUTED
