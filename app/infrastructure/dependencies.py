"""Dependency injection for FastAPI.

Provides FastAPI dependency functions for repositories and services.
"""

from fastapi import Depends
import aiosqlite

from app.database import get_db
from app.infrastructure.database.repositories import (
    SQLiteStockRepository,
    SQLitePositionRepository,
    SQLitePortfolioRepository,
    SQLiteAllocationRepository,
    SQLiteScoreRepository,
    SQLiteTradeRepository,
    SQLiteSettingsRepository,
    SQLiteCashFlowRepository,
)
from app.domain.repositories import (
    StockRepository,
    PositionRepository,
    PortfolioRepository,
    AllocationRepository,
    ScoreRepository,
    TradeRepository,
    SettingsRepository,
    CashFlowRepository,
)


def get_stock_repository(
    db: aiosqlite.Connection = Depends(get_db)
) -> StockRepository:
    """Get stock repository instance."""
    return SQLiteStockRepository(db)


def get_position_repository(
    db: aiosqlite.Connection = Depends(get_db)
) -> PositionRepository:
    """Get position repository instance."""
    return SQLitePositionRepository(db)


def get_portfolio_repository(
    db: aiosqlite.Connection = Depends(get_db)
) -> PortfolioRepository:
    """Get portfolio repository instance."""
    return SQLitePortfolioRepository(db)


def get_allocation_repository(
    db: aiosqlite.Connection = Depends(get_db)
) -> AllocationRepository:
    """Get allocation repository instance."""
    return SQLiteAllocationRepository(db)


def get_score_repository(
    db: aiosqlite.Connection = Depends(get_db)
) -> ScoreRepository:
    """Get score repository instance."""
    return SQLiteScoreRepository(db)


def get_trade_repository(
    db: aiosqlite.Connection = Depends(get_db)
) -> TradeRepository:
    """Get trade repository instance."""
    return SQLiteTradeRepository(db)


def get_settings_repository(
    db: aiosqlite.Connection = Depends(get_db)
) -> SettingsRepository:
    """Get settings repository instance."""
    return SQLiteSettingsRepository(db)


def get_cash_flow_repository(
    db: aiosqlite.Connection = Depends(get_db)
) -> CashFlowRepository:
    """Get cash flow repository instance."""
    return SQLiteCashFlowRepository(db)
