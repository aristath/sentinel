"""Price value object for representing per-share/unit prices.

DEPRECATED: This module is kept for backward compatibility during migration.
Import from app.shared.domain.value_objects instead.
"""

# Backward compatibility re-export (temporary - will be removed in Phase 5)
from app.shared.domain.value_objects.price import Price

__all__ = ["Price"]
