"""Standard calculation result types.

Provides consistent return types for all calculation functions.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class CalculationResult:
    """Standard result for calculation functions.

    Replaces Optional[float] pattern with richer information about the calculation.

    Example:
        # Before
        if insufficient_data:
            return None
        return 0.11

        # After
        if insufficient_data:
            return CalculationResult(
                value=0.0,
                success=False,
                error="insufficient_data"
            )
        return CalculationResult(
            value=0.11,
            sub_components={"5y": 0.11, "10y": 0.10}
        )
    """

    value: float  # The calculated value
    success: bool = True  # Whether calculation succeeded
    sub_components: Dict[str, float] = field(default_factory=dict)  # Breakdown
    error: Optional[str] = None  # Error message if failed
    metadata: Optional[Dict[str, Any]] = None  # Additional context (e.g., months_used)
