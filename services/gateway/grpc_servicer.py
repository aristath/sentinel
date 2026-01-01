"""gRPC servicer implementation for Gateway service."""

from typing import AsyncIterator

from contracts import gateway_pb2, gateway_pb2_grpc  # type: ignore[attr-defined]
from contracts.common import common_pb2  # type: ignore[attr-defined]
from app.modules.gateway.services.local_gateway_service import LocalGatewayService


class GatewayServicer(gateway_pb2_grpc.GatewayServiceServicer):
    """
    gRPC servicer for Gateway service.

    Implements the GatewayService gRPC interface by delegating to LocalGatewayService.
    """

    def __init__(self):
        """Initialize Gateway servicer."""
        self.local_service = LocalGatewayService()

    async def GetSystemStatus(
        self,
        request: gateway_pb2.GetSystemStatusRequest,
        context,
    ) -> gateway_pb2.GetSystemStatusResponse:
        """Get overall system status."""
        status = await self.local_service.get_system_status()

        # Convert service statuses to protobuf
        grpc_services = [
            gateway_pb2.ServiceStatus(
                service_name=service["service_name"],
                healthy=service["healthy"],
                version=service.get("version", ""),
                status_message=service.get("status_message", ""),
            )
            for service in status.services
        ]

        return gateway_pb2.GetSystemStatusResponse(
            system_healthy=status.system_healthy,
            services=grpc_services,
            overall_message=status.overall_message,
        )

    async def TriggerTradingCycle(
        self,
        request: gateway_pb2.TriggerTradingCycleRequest,
        context,
    ) -> AsyncIterator[gateway_pb2.TradingCycleUpdate]:
        """Trigger a complete trading cycle (streaming)."""
        async for update in self.local_service.trigger_trading_cycle(
            force=request.force,
            deposit_amount=(
                float(request.deposit_amount.amount)
                if request.deposit_amount.amount
                else None
            ),
        ):
            grpc_update = gateway_pb2.TradingCycleUpdate(
                cycle_id=update.cycle_id,
                phase=update.phase,
                progress_pct=update.progress_pct,
                message=update.message,
                complete=update.complete,
                success=update.success,
                error=update.error or "",
            )

            # Add results if available
            if update.results:
                grpc_update.results.update(update.results)

            yield grpc_update

    async def ProcessDeposit(
        self,
        request: gateway_pb2.ProcessDepositRequest,
        context,
    ) -> gateway_pb2.ProcessDepositResponse:
        """Process a deposit."""
        amount = float(request.amount.amount)

        result = await self.local_service.process_deposit(
            account_id=request.account_id,
            amount=amount,
        )

        return gateway_pb2.ProcessDepositResponse(
            success=result.success,
            new_balance=common_pb2.Money(
                amount=str(result.new_balance), currency="USD"
            ),
            message=result.message,
        )

    async def GetServiceHealth(
        self,
        request: gateway_pb2.GetServiceHealthRequest,
        context,
    ) -> gateway_pb2.GetServiceHealthResponse:
        """Get health of a specific service."""
        # TODO: Implement specific service health check
        return gateway_pb2.GetServiceHealthResponse(
            found=False,
        )

    async def HealthCheck(
        self,
        request: gateway_pb2.Empty,
        context,
    ) -> gateway_pb2.HealthCheckResponse:
        """Health check."""
        return gateway_pb2.HealthCheckResponse(
            healthy=True,
            version="1.0.0",
            status="OK",
        )
