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
    metrics: Dict[str, float],
) -> Tuple[float, Dict[str, float]]:
    """
    Calculate total return score (CAGR + dividend yield combined).

    Args:
        symbol: Stock symbol (for reference only, not used for DB queries)
        metrics: Pre-fetched metrics dict containing CAGR_5Y and DIVIDEND_YIELD

    Returns:
        Tuple of (total_score, sub_components_dict)
    """
    # Get CAGR from metrics dict
    cagr = metrics.get("CAGR_5Y")
    if cagr is None:
        cagr = 0.0

    # Get dividend yield from metrics dict
    dividend_yield = metrics.get("DIVIDEND_YIELD")
    if dividend_yield is None:
        dividend_yield = 0.0

    # Calculate total return
    total_return = cagr + dividend_yield

    # Score it
    score = score_total_return(total_return)

    sub_components = {
        "cagr": round(cagr, 4),
        "dividend_yield": round(dividend_yield, 4),
        "total_return": round(total_return, 4),
        "score": round(score, 3),
    }

    return round(score, 3), sub_components


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


async def calculate_long_term_promise(
    symbol: str,
    metrics: Dict[str, float],
) -> Tuple[float, Dict[str, float]]:
    """
    Calculate long-term promise score.

    Combines:
    - Consistency (35%): 5Y vs 10Y CAGR similarity
    - Financial Strength (25%): Margins, debt, liquidity
    - Dividend Consistency (25%): No big cuts, sustainable payout
    - Sortino (15%): Good returns with low downside risk

    Args:
        symbol: Stock symbol (for reference only, not used for DB queries)
        metrics: Pre-fetched metrics dict containing CONSISTENCY_SCORE, FINANCIAL_STRENGTH,
                 DIVIDEND_CONSISTENCY (or PAYOUT_RATIO), and SORTINO

    Returns:
        Tuple of (total_score, sub_components_dict)
    """
    # Get consistency score from metrics
    consistency_score = metrics.get("CONSISTENCY_SCORE")
    if consistency_score is None:
        consistency_score = 0.5

    # Get financial strength from metrics
    financial_strength = metrics.get("FINANCIAL_STRENGTH")
    if financial_strength is None:
        financial_strength = 0.5

    # Get dividend consistency from metrics (or derive from payout ratio)
    dividend_consistency = metrics.get("DIVIDEND_CONSISTENCY")
    if dividend_consistency is None:
        payout = metrics.get("PAYOUT_RATIO")
        if payout is not None:
            dividend_consistency = _derive_dividend_consistency_from_payout(payout)
        else:
            dividend_consistency = 0.5

    # Get Sortino and convert to score
    sortino_raw = metrics.get("SORTINO")
    if sortino_raw is not None:
        sortino_score = _convert_sortino_to_score(sortino_raw)
    else:
        sortino_score = 0.5

    total = (
        consistency_score * PROMISE_WEIGHT_CONSISTENCY
        + financial_strength * PROMISE_WEIGHT_FINANCIALS
        + dividend_consistency * PROMISE_WEIGHT_DIVIDEND_STABILITY
        + sortino_score * PROMISE_WEIGHT_SORTINO
    )

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


async def calculate_stability_score(
    symbol: str,
    metrics: Dict[str, float],
) -> Tuple[float, Dict[str, float]]:
    """
    Calculate stability score.

    Combines:
    - Inverse Volatility (50%): Lower volatility = higher score
    - Drawdown Score (30%): Lower max drawdown = higher score
    - Sharpe Score (20%): Higher risk-adjusted returns = higher score

    Args:
        symbol: Stock symbol (for reference only, not used for DB queries)
        metrics: Pre-fetched metrics dict containing VOLATILITY_ANNUAL, MAX_DRAWDOWN, and SHARPE

    Returns:
        Tuple of (total_score, sub_components_dict)
    """
    # Get volatility and convert to score
    volatility_raw = metrics.get("VOLATILITY_ANNUAL")
    if volatility_raw is not None and volatility_raw > 0:
        volatility_score = _convert_volatility_to_score(volatility_raw)
    else:
        volatility_score = 0.5

    # Get drawdown and convert to score
    max_dd = metrics.get("MAX_DRAWDOWN")
    if max_dd is not None:
        drawdown_score = _convert_drawdown_to_score(max_dd)
    else:
        drawdown_score = 0.5

    # Get Sharpe and convert to score
    sharpe_raw = metrics.get("SHARPE")
    if sharpe_raw is not None:
        sharpe_score = _convert_sharpe_to_score(sharpe_raw)
    else:
        sharpe_score = 0.5

    total = (
        volatility_score * STABILITY_WEIGHT_VOLATILITY
        + drawdown_score * STABILITY_WEIGHT_DRAWDOWN
        + sharpe_score * STABILITY_WEIGHT_SHARPE
    )

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
    metrics_cache: Dict[str, Dict[str, float]],
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
        metrics_cache: Pre-fetched metrics dict mapping symbol -> metrics dict
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

        # Get metrics for this symbol (use empty dict if missing)
        metrics = metrics_cache.get(symbol, {})

        # Get scores for this position using cached metrics
        tr_score, tr_subs = await calculate_total_return_score(symbol, metrics)
        promise_score, promise_subs = await calculate_long_term_promise(symbol, metrics)
        stab_score, stab_subs = await calculate_stability_score(symbol, metrics)

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

    return round(min(1.0, end_state_score), 3), detailed_breakdown  # type: ignore[return-value]
