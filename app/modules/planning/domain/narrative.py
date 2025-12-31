"""
Narrative Generator - Creates human-readable explanations for trading actions.

This module generates clear, contextual explanations for:
- Individual trade actions (buy/sell)
- Overall plan strategy
- Trade-off reasoning ("selling X is individually suboptimal, but enables Y")

The narratives help users understand the "why" behind each recommendation,
making the holistic planner's decisions transparent and educational.
"""

import logging
from typing import TYPE_CHECKING, Dict, List, Optional

if TYPE_CHECKING:
    from app.modules.planning.domain.holistic_planner import (
        ActionCandidate,
        HolisticStep,
    )
    from app.modules.scoring.domain.models import PortfolioContext

logger = logging.getLogger(__name__)


def _add_strategy_summary(
    parts: list, windfall_sells: list, averaging_buys: list, sells: list, buys: list
) -> None:
    """Add strategy summary to narrative parts."""
    if windfall_sells and averaging_buys:
        parts.append(
            "This plan takes profits from windfall gains and reinvests in quality stocks "
            "that are temporarily down."
        )
    elif windfall_sells:
        parts.append(
            "This plan captures windfall profits from positions that have exceeded "
            "their historical growth rates."
        )
    elif averaging_buys:
        parts.append(
            "This plan focuses on averaging down on quality positions that are "
            "temporarily undervalued."
        )
    elif sells and buys:
        parts.append(
            "This plan rebalances the portfolio by trimming overweight positions "
            "and adding to underweight areas."
        )
    elif buys:
        parts.append(
            "This plan deploys available cash into high-quality opportunities."
        )
    elif sells:
        parts.append(
            "This plan reduces risk by taking profits from selected positions."
        )


def _add_step_summary(parts: list, steps: list, sells: list, buys: list) -> None:
    """Add step summary to narrative parts."""
    parts.append(f"The plan consists of {len(steps)} action(s):")

    if sells:
        total_sell = sum(s.estimated_value for s in sells)
        sell_symbols = [s.symbol for s in sells]
        parts.append(f"• Sell €{total_sell:.0f} from {', '.join(sell_symbols)}")

    if buys:
        total_buy = sum(s.estimated_value for s in buys)
        buy_symbols = [s.symbol for s in buys]
        parts.append(f"• Buy €{total_buy:.0f} in {', '.join(buy_symbols)}")


def _add_expected_outcome(
    parts: list, improvement: float, current_score: float, end_score: float
) -> None:
    """Add expected outcome to narrative parts."""
    if improvement > 0:
        parts.append(
            f"Expected portfolio improvement: +{improvement:.1f} points "
            f"(from {current_score:.1f} to {end_score:.1f})."
        )
    elif improvement < 0:
        parts.append(
            f"Note: Short-term score may decrease by {abs(improvement):.1f} points, "
            f"but this positions the portfolio for better long-term growth."
        )
    else:
        parts.append(
            f"This maintains the current portfolio score of {current_score:.1f} "
            f"while improving diversification."
        )


def generate_step_narrative(
    action: "ActionCandidate",
    portfolio_context: "PortfolioContext",
    all_opportunities: Dict[str, List["ActionCandidate"]],
) -> str:
    """
    Generate a human-readable narrative for a single action.

    The narrative explains:
    - What the action is
    - Why it's being recommended
    - How it fits into the broader strategy

    Args:
        action: The action being explained
        portfolio_context: Current portfolio state
        all_opportunities: All identified opportunities for context

    Returns:
        Human-readable explanation string
    """
    from app.domain.value_objects.trade_side import TradeSide

    symbol = action.symbol
    name = action.name
    side = action.side
    tags = action.tags
    reason = action.reason

    # Build the narrative based on action type and tags
    if side == TradeSide.SELL:
        # Calculate percentage of position being sold
        # Get current position value from portfolio context
        current_position_value = portfolio_context.positions.get(symbol, 0)
        sell_percentage = None
        if current_position_value > 0 and action.value_eur > 0:
            sell_percentage = (action.value_eur / current_position_value) * 100

        narrative = _generate_sell_narrative(
            symbol,
            name,
            action.value_eur,
            tags,
            reason,
            portfolio_context,
            all_opportunities,
            sell_percentage=sell_percentage,
        )
    else:
        narrative = _generate_buy_narrative(
            symbol,
            name,
            action.value_eur,
            tags,
            reason,
            portfolio_context,
            all_opportunities,
        )

    return narrative


def _generate_sell_narrative(
    symbol: str,
    name: str,
    value: float,
    tags: List[str],
    reason: str,
    portfolio_context: "PortfolioContext",
    all_opportunities: Dict,
    sell_percentage: Optional[float] = None,
) -> str:
    """Generate narrative for a sell action."""
    if sell_percentage is not None:
        parts = [f"Sell {sell_percentage:.0f}% / €{value:.0f} of {name} ({symbol})"]
    else:
        parts = [f"Sell €{value:.0f} of {name} ({symbol})"]

    # Explain the primary reason
    if "windfall" in tags:
        parts.append(
            f"This position has experienced windfall gains beyond normal growth. {reason}."
        )
        parts.append(
            "Taking profits locks in gains and frees capital for better opportunities."
        )

    elif "profit_taking" in tags:
        parts.append(f"Reason: {reason}.")
        parts.append("This reduces risk by converting paper gains to realized profits.")

    elif "rebalance" in tags:
        # Find which geography is overweight
        overweight_geo = None
        for tag in tags:
            if tag.startswith("overweight_"):
                overweight_geo = tag.replace("overweight_", "").upper()
                break

        if overweight_geo:
            parts.append(f"The portfolio is overweight in {overweight_geo} region.")
            parts.append("Trimming this position improves country diversification.")
        else:
            parts.append(f"Reason: {reason}.")

    else:
        parts.append(f"Reason: {reason}.")

    # Add context about what the freed cash enables
    buy_opportunities = (
        all_opportunities.get("averaging_down", [])
        + all_opportunities.get("rebalance_buys", [])
        + all_opportunities.get("opportunity_buys", [])
    )

    if buy_opportunities:
        top_buy = buy_opportunities[0]
        parts.append(
            f"This frees capital to invest in {top_buy.name}, "
            f"which offers better risk-adjusted returns."
        )

    return " ".join(parts)


def _generate_buy_narrative(
    symbol: str,
    name: str,
    value: float,
    tags: List[str],
    reason: str,
    portfolio_context: "PortfolioContext",
    all_opportunities: Dict,
) -> str:
    """Generate narrative for a buy action."""
    parts = [f"Buy €{value:.0f} of {name} ({symbol})"]

    # Explain based on tags
    if "averaging_down" in tags:
        parts.append(
            "This quality stock is temporarily down, presenting an opportunity to "
            "lower the average cost basis."
        )
        parts.append(f"{reason}.")
        parts.append("Averaging down on quality dips is a proven long-term strategy.")

    elif "rebalance" in tags:
        # Find which geography is underweight
        underweight_geo = None
        for tag in tags:
            if tag.startswith("underweight_"):
                underweight_geo = tag.replace("underweight_", "").upper()
                break

        if underweight_geo:
            parts.append(f"The portfolio is underweight in {underweight_geo} region.")
            parts.append(
                "This purchase improves country diversification and reduces concentration risk."
            )
        else:
            parts.append(f"Reason: {reason}.")

    elif "quality" in tags or "opportunity" in tags:
        parts.append(f"{reason}.")
        parts.append(
            "High-quality stocks with good fundamentals tend to outperform over the long term."
        )

    else:
        parts.append(f"Reason: {reason}.")

    # Add dividend context if relevant
    dividend_yield = (
        portfolio_context.security_dividends.get(symbol, 0)
        if portfolio_context.security_dividends
        else 0
    )
    if dividend_yield and dividend_yield > 0.03:
        parts.append(
            f"This stock also provides a {dividend_yield*100:.1f}% dividend yield for income."
        )

    return " ".join(parts)


def generate_plan_narrative(
    steps: List["HolisticStep"],
    current_score: float,
    end_score: float,
    all_opportunities: Dict,
) -> str:
    """
    Generate an overall narrative summarizing the plan.

    Args:
        steps: List of planned actions
        current_score: Current portfolio score
        end_score: Projected end-state score
        all_opportunities: All identified opportunities

    Returns:
        Summary narrative explaining the overall strategy
    """
    from app.domain.value_objects.trade_side import TradeSide

    if not steps:
        return "No actions recommended. The portfolio is well-positioned."

    # Count action types
    sells = [s for s in steps if s.side == TradeSide.SELL]
    buys = [s for s in steps if s.side == TradeSide.BUY]
    windfall_sells = [s for s in sells if s.is_windfall]
    averaging_buys = [s for s in buys if s.is_averaging_down]

    improvement = end_score - current_score

    parts: list[str] = []
    _add_strategy_summary(parts, windfall_sells, averaging_buys, sells, buys)
    _add_step_summary(parts, steps, sells, buys)
    _add_expected_outcome(parts, improvement, current_score, end_score)

    return " ".join(parts)


def generate_tradeoff_explanation(
    action: "ActionCandidate",
    individual_impact: float,
    sequence_impact: float,
) -> str:
    """
    Generate explanation for trade-offs where an individually negative
    action contributes to a positive overall outcome.

    Example: "Selling AAPL alone would reduce the score by 2 points,
    but it enables buying BABA which improves the score by 5 points."

    Args:
        action: The action being explained
        individual_impact: Score change from this action alone
        sequence_impact: Score change from the full sequence

    Returns:
        Trade-off explanation string
    """
    from app.domain.value_objects.trade_side import TradeSide

    if individual_impact >= 0:
        return ""  # No trade-off to explain

    if sequence_impact <= individual_impact:
        return ""  # Sequence doesn't improve on individual

    action_verb = "Selling" if action.side == TradeSide.SELL else "Buying"

    explanation = (
        f"{action_verb} {action.name} in isolation would "
        f"{'reduce' if individual_impact < 0 else 'increase'} the portfolio score "
        f"by {abs(individual_impact):.1f} points. However, as part of this sequence, "
        f"it enables an overall improvement of {sequence_impact:.1f} points. "
        f"The short-term sacrifice creates a better long-term outcome."
    )

    return explanation


def format_action_summary(action: "ActionCandidate") -> str:
    """
    Format a brief one-line summary of an action.

    Args:
        action: The action to summarize

    Returns:
        One-line summary string
    """
    from app.domain.value_objects.trade_side import TradeSide

    if action.side == TradeSide.SELL:
        return f"SELL {action.quantity} {action.symbol} @ €{action.price:.2f} = €{action.value_eur:.0f}"
    else:
        return f"BUY {action.quantity} {action.symbol} @ €{action.price:.2f} = €{action.value_eur:.0f}"
