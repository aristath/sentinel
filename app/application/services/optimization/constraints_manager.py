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

# Territory mapping: group countries into larger regions
TERRITORY_MAPPING = {
    # EU countries
    "Germany": "EU",
    "France": "EU",
    "Italy": "EU",
    "Spain": "EU",
    "Netherlands": "EU",
    "Belgium": "EU",
    "Austria": "EU",
    "Sweden": "EU",
    "Denmark": "EU",
    "Finland": "EU",
    "Ireland": "EU",
    "Portugal": "EU",
    "Poland": "EU",
    "Greece": "EU",
    "Czech Republic": "EU",
    "Romania": "EU",
    "Hungary": "EU",
    "Bulgaria": "EU",
    "Croatia": "EU",
    "Slovakia": "EU",
    "Slovenia": "EU",
    "Lithuania": "EU",
    "Latvia": "EU",
    "Estonia": "EU",
    "Luxembourg": "EU",
    "Malta": "EU",
    "Cyprus": "EU",
    # US
    "United States": "US",
    "USA": "US",
    # ASIA (major markets)
    "China": "ASIA",
    "Japan": "ASIA",
    "South Korea": "ASIA",
    "India": "ASIA",
    "Singapore": "ASIA",
    "Hong Kong": "ASIA",
    "Taiwan": "ASIA",
    "Thailand": "ASIA",
    "Malaysia": "ASIA",
    "Indonesia": "ASIA",
    "Philippines": "ASIA",
    "Vietnam": "ASIA",
    # Other regions can be added as needed
}

# Industry grouping: group industries into larger categories
INDUSTRY_GROUP_MAPPING = {
    # Technology
    "Technology": "Technology",
    "Software": "Technology",
    "Semiconductors": "Technology",
    "Internet Content & Information": "Technology",
    "Electronic Components": "Technology",
    "Consumer Electronics": "Technology",
    # Industrials
    "Industrials": "Industrials",
    "Aerospace & Defense": "Industrials",
    "Industrial Machinery": "Industrials",
    "Electrical Equipment": "Industrials",
    "Engineering & Construction": "Industrials",
    "Specialty Industrial Machinery": "Industrials",
    # Energy
    "Energy": "Energy",
    "Oil & Gas": "Energy",
    "Renewable Energy": "Energy",
    "Utilities - Renewable": "Energy",
    "Utilities": "Energy",
    # Healthcare
    "Healthcare": "Healthcare",
    "Biotechnology": "Healthcare",
    "Pharmaceuticals": "Healthcare",
    "Medical Devices": "Healthcare",
    # Financials
    "Financial Services": "Financials",
    "Banks": "Financials",
    "Insurance": "Financials",
    "Capital Markets": "Financials",
    # Consumer
    "Consumer Cyclical": "Consumer",
    "Consumer Defensive": "Consumer",
    "Consumer Staples": "Consumer",
    "Retail": "Consumer",
    # Materials
    "Materials": "Materials",
    "Chemicals": "Materials",
    "Metals & Mining": "Materials",
    "Steel": "Materials",
    # Real Estate
    "Real Estate": "Real Estate",
    "REITs": "Real Estate",
    # Communication
    "Communication Services": "Communication",
    "Telecom": "Communication",
    "Media": "Communication",
}


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
    ):
        self.max_concentration = max_concentration
        self.geo_tolerance = geo_tolerance
        self.ind_tolerance = ind_tolerance

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

    def build_sector_constraints(
        self,
        stocks: List[Stock],
        country_targets: Dict[str, float],
        ind_targets: Dict[str, float],
    ) -> Tuple[List[SectorConstraint], List[SectorConstraint]]:
        """
        Build country and industry sector constraints.

        Args:
            stocks: List of Stock objects
            country_targets: Dict mapping country name to target weight
            ind_targets: Dict mapping industry name to target weight

        Returns:
            Tuple of (country_constraints, industry_constraints)
        """
        # Group stocks by territory (EU/US/ASIA/OTHER) instead of individual countries
        # This reduces constraint complexity and improves optimizer feasibility
        territory_groups: Dict[str, List[str]] = {}

        for stock in stocks:
            country = stock.country or "OTHER"
            # Map country to territory
            territory = TERRITORY_MAPPING.get(country, "OTHER")

            if territory not in territory_groups:
                territory_groups[territory] = []
            territory_groups[territory].append(stock.symbol)

        # Aggregate country targets to territory targets
        territory_targets: Dict[str, float] = {}
        for country, target in country_targets.items():
            territory = TERRITORY_MAPPING.get(country, "OTHER")
            territory_targets[territory] = (
                territory_targets.get(territory, 0.0) + target
            )

        logger.info(
            f"Grouped {len(country_targets)} country targets into {len(territory_targets)} territories: "
            f"{', '.join(f'{t}={v:.1%}' for t, v in sorted(territory_targets.items()) if v > 0)}"
        )

        # Group stocks by industry group instead of individual industries
        # This reduces constraint complexity
        industry_group_groups: Dict[str, List[str]] = {}

        for stock in stocks:
            industry = stock.industry or "OTHER"
            # Map industry to industry group
            industry_group = INDUSTRY_GROUP_MAPPING.get(industry, "OTHER")

            if industry_group not in industry_group_groups:
                industry_group_groups[industry_group] = []
            industry_group_groups[industry_group].append(stock.symbol)

        # Aggregate industry targets to industry group targets
        industry_group_targets: Dict[str, float] = {}
        for industry, target in ind_targets.items():
            industry_group = INDUSTRY_GROUP_MAPPING.get(industry, "OTHER")
            industry_group_targets[industry_group] = (
                industry_group_targets.get(industry_group, 0.0) + target
            )

        logger.info(
            f"Grouped {len(ind_targets)} industry targets into {len(industry_group_targets)} groups: "
            f"{', '.join(f'{g}={v:.1%}' for g, v in sorted(industry_group_targets.items()) if v > 0)}"
        )

        # Use territory groups and industry group groups for constraints
        country_groups = territory_groups
        ind_groups = industry_group_groups
        country_targets = territory_targets
        ind_targets = industry_group_targets

        # Normalize country targets to sum to 100% (if they sum to more)
        # Only normalize targets for countries that actually have stocks
        country_targets_for_active_countries = {
            country: country_targets.get(country, 0.0)
            for country in country_groups.keys()
            if country_targets.get(country, 0.0) > 0
        }
        country_sum = sum(country_targets_for_active_countries.values())
        if country_sum > 1.0:
            logger.warning(
                f"Country targets sum to {country_sum:.2%} > 100%, normalizing to 100%"
            )
            country_targets_normalized = {
                k: v / country_sum
                for k, v in country_targets_for_active_countries.items()
            }
            # Merge back with original targets (keep zero targets as zero)
            country_targets_normalized = {
                country: country_targets_normalized.get(
                    country, country_targets.get(country, 0.0)
                )
                for country in country_groups.keys()
            }
        else:
            country_targets_normalized = country_targets

        # Build country constraints
        country_constraints = []
        for country, symbols in country_groups.items():
            target = country_targets_normalized.get(country, 0.0)
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

        # Normalize industry targets to sum to 100% (if they sum to more)
        # Only normalize targets for industries that actually have stocks
        ind_targets_for_active_industries = {
            ind: ind_targets.get(ind, 0.0)
            for ind in ind_groups.keys()
            if ind_targets.get(ind, 0.0) > 0
        }
        ind_sum = sum(ind_targets_for_active_industries.values())
        if ind_sum > 1.0:
            logger.warning(
                f"Industry targets sum to {ind_sum:.2%} > 100%, normalizing to 100%"
            )
            ind_targets_normalized = {
                k: v / ind_sum for k, v in ind_targets_for_active_industries.items()
            }
            # Merge back with original targets (keep zero targets as zero)
            ind_targets_normalized = {
                ind: ind_targets_normalized.get(ind, ind_targets.get(ind, 0.0))
                for ind in ind_groups.keys()
            }
        else:
            ind_targets_normalized = ind_targets

        # Build industry constraints
        # First, count how many industries will have constraints
        industries_with_targets = [
            ind for ind in ind_groups.keys() if ind_targets_normalized.get(ind, 0.0) > 0
        ]
        num_industry_constraints = len(industries_with_targets)

        # Adjust max concentration cap based on number of industries
        # If only 1-2 industries, allow higher allocation (up to 70% for 1, 50% for 2)
        # This prevents the "only 30% total" problem when few industries are constrained
        if num_industry_constraints == 1:
            effective_max_concentration = 0.70  # 70% for single industry
        elif num_industry_constraints == 2:
            effective_max_concentration = 0.50  # 50% each for 2 industries
        else:
            effective_max_concentration = MAX_SECTOR_CONCENTRATION  # 30% default

        ind_constraints = []
        for ind, symbols in ind_groups.items():
            target = ind_targets_normalized.get(ind, 0.0)
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
