"""API routes for Coordinator Service."""

from fastapi import APIRouter, Depends

from app.modules.planning.services.local_coordinator_service import (
    LocalCoordinatorService,
)
from services.coordinator.dependencies import get_coordinator_service
from services.coordinator.models import (
    CreatePlanRequest,
    CreatePlanResponse,
    HealthResponse,
)

router = APIRouter()


@router.post("/create-plan", response_model=CreatePlanResponse)
async def create_plan(
    request: CreatePlanRequest,
    service: LocalCoordinatorService = Depends(get_coordinator_service),
):
    """
    Create a holistic plan by orchestrating microservices.

    Workflow:
    1. Call Opportunity Service to identify trading opportunities
    2. Stream sequences from Generator Service in batches
    3. Distribute batches to Evaluator instances (round-robin)
    4. Aggregate results in global beam
    5. Build final plan from best sequence

    Returns plan with execution statistics.
    """
    result = await service.create_plan(request)
    return result


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    return HealthResponse(
        healthy=True,
        version="1.0.0",
        status="OK",
        checks={},
    )
