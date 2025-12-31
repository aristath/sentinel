"""FastAPI dependency injection container.

This module provides dependency functions for all repositories and services,
enabling proper dependency injection throughout the application.
"""

from typing import Annotated

from fastapi import Depends

from app.core.database.manager import DatabaseManager, get_db_manager
from app.domain.repositories.protocols import (
    IAllocationRepository,
    IPositionRepository,
    ISecurityRepository,
    ISettingsRepository,
    ITradeRepository,
)
from app.domain.services.exchange_rate_service import ExchangeRateService
from app.domain.services.settings_service import SettingsService
from app.infrastructure.external.tradernet import TradernetClient, get_tradernet_client
from app.modules.allocation.database.allocation_repository import AllocationRepository
from app.modules.allocation.services.concentration_alerts import (
    ConcentrationAlertService,
)
from app.modules.cash_flows.database.cash_flow_repository import CashFlowRepository
from app.modules.display.services.display_service import (
    DisplayStateManager,
    _display_state_manager,
)
from app.modules.portfolio.database.portfolio_repository import PortfolioRepository
from app.modules.portfolio.database.position_repository import PositionRepository
from app.modules.portfolio.services.portfolio_service import PortfolioService
from app.modules.rebalancing.services.rebalancing_service import RebalancingService
from app.modules.scoring.services.scoring_service import ScoringService
from app.modules.trading.services.trade_execution_service import TradeExecutionService
from app.modules.trading.services.trade_safety_service import TradeSafetyService
from app.modules.universe.database.security_repository import SecurityRepository
from app.modules.universe.domain.ticker_content_service import TickerContentService
from app.modules.universe.services.stock_setup_service import StockSetupService
from app.repositories.calculations import CalculationsRepository
from app.repositories.grouping import GroupingRepository
from app.repositories.recommendation import RecommendationRepository
from app.repositories.score import ScoreRepository
from app.repositories.settings import SettingsRepository
from app.repositories.trade import TradeRepository
from app.shared.services import CurrencyExchangeService

# Repository Dependencies


def get_security_repository() -> SecurityRepository:
    """Get SecurityRepository instance."""
    return SecurityRepository()


# Backward compatibility alias
def get_stock_repository() -> SecurityRepository:
    """Get SecurityRepository instance (deprecated name)."""
    return get_security_repository()


def get_position_repository() -> IPositionRepository:
    """Get PositionRepository instance."""
    return PositionRepository()


def get_trade_repository() -> ITradeRepository:
    """Get TradeRepository instance."""
    # Type ignore: TradeRepository implements ITradeRepository
    return TradeRepository()  # type: ignore[return-value]


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


def get_settings_repository() -> ISettingsRepository:
    """Get SettingsRepository instance."""
    return SettingsRepository()


def get_recommendation_repository() -> RecommendationRepository:
    """Get RecommendationRepository instance."""
    return RecommendationRepository()


def get_calculations_repository() -> CalculationsRepository:
    """Get CalculationsRepository instance."""
    return CalculationsRepository()


def get_grouping_repository() -> GroupingRepository:
    """Get GroupingRepository instance."""
    return GroupingRepository()


# Infrastructure Dependencies


def get_database_manager() -> DatabaseManager:
    """Get DatabaseManager singleton instance."""
    return get_db_manager()


def get_tradernet() -> TradernetClient:
    """Get TradernetClient singleton instance."""
    return get_tradernet_client()


def get_display_state_manager() -> DisplayStateManager:
    """Get DisplayStateManager singleton instance."""
    return _display_state_manager


# Type aliases for use in function signatures
SecurityRepositoryDep = Annotated[ISecurityRepository, Depends(get_security_repository)]
StockRepositoryDep = SecurityRepositoryDep  # Deprecated: use SecurityRepositoryDep
PositionRepositoryDep = Annotated[IPositionRepository, Depends(get_position_repository)]
TradeRepositoryDep = Annotated[ITradeRepository, Depends(get_trade_repository)]
ScoreRepositoryDep = Annotated[ScoreRepository, Depends(get_score_repository)]
AllocationRepositoryDep = Annotated[
    IAllocationRepository, Depends(get_allocation_repository)
]
CashFlowRepositoryDep = Annotated[CashFlowRepository, Depends(get_cash_flow_repository)]
PortfolioRepositoryDep = Annotated[
    PortfolioRepository, Depends(get_portfolio_repository)
]
SettingsRepositoryDep = Annotated[ISettingsRepository, Depends(get_settings_repository)]
RecommendationRepositoryDep = Annotated[
    RecommendationRepository, Depends(get_recommendation_repository)
]
CalculationsRepositoryDep = Annotated[
    CalculationsRepository, Depends(get_calculations_repository)
]
GroupingRepositoryDep = Annotated[GroupingRepository, Depends(get_grouping_repository)]

# Infrastructure dependency type aliases
DatabaseManagerDep = Annotated[DatabaseManager, Depends(get_database_manager)]
TradernetClientDep = Annotated[TradernetClient, Depends(get_tradernet)]
DisplayStateManagerDep = Annotated[
    DisplayStateManager, Depends(get_display_state_manager)
]


# Application Service Dependencies


def get_portfolio_service(
    portfolio_repo: PortfolioRepositoryDep,
    position_repo: PositionRepositoryDep,
    allocation_repo: AllocationRepositoryDep,
    stock_repo: StockRepositoryDep,
) -> PortfolioService:
    """Get PortfolioService instance."""
    return PortfolioService(
        portfolio_repo=portfolio_repo,
        position_repo=position_repo,
        allocation_repo=allocation_repo,
        stock_repo=stock_repo,
    )


def get_scoring_service(
    stock_repo: StockRepositoryDep,
    score_repo: ScoreRepositoryDep,
    db_manager: DatabaseManagerDep,
) -> ScoringService:
    """Get ScoringService instance."""
    return ScoringService(
        stock_repo=stock_repo,
        score_repo=score_repo,
        db_manager=db_manager,
    )


def get_settings_service(
    settings_repo: SettingsRepositoryDep,
) -> SettingsService:
    """Get SettingsService instance."""
    return SettingsService(settings_repo=settings_repo)


def get_exchange_rate_service(
    db_manager: DatabaseManagerDep,
) -> ExchangeRateService:
    """Get ExchangeRateService instance."""
    return ExchangeRateService(db_manager=db_manager)


def get_ticker_content_service(
    portfolio_repo: PortfolioRepositoryDep,
    position_repo: PositionRepositoryDep,
    stock_repo: StockRepositoryDep,
    settings_repo: SettingsRepositoryDep,
    allocation_repo: AllocationRepositoryDep,
    tradernet_client: TradernetClientDep,
) -> TickerContentService:
    """Get TickerContentService instance."""
    return TickerContentService(
        portfolio_repo=portfolio_repo,
        position_repo=position_repo,
        stock_repo=stock_repo,
        settings_repo=settings_repo,
        allocation_repo=allocation_repo,
        tradernet_client=tradernet_client,
    )


def get_currency_exchange_service_dep(
    tradernet_client: TradernetClientDep,
) -> CurrencyExchangeService:
    """Get CurrencyExchangeService instance."""
    return CurrencyExchangeService(tradernet_client)


def get_rebalancing_service(
    stock_repo: StockRepositoryDep,
    position_repo: PositionRepositoryDep,
    allocation_repo: AllocationRepositoryDep,
    portfolio_repo: PortfolioRepositoryDep,
    trade_repo: TradeRepositoryDep,
    settings_repo: SettingsRepositoryDep,
    recommendation_repo: RecommendationRepositoryDep,
    db_manager: DatabaseManagerDep,
    tradernet_client: TradernetClientDep,
    exchange_rate_service: Annotated[
        ExchangeRateService, Depends(get_exchange_rate_service)
    ],
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
        db_manager=db_manager,
        tradernet_client=tradernet_client,
        exchange_rate_service=exchange_rate_service,
    )


def get_trade_execution_service(
    trade_repo: TradeRepositoryDep,
    position_repo: PositionRepositoryDep,
    tradernet_client: TradernetClientDep,
    currency_exchange_service: Annotated[
        CurrencyExchangeService, Depends(get_currency_exchange_service_dep)
    ],
    exchange_rate_service: Annotated[
        ExchangeRateService, Depends(get_exchange_rate_service)
    ],
    settings_repo: SettingsRepositoryDep,
) -> TradeExecutionService:
    """Get TradeExecutionService instance."""
    stock_repo = get_stock_repository()
    return TradeExecutionService(
        trade_repo=trade_repo,
        position_repo=position_repo,
        stock_repo=stock_repo,
        tradernet_client=tradernet_client,
        currency_exchange_service=currency_exchange_service,
        exchange_rate_service=exchange_rate_service,
        settings_repo=settings_repo,
    )


def get_trade_safety_service(
    trade_repo: TradeRepositoryDep,
    position_repo: PositionRepositoryDep,
    stock_repo: StockRepositoryDep,
) -> TradeSafetyService:
    """Get TradeSafetyService instance."""
    return TradeSafetyService(
        trade_repo=trade_repo,
        position_repo=position_repo,
        stock_repo=stock_repo,
    )


# Type aliases for services
PortfolioServiceDep = Annotated[PortfolioService, Depends(get_portfolio_service)]
ScoringServiceDep = Annotated[ScoringService, Depends(get_scoring_service)]
SettingsServiceDep = Annotated[SettingsService, Depends(get_settings_service)]
RebalancingServiceDep = Annotated[RebalancingService, Depends(get_rebalancing_service)]
TradeExecutionServiceDep = Annotated[
    TradeExecutionService, Depends(get_trade_execution_service)
]
TradeSafetyServiceDep = Annotated[TradeSafetyService, Depends(get_trade_safety_service)]
CurrencyExchangeServiceDep = Annotated[
    CurrencyExchangeService, Depends(get_currency_exchange_service_dep)
]
ExchangeRateServiceDep = Annotated[
    ExchangeRateService, Depends(get_exchange_rate_service)
]
TickerContentServiceDep = Annotated[
    TickerContentService, Depends(get_ticker_content_service)
]


def get_concentration_alert_service(
    position_repo: PositionRepositoryDep,
) -> ConcentrationAlertService:
    """Get ConcentrationAlertService instance."""
    return ConcentrationAlertService(position_repo=position_repo)


ConcentrationAlertServiceDep = Annotated[
    ConcentrationAlertService, Depends(get_concentration_alert_service)
]


def get_stock_setup_service(
    stock_repo: StockRepositoryDep,
    scoring_service: ScoringServiceDep,
    tradernet_client: TradernetClientDep,
    db_manager: DatabaseManagerDep,
) -> StockSetupService:
    """Get StockSetupService instance."""
    # StockRepositoryDep is IStockRepository, but StockSetupService needs StockRepository
    # We can safely cast since get_stock_repository() returns StockRepository
    return StockSetupService(
        stock_repo=stock_repo,  # type: ignore[arg-type]
        scoring_service=scoring_service,
        tradernet_client=tradernet_client,
        db_manager=db_manager,
    )


StockSetupServiceDep = Annotated[StockSetupService, Depends(get_stock_setup_service)]
