"""
Constraints Manager for Portfolio Optimization.

Translates business rules into PyPortfolioOpt constraints:
- allow_buy/allow_sell flags
- min_lot constraints (can't partially sell if at min lot)
- Concentration limits (20% max per stock)
- Geography/Industry sector constraints
"""

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from app.domain.models import Position, Stock
from app.domain.scoring.constants import (
    GEO_ALLOCATION_TOLERANCE,
    IND_ALLOCATION_TOLERANCE,
    MAX_CONCENTRATION,
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
    """Constraint for a sector (geography or industry)."""

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

            # Default bounds
            lower = 0.0
            upper = self.max_concentration

            # Check allow_buy constraint
            if not stock.allow_buy:
                # Can't buy more, so upper bound = current weight
                upper = min(upper, current_weight)
                logger.debug(f"{symbol}: allow_buy=False, upper={upper:.2%}")

            # Check allow_sell constraint
            if not stock.allow_sell:
                # Can't sell, so lower bound = current weight
                lower = max(lower, current_weight)
                logger.debug(f"{symbol}: allow_sell=False, lower={lower:.2%}")

            # Check min_lot constraint
            if position and stock.min_lot > 0 and current_price > 0:
                if position.quantity <= stock.min_lot:
                    # Can't partially sell - it's all or nothing
                    # Set lower bound to current weight (can't reduce)
                    lower = max(lower, current_weight)
                    logger.debug(
                        f"{symbol}: at min_lot ({position.quantity} <= {stock.min_lot}), "
                        f"lower={lower:.2%}"
                    )
                else:
                    # Can sell down to min_lot worth
                    min_lot_value = stock.min_lot * current_price
                    min_weight = (
                        min_lot_value / portfolio_value if portfolio_value > 0 else 0
                    )
                    lower = max(lower, min_weight)

            # Ensure lower <= upper
            if lower > upper:
                # Constraint conflict - keep current weight
                logger.warning(
                    f"{symbol}: constraint conflict (lower={lower:.2%} > upper={upper:.2%}), "
                    f"using current weight {current_weight:.2%}"
                )
                lower = current_weight
                upper = current_weight

            bounds[symbol] = (lower, upper)

        return bounds

    def build_sector_constraints(
        self,
        stocks: List[Stock],
        geo_targets: Dict[str, float],
        ind_targets: Dict[str, float],
    ) -> Tuple[List[SectorConstraint], List[SectorConstraint]]:
        """
        Build geography and industry sector constraints.

        Args:
            stocks: List of Stock objects
            geo_targets: Dict mapping geography name to target weight
            ind_targets: Dict mapping industry name to target weight

        Returns:
            Tuple of (geography_constraints, industry_constraints)
        """
        # Group stocks by geography
        geo_groups: Dict[str, List[str]] = {}
        for stock in stocks:
            geo = stock.geography or "OTHER"
            if geo not in geo_groups:
                geo_groups[geo] = []
            geo_groups[geo].append(stock.symbol)

        # Group stocks by industry
        ind_groups: Dict[str, List[str]] = {}
        for stock in stocks:
            ind = stock.industry or "OTHER"
            if ind not in ind_groups:
                ind_groups[ind] = []
            ind_groups[ind].append(stock.symbol)

        # Build geography constraints
        geo_constraints = []
        for geo, symbols in geo_groups.items():
            target = geo_targets.get(geo, 0.0)
            if target > 0:
                geo_constraints.append(
                    SectorConstraint(
                        name=geo,
                        symbols=symbols,
                        target=target,
                        lower=max(0.0, target - self.geo_tolerance),
                        upper=min(1.0, target + self.geo_tolerance),
                    )
                )

        # Build industry constraints
        ind_constraints = []
        for ind, symbols in ind_groups.items():
            target = ind_targets.get(ind, 0.0)
            if target > 0:
                ind_constraints.append(
                    SectorConstraint(
                        name=ind,
                        symbols=symbols,
                        target=target,
                        lower=max(0.0, target - self.ind_tolerance),
                        upper=min(1.0, target + self.ind_tolerance),
                    )
                )

        logger.info(
            f"Built {len(geo_constraints)} geography constraints, "
            f"{len(ind_constraints)} industry constraints"
        )

        return geo_constraints, ind_constraints

    def get_constraint_summary(
        self,
        bounds: Dict[str, Tuple[float, float]],
        geo_constraints: List[SectorConstraint],
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
            "geography_constraints": [
                {"name": c.name, "target": c.target, "range": (c.lower, c.upper)}
                for c in geo_constraints
            ],
            "industry_constraints": [
                {"name": c.name, "target": c.target, "range": (c.lower, c.upper)}
                for c in ind_constraints
            ],
        }
