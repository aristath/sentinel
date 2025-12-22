"""Repository interfaces - abstract contracts for data access."""

from app.domain.repositories.stock_repository import (
    StockRepository,
    Stock,
)
from app.domain.repositories.position_repository import (
    PositionRepository,
    Position,
)
from app.domain.repositories.portfolio_repository import (
    PortfolioRepository,
    PortfolioSnapshot,
)
from app.domain.repositories.allocation_repository import (
    AllocationRepository,
    AllocationTarget,
)
from app.domain.repositories.score_repository import (
    ScoreRepository,
    StockScore,
)
from app.domain.repositories.trade_repository import (
    TradeRepository,
    Trade,
)
from app.domain.repositories.settings_repository import (
    SettingsRepository,
)
from app.domain.repositories.cash_flow_repository import (
    CashFlowRepository,
)

__all__ = [
    "StockRepository",
    "Stock",
    "PositionRepository",
    "Position",
    "PortfolioRepository",
    "PortfolioSnapshot",
    "AllocationRepository",
    "AllocationTarget",
    "ScoreRepository",
    "StockScore",
    "TradeRepository",
    "Trade",
    "SettingsRepository",
    "CashFlowRepository",
]
