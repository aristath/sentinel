"""
End-State Scoring - Portfolio-level scoring for holistic planning.

This module provides scoring functions that evaluate the overall health
of a portfolio after a sequence of trades, focusing on:
- Total Return (CAGR + dividends combined)
- Long-term Promise (consistency, financials, dividend stability)
- Stability (low volatility, minimal drawdown)

Used by the holistic planner to evaluate and compare action sequences.
"""

import logging
from typing import Dict, Optional, Tuple

# Import scorer from dedicated module
from app.domain.scoring.scorers.end_state import score_total_return

logger = logging.getLogger(__name__)

# End-state scoring weights
WEIGHT_TOTAL_RETURN = 0.35
WEIGHT_DIVERSIFICATION = 0.25
WEIGHT_LONG_TERM_PROMISE = 0.20
WEIGHT_STABILITY = 0.15
WEIGHT_OPINION = 0.05

# Long-term promise sub-weights
PROMISE_WEIGHT_CONSISTENCY = 0.35
PROMISE_WEIGHT_FINANCIALS = 0.25
PROMISE_WEIGHT_DIVIDEND_STABILITY = 0.25
PROMISE_WEIGHT_SORTINO = 0.15

# Stability sub-weights
STABILITY_WEIGHT_VOLATILITY = 0.50
STABILITY_WEIGHT_DRAWDOWN = 0.30
STABILITY_WEIGHT_SHARPE = 0.20


async def calculate_total_return_score(
    symbol: str,
    cagr: Optional[float] = None,
    dividend_yield: Optional[float] = None,
) -> Tuple[float, Dict[str, float]]:
    """
    Calculate total return score (CAGR + dividend yield combined).

    Args:
        symbol: Stock symbol (for cache lookup)
        cagr: Pre-calculated CAGR (optional, will fetch from cache)
        dividend_yield: Pre-calculated dividend yield (optional)

    Returns:
        Tuple of (total_score, sub_components_dict)
    """
    from app.repositories.calculations import CalculationsRepository

    calc_repo = CalculationsRepository()

    # Get CAGR from cache if not provided
    if cagr is None:
        cagr = await calc_repo.get_metric(symbol, "CAGR_5Y")
    if cagr is None:
        cagr = 0.0

    # Get dividend yield from cache if not provided
    if dividend_yield is None:
        dividend_yield = await calc_repo.get_metric(symbol, "DIVIDEND_YIELD")
    if dividend_yield is None:
        dividend_yield = 0.0

    # Calculate total return
    total_return = cagr + dividend_yield

    # Cache the total return
    await calc_repo.set_metric(symbol, "TOTAL_RETURN", total_return)

    # Score it
    score = score_total_return(total_return)

    sub_components = {
        "cagr": round(cagr, 4),
        "dividend_yield": round(dividend_yield, 4),
        "total_return": round(total_return, 4),
        "score": round(score, 3),
    }

    return round(score, 3), sub_components


async def _get_consistency_score(
    calc_repo, symbol: str, provided: Optional[float]
) -> float:
    """Get consistency score from cache or use provided value."""
    if provided is not None:
        return provided
    cached = await calc_repo.get_metric(symbol, "CONSISTENCY_SCORE")
    return cached if cached is not None else 0.5


async def _get_financial_strength(
    calc_repo, symbol: str, provided: Optional[float]
) -> float:
    """Get financial strength from cache or use provided value."""
    if provided is not None:
        return provided
    cached = await calc_repo.get_metric(symbol, "FINANCIAL_STRENGTH")
    return cached if cached is not None else 0.5


def _derive_dividend_consistency_from_payout(payout: float) -> float:
    """Derive dividend consistency score from payout ratio."""
    if 0.3 <= payout <= 0.6:
        return 1.0
    elif payout < 0.3:
        return 0.5 + (payout / 0.3) * 0.5
    elif payout <= 0.8:
        return 1.0 - ((payout - 0.6) / 0.2) * 0.3
    else:
        return 0.4


async def _get_dividend_consistency(
    calc_repo, symbol: str, provided: Optional[float]
) -> float:
    """Get dividend consistency from cache, derive from payout, or use provided value."""
    if provided is not None:
        return provided

    cached = await calc_repo.get_metric(symbol, "DIVIDEND_CONSISTENCY")
    if cached is not None:
        return cached

    payout = await calc_repo.get_metric(symbol, "PAYOUT_RATIO")
    if payout is not None:
        return _derive_dividend_consistency_from_payout(payout)

    return 0.5


def _convert_sortino_to_score(sortino: float) -> float:
    """Convert Sortino ratio to score (0-1)."""
    if sortino >= 2.0:
        return 1.0
    elif sortino >= 1.5:
        return 0.8 + (sortino - 1.5) * 0.4
    elif sortino >= 1.0:
        return 0.6 + (sortino - 1.0) * 0.4
    elif sortino >= 0:
        return sortino * 0.6
    else:
        return 0.0


async def _get_sortino_score(
    calc_repo, symbol: str, provided: Optional[float]
) -> float:
    """Get Sortino score from cache (converted) or use provided value."""
    if provided is not None:
        return provided

    sortino = await calc_repo.get_metric(symbol, "SORTINO")
    if sortino is not None:
        return _convert_sortino_to_score(sortino)

    return 0.5


async def calculate_long_term_promise(
    symbol: str,
    consistency_score: Optional[float] = None,
    financial_strength: Optional[float] = None,
    dividend_consistency: Optional[float] = None,
    sortino_score: Optional[float] = None,
) -> Tuple[float, Dict[str, float]]:
    """
    Calculate long-term promise score.

    Combines:
    - Consistency (35%): 5Y vs 10Y CAGR similarity
    - Financial Strength (25%): Margins, debt, liquidity
    - Dividend Consistency (25%): No big cuts, sustainable payout
    - Sortino (15%): Good returns with low downside risk

    Args:
        symbol: Stock symbol (for cache lookup)
        consistency_score: Pre-calculated consistency (optional)
        financial_strength: Pre-calculated financial strength (optional)
        dividend_consistency: Pre-calculated dividend consistency (optional)
        sortino_score: Pre-calculated Sortino score (optional)

    Returns:
        Tuple of (total_score, sub_components_dict)
    """
    from app.repositories.calculations import CalculationsRepository

    calc_repo = CalculationsRepository()

    consistency_score = await _get_consistency_score(
        calc_repo, symbol, consistency_score
    )
    financial_strength = await _get_financial_strength(
        calc_repo, symbol, financial_strength
    )
    dividend_consistency = await _get_dividend_consistency(
        calc_repo, symbol, dividend_consistency
    )
    sortino_score = await _get_sortino_score(calc_repo, symbol, sortino_score)

    total = (
        consistency_score * PROMISE_WEIGHT_CONSISTENCY
        + financial_strength * PROMISE_WEIGHT_FINANCIALS
        + dividend_consistency * PROMISE_WEIGHT_DIVIDEND_STABILITY
        + sortino_score * PROMISE_WEIGHT_SORTINO
    )

    await calc_repo.set_metric(symbol, "LONG_TERM_PROMISE", total)

    sub_components = {
        "consistency": round(consistency_score, 3),
        "financial_strength": round(financial_strength, 3),
        "dividend_consistency": round(dividend_consistency, 3),
        "sortino": round(sortino_score, 3),
    }

    return round(min(1.0, total), 3), sub_components


def _convert_volatility_to_score(volatility: float) -> float:
    """Convert volatility to score (inverse - lower is better)."""
    if volatility <= 0.15:
        return 1.0
    elif volatility <= 0.25:
        return 1.0 - ((volatility - 0.15) / 0.10) * 0.3
    elif volatility <= 0.40:
        return 0.7 - ((volatility - 0.25) / 0.15) * 0.4
    else:
        return max(0.1, 0.3 - (volatility - 0.40))


async def _get_volatility_score(
    calc_repo, symbol: str, provided: Optional[float]
) -> float:
    """Get volatility score from cache or use provided value."""
    if provided is not None:
        return _convert_volatility_to_score(provided)

    volatility = await calc_repo.get_metric(symbol, "VOLATILITY_ANNUAL")
    if volatility is not None and volatility > 0:
        return _convert_volatility_to_score(volatility)

    return 0.5


def _convert_drawdown_to_score(max_dd: float) -> float:
    """Convert max drawdown to score."""
    dd_pct = abs(max_dd)
    if dd_pct <= 0.10:
        return 1.0
    elif dd_pct <= 0.20:
        return 0.8 + (0.20 - dd_pct) * 2
    elif dd_pct <= 0.30:
        return 0.6 + (0.30 - dd_pct) * 2
    elif dd_pct <= 0.50:
        return 0.2 + (0.50 - dd_pct) * 2
    else:
        return max(0.0, 0.2 - (dd_pct - 0.50))


async def _get_drawdown_score(
    calc_repo, symbol: str, provided: Optional[float]
) -> float:
    """Get drawdown score from cache or use provided value."""
    if provided is not None:
        return provided

    max_dd = await calc_repo.get_metric(symbol, "MAX_DRAWDOWN")
    if max_dd is not None:
        return _convert_drawdown_to_score(max_dd)

    return 0.5


def _convert_sharpe_to_score(sharpe: float) -> float:
    """Convert Sharpe ratio to score."""
    if sharpe >= 2.0:
        return 1.0
    elif sharpe >= 1.0:
        return 0.7 + (sharpe - 1.0) * 0.3
    elif sharpe >= 0.5:
        return 0.4 + (sharpe - 0.5) * 0.6
    elif sharpe >= 0:
        return sharpe * 0.8
    else:
        return 0.0


async def _get_sharpe_score(calc_repo, symbol: str, provided: Optional[float]) -> float:
    """Get Sharpe score from cache (converted) or use provided value."""
    if provided is not None:
        return provided

    sharpe = await calc_repo.get_metric(symbol, "SHARPE")
    if sharpe is not None:
        return _convert_sharpe_to_score(sharpe)

    return 0.5


async def calculate_stability_score(
    symbol: str,
    volatility: Optional[float] = None,
    drawdown_score: Optional[float] = None,
    sharpe_score: Optional[float] = None,
) -> Tuple[float, Dict[str, float]]:
    """
    Calculate stability score.

    Combines:
    - Inverse Volatility (50%): Lower volatility = higher score
    - Drawdown Score (30%): Lower max drawdown = higher score
    - Sharpe Score (20%): Higher risk-adjusted returns = higher score

    Args:
        symbol: Stock symbol (for cache lookup)
        volatility: Pre-calculated annualized volatility (optional)
        drawdown_score: Pre-calculated drawdown score (optional)
        sharpe_score: Pre-calculated Sharpe score (optional)

    Returns:
        Tuple of (total_score, sub_components_dict)
    """
    from app.repositories.calculations import CalculationsRepository

    calc_repo = CalculationsRepository()

    volatility_score = await _get_volatility_score(calc_repo, symbol, volatility)
    drawdown_score = await _get_drawdown_score(calc_repo, symbol, drawdown_score)
    sharpe_score = await _get_sharpe_score(calc_repo, symbol, sharpe_score)

    total = (
        volatility_score * STABILITY_WEIGHT_VOLATILITY
        + drawdown_score * STABILITY_WEIGHT_DRAWDOWN
        + sharpe_score * STABILITY_WEIGHT_SHARPE
    )

    await calc_repo.set_metric(symbol, "STABILITY_SCORE", total)

    sub_components = {
        "volatility": round(volatility_score, 3),
        "drawdown": round(drawdown_score, 3),
        "sharpe": round(sharpe_score, 3),
    }

    return round(min(1.0, total), 3), sub_components


async def calculate_portfolio_end_state_score(
    positions: Dict[str, float],
    total_value: float,
    diversification_score: float,
    opinion_score: float = 0.5,
) -> Tuple[float, Dict[str, float]]:
    """
    Calculate end-state score for an entire portfolio.

    This is the main function used by the holistic planner to evaluate
    the quality of a portfolio after executing a sequence of trades.

    Args:
        positions: Dict of symbol -> position value in EUR
        total_value: Total portfolio value in EUR
        diversification_score: Pre-calculated diversification score (0-1)
        opinion_score: Average analyst opinion score (default 0.5)

    Returns:
        Tuple of (total_score, detailed_breakdown)
    """
    if total_value <= 0 or not positions:
        return 0.5, {"error": "Invalid portfolio data"}  # type: ignore[dict-item]

    # Calculate weighted averages across all positions
    weighted_total_return = 0.0
    weighted_promise = 0.0
    weighted_stability = 0.0

    total_return_details = {}
    promise_details = {}
    stability_details = {}

    for symbol, value in positions.items():
        if value <= 0:
            continue

        weight = value / total_value

        # Get scores for this position
        tr_score, tr_subs = await calculate_total_return_score(symbol)
        promise_score, promise_subs = await calculate_long_term_promise(symbol)
        stab_score, stab_subs = await calculate_stability_score(symbol)

        weighted_total_return += tr_score * weight
        weighted_promise += promise_score * weight
        weighted_stability += stab_score * weight

        # Store details for transparency
        total_return_details[symbol] = {"score": tr_score, "weight": round(weight, 3)}
        promise_details[symbol] = {"score": promise_score, "weight": round(weight, 3)}
        stability_details[symbol] = {"score": stab_score, "weight": round(weight, 3)}

    # Calculate final end-state score
    end_state_score = (
        weighted_total_return * WEIGHT_TOTAL_RETURN
        + diversification_score * WEIGHT_DIVERSIFICATION
        + weighted_promise * WEIGHT_LONG_TERM_PROMISE
        + weighted_stability * WEIGHT_STABILITY
        + opinion_score * WEIGHT_OPINION
    )

    detailed_breakdown = {
        "total_return": {
            "weighted_score": round(weighted_total_return, 3),
            "weight": WEIGHT_TOTAL_RETURN,
            "contribution": round(weighted_total_return * WEIGHT_TOTAL_RETURN, 3),
        },
        "diversification": {
            "score": round(diversification_score, 3),
            "weight": WEIGHT_DIVERSIFICATION,
            "contribution": round(diversification_score * WEIGHT_DIVERSIFICATION, 3),
        },
        "long_term_promise": {
            "weighted_score": round(weighted_promise, 3),
            "weight": WEIGHT_LONG_TERM_PROMISE,
            "contribution": round(weighted_promise * WEIGHT_LONG_TERM_PROMISE, 3),
        },
        "stability": {
            "weighted_score": round(weighted_stability, 3),
            "weight": WEIGHT_STABILITY,
            "contribution": round(weighted_stability * WEIGHT_STABILITY, 3),
        },
        "opinion": {
            "score": round(opinion_score, 3),
            "weight": WEIGHT_OPINION,
            "contribution": round(opinion_score * WEIGHT_OPINION, 3),
        },
        "end_state_score": round(end_state_score, 3),
    }

    return round(min(1.0, end_state_score), 3), detailed_breakdown
