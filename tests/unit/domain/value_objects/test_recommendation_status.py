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
        assert RecommendationStatus.EXECUTED.value == "executed"
        assert RecommendationStatus.DISMISSED.value == "dismissed"

    def test_from_string_with_valid_status(self):
        """Test from_string with valid status strings."""
        assert (
            RecommendationStatus.from_string("pending") == RecommendationStatus.PENDING
        )
        assert (
            RecommendationStatus.from_string("executed")
            == RecommendationStatus.EXECUTED
        )
        assert (
            RecommendationStatus.from_string("dismissed")
            == RecommendationStatus.DISMISSED
        )

    def test_from_string_case_insensitive(self):
        """Test that from_string is case-insensitive."""
        assert (
            RecommendationStatus.from_string("PENDING") == RecommendationStatus.PENDING
        )
        assert (
            RecommendationStatus.from_string("Pending") == RecommendationStatus.PENDING
        )
        assert (
            RecommendationStatus.from_string("pending") == RecommendationStatus.PENDING
        )
        assert (
            RecommendationStatus.from_string("EXECUTED")
            == RecommendationStatus.EXECUTED
        )

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

    def test_can_transition_to_from_pending(self):
        """Test can_transition_to method from PENDING status."""
        assert (
            RecommendationStatus.PENDING.can_transition_to(
                RecommendationStatus.EXECUTED
            )
            is True
        )
        assert (
            RecommendationStatus.PENDING.can_transition_to(
                RecommendationStatus.DISMISSED
            )
            is True
        )
        assert (
            RecommendationStatus.PENDING.can_transition_to(RecommendationStatus.PENDING)
            is False
        )

    def test_can_transition_to_from_executed(self):
        """Test can_transition_to method from EXECUTED status (terminal state)."""
        assert (
            RecommendationStatus.EXECUTED.can_transition_to(
                RecommendationStatus.PENDING
            )
            is False
        )
        assert (
            RecommendationStatus.EXECUTED.can_transition_to(
                RecommendationStatus.DISMISSED
            )
            is False
        )
        assert (
            RecommendationStatus.EXECUTED.can_transition_to(
                RecommendationStatus.EXECUTED
            )
            is False
        )

    def test_can_transition_to_from_dismissed(self):
        """Test can_transition_to method from DISMISSED status (terminal state)."""
        assert (
            RecommendationStatus.DISMISSED.can_transition_to(
                RecommendationStatus.PENDING
            )
            is False
        )
        assert (
            RecommendationStatus.DISMISSED.can_transition_to(
                RecommendationStatus.EXECUTED
            )
            is False
        )
        assert (
            RecommendationStatus.DISMISSED.can_transition_to(
                RecommendationStatus.DISMISSED
            )
            is False
        )

    def test_recommendation_status_str_representation(self):
        """Test that RecommendationStatus enum values have correct string representation."""
        assert str(RecommendationStatus.PENDING) == "RecommendationStatus.PENDING"
        assert str(RecommendationStatus.EXECUTED) == "RecommendationStatus.EXECUTED"

    def test_recommendation_status_equality(self):
        """Test RecommendationStatus enum equality."""
        assert RecommendationStatus.PENDING == RecommendationStatus.PENDING
        assert RecommendationStatus.EXECUTED == RecommendationStatus.EXECUTED
        assert RecommendationStatus.PENDING != RecommendationStatus.EXECUTED
