"""Concentration alert detection service.

DEPRECATED: This module is kept for backward compatibility during migration.
Import from app.modules.allocation.services.concentration_alerts instead.
"""

# Backward compatibility re-export (temporary - will be removed in Phase 5)
from app.modules.allocation.services.concentration_alerts import (
    ConcentrationAlert,
    ConcentrationAlertService,
)

__all__ = ["ConcentrationAlert", "ConcentrationAlertService"]
