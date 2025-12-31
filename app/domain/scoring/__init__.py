"""Re-export scoring domain for backward compatibility."""

from app.modules.scoring.domain import (
    CalculatedSecurityScore,
    PortfolioContext,
    TechnicalData,
)

# Backward compatibility alias
CalculatedStockScore = CalculatedSecurityScore

__all__ = [
    "CalculatedSecurityScore",
    "CalculatedStockScore",
    "PortfolioContext",
    "TechnicalData",
]
