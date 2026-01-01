"""gRPC servicer implementation for Portfolio service."""

from contracts import portfolio_pb2, portfolio_pb2_grpc  # type: ignore[attr-defined]
from contracts.common import common_pb2  # type: ignore[attr-defined]
from app.modules.portfolio.services.local_portfolio_service import (
    LocalPortfolioService,
)


class PortfolioServicer(portfolio_pb2_grpc.PortfolioServiceServicer):
    """
    gRPC servicer for Portfolio service.

    Implements the PortfolioService gRPC interface by delegating to LocalPortfolioService.
    """

    def __init__(self):
        """Initialize Portfolio servicer."""
        self.local_service = LocalPortfolioService()

    async def GetPositions(
        self,
        request: portfolio_pb2.GetPositionsRequest,
        context,
    ) -> portfolio_pb2.GetPositionsResponse:
        """Get current portfolio positions."""
        positions = await self.local_service.get_positions(
            account_id=request.account_id
        )

        grpc_positions = [
            portfolio_pb2.Position(
                symbol=pos.symbol,
                isin=pos.isin,
                quantity=pos.quantity,
                average_price=common_pb2.Money(
                    amount=str(pos.average_price), currency="USD"
                ),
                current_price=common_pb2.Money(
                    amount=str(pos.current_price), currency="USD"
                ),
                market_value=common_pb2.Money(
                    amount=str(pos.market_value), currency="USD"
                ),
                unrealized_pnl=common_pb2.Money(
                    amount=str(pos.unrealized_pnl), currency="USD"
                ),
            )
            for pos in positions
        ]

        return portfolio_pb2.GetPositionsResponse(
            positions=grpc_positions,
            total_positions=len(positions),
        )

    async def GetPosition(
        self,
        request: portfolio_pb2.GetPositionRequest,
        context,
    ) -> portfolio_pb2.GetPositionResponse:
        """Get a specific position."""
        # TODO: Implement get single position
        return portfolio_pb2.GetPositionResponse(found=False)

    async def GetSummary(
        self,
        request: portfolio_pb2.GetSummaryRequest,
        context,
    ) -> portfolio_pb2.GetSummaryResponse:
        """Get portfolio summary."""
        summary = await self.local_service.get_summary(account_id=request.account_id)

        return portfolio_pb2.GetSummaryResponse(
            portfolio_hash=summary.portfolio_hash,
            total_value=common_pb2.Money(amount=str(summary.total_value), currency="USD"),
            total_cost=common_pb2.Money(amount="0", currency="USD"),
            total_pnl=common_pb2.Money(amount=str(summary.total_pnl), currency="USD"),
            cash_balance=common_pb2.Money(
                amount=str(summary.cash_balance), currency="USD"
            ),
            position_count=summary.position_count,
        )

    async def GetPerformance(
        self,
        request: portfolio_pb2.GetPerformanceRequest,
        context,
    ) -> portfolio_pb2.GetPerformanceResponse:
        """Get portfolio performance."""
        # TODO: Implement performance metrics
        return portfolio_pb2.GetPerformanceResponse(
            history=[],
        )

    async def UpdatePositions(
        self,
        request: portfolio_pb2.UpdatePositionsRequest,
        context,
    ) -> portfolio_pb2.UpdatePositionsResponse:
        """Update positions (sync from broker)."""
        # TODO: Implement position update
        return portfolio_pb2.UpdatePositionsResponse(
            success=True,
            positions_updated=0,
            positions_added=0,
            positions_removed=0,
        )

    async def GetCashBalance(
        self,
        request: portfolio_pb2.GetCashBalanceRequest,
        context,
    ) -> portfolio_pb2.GetCashBalanceResponse:
        """Get cash balance."""
        balance = await self.local_service.get_cash_balance(
            account_id=request.account_id
        )

        return portfolio_pb2.GetCashBalanceResponse(
            cash_balance=common_pb2.Money(amount=str(balance), currency="USD"),
            pending_deposits=common_pb2.Money(amount="0", currency="USD"),
            pending_withdrawals=common_pb2.Money(amount="0", currency="USD"),
            available_for_trading=common_pb2.Money(amount=str(balance), currency="USD"),
        )

    async def HealthCheck(
        self,
        request: portfolio_pb2.Empty,
        context,
    ) -> portfolio_pb2.HealthCheckResponse:
        """Health check."""
        return portfolio_pb2.HealthCheckResponse(
            healthy=True,
            version="1.0.0",
            status="OK",
        )
