"""
Repositories - Data access layer.

Direct implementations using the DatabaseManager.
No abstract interfaces - there's only one implementation (SQLite).

Note: Imports are done lazily to avoid circular import issues.
"""

__all__ = [
    "AllocationRepository",
    "CalculationsRepository",
    "CashFlowRepository",
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


def __getattr__(name: str):
    """Lazy import repositories to avoid circular imports."""
    if name == "AllocationRepository":
        from app.modules.allocation.database.allocation_repository import AllocationRepository
        return AllocationRepository
    elif name == "CashFlowRepository":
        from app.modules.cash_flows.database.cash_flow_repository import CashFlowRepository
        return CashFlowRepository
    elif name == "DividendRepository":
        from app.modules.dividends.database.dividend_repository import DividendRepository
        return DividendRepository
    elif name == "PlannerRepository":
        from app.modules.planning.database.planner_repository import PlannerRepository
        return PlannerRepository
    elif name == "HistoryRepository":
        from app.modules.portfolio.database.history_repository import HistoryRepository
        return HistoryRepository
    elif name == "PortfolioRepository":
        from app.modules.portfolio.database.portfolio_repository import PortfolioRepository
        return PortfolioRepository
    elif name == "PositionRepository":
        from app.modules.portfolio.database.position_repository import PositionRepository
        return PositionRepository
    elif name == "StockRepository":
        from app.modules.universe.database.stock_repository import StockRepository
        return StockRepository
    elif name == "CalculationsRepository":
        from app.repositories.calculations import CalculationsRepository
        return CalculationsRepository
    elif name == "GroupingRepository":
        from app.repositories.grouping import GroupingRepository
        return GroupingRepository
    elif name == "RecommendationRepository":
        from app.repositories.recommendation import RecommendationRepository
        return RecommendationRepository
    elif name == "ScoreRepository":
        from app.repositories.score import ScoreRepository
        return ScoreRepository
    elif name == "SettingsRepository":
        from app.repositories.settings import SettingsRepository
        return SettingsRepository
    elif name == "TradeRepository":
        from app.repositories.trade import TradeRepository
        return TradeRepository
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
