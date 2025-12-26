"""FastAPI dependency injection container.

This module provides dependency functions for all repositories and services,
enabling proper dependency injection throughout the application.
"""

from fastapi import Depends
from typing import Annotated

from app.repositories import (
    StockRepository,
    PositionRepository,
    TradeRepository,
    ScoreRepository,
    AllocationRepository,
    CashFlowRepository,
    PortfolioRepository,
    HistoryRepository,
    SettingsRepository,
    RecommendationRepository,
    CalculationsRepository,
)
from app.domain.repositories.protocols import (
    IStockRepository,
    IPositionRepository,
    ITradeRepository,
    ISettingsRepository,
    IAllocationRepository,
)
from app.application.services.portfolio_service import PortfolioService
from app.application.services.scoring_service import ScoringService
from app.application.services.rebalancing_service import RebalancingService
from app.application.services.trade_execution_service import TradeExecutionService
from app.application.services.trade_safety_service import TradeSafetyService
from app.application.services.currency_exchange_service import (
    CurrencyExchangeService,
    get_currency_exchange_service,
)
from app.domain.services.settings_service import SettingsService


# Repository Dependencies

def get_stock_repository() -> IStockRepository:
    """Get StockRepository instance."""
    return StockRepository()


def get_position_repository() -> IPositionRepository:
    """Get PositionRepository instance."""
    return PositionRepository()


def get_trade_repository() -> ITradeRepository:
    """Get TradeRepository instance."""
    return TradeRepository()


def get_score_repository() -> ScoreRepository:
    """Get ScoreRepository instance."""
    return ScoreRepository()


def get_allocation_repository() -> IAllocationRepository:
    """Get AllocationRepository instance."""
    return AllocationRepository()


def get_cash_flow_repository() -> CashFlowRepository:
    """Get CashFlowRepository instance."""
    return CashFlowRepository()


def get_portfolio_repository() -> PortfolioRepository:
    """Get PortfolioRepository instance."""
    return PortfolioRepository()


def get_history_repository() -> HistoryRepository:
    """Get HistoryRepository instance."""
    return HistoryRepository()


def get_settings_repository() -> ISettingsRepository:
    """Get SettingsRepository instance."""
    return SettingsRepository()


def get_recommendation_repository() -> RecommendationRepository:
    """Get RecommendationRepository instance."""
    return RecommendationRepository()


def get_calculations_repository() -> CalculationsRepository:
    """Get CalculationsRepository instance."""
    return CalculationsRepository()


# Type aliases for use in function signatures
StockRepositoryDep = Annotated[IStockRepository, Depends(get_stock_repository)]
PositionRepositoryDep = Annotated[IPositionRepository, Depends(get_position_repository)]
TradeRepositoryDep = Annotated[ITradeRepository, Depends(get_trade_repository)]
ScoreRepositoryDep = Annotated[ScoreRepository, Depends(get_score_repository)]
AllocationRepositoryDep = Annotated[IAllocationRepository, Depends(get_allocation_repository)]
CashFlowRepositoryDep = Annotated[CashFlowRepository, Depends(get_cash_flow_repository)]
PortfolioRepositoryDep = Annotated[PortfolioRepository, Depends(get_portfolio_repository)]
HistoryRepositoryDep = Annotated[HistoryRepository, Depends(get_history_repository)]
SettingsRepositoryDep = Annotated[ISettingsRepository, Depends(get_settings_repository)]
RecommendationRepositoryDep = Annotated[RecommendationRepository, Depends(get_recommendation_repository)]
CalculationsRepositoryDep = Annotated[CalculationsRepository, Depends(get_calculations_repository)]


# Application Service Dependencies

def get_portfolio_service(
    portfolio_repo: PortfolioRepositoryDep,
    position_repo: PositionRepositoryDep,
    allocation_repo: AllocationRepositoryDep,
) -> PortfolioService:
    """Get PortfolioService instance."""
    return PortfolioService(
        portfolio_repo=portfolio_repo,
        position_repo=position_repo,
        allocation_repo=allocation_repo,
    )


def get_scoring_service(
    stock_repo: StockRepositoryDep,
    score_repo: ScoreRepositoryDep,
) -> ScoringService:
    """Get ScoringService instance."""
    return ScoringService(
        stock_repo=stock_repo,
        score_repo=score_repo,
    )


def get_settings_service(
    settings_repo: SettingsRepositoryDep,
) -> SettingsService:
    """Get SettingsService instance."""
    return SettingsService(settings_repo=settings_repo)


def get_rebalancing_service(
    stock_repo: StockRepositoryDep,
    position_repo: PositionRepositoryDep,
    allocation_repo: AllocationRepositoryDep,
    portfolio_repo: PortfolioRepositoryDep,
    trade_repo: TradeRepositoryDep,
    settings_repo: SettingsRepositoryDep,
    recommendation_repo: RecommendationRepositoryDep,
) -> RebalancingService:
    """Get RebalancingService instance."""
    return RebalancingService(
        stock_repo=stock_repo,
        position_repo=position_repo,
        allocation_repo=allocation_repo,
        portfolio_repo=portfolio_repo,
        trade_repo=trade_repo,
        settings_repo=settings_repo,
        recommendation_repo=recommendation_repo,
    )


def get_trade_execution_service(
    trade_repo: TradeRepositoryDep,
    position_repo: PositionRepositoryDep,
) -> TradeExecutionService:
    """Get TradeExecutionService instance."""
    return TradeExecutionService(
        trade_repo=trade_repo,
        position_repo=position_repo,
    )


def get_trade_safety_service(
    trade_repo: TradeRepositoryDep,
    position_repo: PositionRepositoryDep,
) -> TradeSafetyService:
    """Get TradeSafetyService instance."""
    return TradeSafetyService(
        trade_repo=trade_repo,
        position_repo=position_repo,
    )


def get_currency_exchange_service_dep() -> CurrencyExchangeService:
    """Get CurrencyExchangeService instance."""
    return get_currency_exchange_service()


# Type aliases for services
PortfolioServiceDep = Annotated[PortfolioService, Depends(get_portfolio_service)]
ScoringServiceDep = Annotated[ScoringService, Depends(get_scoring_service)]
SettingsServiceDep = Annotated[SettingsService, Depends(get_settings_service)]
RebalancingServiceDep = Annotated[RebalancingService, Depends(get_rebalancing_service)]
TradeExecutionServiceDep = Annotated[TradeExecutionService, Depends(get_trade_execution_service)]
TradeSafetyServiceDep = Annotated[TradeSafetyService, Depends(get_trade_safety_service)]
CurrencyExchangeServiceDep = Annotated[CurrencyExchangeService, Depends(get_currency_exchange_service_dep)]

