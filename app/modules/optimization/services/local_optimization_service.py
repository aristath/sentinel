"""Local (in-process) optimization service implementation."""

from typing import List

from app.modules.allocation.database.allocation_repository import AllocationRepository
from app.modules.optimization.services.optimization_service_interface import (
    AllocationTarget,
    OptimizationResult,
)
from app.modules.portfolio.database.position_repository import PositionRepository


class LocalOptimizationService:
    """
    Local optimization service implementation.

    Wraps existing domain logic for in-process execution.
    """

    def __init__(self):
        """Initialize local optimization service."""
        self.allocation_repo = AllocationRepository()
        self.position_repo = PositionRepository()

    async def optimize_allocation(
        self,
        targets: List[AllocationTarget],
        available_cash: float,
    ) -> OptimizationResult:
        """
        Optimize portfolio allocation.

        Args:
            targets: Target allocations
            available_cash: Available cash

        Returns:
            Optimization result
        """
        # Simple allocation optimization
        # Calculate suggested changes based on targets
        changes = []

        for target in targets:
            # Get current allocation
            current_allocation = self.allocation_repo.get_by_symbol(target.symbol)
            current_weight = (
                current_allocation.target_weight if current_allocation else 0.0
            )

            # Calculate weight diff
            weight_diff = target.target_weight - current_weight

            if abs(weight_diff) > 0.01:  # 1% threshold
                # Note: Dict values must be float per OptimizationResult interface
                changes.append(
                    {
                        "current_weight": current_weight,
                        "target_weight": target.target_weight,
                        "weight_change": weight_diff,
                    }
                )

        return OptimizationResult(
            success=True,
            message=f"Generated {len(changes)} allocation changes",
            recommended_changes=changes,
        )

    async def calculate_rebalancing(
        self,
        targets: List[AllocationTarget],
        available_cash: float,
    ) -> OptimizationResult:
        """
        Calculate optimal rebalancing.

        Args:
            targets: Target allocations
            available_cash: Available cash

        Returns:
            Rebalancing result
        """
        # Rebalancing uses same logic as optimization
        return await self.optimize_allocation(targets, available_cash)
