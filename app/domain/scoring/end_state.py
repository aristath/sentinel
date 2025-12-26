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

    # Get consistency score from cache if not provided
    if consistency_score is None:
        cached = await calc_repo.get_metric(symbol, "CONSISTENCY_SCORE")
        consistency_score = cached if cached is not None else 0.5

    # Get financial strength from cache if not provided
    if financial_strength is None:
        cached = await calc_repo.get_metric(symbol, "FINANCIAL_STRENGTH")
        financial_strength = cached if cached is not None else 0.5

    # Get dividend consistency - derive from payout ratio if not provided
    if dividend_consistency is None:
        cached = await calc_repo.get_metric(symbol, "DIVIDEND_CONSISTENCY")
        if cached is not None:
            dividend_consistency = cached
        else:
            # Derive from payout ratio
            payout = await calc_repo.get_metric(symbol, "PAYOUT_RATIO")
            if payout is not None:
                # Ideal payout: 30-60%
                if 0.3 <= payout <= 0.6:
                    dividend_consistency = 1.0
                elif payout < 0.3:
                    dividend_consistency = 0.5 + (payout / 0.3) * 0.5
                elif payout <= 0.8:
                    dividend_consistency = 1.0 - ((payout - 0.6) / 0.2) * 0.3
                else:
                    dividend_consistency = 0.4
            else:
                dividend_consistency = 0.5

    # Get Sortino score from cache if not provided
    if sortino_score is None:
        sortino = await calc_repo.get_metric(symbol, "SORTINO")
        if sortino is not None:
            # Convert ratio to score
            if sortino >= 2.0:
                sortino_score = 1.0
            elif sortino >= 1.5:
                sortino_score = 0.8 + (sortino - 1.5) * 0.4
            elif sortino >= 1.0:
                sortino_score = 0.6 + (sortino - 1.0) * 0.4
            elif sortino >= 0:
                sortino_score = sortino * 0.6
            else:
                sortino_score = 0.0
        else:
            sortino_score = 0.5

    # Calculate weighted total
    total = (
        consistency_score * PROMISE_WEIGHT_CONSISTENCY
        + financial_strength * PROMISE_WEIGHT_FINANCIALS
        + dividend_consistency * PROMISE_WEIGHT_DIVIDEND_STABILITY
        + sortino_score * PROMISE_WEIGHT_SORTINO
    )

    # Cache the result
    await calc_repo.set_metric(symbol, "LONG_TERM_PROMISE", total)

    sub_components = {
        "consistency": round(consistency_score, 3),
        "financial_strength": round(financial_strength, 3),
        "dividend_consistency": round(dividend_consistency, 3),
        "sortino": round(sortino_score, 3),
    }

    return round(min(1.0, total), 3), sub_components


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

    # Get volatility and convert to score (inverse - lower is better)
    if volatility is None:
        volatility = await calc_repo.get_metric(symbol, "VOLATILITY_ANNUAL")

    if volatility is not None and volatility > 0:
        # Typical annual volatility: 15-40%
        # Score: 30% vol = 0.5, 15% vol = 1.0, 50% vol = 0.2
        if volatility <= 0.15:
            volatility_score = 1.0
        elif volatility <= 0.25:
            volatility_score = 1.0 - ((volatility - 0.15) / 0.10) * 0.3
        elif volatility <= 0.40:
            volatility_score = 0.7 - ((volatility - 0.25) / 0.15) * 0.4
        else:
            volatility_score = max(0.1, 0.3 - (volatility - 0.40))
    else:
        volatility_score = 0.5

    # Get drawdown score from cache if not provided
    if drawdown_score is None:
        max_dd = await calc_repo.get_metric(symbol, "MAX_DRAWDOWN")
        if max_dd is not None:
            dd_pct = abs(max_dd)
            if dd_pct <= 0.10:
                drawdown_score = 1.0
            elif dd_pct <= 0.20:
                drawdown_score = 0.8 + (0.20 - dd_pct) * 2
            elif dd_pct <= 0.30:
                drawdown_score = 0.6 + (0.30 - dd_pct) * 2
            elif dd_pct <= 0.50:
                drawdown_score = 0.2 + (0.50 - dd_pct) * 2
            else:
                drawdown_score = max(0.0, 0.2 - (dd_pct - 0.50))
        else:
            drawdown_score = 0.5

    # Get Sharpe score from cache if not provided
    if sharpe_score is None:
        sharpe = await calc_repo.get_metric(symbol, "SHARPE")
        if sharpe is not None:
            if sharpe >= 2.0:
                sharpe_score = 1.0
            elif sharpe >= 1.0:
                sharpe_score = 0.7 + (sharpe - 1.0) * 0.3
            elif sharpe >= 0.5:
                sharpe_score = 0.4 + (sharpe - 0.5) * 0.6
            elif sharpe >= 0:
                sharpe_score = sharpe * 0.8
            else:
                sharpe_score = 0.0
        else:
            sharpe_score = 0.5

    # Calculate weighted total
    total = (
        volatility_score * STABILITY_WEIGHT_VOLATILITY
        + drawdown_score * STABILITY_WEIGHT_DRAWDOWN
        + sharpe_score * STABILITY_WEIGHT_SHARPE
    )

    # Cache the result
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
        return 0.5, {"error": "Invalid portfolio data"}

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
