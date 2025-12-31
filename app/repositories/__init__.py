"""
Repositories - Data access layer.

Direct implementations using the DatabaseManager.
No abstract interfaces - there's only one implementation (SQLite).
"""

from app.modules.dividends.database.dividend_repository import DividendRepository
from app.modules.planning.database.planner_repository import PlannerRepository
from app.modules.portfolio.database.history_repository import HistoryRepository
from app.modules.portfolio.database.portfolio_repository import PortfolioRepository
from app.modules.portfolio.database.position_repository import PositionRepository
from app.modules.universe.database.stock_repository import StockRepository
from app.repositories.calculations import CalculationsRepository
from app.repositories.grouping import GroupingRepository
from app.repositories.recommendation import RecommendationRepository
from app.repositories.score import ScoreRepository
from app.repositories.settings import SettingsRepository
from app.repositories.trade import TradeRepository

__all__ = [
    "CalculationsRepository",
    "DividendRepository",
    "GroupingRepository",
    "HistoryRepository",
    "PlannerRepository",
    "PortfolioRepository",
    "PositionRepository",
    "RecommendationRepository",
    "ScoreRepository",
    "SettingsRepository",
    "StockRepository",
    "TradeRepository",
]
