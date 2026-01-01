"""Portfolio simulation functions.

Simulates the execution of action sequences to predict portfolio end states.
"""

from typing import Dict, List, Optional, Tuple

from app.domain.models import Security
from app.domain.value_objects.trade_side import TradeSide
from app.modules.planning.domain.calculations.context import EvaluationContext
from app.modules.planning.domain.models import ActionCandidate
from app.modules.scoring.domain.models import PortfolioContext


async def simulate_sequence(
    sequence: List[ActionCandidate],
    portfolio_context: PortfolioContext,
    available_cash: float,
    securities: List[Security],
    price_adjustments: Optional[Dict[str, float]] = None,
) -> Tuple[PortfolioContext, float]:
    """
    Simulate executing a sequence and return the resulting portfolio state.

    This function applies each action in the sequence to the portfolio,
    updating positions and cash. It supports price adjustments for
    stochastic evaluation scenarios.

    Args:
        sequence: List of actions to execute in order
        portfolio_context: Starting portfolio state
        available_cash: Starting cash in EUR
        securities: Available securities for metadata lookup
        price_adjustments: Optional dict mapping symbol -> price multiplier
                          (e.g., 1.05 for +5% price increase)

    Returns:
        Tuple of (final_portfolio_context, final_cash_eur)
    """
    securities_by_symbol = {s.symbol: s for s in securities}
    current_context = portfolio_context
    current_cash = available_cash

    for action in sequence:
        security = securities_by_symbol.get(action.symbol)
        country = security.country if security else None
        industry = security.industry if security else None

        # Apply price adjustment if provided (for stochastic scenarios)
        adjusted_price = action.price
        adjusted_value_eur = action.value_eur
        if price_adjustments and action.symbol in price_adjustments:
            multiplier = price_adjustments[action.symbol]
            adjusted_price = action.price * multiplier
            # Recalculate value with adjusted price (maintain same quantity)
            adjusted_value_eur = abs(action.quantity) * adjusted_price
            # Note: Currency conversion would happen here if needed

        # Copy-on-write optimization: Only copy dicts we're about to modify
        # This reduces memory allocations significantly for long sequences
        new_positions = current_context.positions.copy()
        # Geography/industry only modified for BUY, so delay copy until needed
        new_geographies = current_context.security_countries or {}
        new_industries = current_context.security_industries or {}

        if action.side == TradeSide.SELL:
            # Reduce position (cash is PART of portfolio, so total doesn't change)
            # Use adjusted value if price adjustments provided
            sell_value = (
                adjusted_value_eur
                if price_adjustments and action.symbol in price_adjustments
                else action.value_eur
            )
            current_value = new_positions.get(action.symbol, 0)
            new_positions[action.symbol] = max(0, current_value - sell_value)
            if new_positions[action.symbol] <= 0:
                new_positions.pop(action.symbol, None)
            current_cash += sell_value
            # Total portfolio value stays the same - we just converted security to cash
            new_total = current_context.total_value
        else:  # BUY
            # Use adjusted value if price adjustments provided
            buy_value = (
                adjusted_value_eur
                if price_adjustments and action.symbol in price_adjustments
                else action.value_eur
            )
            if buy_value > current_cash:
                continue  # Skip if can't afford
            new_positions[action.symbol] = (
                new_positions.get(action.symbol, 0) + buy_value
            )
            # Copy geography/industry dicts now that we know we're modifying them
            if country or industry:
                new_geographies = new_geographies.copy()
                new_industries = new_industries.copy()
                if country:
                    new_geographies[action.symbol] = country
                if industry:
                    new_industries[action.symbol] = industry
            current_cash -= buy_value
            # Total portfolio value stays the same - we just converted cash to security
            new_total = current_context.total_value

        # Create new context with updated positions
        current_context = PortfolioContext(
            country_weights=current_context.country_weights,
            industry_weights=current_context.industry_weights,
            positions=new_positions,
            total_value=new_total,
            security_countries=new_geographies,
            security_industries=new_industries,
            security_scores=current_context.security_scores,
            security_dividends=current_context.security_dividends,
        )

    return current_context, current_cash


async def simulate_sequence_with_context(
    sequence: List[ActionCandidate],
    context: EvaluationContext,
) -> Tuple[PortfolioContext, float]:
    """
    Simulate sequence using EvaluationContext.

    Convenience wrapper around simulate_sequence that extracts parameters
    from the evaluation context.

    Args:
        sequence: List of actions to execute
        context: Evaluation context with portfolio state and configuration

    Returns:
        Tuple of (final_portfolio_context, final_cash_eur)
    """
    return await simulate_sequence(
        sequence=sequence,
        portfolio_context=context.portfolio_context,
        available_cash=context.available_cash_eur,
        securities=context.securities,
        price_adjustments=context.price_adjustments,
    )


def check_sequence_feasibility(
    sequence: List[ActionCandidate],
    available_cash: float,
    portfolio_context: PortfolioContext,
) -> bool:
    """
    Quick check if sequence is feasible without full simulation.

    Checks if we have enough cash to execute all buys in the sequence.
    This is a fast pre-filter before expensive simulation.

    Args:
        sequence: List of actions to check
        available_cash: Available cash in EUR
        portfolio_context: Current portfolio state

    Returns:
        True if sequence is feasible, False otherwise
    """
    cash = available_cash

    # Check in sequence order (sells first, then buys)
    for action in sequence:
        if action.side == TradeSide.SELL:
            # Sells add cash
            cash += action.value_eur
        else:  # BUY
            # Buys consume cash
            if action.value_eur > cash:
                return False  # Not enough cash for this buy
            cash -= action.value_eur

    return True


def calculate_sequence_cash_flow(sequence: List[ActionCandidate]) -> Dict[str, float]:
    """
    Calculate cash flow summary for a sequence.

    Args:
        sequence: List of actions

    Returns:
        Dict with keys:
        - cash_generated: Total from sells
        - cash_required: Total for buys
        - net_cash_flow: Difference (positive = net inflow)
    """
    cash_generated = 0.0
    cash_required = 0.0

    for action in sequence:
        if action.side == TradeSide.SELL:
            cash_generated += action.value_eur
        else:  # BUY
            cash_required += action.value_eur

    return {
        "cash_generated": cash_generated,
        "cash_required": cash_required,
        "net_cash_flow": cash_generated - cash_required,
    }
