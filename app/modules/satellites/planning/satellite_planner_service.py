"""Satellite planner service - generates trading plans for individual satellites.

This service wraps the existing holistic planner but applies satellite-specific logic:
1. Filters securities to satellite's universe (bucket_id)
2. Applies satellite-specific trading parameters (from settings)
3. Scales position sizes based on aggression level
4. Respects satellite cash balances (not total portfolio cash)
"""

import logging
from typing import Optional

from app.core.database.manager import get_db_manager
from app.domain.models import Position, Security
from app.domain.services.exchange_rate_service import ExchangeRateService
from app.modules.planning.domain.holistic_planner import (
    ActionCandidate,
    create_holistic_plan,
)
from app.modules.satellites.domain.aggression_calculator import (
    calculate_aggression,
    scale_position_size,
)
from app.modules.satellites.domain.parameter_mapper import map_settings_to_parameters
from app.modules.satellites.services.balance_service import BalanceService
from app.modules.satellites.services.bucket_service import BucketService
from app.repositories import SecurityRepository

logger = logging.getLogger(__name__)


class SatellitePlannerService:
    """Service for generating satellite-specific trading plans."""

    def __init__(self):
        self.bucket_service = BucketService()
        self.balance_service = BalanceService()
        self.security_repo = SecurityRepository()

    async def generate_plan_for_bucket(
        self,
        bucket_id: str,
        positions: list[Position],
        all_securities: list[Security],
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
        """Generate a trading plan for a specific bucket.

        Args:
            bucket_id: The bucket to plan for ("core" or satellite ID)
            positions: All current positions
            all_securities: All available securities
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
            List of ActionCandidate objects representing the plan, or None
        """
        # Get bucket and verify it's trading-allowed
        bucket = await self.bucket_service.get_bucket(bucket_id)
        if not bucket:
            logger.warning(f"Bucket {bucket_id} not found")
            return None

        if not bucket.is_trading_allowed:
            logger.info(
                f"Bucket {bucket_id} is not allowed to trade "
                f"(status={bucket.status})"
            )
            return None

        # Filter securities to bucket's universe
        bucket_securities = [s for s in all_securities if s.bucket_id == bucket_id]

        if not bucket_securities:
            logger.info(f"No securities assigned to bucket {bucket_id}")
            return None

        # Filter positions to bucket's securities
        bucket_symbols = {s.symbol for s in bucket_securities}
        bucket_positions = [p for p in positions if p.symbol in bucket_symbols]

        # Get bucket cash balance (convert to EUR)
        balances = await self.balance_service.get_all_balances(bucket_id)
        available_cash_eur = sum(b.balance for b in balances if b.currency == "EUR")

        # Convert USD balances to EUR
        usd_balances = [b for b in balances if b.currency == "USD"]
        if usd_balances:
            db_manager = get_db_manager()
            exchange_service = ExchangeRateService(db_manager)
            usd_rate = await exchange_service.get_rate("USD", "EUR")
            for usd_bal in usd_balances:
                eur_equivalent = usd_bal.balance * usd_rate
                available_cash_eur += eur_equivalent
                logger.debug(
                    f"Converted USD {usd_bal.balance:.2f} to EUR {eur_equivalent:.2f} "
                    f"(rate: {usd_rate:.4f})"
                )

        # For satellites, apply trading parameters from settings
        if bucket_id != "core":
            settings = await self.bucket_service.get_settings(bucket_id)
            if not settings:
                logger.warning(
                    f"No settings found for satellite {bucket_id}, " "using defaults"
                )
                trading_params = None
            else:
                trading_params = map_settings_to_parameters(settings)
                logger.info(
                    f"Satellite {bucket_id} using parameters: "
                    f"position_size_max={trading_params.position_size_max:.2%}, "
                    f"max_positions={trading_params.max_positions}"
                )

            # Calculate aggression level
            position_values = [
                p.market_value_eur
                for p in bucket_positions
                if p.market_value_eur is not None
            ]
            current_value = sum(position_values) + available_cash_eur
            aggression_result = calculate_aggression(
                current_value=current_value,
                target_value=bucket.target_allocation_pct
                * portfolio_context.total_value,
                high_water_mark=bucket.high_water_mark,
            )

            if aggression_result.in_hibernation:
                logger.info(
                    f"Satellite {bucket_id} is in hibernation "
                    f"(aggression={aggression_result.aggression:.0%})"
                )
                return None

            logger.info(
                f"Satellite {bucket_id} aggression: {aggression_result.aggression:.0%} "
                f"(funding={aggression_result.pct_of_target:.1%}, "
                f"drawdown={aggression_result.drawdown:.1%})"
            )
        else:
            trading_params = None
            aggression_result = None

        # Generate plan using holistic planner
        logger.info(
            f"Generating plan for bucket {bucket_id} with "
            f"{len(bucket_securities)} securities, "
            f"{len(bucket_positions)} positions, "
            f"€{available_cash_eur:.2f} cash"
        )

        holistic_plan = await create_holistic_plan(
            portfolio_context=portfolio_context,
            available_cash=available_cash_eur,
            securities=bucket_securities,
            positions=bucket_positions,
            exchange_rate_service=exchange_rate_service,
            target_weights=target_weights,
            current_prices=current_prices,
            transaction_cost_fixed=transaction_cost_fixed,
            transaction_cost_percent=transaction_cost_percent,
            max_plan_depth=max_steps,
        )

        if not holistic_plan or not holistic_plan.steps:
            logger.info(f"No plan generated for bucket {bucket_id}")
            return None

        # Convert HolisticPlan steps to ActionCandidates
        plan = [
            ActionCandidate(
                side=step.side,
                symbol=step.symbol,
                name=step.name,
                quantity=step.quantity,
                price=step.estimated_price,
                value_eur=step.estimated_value,
                currency=step.currency,
                priority=1.0,  # Use priority from plan score
                reason=step.reason,
                tags=step.contributes_to,
            )
            for step in holistic_plan.steps
        ]

        # For satellites, apply aggression-based position sizing
        if bucket_id != "core" and aggression_result:
            plan = await self._apply_aggression_scaling(
                plan, aggression_result.aggression
            )

        logger.info(
            f"Generated plan for bucket {bucket_id}: {len(plan)} actions, "
            f"total value €{sum(abs(a.value_eur) for a in plan):.2f}"
        )

        return plan

    async def _apply_aggression_scaling(
        self, plan: list[ActionCandidate], aggression: float
    ) -> list[ActionCandidate]:
        """Scale position sizes in plan based on aggression level.

        Args:
            plan: Original plan from holistic planner
            aggression: Aggression level (0.0-1.0)

        Returns:
            Plan with scaled position sizes
        """
        if aggression >= 1.0:
            return plan  # No scaling needed

        scaled_plan = []
        for action in plan:
            # Scale quantity and value
            scaled_quantity = int(scale_position_size(action.quantity, aggression))

            if scaled_quantity == 0:
                logger.debug(
                    f"Skipping {action.symbol} {action.side} - "
                    f"scaled to 0 shares (aggression={aggression:.0%})"
                )
                continue

            # Recalculate value with scaled quantity (convert to EUR if needed)
            scaled_value = scaled_quantity * action.price
            if action.currency != "EUR":
                # Apply exchange rate to convert to EUR
                db_manager = get_db_manager()
                exchange_service = ExchangeRateService(db_manager)
                rate = await exchange_service.get_rate(action.currency, "EUR")
                scaled_value = scaled_value * rate
                logger.debug(
                    f"Converted {action.currency} {scaled_value/rate:.2f} to EUR {scaled_value:.2f} "
                    f"(rate: {rate:.4f})"
                )

            scaled_action = ActionCandidate(
                side=action.side,
                symbol=action.symbol,
                name=action.name,
                quantity=scaled_quantity,
                price=action.price,
                value_eur=scaled_value,
                currency=action.currency,
                priority=action.priority,
                reason=f"{action.reason} (scaled {aggression:.0%} due to aggression)",
                tags=action.tags + ["aggression_scaled"],
            )

            scaled_plan.append(scaled_action)

        logger.info(
            f"Scaled plan from {len(plan)} to {len(scaled_plan)} actions "
            f"(aggression={aggression:.0%})"
        )

        return scaled_plan
