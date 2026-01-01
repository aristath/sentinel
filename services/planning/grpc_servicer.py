"""gRPC servicer implementation for Planning service."""

from typing import AsyncIterator

from contracts import planning_pb2, planning_pb2_grpc  # type: ignore[attr-defined]
from app.infrastructure.grpc_helpers.protobuf_converters import (
    holistic_plan_to_proto,
    proto_list_to_positions,
    proto_list_to_securities,
)
from app.modules.planning.services.local_planning_service import LocalPlanningService
from app.modules.planning.services.planning_service_interface import (
    PlanRequest,
)


class PlanningServicer(planning_pb2_grpc.PlanningServiceServicer):
    """
    gRPC servicer for Planning service.

    Implements the PlanningService gRPC interface by delegating to LocalPlanningService.
    """

    def __init__(self):
        """Initialize Planning servicer."""
        self.local_service = LocalPlanningService()

    async def CreatePlan(
        self,
        request: planning_pb2.CreatePlanRequest,
        context,
    ) -> AsyncIterator[planning_pb2.PlanUpdate]:
        """
        Create a new portfolio plan.

        Args:
            request: CreatePlanRequest protobuf
            context: gRPC context

        Yields:
            PlanUpdate protobuf messages
        """
        # Convert protobuf request to domain request
        positions = proto_list_to_positions(list(request.positions))

        # Build securities list from positions (simplified - in real implementation
        # would fetch from universe service)
        securities = []

        # Extract target weights from constraints if provided
        target_weights = None
        if request.constraints:
            # Parse constraints for target weights
            # Format: {"target_SYMBOL": "0.15", ...}
            target_weights = {}
            for key, value in request.constraints.items():
                if key.startswith("target_"):
                    symbol = key.replace("target_", "")
                    target_weights[symbol] = float(value)

        domain_request = PlanRequest(
            portfolio_hash=request.portfolio_hash,
            available_cash=float(request.available_cash.amount),
            securities=securities,
            positions=positions,
            target_weights=target_weights,
            parameters=dict(request.constraints) if request.constraints else {},
        )

        # Call local service and stream updates
        async for update in self.local_service.create_plan(domain_request):
            # Convert domain update to protobuf
            grpc_update = planning_pb2.PlanUpdate(
                plan_id=update.plan_id,
                progress_pct=update.progress_pct,
                current_step=update.current_step,
                complete=update.complete,
                error=update.error if update.error else "",
            )

            # Convert plan if present
            if update.plan:
                grpc_update.plan.CopyFrom(holistic_plan_to_proto(update.plan))

            yield grpc_update

    async def GetPlan(
        self,
        request: planning_pb2.GetPlanRequest,
        context,
    ) -> planning_pb2.GetPlanResponse:
        """
        Get an existing plan.

        Args:
            request: GetPlanRequest protobuf
            context: gRPC context

        Returns:
            GetPlanResponse protobuf
        """
        plan = await self.local_service.get_plan(request.plan_id)

        if plan:
            return planning_pb2.GetPlanResponse(
                found=True,
                plan=holistic_plan_to_proto(plan),
            )
        else:
            return planning_pb2.GetPlanResponse(found=False)

    async def ListPlans(
        self,
        request: planning_pb2.ListPlansRequest,
        context,
    ) -> planning_pb2.ListPlansResponse:
        """
        List all plans for a portfolio.

        Args:
            request: ListPlansRequest protobuf
            context: gRPC context

        Returns:
            ListPlansResponse protobuf
        """
        # Get plans from repository
        plans = await self.local_service.planner_repo.get_plans_for_portfolio(
            request.portfolio_hash,
            limit=request.limit if request.limit > 0 else 100,
            offset=request.offset if request.offset > 0 else 0,
        )

        # Convert to protobuf
        proto_plans = [holistic_plan_to_proto(plan) for plan in plans]

        return planning_pb2.ListPlansResponse(plans=proto_plans, total=len(plans))

    async def GetBestResult(
        self,
        request: planning_pb2.GetBestResultRequest,
        context,
    ) -> planning_pb2.GetBestResultResponse:
        """
        Get best result for a portfolio.

        Args:
            request: GetBestResultRequest protobuf
            context: gRPC context

        Returns:
            GetBestResultResponse protobuf
        """
        # Get best plan for portfolio from repository
        plans = await self.local_service.planner_repo.get_plans_for_portfolio(
            request.portfolio_hash,
            limit=1,
            offset=0,
        )

        if plans:
            best_plan = plans[0]  # Already sorted by score
            return planning_pb2.GetBestResultResponse(
                found=True,
                plan=holistic_plan_to_proto(best_plan),
            )
        else:
            return planning_pb2.GetBestResultResponse(found=False)

    async def HealthCheck(
        self,
        request: planning_pb2.Empty,
        context,
    ) -> planning_pb2.HealthCheckResponse:
        """
        Health check.

        Args:
            request: Empty protobuf
            context: gRPC context

        Returns:
            HealthCheckResponse protobuf
        """
        return planning_pb2.HealthCheckResponse(
            healthy=True,
            version="1.0.0",
            status="OK",
        )
