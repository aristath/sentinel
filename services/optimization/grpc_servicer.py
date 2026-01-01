"""gRPC servicer implementation for Optimization service."""

from contracts import optimization_pb2, optimization_pb2_grpc  # type: ignore[attr-defined]
from app.modules.optimization.services.local_optimization_service import (
    LocalOptimizationService,
)
from app.modules.optimization.services.optimization_service_interface import (
    AllocationTarget,
)


class OptimizationServicer(optimization_pb2_grpc.OptimizationServiceServicer):
    """
    gRPC servicer for Optimization service.

    Implements the OptimizationService gRPC interface by delegating to LocalOptimizationService.
    """

    def __init__(self):
        """Initialize Optimization servicer."""
        self.local_service = LocalOptimizationService()

    async def OptimizeAllocation(
        self,
        request: optimization_pb2.OptimizeAllocationRequest,
        context,
    ) -> optimization_pb2.OptimizeAllocationResponse:
        """Optimize portfolio allocation."""
        # Calculate current weights from positions
        total_value = sum(
            float(p.market_value.amount) for p in request.current_positions
        )
        current_weights = {}
        if total_value > 0:
            for p in request.current_positions:
                weight = float(p.market_value.amount) / total_value
                current_weights[p.isin] = weight

        # Convert protobuf targets to domain targets
        targets = [
            AllocationTarget(
                isin=t.isin,
                symbol=t.symbol,
                target_weight=t.target_weight,
                current_weight=current_weights.get(t.isin, 0.0),
            )
            for t in request.target_allocations
        ]

        available_cash = float(request.available_cash.amount)

        result = await self.local_service.optimize_allocation(
            targets=targets,
            available_cash=available_cash,
        )

        # Convert domain result to protobuf
        grpc_changes = [
            optimization_pb2.AllocationChange(
                isin=change.get("isin", ""),
                symbol=change.get("symbol", ""),
                quantity_change=change.get("quantity_change", 0.0),
            )
            for change in result.recommended_changes
        ]

        return optimization_pb2.OptimizeAllocationResponse(
            success=result.success,
            changes=grpc_changes,
            objective_value=result.objective_value or 0.0,
            solver_status=result.message,
        )

    async def OptimizeExecution(
        self,
        request: optimization_pb2.OptimizeExecutionRequest,
        context,
    ) -> optimization_pb2.OptimizeExecutionResponse:
        """Optimize trade execution."""
        # Simple execution optimization: sort trades by priority
        # Full implementation would consider slippage, timing, etc.
        execution_plans = []

        for trade in request.trades:
            # Create execution plan for each trade
            plan = optimization_pb2.ExecutionPlan(
                trade_id=trade.isin + "_plan",
                isin=trade.isin,
                symbol=trade.symbol,
                total_quantity=trade.quantity,
                slice_count=1,  # Execute all at once for now
                estimated_slippage=0.001,  # 0.1% slippage estimate
            )
            execution_plans.append(plan)

        return optimization_pb2.OptimizeExecutionResponse(
            success=True,
            execution_plans=execution_plans,
        )

    async def CalculateRebalancing(
        self,
        request: optimization_pb2.CalculateRebalancingRequest,
        context,
    ) -> optimization_pb2.CalculateRebalancingResponse:
        """Calculate optimal rebalancing."""
        targets = [
            AllocationTarget(
                isin=t.isin,
                symbol=t.symbol,
                target_weight=t.target_weight,
                current_weight=0.0,
            )
            for t in request.target_allocations
        ]

        available_cash = float(request.available_cash.amount)

        result = await self.local_service.calculate_rebalancing(
            targets=targets,
            available_cash=available_cash,
        )

        grpc_changes = [
            optimization_pb2.AllocationChange(
                isin=change.get("isin", ""),
                symbol=change.get("symbol", ""),
                quantity_change=change.get("quantity_change", 0.0),
            )
            for change in result.recommended_changes
        ]

        return optimization_pb2.CalculateRebalancingResponse(
            needs_rebalancing=result.success,
            changes=grpc_changes,
            total_drift_pct=0.0,
        )

    async def HealthCheck(
        self,
        request: optimization_pb2.Empty,
        context,
    ) -> optimization_pb2.HealthCheckResponse:
        """Health check."""
        return optimization_pb2.HealthCheckResponse(
            healthy=True,
            version="1.0.0",
            status="OK",
        )
