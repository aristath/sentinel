"""Backward compatibility adapter for the modular planner.

This module provides functions that match the old holistic_planner.py API
but internally use the new modular HolisticPlanner class. This allows
existing code to continue working without changes while using the new
modular architecture under the hood.
"""

import logging
from typing import Dict, List, Optional

from app.domain.models import Position, Security
from app.modules.planning.domain.config.factory import ModularPlannerFactory
from app.modules.planning.domain.holistic_planner import HolisticPlan
from app.modules.planning.domain.planner import HolisticPlanner
from app.modules.scoring.domain.models import PortfolioContext
from app.repositories import SettingsRepository, TradeRepository

logger = logging.getLogger(__name__)


async def create_holistic_plan_modular(
    portfolio_context: PortfolioContext,
    available_cash: float,
    securities: List[Security],
    positions: List[Position],
    exchange_rate_service=None,
    target_weights: Optional[Dict[str, float]] = None,
    current_prices: Optional[Dict[str, float]] = None,
    transaction_cost_fixed: float = 2.0,
    transaction_cost_percent: float = 0.002,
    max_plan_depth: int = 5,
    max_opportunities_per_category: int = 5,
    enable_combinatorial: bool = True,
    priority_threshold: float = 0.3,
    combinatorial_max_combinations_per_depth: int = 50,
    combinatorial_max_sells: int = 4,
    combinatorial_max_buys: int = 4,
    combinatorial_max_candidates: int = 12,
    beam_width: int = 10,
) -> HolisticPlan:
    """
    Create a holistic plan using the modular planner.

    This function has the same signature as the original create_holistic_plan()
    but uses the new modular HolisticPlanner class internally.

    Args:
        portfolio_context: Current portfolio state
        available_cash: Available cash in EUR
        securities: Available securities
        positions: Current positions
        exchange_rate_service: Optional exchange rate service
        target_weights: Optional dict from optimizer (symbol -> target weight)
        current_prices: Current prices (required if target_weights provided)
        transaction_cost_fixed: Fixed transaction cost in EUR
        transaction_cost_percent: Variable transaction cost as fraction
        max_plan_depth: Maximum sequence depth to test (default 5)
        max_opportunities_per_category: Max opportunities per category (default 5)
        enable_combinatorial: Enable combinatorial generation (default True)
        priority_threshold: Minimum priority for combinations (default 0.3)
        combinatorial_max_combinations_per_depth: Max combinations per depth
        combinatorial_max_sells: Max sells in combinatorial
        combinatorial_max_buys: Max buys in combinatorial
        combinatorial_max_candidates: Max candidates in combinatorial
        beam_width: Beam width for search

    Returns:
        HolisticPlan with the best sequence and end-state analysis
    """
    # Get repositories
    settings_repo = SettingsRepository()
    trade_repo = TradeRepository()

    # Load configuration
    # TODO: In future, this should load from bucket-specific config
    from pathlib import Path

    from app.modules.planning.domain.config.models import PlannerConfiguration

    config: PlannerConfiguration
    try:
        config_path = Path("config/planner/default.toml")
        if config_path.exists():
            factory = ModularPlannerFactory.from_config_file(config_path)
            if factory.config is None:
                raise ValueError("Factory failed to load configuration")
            config = factory.config
        else:
            # Fallback to creating config from parameters
            config = PlannerConfiguration(
                name="dynamic",
                description="Dynamically created from function parameters",
                max_depth=max_plan_depth,
                max_opportunities_per_category=max_opportunities_per_category,
                priority_threshold=priority_threshold,
                enable_diverse_selection=True,
                diversity_weight=0.3,
                transaction_cost_fixed=transaction_cost_fixed,
                transaction_cost_percent=transaction_cost_percent,
                allow_sell=True,
                allow_buy=True,
            )
    except Exception as e:
        logger.warning(f"Failed to load config, creating default: {e}", exc_info=True)
        config = PlannerConfiguration(
            max_depth=max_plan_depth,
            max_opportunities_per_category=max_opportunities_per_category,
            priority_threshold=priority_threshold,
            transaction_cost_fixed=transaction_cost_fixed,
            transaction_cost_percent=transaction_cost_percent,
        )

    # Create planner instance
    planner = HolisticPlanner(
        config=config,
        settings_repo=settings_repo,
        trade_repo=trade_repo,
        metrics_cache=None,  # TODO: Add metrics cache support
        risk_profile=None,  # TODO: Add risk profile support
    )

    # Create plan using modular planner
    plan = await planner.create_plan(
        portfolio_context=portfolio_context,
        positions=positions,
        securities=securities,
        available_cash=available_cash,
        current_prices=current_prices or {},
        target_weights=target_weights,
        exchange_rate_service=exchange_rate_service,
    )

    return plan


# Alias for drop-in replacement
async def create_holistic_plan_modular_replacement(*args, **kwargs) -> HolisticPlan:
    """
    Drop-in replacement for create_holistic_plan().

    Use this to test the modular planner without changing existing code:

    Before:
        from app.modules.planning.domain.holistic_planner import create_holistic_plan
        plan = await create_holistic_plan(...)

    After (testing):
        from app.modules.planning.domain.planner_adapter import (
            create_holistic_plan_modular_replacement as create_holistic_plan
        )
        plan = await create_holistic_plan(...)
    """
    return await create_holistic_plan_modular(*args, **kwargs)
