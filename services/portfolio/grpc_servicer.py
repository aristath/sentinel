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
        # Get all positions and filter for the requested symbol
        positions = await self.local_service.get_positions(account_id=request.account_id)

        matching_pos = None
        for pos in positions:
            if pos.symbol == request.symbol or (
                request.isin and pos.isin == request.isin
            ):
                matching_pos = pos
                break

        if matching_pos:
            grpc_position = portfolio_pb2.Position(
                symbol=matching_pos.symbol,
                isin=matching_pos.isin or "",
                quantity=matching_pos.quantity,
                average_price=common_pb2.Money(
                    amount=str(matching_pos.average_price), currency="USD"
                ),
                current_price=common_pb2.Money(
                    amount=str(matching_pos.current_price or matching_pos.average_price),
                    currency="USD",
                ),
                market_value=common_pb2.Money(
                    amount=str(matching_pos.market_value or 0.0), currency="USD"
                ),
                unrealized_pnl=common_pb2.Money(
                    amount=str(matching_pos.unrealized_pnl or 0.0), currency="USD"
                ),
            )

            return portfolio_pb2.GetPositionResponse(found=True, position=grpc_position)
        else:
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
        # Get current portfolio summary for performance data
        summary = await self.local_service.get_summary(account_id=request.account_id)

        # Create basic performance history entry for current state
        # In a full implementation, would query historical data from database
        history_entry = portfolio_pb2.PerformanceDataPoint(
            date=common_pb2.Timestamp(seconds=int(summary.last_updated.timestamp())),
            portfolio_value=common_pb2.Money(
                amount=str(summary.total_value), currency="USD"
            ),
            cash_balance=common_pb2.Money(
                amount=str(summary.cash_balance), currency="USD"
            ),
            total_pnl=common_pb2.Money(amount=str(summary.total_pnl), currency="USD"),
            daily_return_pct=0.0,  # Would calculate from historical data
            cumulative_return_pct=0.0,  # Would calculate from historical data
        )

        return portfolio_pb2.GetPerformanceResponse(
            history=[history_entry],
        )

    async def UpdatePositions(
        self,
        request: portfolio_pb2.UpdatePositionsRequest,
        context,
    ) -> portfolio_pb2.UpdatePositionsResponse:
        """Update positions (sync from broker)."""
        # Get current positions before sync
        positions_before = await self.local_service.get_positions(
            account_id=request.account_id
        )

        # In a full implementation, would trigger broker sync here
        # For now, get current positions (which may have been synced by background task)
        positions_after = await self.local_service.get_positions(
            account_id=request.account_id
        )

        # Calculate changes (simplified - full implementation would track actual changes)
        positions_updated = len(positions_after)
        positions_added = max(0, len(positions_after) - len(positions_before))
        positions_removed = max(0, len(positions_before) - len(positions_after))

        return portfolio_pb2.UpdatePositionsResponse(
            success=True,
            positions_updated=positions_updated,
            positions_added=positions_added,
            positions_removed=positions_removed,
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
