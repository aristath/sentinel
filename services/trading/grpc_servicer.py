"""gRPC servicer implementation for Trading service."""

from contracts import trading_pb2, trading_pb2_grpc  # type: ignore[attr-defined]
from contracts.common import common_pb2  # type: ignore[attr-defined]
from app.modules.trading.services.local_trading_service import LocalTradingService
from app.modules.trading.services.trading_service_interface import (
    TradeRequest,
)


class TradingServicer(trading_pb2_grpc.TradingServiceServicer):
    """
    gRPC servicer for Trading service.

    Implements the TradingService gRPC interface by delegating to LocalTradingService.
    """

    def __init__(self):
        """Initialize Trading servicer."""
        self.local_service = LocalTradingService()

    async def ExecuteTrade(
        self,
        request: trading_pb2.ExecuteTradeRequest,
        context,
    ) -> trading_pb2.ExecuteTradeResponse:
        """Execute a single trade."""
        # Map protobuf side to domain side
        side_map = {
            trading_pb2.BUY: "BUY",
            trading_pb2.SELL: "SELL",
        }

        domain_request = TradeRequest(
            account_id=request.account_id,
            isin=request.isin,
            symbol=request.symbol,
            side=side_map.get(request.side, "BUY"),
            quantity=request.quantity,
            limit_price=float(request.limit_price.amount)
            if request.limit_price.amount
            else None,
        )

        result = await self.local_service.execute_trade(domain_request)

        execution = None
        if result.executed_quantity > 0:
            execution = trading_pb2.TradeExecution(
                trade_id=result.trade_id,
                isin=request.isin,
                symbol=request.symbol,
                side=request.side,
                quantity_requested=request.quantity,
                quantity_filled=result.executed_quantity,
                average_price=common_pb2.Money(
                    amount=str(result.executed_price or 0), currency="USD"
                ),
            )

        return trading_pb2.ExecuteTradeResponse(
            success=result.success,
            trade_id=result.trade_id,
            status=trading_pb2.EXECUTED if result.success else trading_pb2.FAILED,
            message=result.message,
            execution=execution,
        )

    async def BatchExecuteTrades(
        self,
        request: trading_pb2.BatchExecuteTradesRequest,
        context,
    ) -> trading_pb2.BatchExecuteTradesResponse:
        """Execute multiple trades."""
        # Convert protobuf requests to domain requests
        side_map = {
            trading_pb2.BUY: "BUY",
            trading_pb2.SELL: "SELL",
        }

        domain_requests = [
            TradeRequest(
                account_id=trade.account_id,
                isin=trade.isin,
                symbol=trade.symbol,
                side=side_map.get(trade.side, "BUY"),
                quantity=trade.quantity,
            )
            for trade in request.trades
        ]

        results = await self.local_service.batch_execute_trades(domain_requests)

        grpc_results = [
            trading_pb2.ExecuteTradeResponse(
                success=result.success,
                trade_id=result.trade_id,
                message=result.message,
            )
            for result in results
        ]

        successful = sum(1 for r in results if r.success)

        return trading_pb2.BatchExecuteTradesResponse(
            all_success=successful == len(results),
            results=grpc_results,
            successful=successful,
            failed=len(results) - successful,
        )

    async def GetTradeStatus(
        self,
        request: trading_pb2.GetTradeStatusRequest,
        context,
    ) -> trading_pb2.GetTradeStatusResponse:
        """Get trade status."""
        # In full implementation, would query trade status from database/broker
        # For now, return not found (trades are executed immediately in current implementation)
        return trading_pb2.GetTradeStatusResponse(
            found=False,
            status=trading_pb2.UNKNOWN,
            message="Trade status tracking not yet implemented",
        )

    async def GetTradeHistory(
        self,
        request: trading_pb2.GetTradeHistoryRequest,
        context,
    ) -> trading_pb2.GetTradeHistoryResponse:
        """Get trade history."""
        # Get trade history from local service
        # In full implementation, would have pagination and filtering
        history = await self.local_service.get_trade_history(
            account_id=request.account_id,
            limit=request.limit if request.limit > 0 else 100,
        )

        # Convert to protobuf
        grpc_executions = [
            trading_pb2.TradeExecution(
                trade_id=str(trade.id) if trade.id else "",
                isin=trade.isin or "",
                symbol=trade.symbol,
                side=trading_pb2.BUY if trade.side == "BUY" else trading_pb2.SELL,
                quantity_requested=trade.quantity,
                quantity_filled=trade.quantity,
                average_price=common_pb2.Money(amount=str(trade.price), currency="USD"),
            )
            for trade in history
        ]

        return trading_pb2.GetTradeHistoryResponse(
            executions=grpc_executions,
            total=len(history),
        )

    async def CancelTrade(
        self,
        request: trading_pb2.CancelTradeRequest,
        context,
    ) -> trading_pb2.CancelTradeResponse:
        """Cancel a pending trade."""
        # Current implementation executes trades immediately, so cancellation not applicable
        # In full implementation with pending orders, would call broker API to cancel
        return trading_pb2.CancelTradeResponse(
            success=False,
            message="Trade cancellation not supported - trades execute immediately",
        )

    async def ValidateTrade(
        self,
        request: trading_pb2.ValidateTradeRequest,
        context,
    ) -> trading_pb2.ValidateTradeResponse:
        """Validate trade (pre-execution check)."""
        errors = []
        warnings = []

        # Basic validation
        if request.quantity <= 0:
            errors.append("Quantity must be positive")

        if not request.symbol and not request.isin:
            errors.append("Either symbol or ISIN must be provided")

        # Check if sufficient cash (simplified - full implementation would check actual balance)
        if request.side == trading_pb2.BUY:
            estimated_cost = request.quantity * float(
                request.limit_price.amount if request.limit_price.amount else 0
            )
            if estimated_cost > 10000:  # Placeholder limit
                warnings.append("Trade value exceeds typical limit")

        return trading_pb2.ValidateTradeResponse(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
        )

    async def HealthCheck(
        self,
        request: trading_pb2.Empty,
        context,
    ) -> trading_pb2.HealthCheckResponse:
        """Health check."""
        return trading_pb2.HealthCheckResponse(
            healthy=True,
            version="1.0.0",
            status="OK",
        )
