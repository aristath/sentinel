"""Money value object for representing monetary amounts with currency.

DEPRECATED: This module is kept for backward compatibility during migration.
Import from app.shared.domain.value_objects instead.
"""

# Backward compatibility re-export (temporary - will be removed in Phase 5)
from app.shared.domain.value_objects.money import Money

__all__ = ["Money"]
