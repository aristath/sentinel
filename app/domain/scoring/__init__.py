"""Re-export scoring domain for backward compatibility."""

from app.modules.scoring.domain import (
    CalculatedStockScore,
    PortfolioContext,
    TechnicalData,
)

__all__ = ["CalculatedStockScore", "PortfolioContext", "TechnicalData"]
