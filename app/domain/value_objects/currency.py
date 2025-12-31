"""Currency value object.

DEPRECATED: This module is kept for backward compatibility during migration.
Import from app.shared.domain.value_objects instead.
"""

# Backward compatibility re-export (temporary - will be removed in Phase 5)
from app.shared.domain.value_objects.currency import Currency

__all__ = ["Currency"]
