"""Standard calculation result types.

Provides consistent return types for all calculation functions.
"""

from dataclasses import dataclass
from typing import Dict, Optional, Any


@dataclass
class CalculationResult:
    """Standard result for any calculation.
    
    Use this for all calculation functions that compute a single numeric value,
    replacing Optional[float] return types.
    
    Attributes:
        value: The calculated value (always present, use 0.0 if calculation fails)
        sub_components: Breakdown of calculation components (e.g., {"5y": 0.11, "10y": 0.10})
        metadata: Additional context (errors, warnings, calculation parameters)
    """
    value: float
    sub_components: Dict[str, float]
    metadata: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        """Ensure value is always a float."""
        if self.sub_components is None:
            self.sub_components = {}
        if not isinstance(self.value, (int, float)):
            raise ValueError(f"value must be numeric, got {type(self.value)}")
    
    @property
    def is_valid(self) -> bool:
        """Check if calculation was successful."""
        if self.metadata and self.metadata.get("error"):
            return False
        return True
    
    @property
    def error_message(self) -> Optional[str]:
        """Get error message if calculation failed."""
        if self.metadata and "error" in self.metadata:
            return self.metadata["error"]
        return None

