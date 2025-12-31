"""Domain value objects.

DEPRECATED: This module is kept for backward compatibility during migration.
Import from app.shared.domain.value_objects instead.
"""

# Backward compatibility re-exports (temporary - will be removed in Phase 5)
from app.shared.domain.value_objects import Currency, Money, Price

__all__ = ["Currency", "Money", "Price"]
