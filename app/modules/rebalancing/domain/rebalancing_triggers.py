"""Event-driven rebalancing trigger checker.

Checks if portfolio conditions warrant rebalancing outside of scheduled intervals.
"""

import logging
from typing import Dict, List, Optional

from app.modules.portfolio.domain.models import Position
from app.domain.repositories.protocols import ISettingsRepository
from app.repositories import SettingsRepository

logger = logging.getLogger(__name__)


async def check_rebalance_triggers(
    positions: List[Position],
    target_allocations: Dict[str, float],
    total_portfolio_value: float,
    cash_balance: float,
    settings_repo: Optional[ISettingsRepository] = None,
) -> tuple[bool, str]:
    """
    Check if event-driven rebalancing should be triggered.

    Triggers rebalancing when:
    1. Position drift: Any position has drifted >= threshold from target allocation
    2. Cash accumulation: Cash >= threshold_multiplier × min_trade_size

    Args:
        positions: Current portfolio positions
        target_allocations: Target allocation weights per symbol (0.0 to 1.0)
        total_portfolio_value: Total portfolio value in EUR (positions + cash)
        cash_balance: Available cash in EUR
        settings_repo: Optional settings repository (creates if not provided)

    Returns:
        Tuple of (should_rebalance: bool, reason: str)
    """
    if settings_repo is None:
        settings_repo = SettingsRepository()

    # Check if event-driven rebalancing is enabled
    enabled = await settings_repo.get_float("event_driven_rebalancing_enabled", 1.0)
    if enabled == 0.0:
        return False, "event-driven rebalancing disabled"

    # Check position drift
    drift_triggered, drift_reason = await _check_position_drift(
        positions=positions,
        target_allocations=target_allocations,
        total_portfolio_value=total_portfolio_value,
        settings_repo=settings_repo,
    )

    if drift_triggered:
        return True, drift_reason

    # Check cash accumulation
    cash_triggered, cash_reason = await _check_cash_accumulation(
        cash_balance=cash_balance,
        settings_repo=settings_repo,
    )

    if cash_triggered:
        return True, cash_reason

    return False, "no triggers met"


async def _check_position_drift(
    positions: List[Position],
    target_allocations: Dict[str, float],
    total_portfolio_value: float,
    settings_repo: ISettingsRepository,
) -> tuple[bool, str]:
    """
    Check if any position has drifted significantly from target allocation.

    Args:
        positions: Current portfolio positions
        target_allocations: Target allocation weights per symbol
        total_portfolio_value: Total portfolio value in EUR
        settings_repo: Settings repository

    Returns:
        Tuple of (triggered: bool, reason: str)
    """
    if not positions or total_portfolio_value <= 0:
        return False, "no positions or zero portfolio value"

    if not target_allocations:
        # No target allocations provided, skip drift check
        return False, "no target allocations provided"

    # Get drift threshold from settings
    drift_threshold = await settings_repo.get_float(
        "rebalance_position_drift_threshold", 0.05
    )

    # Check each position for drift
    for position in positions:
        if position.market_value_eur is None or position.market_value_eur <= 0:
            continue

        # Calculate current allocation weight
        current_weight = position.market_value_eur / total_portfolio_value

        # Get target allocation (default to 0 if not specified)
        target_weight = target_allocations.get(position.symbol, 0.0)

        # Calculate absolute drift
        drift = abs(current_weight - target_weight)

        if drift >= drift_threshold:
            logger.info(
                f"Position drift detected: {position.symbol} "
                f"current={current_weight:.1%}, target={target_weight:.1%}, "
                f"drift={drift:.1%} (threshold={drift_threshold:.1%})"
            )
            return True, (
                f"position drift: {position.symbol} "
                f"drifted {drift:.1%} from target (threshold: {drift_threshold:.1%})"
            )

    return False, "no position drift detected"


async def _check_cash_accumulation(
    cash_balance: float,
    settings_repo: ISettingsRepository,
) -> tuple[bool, str]:
    """
    Check if cash has accumulated above threshold.

    Args:
        cash_balance: Available cash in EUR
        settings_repo: Settings repository

    Returns:
        Tuple of (triggered: bool, reason: str)
    """
    if cash_balance <= 0:
        return False, "no cash available"

    # Get settings
    threshold_multiplier = await settings_repo.get_float(
        "rebalance_cash_threshold_multiplier", 2.0
    )
    transaction_cost_fixed = await settings_repo.get_float(
        "transaction_cost_fixed", 2.0
    )
    transaction_cost_percent = await settings_repo.get_float(
        "transaction_cost_percent", 0.002
    )

    # Calculate min_trade_size using same logic as rebalancing service
    from app.application.services.rebalancing_service import calculate_min_trade_amount

    min_trade_size = calculate_min_trade_amount(
        transaction_cost_fixed=transaction_cost_fixed,
        transaction_cost_percent=transaction_cost_percent,
    )

    # Calculate threshold
    cash_threshold = threshold_multiplier * min_trade_size

    if cash_balance >= cash_threshold:
        logger.info(
            f"Cash accumulation detected: €{cash_balance:.2f} "
            f">= €{cash_threshold:.2f} (threshold: {threshold_multiplier}x min_trade)"
        )
        return True, (
            f"cash accumulation: €{cash_balance:.2f} "
            f">= €{cash_threshold:.2f} (threshold: {threshold_multiplier}x min_trade)"
        )

    return False, "cash below threshold"
