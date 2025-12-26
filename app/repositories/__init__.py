"""
Repositories - Data access layer.

Direct implementations using the DatabaseManager.
No abstract interfaces - there's only one implementation (SQLite).
"""

from app.repositories.allocation import AllocationRepository
from app.repositories.calculations import CalculationsRepository
from app.repositories.cash_flow import CashFlowRepository
from app.repositories.dividend import DividendRepository
from app.repositories.history import HistoryRepository
from app.repositories.portfolio import PortfolioRepository
from app.repositories.position import PositionRepository
from app.repositories.recommendation import RecommendationRepository
from app.repositories.score import ScoreRepository
from app.repositories.settings import SettingsRepository
from app.repositories.stock import StockRepository
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
]
