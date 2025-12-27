"""Recommendation status value object."""

from enum import Enum


class RecommendationStatus(str, Enum):
    """Recommendation status enumeration."""

    PENDING = "pending"
    EXECUTED = "executed"
    DISMISSED = "dismissed"

    @classmethod
    def from_string(cls, value: str) -> "RecommendationStatus":
        """Create RecommendationStatus from string (case-insensitive).

        Args:
            value: Status string (e.g., "pending", "executed", "dismissed")

        Returns:
            RecommendationStatus enum value

        Raises:
            ValueError: If status is not supported
        """
        if not value:
            raise ValueError("Invalid recommendation status: empty string")

        value_lower = value.lower()
        try:
            return cls(value_lower)
        except ValueError:
            raise ValueError(f"Invalid recommendation status: {value}")

    @classmethod
    def is_valid(cls, value: str) -> bool:
        """Check if string is a valid status (case-insensitive).

        Args:
            value: Status string to check

        Returns:
            True if valid, False otherwise
        """
        if not value:
            return False
        try:
            cls.from_string(value)
            return True
        except ValueError:
            return False

    def can_transition_to(self, target: "RecommendationStatus") -> bool:
        """Check if this status can transition to target status.

        Args:
            target: Target status to transition to

        Returns:
            True if transition is valid, False otherwise
        """
        # PENDING can transition to EXECUTED or DISMISSED
        if self == RecommendationStatus.PENDING:
            return target in (
                RecommendationStatus.EXECUTED,
                RecommendationStatus.DISMISSED,
            )

        # EXECUTED and DISMISSED are terminal states (cannot transition)
        return False

