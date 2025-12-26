"""Tests for RecommendationStatus enum."""

import pytest

from app.domain.value_objects.recommendation_status import RecommendationStatus


class TestRecommendationStatus:
    """Test RecommendationStatus enum values and methods."""

    def test_enum_values_exist(self):
        """Test that all expected status values exist."""
        assert RecommendationStatus.PENDING == "pending"
        assert RecommendationStatus.EXECUTED == "executed"
        assert RecommendationStatus.DISMISSED == "dismissed"

    def test_status_values_are_strings(self):
        """Test that status values are strings."""
        assert isinstance(RecommendationStatus.PENDING, str)
        assert isinstance(RecommendationStatus.EXECUTED, str)
        assert isinstance(RecommendationStatus.DISMISSED, str)

    def test_status_from_string_valid(self):
        """Test creating status from valid string."""
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
        assert (
            RecommendationStatus.from_string("PENDING") == RecommendationStatus.PENDING
        )  # Case insensitive
        assert (
            RecommendationStatus.from_string("EXECUTED")
            == RecommendationStatus.EXECUTED
        )

    def test_status_from_string_invalid(self):
        """Test creating status from invalid string raises error."""
        with pytest.raises(ValueError, match="Invalid recommendation status"):
            RecommendationStatus.from_string("INVALID")

        with pytest.raises(ValueError, match="Invalid recommendation status"):
            RecommendationStatus.from_string("")

        with pytest.raises(ValueError, match="Invalid recommendation status"):
            RecommendationStatus.from_string("cancelled")

    def test_status_is_valid(self):
        """Test checking if status string is valid."""
        assert RecommendationStatus.is_valid("pending") is True
        assert RecommendationStatus.is_valid("executed") is True
        assert RecommendationStatus.is_valid("dismissed") is True
        assert RecommendationStatus.is_valid("PENDING") is True  # Case insensitive
        assert RecommendationStatus.is_valid("INVALID") is False
        assert RecommendationStatus.is_valid("") is False

    def test_status_transitions(self):
        """Test that status transitions are valid."""
        # PENDING can transition to EXECUTED or DISMISSED
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

        # EXECUTED and DISMISSED are terminal states
        assert (
            RecommendationStatus.EXECUTED.can_transition_to(
                RecommendationStatus.PENDING
            )
            is False
        )
        assert (
            RecommendationStatus.DISMISSED.can_transition_to(
                RecommendationStatus.PENDING
            )
            is False
        )
