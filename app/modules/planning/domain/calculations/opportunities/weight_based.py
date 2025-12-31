"""Weight-based opportunity calculator.

Uses portfolio optimizer target weights to identify rebalancing opportunities.
"""

from typing import Any, Dict, List, Optional

from app.domain.models import Position, Security
from app.domain.services.exchange_rate_service import ExchangeRateService
from app.domain.value_objects.trade_side import TradeSide
from app.modules.planning.domain.calculations.opportunities.base import (
    OpportunityCalculator,
    OpportunityContext,
    opportunity_calculator_registry,
)
from app.modules.planning.domain.holistic_planner import ActionCandidate


class WeightBasedCalculator(OpportunityCalculator):
    """Uses optimizer target weights to identify opportunities.

    Requires portfolio optimizer to be active and providing target weights.
    More sophisticated than simple rebalancing - uses mean-variance optimization.
    """

    def __init__(self, exchange_rate_service: Optional[ExchangeRateService] = None):
        self.exchange_rate_service = exchange_rate_service

    @property
    def name(self) -> str:
        return "weight_based"

    def default_params(self) -> Dict[str, Any]:
        return {
            "transaction_cost_fixed": 2.0,  # EUR per trade
            "transaction_cost_percent": 0.002,  # 0.2% of trade value
            "min_gap_threshold": 0.005,  # Ignore gaps < 0.5%
        }

    async def calculate(
        self,
        context: OpportunityContext,
        params: Dict[str, Any],
    ) -> List[ActionCandidate]:
        """
        Identify opportunities based on optimizer target weights.

        Compares current portfolio weights to target weights and generates:
        - Buy candidates for underweight positions
        - Sell candidates for overweight positions

        Categorizes as:
        - averaging_down: If buying more of a position below cost
        - rebalance_buys: If increasing an underweight position
        - rebalance_sells: If reducing an overweight position

        Args:
            context: Portfolio context with target weights
            params: Calculator parameters

        Returns:
            List of ActionCandidates for weight-based rebalancing
        """
        opportunities: List[ActionCandidate] = []

        # Require target weights from optimizer
        if not context.target_weights:
            return opportunities

        if context.total_portfolio_value_eur <= 0:
            return opportunities

        transaction_cost_fixed = params.get("transaction_cost_fixed", 2.0)
        transaction_cost_percent = params.get("transaction_cost_percent", 0.002)
        min_gap_threshold = params.get("min_gap_threshold", 0.005)

        # Calculate current weights
        current_weights: Dict[str, float] = {}
        for pos in context.positions:
            pos_value = pos.market_value_eur or 0
            current_weights[pos.symbol] = pos_value / context.total_portfolio_value_eur

        # Calculate weight gaps
        weight_gaps = self._calculate_weight_gaps(
            context.target_weights,
            current_weights,
            context.total_portfolio_value_eur,
            min_gap_threshold,
        )

        # Build lookup maps
        positions_by_symbol = {p.symbol: p for p in context.positions}

        # Process each gap
        for gap_info in weight_gaps:
            symbol = gap_info["symbol"]
            gap = gap_info["gap"]
            gap_value = gap_info["gap_value"]

            security = context.stocks_by_symbol.get(symbol)
            position = positions_by_symbol.get(symbol)

            # Get current price
            price = None
            if position:
                price = position.current_price or position.avg_price
            if not price or price <= 0:
                continue

            # Check if trade is worthwhile given transaction costs
            if not self._is_trade_worthwhile(
                gap_value, transaction_cost_fixed, transaction_cost_percent
            ):
                continue

            if gap > 0:
                # Need to buy
                candidate = self._process_buy_opportunity(
                    gap_info, security, position, price
                )
                if candidate:
                    opportunities.append(candidate)
            else:
                # Need to sell
                # Skip if recently sold or ineligible (checked externally)
                if position:
                    candidate = self._process_sell_opportunity(
                        gap_info, security, position, price
                    )
                    if candidate:
                        opportunities.append(candidate)

        return opportunities

    def _calculate_weight_gaps(
        self,
        target_weights: Dict[str, float],
        current_weights: Dict[str, float],
        total_value: float,
        min_gap_threshold: float,
    ) -> List[Dict[str, Any]]:
        """Calculate weight gaps between target and current weights."""
        weight_gaps: List[Dict[str, Any]] = []

        # Check all target weights
        for symbol, target in target_weights.items():
            current = current_weights.get(symbol, 0.0)
            gap = target - current
            if abs(gap) > min_gap_threshold:
                weight_gaps.append(
                    {
                        "symbol": symbol,
                        "current": current,
                        "target": target,
                        "gap": gap,
                        "gap_value": gap * total_value,
                    }
                )

        # Check positions not in target (should be zero)
        for symbol, current in current_weights.items():
            if symbol not in target_weights and current > min_gap_threshold:
                weight_gaps.append(
                    {
                        "symbol": symbol,
                        "current": current,
                        "target": 0.0,
                        "gap": -current,
                        "gap_value": -current * total_value,
                    }
                )

        # Sort by absolute gap value (largest first)
        weight_gaps.sort(key=lambda x: abs(x["gap"]), reverse=True)
        return weight_gaps

    def _is_trade_worthwhile(
        self,
        gap_value: float,
        transaction_cost_fixed: float,
        transaction_cost_percent: float,
    ) -> bool:
        """Check if trade is worthwhile based on transaction costs.

        Trade must be at least 2x the transaction cost to be worthwhile.
        """
        trade_cost = transaction_cost_fixed + abs(gap_value) * transaction_cost_percent
        return abs(gap_value) >= trade_cost * 2

    def _process_buy_opportunity(
        self,
        gap_info: Dict[str, Any],
        security: Optional[Security],
        position: Optional[Position],
        price: float,
    ) -> Optional[ActionCandidate]:
        """Process a buy opportunity from weight gap."""
        if not security or not security.allow_buy:
            return None

        symbol = gap_info["symbol"]
        gap_value = gap_info["gap_value"]

        quantity = int(gap_value / price)
        if security.min_lot and quantity < security.min_lot:
            quantity = security.min_lot

        if quantity <= 0:
            return None

        trade_value = quantity * price
        currency = position.currency if position else "EUR"

        # Categorize: averaging_down if buying below cost, else rebalance_buys
        if position and position.avg_price and position.avg_price > price:
            tags = ["averaging_down", "optimizer_target"]
        else:
            tags = ["rebalance", "optimizer_target"]

        # Apply priority multiplier: higher multiplier = higher buy priority
        base_priority = abs(gap_info["gap"]) * 100
        security_multiplier = security.priority_multiplier if security else 1.0
        final_priority = base_priority * security_multiplier

        return ActionCandidate(
            side=TradeSide.BUY,
            symbol=symbol,
            name=security.name if security else symbol,
            quantity=quantity,
            price=price,
            value_eur=trade_value,
            currency=currency,
            priority=final_priority,
            reason=f"Optimizer target: {gap_info['target']:.1%} (current: {gap_info['current']:.1%})",
            tags=tags,
        )

    def _process_sell_opportunity(
        self,
        gap_info: Dict[str, Any],
        security: Optional[Security],
        position: Position,
        price: float,
    ) -> Optional[ActionCandidate]:
        """Process a sell opportunity from weight gap."""
        if not position:
            return None

        if security and not security.allow_sell:
            return None

        # Don't sell if at minimum lot size
        if security and position.quantity <= (security.min_lot or 0):
            return None

        symbol = gap_info["symbol"]
        gap_value = gap_info["gap_value"]
        sell_value = abs(gap_value)
        quantity = int(sell_value / price)

        # Ensure we don't go below min_lot
        if security and security.min_lot:
            remaining = position.quantity - quantity
            if remaining < security.min_lot and remaining > 0:
                quantity = int(position.quantity - security.min_lot)

        if quantity <= 0:
            return None

        trade_value = quantity * price

        # Apply priority multiplier inversely: higher multiplier = lower sell priority
        base_priority = abs(gap_info["gap"]) * 100
        security_multiplier = security.priority_multiplier if security else 1.0
        final_priority = base_priority / security_multiplier

        return ActionCandidate(
            side=TradeSide.SELL,
            symbol=symbol,
            name=security.name if security else symbol,
            quantity=quantity,
            price=price,
            value_eur=trade_value,
            currency=position.currency,
            priority=final_priority,
            reason=f"Optimizer target: {gap_info['target']:.1%} (current: {gap_info['current']:.1%})",
            tags=["rebalance", "optimizer_target"],
        )


# Auto-register this calculator
_weight_based_calculator = WeightBasedCalculator()
opportunity_calculator_registry.register(
    _weight_based_calculator.name, _weight_based_calculator
)
