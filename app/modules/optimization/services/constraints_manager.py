"""
Constraints Manager for Portfolio Optimization.

Translates business rules into PyPortfolioOpt constraints:
- allow_buy/allow_sell flags
- min_lot constraints (can't partially sell if at min lot)
- Concentration limits (20% max per stock)
- Country/Industry sector constraints (grouped into territories/industry groups)
"""

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from app.domain.models import Position, Stock
from app.domain.scoring.constants import (
    GEO_ALLOCATION_TOLERANCE,
    IND_ALLOCATION_TOLERANCE,
    MAX_CONCENTRATION,
    MAX_COUNTRY_CONCENTRATION,
    MAX_SECTOR_CONCENTRATION,
)

logger = logging.getLogger(__name__)


@dataclass
class WeightBounds:
    """Weight bounds for a single stock."""

    symbol: str
    lower: float  # Minimum weight (0.0 to 1.0)
    upper: float  # Maximum weight (0.0 to 1.0)
    reason: Optional[str] = None


@dataclass
class SectorConstraint:
    """Constraint for a sector (country or industry)."""

    name: str
    symbols: List[str]
    target: float  # Target weight
    lower: float  # Lower bound
    upper: float  # Upper bound


class ConstraintsManager:
    """Manage portfolio optimization constraints."""

    def __init__(
        self,
        max_concentration: float = MAX_CONCENTRATION,
        geo_tolerance: float = GEO_ALLOCATION_TOLERANCE,
        ind_tolerance: float = IND_ALLOCATION_TOLERANCE,
        grouping_repo=None,
    ):
        self.max_concentration = max_concentration
        self.geo_tolerance = geo_tolerance
        self.ind_tolerance = ind_tolerance
        self._grouping_repo = grouping_repo

    def calculate_weight_bounds(
        self,
        stocks: List[Stock],
        positions: Dict[str, Position],
        portfolio_value: float,
        current_prices: Dict[str, float],
    ) -> Dict[str, Tuple[float, float]]:
        """
        Calculate weight bounds for each stock.

        Args:
            stocks: List of Stock objects
            positions: Dict mapping symbol to Position
            portfolio_value: Total portfolio value in EUR
            current_prices: Dict mapping symbol to current price

        Returns:
            Dict mapping symbol to (lower_bound, upper_bound) tuple
        """
        bounds = {}

        logger.debug(
            f"Calculating weight bounds for {len(stocks)} stocks, "
            f"portfolio_value={portfolio_value:.2f} EUR"
        )

        for stock in stocks:
            symbol = stock.symbol
            position = positions.get(symbol)
            current_price = current_prices.get(symbol, 0)

            # Calculate current weight
            if (
                position is not None
                and position.market_value_eur is not None
                and portfolio_value > 0
            ):
                current_weight = position.market_value_eur / portfolio_value
            else:
                current_weight = 0.0

            # Track constraint application for diagnostics
            constraint_steps = []

            # Default bounds
            lower = 0.0
            upper = self.max_concentration
            constraint_steps.append(f"initial: lower={lower:.2%}, upper={upper:.2%}")

            # Apply user-defined portfolio targets (convert percentage to fraction)
            if stock.min_portfolio_target is not None:
                lower = stock.min_portfolio_target / 100.0
                constraint_steps.append(
                    f"min_portfolio_target={stock.min_portfolio_target}% → lower={lower:.2%}"
                )

            if stock.max_portfolio_target is not None:
                upper = stock.max_portfolio_target / 100.0
                constraint_steps.append(
                    f"max_portfolio_target={stock.max_portfolio_target}% → upper={upper:.2%}"
                )

            # Check allow_buy constraint
            if not stock.allow_buy:
                # Can't buy more, so upper bound = current weight
                old_upper = upper
                upper = min(upper, current_weight)
                constraint_steps.append(
                    f"allow_buy=False → upper=min({old_upper:.2%}, {current_weight:.2%})={upper:.2%}"
                )

            # Check allow_sell constraint
            if not stock.allow_sell:
                # Can't sell, so lower bound = current weight
                old_lower = lower
                lower = max(lower, current_weight)
                constraint_steps.append(
                    f"allow_sell=False → lower=max({old_lower:.2%}, {current_weight:.2%})={lower:.2%}"
                )

            # Check min_lot constraint
            if position and stock.min_lot > 0 and current_price > 0:
                if position.quantity <= stock.min_lot:
                    # Can't partially sell - it's all or nothing
                    # Set lower bound to current weight (can't reduce)
                    old_lower = lower
                    lower = max(lower, current_weight)
                    constraint_steps.append(
                        f"at min_lot (qty={position.quantity} <= {stock.min_lot}) → "
                        f"lower=max({old_lower:.2%}, {current_weight:.2%})={lower:.2%}"
                    )
                else:
                    # Can sell down to min_lot worth
                    min_lot_value = stock.min_lot * current_price
                    min_weight = (
                        min_lot_value / portfolio_value if portfolio_value > 0 else 0
                    )
                    # Check if min_lot constraint would violate upper bound
                    # If min_weight > upper, the constraint is infeasible - ignore it
                    if min_weight > upper:
                        logger.warning(
                            f"{symbol}: min_lot constraint would create infeasible bounds "
                            f"(min_weight={min_weight:.2%} > upper={upper:.2%}). "
                            f"Ignoring min_lot constraint. Consider reducing min_lot "
                            f"from {stock.min_lot} to allow rebalancing."
                        )
                        constraint_steps.append(
                            f"min_lot constraint ignored (min_weight={min_weight:.2%} > "
                            f"upper={upper:.2%})"
                        )
                    else:
                        old_lower = lower
                        lower = max(lower, min_weight)
                        constraint_steps.append(
                            f"min_lot constraint (min_lot_value={min_lot_value:.2f} EUR) → "
                            f"lower=max({old_lower:.2%}, {min_weight:.2%})={lower:.2%}"
                        )

            # Ensure lower <= upper
            if lower > upper:
                # Constraint conflict - keep current weight
                logger.warning(
                    f"{symbol}: constraint conflict detected! "
                    f"lower={lower:.2%} > upper={upper:.2%}, "
                    f"current_weight={current_weight:.2%}, "
                    f"portfolio_value={portfolio_value:.2f} EUR, "
                    f"position_value={position.market_value_eur if position and position.market_value_eur else 0:.2f} EUR, "
                    f"min_portfolio_target={stock.min_portfolio_target}, "
                    f"max_portfolio_target={stock.max_portfolio_target}, "
                    f"allow_sell={stock.allow_sell}, allow_buy={stock.allow_buy}, "
                    f"min_lot={stock.min_lot}, position_qty={position.quantity if position else 0}, "
                    f"current_price={current_price:.2f}. "
                    f"Constraint steps: {'; '.join(constraint_steps)}. "
                    f"Using current weight {current_weight:.2%} for both bounds."
                )
                lower = current_weight
                upper = current_weight
            elif lower == upper and lower > 0:
                # Locked position - log for diagnostics
                logger.debug(
                    f"{symbol}: locked position (lower=upper={lower:.2%}), "
                    f"constraint steps: {'; '.join(constraint_steps)}"
                )

            bounds[symbol] = (lower, upper)

        return bounds

    async def _get_country_group_mapping(self) -> Dict[str, str]:
        """Get country to group mapping from DB or fallback to hardcoded."""
        if self._grouping_repo:
            try:
                db_groups = await self._grouping_repo.get_country_groups()
                # Build reverse mapping: country -> group
                mapping: Dict[str, str] = {}
                for group_name, country_names in db_groups.items():
                    for country_name in country_names:
                        mapping[country_name] = group_name
                if mapping:
                    logger.info(
                        f"Using custom country groups from DB: {len(db_groups)} groups"
                    )
                    return mapping
            except Exception as e:
                logger.warning(f"Failed to load custom country groups: {e}")

        return {}

    async def _get_industry_group_mapping(self) -> Dict[str, str]:
        """Get industry to group mapping from DB (custom groups only)."""
        if not self._grouping_repo:
            logger.warning(
                "No grouping repository available - no industry groups will be used"
            )
            return {}

        try:
            db_groups = await self._grouping_repo.get_industry_groups()
            # Build reverse mapping: industry -> group
            mapping: Dict[str, str] = {}
            for group_name, industry_names in db_groups.items():
                for industry_name in industry_names:
                    mapping[industry_name] = group_name
            if mapping:
                logger.info(
                    f"Using custom industry groups from DB: {len(db_groups)} groups"
                )
            return mapping
        except Exception as e:
            logger.warning(f"Failed to load custom industry groups: {e}")
            return {}

    async def build_sector_constraints(
        self,
        stocks: List[Stock],
        country_targets: Dict[str, float],
        ind_targets: Dict[str, float],
    ) -> Tuple[List[SectorConstraint], List[SectorConstraint]]:
        """
        Build country and industry sector constraints.

        Accepts group targets directly (no aggregation needed).
        Maps stocks to groups and creates constraints for groups with targets.

        Args:
            stocks: List of Stock objects
            country_targets: Dict mapping group name to target weight (already at group level)
            ind_targets: Dict mapping group name to target weight (already at group level)

        Returns:
            Tuple of (country_constraints, industry_constraints)
        """
        # Get country to group mapping (custom from DB or hardcoded fallback)
        country_to_group = await self._get_country_group_mapping()

        # Group stocks by territory/group instead of individual countries
        territory_groups: Dict[str, List[str]] = {}

        for stock in stocks:
            country = stock.country or "OTHER"
            # Map country to group
            territory = country_to_group.get(country, "OTHER")

            if territory not in territory_groups:
                territory_groups[territory] = []
            territory_groups[territory].append(stock.symbol)

        logger.info(
            f"Grouped stocks into {len(territory_groups)} country groups: "
            f"{', '.join(f'{t}={len(s)} stocks' for t, s in sorted(territory_groups.items()))}"
        )

        # Get industry to group mapping (custom from DB or hardcoded fallback)
        industry_to_group = await self._get_industry_group_mapping()

        # Group stocks by industry group instead of individual industries
        industry_group_groups: Dict[str, List[str]] = {}

        for stock in stocks:
            industry = stock.industry or "OTHER"
            # Map industry to group
            industry_group = industry_to_group.get(industry, "OTHER")

            if industry_group not in industry_group_groups:
                industry_group_groups[industry_group] = []
            industry_group_groups[industry_group].append(stock.symbol)

        logger.info(
            f"Grouped stocks into {len(industry_group_groups)} industry groups: "
            f"{', '.join(f'{g}={len(s)} stocks' for g, s in sorted(industry_group_groups.items()))}"
        )

        # Use territory groups and industry group groups for constraints
        # Targets are already at group level, no aggregation needed
        country_groups = territory_groups
        ind_groups = industry_group_groups

        # Build country constraints
        # Targets are already at group level, no normalization needed
        # Groups should sum to 100% at user level
        country_constraints = []
        for country, symbols in country_groups.items():
            target = country_targets.get(country, 0.0)
            if target > 0:
                # Calculate tolerance-based bounds
                tolerance_upper = min(1.0, target + self.geo_tolerance)
                # Enforce hard limit: cap at MAX_COUNTRY_CONCENTRATION
                hard_upper = min(tolerance_upper, MAX_COUNTRY_CONCENTRATION)
                country_constraints.append(
                    SectorConstraint(
                        name=country,
                        symbols=symbols,
                        target=target,
                        lower=max(0.0, target - self.geo_tolerance),
                        upper=hard_upper,
                    )
                )

        # Scale down country constraint upper bounds if they sum to > 100%
        # This prevents optimization infeasibility when many countries are constrained
        if country_constraints:
            country_max_sum = sum(c.upper for c in country_constraints)
            if country_max_sum > 1.0:
                logger.warning(
                    f"Country constraint upper bounds sum to {country_max_sum:.2%} > 100%, "
                    f"scaling down proportionally to 100%"
                )
                # Scale all upper bounds proportionally
                scale_factor = 1.0 / country_max_sum
                for constraint in country_constraints:
                    constraint.upper = constraint.upper * scale_factor
                    # Ensure upper is still >= lower
                    constraint.upper = max(constraint.upper, constraint.lower)

            country_min_sum = sum(c.lower for c in country_constraints)
            country_max_sum_final = sum(c.upper for c in country_constraints)
            logger.debug(
                f"Country constraints sum: min={country_min_sum:.2%}, max={country_max_sum_final:.2%}"
            )

        # Build industry constraints
        # Targets are already at group level, no normalization needed
        # Groups should sum to 100% at user level
        # First, count how many industries will have constraints
        industries_with_targets = [
            ind for ind in ind_groups.keys() if ind_targets.get(ind, 0.0) > 0
        ]
        num_industry_constraints = len(industries_with_targets)

        # Adjust max concentration cap based on number of industries
        # When using industry groups (instead of individual industries), allow higher caps
        # because groups are larger and more flexible
        # If only 1-2 industries, allow higher allocation (up to 70% for 1, 50% for 2)
        # For 3-4 groups, allow up to 40% per group (more flexible than 30%)
        # For 5+ groups, use default 30%
        if num_industry_constraints == 1:
            effective_max_concentration = 0.70  # 70% for single industry
        elif num_industry_constraints == 2:
            effective_max_concentration = 0.50  # 50% each for 2 industries
        elif num_industry_constraints <= 4:
            # For grouped industries (3-4 groups), allow 40% per group
            # This accommodates groups like "OTHER" that may have high targets
            effective_max_concentration = 0.40
            logger.info(
                f"Using 40% max concentration cap for {num_industry_constraints} "
                f"industry groups (more flexible than 30% for grouped industries)"
            )
        else:
            effective_max_concentration = MAX_SECTOR_CONCENTRATION  # 30% default

        ind_constraints = []
        for ind, symbols in ind_groups.items():
            target = ind_targets.get(ind, 0.0)
            if target > 0:
                # Calculate tolerance-based bounds
                tolerance_upper = min(1.0, target + self.ind_tolerance)
                # Enforce hard limit: cap at effective_max_concentration
                hard_upper = min(tolerance_upper, effective_max_concentration)
                ind_constraints.append(
                    SectorConstraint(
                        name=ind,
                        symbols=symbols,
                        target=target,
                        lower=max(0.0, target - self.ind_tolerance),
                        upper=hard_upper,
                    )
                )

        if num_industry_constraints <= 2:
            logger.info(
                f"Adjusted industry max concentration to {effective_max_concentration:.0%} "
                f"(from {MAX_SECTOR_CONCENTRATION:.0%}) for {num_industry_constraints} "
                f"industry constraint(s)"
            )

        # Scale down industry constraint minimum bounds if they sum to > 100%
        # Also scale down if combined with country minimums they exceed 80% (too restrictive)
        # This prevents optimization infeasibility when minimum bounds are too restrictive
        if ind_constraints:
            ind_min_sum = sum(c.lower for c in ind_constraints)
            country_min_sum = sum(c.lower for c in country_constraints)
            total_min_sum = country_min_sum + ind_min_sum

            # Scale down if industry minimums alone exceed 100%
            if ind_min_sum > 1.0:
                logger.warning(
                    f"Industry constraint minimum bounds sum to {ind_min_sum:.2%} > 100%, "
                    f"scaling down proportionally to 100%"
                )
                scale_factor = 1.0 / ind_min_sum
                for constraint in ind_constraints:
                    constraint.lower = constraint.lower * scale_factor
                    constraint.lower = min(constraint.lower, constraint.upper)
            # Scale down BOTH country and industry minimums proportionally if combined > 70%
            # This leaves 30% slack for individual stock bounds and optimization flexibility
            # Scaling both proportionally maintains relative weights while ensuring feasibility
            elif total_min_sum > 0.70:
                logger.warning(
                    f"Combined minimum bounds (country={country_min_sum:.2%} + "
                    f"industry={ind_min_sum:.2%} = {total_min_sum:.2%}) exceed 60%, "
                    f"scaling down both proportionally to 60% total"
                )
                # Scale both country and industry minimums proportionally
                scale_factor = 0.60 / total_min_sum
                for constraint in country_constraints:
                    constraint.lower = constraint.lower * scale_factor
                    constraint.lower = min(constraint.lower, constraint.upper)
                for constraint in ind_constraints:
                    constraint.lower = constraint.lower * scale_factor
                    constraint.lower = min(constraint.lower, constraint.upper)

        logger.info(
            f"Built {len(country_constraints)} country constraints, "
            f"{len(ind_constraints)} industry constraints"
        )

        # Log constraint details for debugging
        if ind_constraints:
            ind_details = [
                f"{c.name}: target={c.target:.2%}, range=[{c.lower:.2%}, {c.upper:.2%}]"
                for c in ind_constraints
            ]
            logger.info(f"Industry constraints: {', '.join(ind_details)}")
            ind_min_sum = sum(c.lower for c in ind_constraints)
            ind_max_sum = sum(c.upper for c in ind_constraints)
            logger.info(
                f"Industry constraints sum: min={ind_min_sum:.2%}, max={ind_max_sum:.2%}"
            )

        return country_constraints, ind_constraints

    def get_constraint_summary(
        self,
        bounds: Dict[str, Tuple[float, float]],
        country_constraints: List[SectorConstraint],
        ind_constraints: List[SectorConstraint],
    ) -> Dict:
        """
        Get a summary of all constraints for logging/debugging.

        Returns:
            Dict with constraint details
        """
        # Count constrained stocks
        locked = []  # lower == upper (can't change)
        buy_only = []  # lower == 0, upper < max (can only buy)
        sell_blocked = []  # lower > 0 (can't fully exit)

        for symbol, (lower, upper) in bounds.items():
            if lower == upper:
                locked.append(symbol)
            elif lower == 0 and upper < self.max_concentration:
                buy_only.append(symbol)
            elif lower > 0:
                sell_blocked.append(symbol)

        return {
            "total_stocks": len(bounds),
            "locked_positions": locked,
            "buy_only": buy_only,
            "sell_blocked": sell_blocked,
            "country_constraints": [
                {"name": c.name, "target": c.target, "range": (c.lower, c.upper)}
                for c in country_constraints
            ],
            "industry_constraints": [
                {"name": c.name, "target": c.target, "range": (c.lower, c.upper)}
                for c in ind_constraints
            ],
        }
