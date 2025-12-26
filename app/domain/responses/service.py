"""Standard service result types.

Provides consistent return types for service operations with error handling.
"""

from dataclasses import dataclass
from typing import Any, Dict, Generic, Optional, TypeVar

T = TypeVar("T")


@dataclass
class ServiceResult(Generic[T]):
    """Generic service result with success/error handling.

    Use this for service methods that need to handle errors gracefully,
    replacing Optional[T] or exception-only error handling.

    Attributes:
        success: Whether the operation succeeded
        data: Result data (only present if success=True)
        error: Error message (only present if success=False)
        metadata: Additional context (operation details, warnings, etc.)

    Example:
        # Success case
        result = ServiceResult(
            success=True,
            data=some_data,
            metadata={"processing_time": 0.5}
        )

        # Error case
        result = ServiceResult(
            success=False,
            error="Insufficient data for calculation",
            metadata={"symbol": "AAPL"}
        )
    """

    success: bool
    data: Optional[T] = None
    error: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        """Validate result state."""
        if self.success:
            if self.data is None and self.error is None:
                # Allow success=True with data=None (e.g., empty list is valid)
                pass
        else:
            if not self.error:
                raise ValueError(
                    "ServiceResult with success=False must have error message"
                )

    @property
    def is_success(self) -> bool:
        """Check if operation succeeded."""
        return self.success

    @property
    def is_error(self) -> bool:
        """Check if operation failed."""
        return not self.success
