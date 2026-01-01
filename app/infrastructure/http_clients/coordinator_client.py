"""HTTP Client for Coordinator Service."""

from app.infrastructure.http_clients.base import BaseHTTPClient
from services.coordinator.models import CreatePlanRequest, CreatePlanResponse


class CoordinatorHTTPClient(BaseHTTPClient):
    """HTTP client for Coordinator Service."""

    async def create_plan(self, request: CreatePlanRequest) -> CreatePlanResponse:
        """
        Create a holistic plan via coordinator orchestration.

        Args:
            request: Plan creation request

        Returns:
            Complete plan with execution statistics
        """
        response = await self.post(
            "/coordinator/create-plan",
            json=request.model_dump(),
            timeout=300.0,  # Full workflow can take up to 5 minutes
        )
        return CreatePlanResponse(**response.json())

    async def health_check(self) -> dict:
        """Check service health."""
        response = await self.get("/coordinator/health")
        return response.json()
