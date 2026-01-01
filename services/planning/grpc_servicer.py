"""gRPC servicer implementation for Planning service."""

from typing import AsyncIterator

from contracts import planning_pb2, planning_pb2_grpc  # type: ignore[attr-defined]
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
        domain_request = PlanRequest(
            portfolio_hash=request.portfolio_hash,
            available_cash=float(request.available_cash.amount),
            securities=[],  # TODO: Convert protobuf positions
            positions=[],  # TODO: Convert protobuf positions
            target_weights=None,
            parameters={},
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

            # TODO: Convert plan if present
            # if update.plan:
            #     grpc_update.plan = convert_plan_to_proto(update.plan)

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
            # TODO: Convert plan to protobuf
            return planning_pb2.GetPlanResponse(
                found=True,
                # plan=convert_plan_to_proto(plan),
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
        # TODO: Implement list plans
        return planning_pb2.ListPlansResponse(plans=[], total=0)

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
        plan = await self.local_service.get_plan(request.portfolio_hash)

        if plan:
            return planning_pb2.GetBestResultResponse(
                found=True,
                # plan=convert_plan_to_proto(plan),
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
