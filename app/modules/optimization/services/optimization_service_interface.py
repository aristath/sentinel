"""Optimization service interface."""

from dataclasses import dataclass
from typing import Dict, List, Optional, Protocol


@dataclass
class AllocationTarget:
    """Target allocation for optimization."""

    isin: str
    symbol: str
    target_weight: float
    current_weight: float


@dataclass
class OptimizationResult:
    """Result of portfolio optimization."""

    success: bool
    message: str
    recommended_changes: List[Dict[str, float]]
    objective_value: Optional[float] = None


class OptimizationServiceInterface(Protocol):
    """Optimization service interface."""

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
        ...

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
        ...
