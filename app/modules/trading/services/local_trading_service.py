"""Local (in-process) trading service implementation."""

import uuid
from typing import List

from app.core.database.manager import get_db_manager
from app.domain.services.settings_service import SettingsService
from app.domain.value_objects.trade_side import TradeSide
from app.infrastructure.external.tradernet import get_tradernet_client
from app.modules.portfolio.database.position_repository import PositionRepository
from app.modules.trading.services.trade_execution_service import TradeExecutionService
from app.modules.trading.services.trading_service_interface import (
    TradeRequest,
    TradeResult,
)
from app.modules.universe.database.security_repository import SecurityRepository
from app.repositories.settings import SettingsRepository
from app.repositories.trade import TradeRepository
from app.shared.services import CurrencyExchangeService


class LocalTradingService:
    """
    Local trading service implementation.

    Wraps existing domain logic for in-process execution.
    """

    def __init__(self):
        """Initialize local trading service."""
        # Create dependencies
        self.trade_repo = TradeRepository()
        self.position_repo = PositionRepository()
        self.security_repo = SecurityRepository()
        self.tradernet = get_tradernet_client()
        self.settings_repo = SettingsRepository()
        self.db_manager = get_db_manager()

        # Create services
        settings_service = SettingsService(settings_repo=self.settings_repo)
        currency_service = CurrencyExchangeService(tradernet_client=self.tradernet)
        exchange_rate_service = settings_service  # type: ignore[assignment]

        self.trade_execution_service = TradeExecutionService(
            trade_repo=self.trade_repo,
            position_repo=self.position_repo,
            security_repo=self.security_repo,
            tradernet_client=self.tradernet,
            currency_exchange_service=currency_service,
            exchange_rate_service=exchange_rate_service,
            settings_repo=self.settings_repo,
        )

    async def execute_trade(self, request: TradeRequest) -> TradeResult:
        """
        Execute a single trade.

        Args:
            request: Trade request

        Returns:
            Trade execution result
        """
        try:
            # Get security
            security = self.security_repo.get_by_symbol(request.symbol)
            if not security:
                return TradeResult(
                    trade_id=str(uuid.uuid4()),
                    success=False,
                    message=f"Security {request.symbol} not found",
                    executed_quantity=0.0,
                )

            # Convert side
            side = TradeSide.BUY if request.side == "BUY" else TradeSide.SELL

            # Execute trade using existing service
            result = await self.trade_execution_service.execute_trade(
                security=security,
                side=side,
                quantity=request.quantity,
            )

            if result.success:
                return TradeResult(
                    trade_id=str(uuid.uuid4()),
                    success=True,
                    message="Trade executed successfully",
                    executed_quantity=request.quantity,
                    executed_price=getattr(result, "executed_price", 0.0),
                )
            else:
                return TradeResult(
                    trade_id=str(uuid.uuid4()),
                    success=False,
                    message=result.error or "Trade failed",
                    executed_quantity=0.0,
                )

        except Exception as e:
            return TradeResult(
                trade_id=str(uuid.uuid4()),
                success=False,
                message=f"Trade execution error: {e}",
                executed_quantity=0.0,
            )

    async def batch_execute_trades(
        self, requests: List[TradeRequest]
    ) -> List[TradeResult]:
        """
        Execute multiple trades.

        Args:
            requests: List of trade requests

        Returns:
            List of trade results
        """
        results = []
        for req in requests:
            result = await self.execute_trade(req)
            results.append(result)
        return results
