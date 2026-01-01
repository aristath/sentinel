"""Planner factory - creates appropriate planner for each bucket.

This factory orchestrates multi-bucket planning by:
1. Identifying all active buckets (core + satellites)
2. Generating separate plans for each bucket
3. Tagging plans with bucket_id for execution
4. Aggregating plans for presentation
"""

import logging
from typing import Optional

from app.domain.models import Position, Security
from app.modules.planning.domain.models import ActionCandidate
from app.modules.satellites.database.bucket_repository import BucketRepository
from app.modules.satellites.planning.satellite_planner_service import (
    SatellitePlannerService,
)
from app.modules.satellites.services.bucket_service import BucketService

logger = logging.getLogger(__name__)


class PlannerFactory:
    """Factory for creating bucket-specific planners."""

    def __init__(self):
        self.satellite_planner = SatellitePlannerService()
        self.bucket_service = BucketService()
        self.bucket_repo = BucketRepository()

    async def generate_plans_for_all_buckets(
        self,
        positions: list[Position],
        securities: list[Security],
        portfolio_context,
        current_prices: dict[str, float],
        transaction_cost_fixed: float = 2.0,
        transaction_cost_percent: float = 0.002,
        exchange_rate_service=None,
        recently_sold: Optional[set[str]] = None,
        trade_repo=None,
        settings_repo=None,
        max_steps: int = 10,
        target_weights: Optional[dict[str, float]] = None,
    ) -> dict[str, list[ActionCandidate]]:
        """Generate trading plans for all active buckets.

        Args:
            positions: All current positions
            securities: All available securities
            portfolio_context: Portfolio context for scoring
            current_prices: Current prices for all symbols
            transaction_cost_fixed: Fixed cost per trade (EUR)
            transaction_cost_percent: Variable cost as fraction
            exchange_rate_service: Service for currency conversion
            recently_sold: Set of recently sold symbols to avoid
            trade_repo: Trade repository for history
            settings_repo: Settings repository for parameters
            max_steps: Maximum number of actions in sequence per bucket
            target_weights: Optional target weights override

        Returns:
            Dict mapping bucket_id to list of ActionCandidate objects
        """
        plans = {}

        # Get all active buckets (core + satellites)
        all_buckets = await self.bucket_repo.get_all()
        active_buckets = [b for b in all_buckets if b.is_trading_allowed]

        logger.info(
            f"Generating plans for {len(active_buckets)} active buckets "
            f"(core + {len(active_buckets) - 1} satellites)"
        )

        for bucket in active_buckets:
            try:
                plan = await self.satellite_planner.generate_plan_for_bucket(
                    bucket_id=bucket.id,
                    positions=positions,
                    all_securities=securities,
                    portfolio_context=portfolio_context,
                    current_prices=current_prices,
                    transaction_cost_fixed=transaction_cost_fixed,
                    transaction_cost_percent=transaction_cost_percent,
                    exchange_rate_service=exchange_rate_service,
                    recently_sold=recently_sold,
                    trade_repo=trade_repo,
                    settings_repo=settings_repo,
                    max_steps=max_steps,
                    target_weights=target_weights,
                )

                if plan:
                    plans[bucket.id] = plan
                    logger.info(f"Generated plan for {bucket.id}: {len(plan)} actions")
                else:
                    logger.debug(f"No plan generated for {bucket.id}")

            except Exception as e:
                logger.error(
                    f"Error generating plan for bucket {bucket.id}: {e}",
                    exc_info=True,
                )
                # Continue with other buckets even if one fails

        total_actions = sum(len(p) for p in plans.values())
        logger.info(f"Generated {len(plans)} plans with {total_actions} total actions")

        return plans

    async def generate_plan_for_bucket(
        self,
        bucket_id: str,
        positions: list[Position],
        securities: list[Security],
        portfolio_context,
        current_prices: dict[str, float],
        transaction_cost_fixed: float = 2.0,
        transaction_cost_percent: float = 0.002,
        exchange_rate_service=None,
        recently_sold: Optional[set[str]] = None,
        trade_repo=None,
        settings_repo=None,
        max_steps: int = 10,
        target_weights: Optional[dict[str, float]] = None,
    ) -> Optional[list[ActionCandidate]]:
        """Generate trading plan for a specific bucket.

        This is a convenience method that delegates to SatellitePlannerService.

        Args:
            bucket_id: The bucket to plan for
            positions: All current positions
            securities: All available securities
            portfolio_context: Portfolio context for scoring
            current_prices: Current prices for all symbols
            transaction_cost_fixed: Fixed cost per trade (EUR)
            transaction_cost_percent: Variable cost as fraction
            exchange_rate_service: Service for currency conversion
            recently_sold: Set of recently sold symbols to avoid
            trade_repo: Trade repository for history
            settings_repo: Settings repository for parameters
            max_steps: Maximum number of actions in sequence
            target_weights: Optional target weights override

        Returns:
            List of ActionCandidate objects, or None if no plan
        """
        return await self.satellite_planner.generate_plan_for_bucket(
            bucket_id=bucket_id,
            positions=positions,
            all_securities=securities,
            portfolio_context=portfolio_context,
            current_prices=current_prices,
            transaction_cost_fixed=transaction_cost_fixed,
            transaction_cost_percent=transaction_cost_percent,
            exchange_rate_service=exchange_rate_service,
            recently_sold=recently_sold,
            trade_repo=trade_repo,
            settings_repo=settings_repo,
            max_steps=max_steps,
            target_weights=target_weights,
        )

    def aggregate_plans(
        self, plans: dict[str, list[ActionCandidate]]
    ) -> list[ActionCandidate]:
        """Aggregate plans from all buckets into a single prioritized list.

        Args:
            plans: Dict mapping bucket_id to list of ActionCandidate

        Returns:
            Flat list of all actions, sorted by priority descending
        """
        all_actions = []

        for bucket_id, plan in plans.items():
            # Tag each action with its bucket
            for action in plan:
                # Add bucket_id to tags
                tagged_action = ActionCandidate(
                    side=action.side,
                    symbol=action.symbol,
                    name=action.name,
                    quantity=action.quantity,
                    price=action.price,
                    value_eur=action.value_eur,
                    currency=action.currency,
                    priority=action.priority,
                    reason=f"[{bucket_id}] {action.reason}",
                    tags=action.tags + [f"bucket:{bucket_id}"],
                )
                all_actions.append(tagged_action)

        # Sort by priority descending
        all_actions.sort(key=lambda a: a.priority, reverse=True)

        return all_actions

    def get_highest_priority_action(
        self, plans: dict[str, list[ActionCandidate]]
    ) -> Optional[tuple[str, ActionCandidate]]:
        """Get the single highest priority action across all buckets.

        Args:
            plans: Dict mapping bucket_id to list of ActionCandidate

        Returns:
            Tuple of (bucket_id, ActionCandidate) or None if no actions
        """
        if not plans:
            return None

        best_bucket = None
        best_action = None
        best_priority = float("-inf")

        for bucket_id, plan in plans.items():
            if not plan:
                continue

            # Get highest priority action from this bucket
            bucket_best = max(plan, key=lambda a: a.priority)

            if bucket_best.priority > best_priority:
                best_priority = bucket_best.priority
                best_action = bucket_best
                best_bucket = bucket_id

        if best_bucket and best_action:
            return (best_bucket, best_action)

        return None
