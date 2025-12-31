"""
Repositories - Data access layer.

Direct implementations using the DatabaseManager.
No abstract interfaces - there's only one implementation (SQLite).
"""

# Backward compatibility re-export (temporary - will be removed in Phase 5)
from app.modules.planning.database.planner_repository import PlannerRepository
from app.repositories.allocation import AllocationRepository
from app.repositories.calculations import CalculationsRepository
from app.repositories.cash_flow import CashFlowRepository
# Backward compatibility re-export (temporary - will be removed in Phase 5)
from app.modules.dividends.database.dividend_repository import DividendRepository
from app.repositories.grouping import GroupingRepository
# Backward compatibility re-export (temporary - will be removed in Phase 5)
from app.modules.portfolio.database.history_repository import HistoryRepository
from app.modules.portfolio.database.portfolio_repository import PortfolioRepository
from app.modules.portfolio.database.position_repository import PositionRepository
from app.repositories.recommendation import RecommendationRepository
from app.repositories.score import ScoreRepository
from app.repositories.settings import SettingsRepository
# Backward compatibility re-export (temporary - will be removed in Phase 5)
from app.modules.universe.database.stock_repository import StockRepository
from app.repositories.trade import TradeRepository

__all__ = [
    "StockRepository",
    "PositionRepository",
    "TradeRepository",
    "ScoreRepository",
    "AllocationRepository",
    "CashFlowRepository",
    "PortfolioRepository",
    "HistoryRepository",
    "SettingsRepository",
    "RecommendationRepository",
    "CalculationsRepository",
    "DividendRepository",
    "GroupingRepository",
    "PlannerRepository",
]
