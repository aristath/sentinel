"""Local (in-process) planning service implementation."""

import uuid
from typing import AsyncIterator, Optional

from app.domain.models import Position, Security
from app.modules.planning.database.planner_repository import PlannerRepository
from app.modules.planning.domain.holistic_planner import (
    HolisticPlan,
    create_holistic_plan,
)
from app.modules.planning.services.planning_service_interface import (
    PlanRequest,
    PlanUpdate,
)
from app.modules.scoring.domain.models import PortfolioContext


class LocalPlanningService:
    """
    Local planning service implementation.

    Wraps existing domain logic for in-process execution.
    """

    def __init__(
        self,
        planner_repo: Optional[PlannerRepository] = None,
    ):
        """
        Initialize local planning service.

        Args:
            planner_repo: Planner repository for persistence
        """
        self.planner_repo = planner_repo or PlannerRepository()

    async def create_plan(self, request: PlanRequest) -> AsyncIterator[PlanUpdate]:
        """
        Create a new portfolio plan.

        Args:
            request: Planning request

        Yields:
            Progress updates
        """
        plan_id = str(uuid.uuid4())

        # Yield initial progress
        yield PlanUpdate(
            plan_id=plan_id,
            progress_pct=0,
            current_step="Initializing plan",
            complete=False,
        )

        try:
            # Build PortfolioContext from request
            # Note: request.securities and request.positions are already
            # domain objects from the caller
            securities: list[Security] = request.securities  # type: ignore[assignment]
            positions: list[Position] = request.positions  # type: ignore[assignment]

            # Build position values for portfolio context
            position_values = {p.symbol: (p.market_value_eur or 0.0) for p in positions}
            total_value = sum(position_values.values()) + request.available_cash

            # Build basic portfolio context
            # In a full implementation, this would include country/industry analysis
            portfolio_context = PortfolioContext(
                country_weights={},  # Simplified - would calculate from positions
                industry_weights={},  # Simplified - would calculate from positions
                positions=position_values,
                total_value=total_value,
            )

            yield PlanUpdate(
                plan_id=plan_id,
                progress_pct=20,
                current_step="Building portfolio context",
                complete=False,
            )

            # Create holistic plan using domain logic
            yield PlanUpdate(
                plan_id=plan_id,
                progress_pct=40,
                current_step="Generating plan candidates",
                complete=False,
            )

            plan = await create_holistic_plan(
                portfolio_context=portfolio_context,
                available_cash=request.available_cash,
                securities=securities,
                positions=positions,
                target_weights=request.target_weights,
                **request.parameters if request.parameters else {},
            )

            yield PlanUpdate(
                plan_id=plan_id,
                progress_pct=80,
                current_step="Evaluating sequences",
                complete=False,
            )

            # Note: Simplified local implementation doesn't persist plans
            # In production, would save to database here

            # Yield completion
            yield PlanUpdate(
                plan_id=plan_id,
                progress_pct=100,
                current_step="Plan complete",
                complete=True,
                plan=plan,
            )

        except Exception as e:
            # Yield error
            yield PlanUpdate(
                plan_id=plan_id,
                progress_pct=100,
                current_step="Plan failed",
                complete=True,
                error=str(e),
            )

    async def get_plan(self, portfolio_hash: str) -> Optional[HolisticPlan]:
        """
        Get an existing plan.

        Args:
            portfolio_hash: Portfolio identifier

        Returns:
            Plan if found, None otherwise
        """
        # Simplified local implementation - doesn't persist plans
        # Would retrieve from database in production
        return None
