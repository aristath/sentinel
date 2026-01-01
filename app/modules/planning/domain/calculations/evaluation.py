"""Portfolio evaluation functions.

Evaluates action sequences using various scoring methods:
- Single-objective end-state scoring
- Multi-objective Pareto optimization
- Stochastic evaluation with price scenarios
- Monte Carlo path simulation
"""

from typing import Any, Dict, List, Tuple

from app.modules.planning.domain.calculations.utils import calculate_transaction_cost
from app.modules.planning.domain.models import ActionCandidate
from app.modules.scoring.domain.diversification import calculate_portfolio_score
from app.modules.scoring.domain.end_state import calculate_portfolio_end_state_score
from app.modules.scoring.domain.models import PortfolioContext


async def evaluate_end_state(
    end_context: PortfolioContext,
    sequence: List[ActionCandidate],
    transaction_cost_fixed: float = 2.0,
    transaction_cost_percent: float = 0.002,
    cost_penalty_factor: float = 0.0,
    metrics_cache=None,
    risk_profile=None,
) -> Tuple[float, Dict]:
    """
    Evaluate the end state of a portfolio after executing a sequence.

    This is the core single-objective evaluation function that:
    1. Calculates diversification score
    2. Calculates end-state score with risk profile
    3. Applies transaction cost penalty if enabled
    4. Returns final score and detailed breakdown

    Args:
        end_context: Final portfolio state after sequence execution
        sequence: The action sequence that was executed
        transaction_cost_fixed: Fixed cost per trade (EUR)
        transaction_cost_percent: Variable cost as fraction
        cost_penalty_factor: Penalty factor for transaction costs (0.0 = no penalty)
        metrics_cache: Optional cache for metrics lookup
        risk_profile: Optional risk profile for scoring

    Returns:
        Tuple of (final_score, breakdown_dict)
    """
    # Calculate diversification score for end state
    div_score = await calculate_portfolio_score(end_context)

    # Calculate full end-state score with risk profile
    end_score, breakdown_dict = await calculate_portfolio_end_state_score(
        positions=end_context.positions,
        total_value=end_context.total_value,
        diversification_score=div_score.total / 100,  # Normalize to 0-1
        metrics_cache=metrics_cache,
        risk_profile=risk_profile,
    )

    # Ensure breakdown is a dict we can modify
    breakdown: Dict[str, Any] = (
        dict(breakdown_dict) if not isinstance(breakdown_dict, dict) else breakdown_dict
    )

    # Calculate transaction cost
    total_cost = calculate_transaction_cost(
        sequence, transaction_cost_fixed, transaction_cost_percent
    )

    # Apply transaction cost penalty if enabled
    if cost_penalty_factor > 0.0 and end_context.total_value > 0:
        cost_penalty = (total_cost / end_context.total_value) * cost_penalty_factor
        end_score = max(0.0, end_score - cost_penalty)
        breakdown["transaction_cost"] = {
            "total_cost_eur": round(total_cost, 2),
            "cost_penalty": round(cost_penalty, 4),
            "adjusted_score": round(end_score, 3),
        }

    # Extract risk score from breakdown (stability score, normalized to 0-1)
    stability_data = breakdown.get("stability")
    if isinstance(stability_data, dict):
        risk_score = stability_data.get("weighted_score", 0.5)
        if not isinstance(risk_score, (int, float)):
            risk_score = 0.5
    else:
        risk_score = 0.5

    # Store multi-objective metrics in breakdown
    breakdown["multi_objective"] = {
        "end_score": round(end_score, 3),
        "diversification_score": round(div_score.total / 100, 3),
        "risk_score": round(risk_score, 3),
        "transaction_cost": round(total_cost, 2),
    }

    return end_score, breakdown


async def evaluate_with_multi_timeframe(
    end_context: PortfolioContext,
    sequence: List[ActionCandidate],
    base_score: float,
    breakdown: Dict,
    transaction_cost_fixed: float = 2.0,
    transaction_cost_percent: float = 0.002,
    cost_penalty_factor: float = 0.0,
) -> Tuple[float, Dict]:
    """
    Evaluate sequence across multiple time horizons.

    Applies different weights to short-term (1y), medium-term (3y), and
    long-term (5y) outcomes to optimize for the user's time preference.

    Args:
        end_context: Final portfolio state
        sequence: Action sequence
        base_score: Base end-state score
        breakdown: Existing breakdown dict (will be updated)
        transaction_cost_fixed: Fixed cost per trade
        transaction_cost_percent: Variable cost as fraction
        cost_penalty_factor: Cost penalty factor

    Returns:
        Tuple of (multi_timeframe_score, updated_breakdown)
    """
    # Short-term: 1 year (weight: 0.2)
    # Medium-term: 3 years (weight: 0.3)
    # Long-term: 5 years (weight: 0.5)
    # Adjust scoring weights based on timeframe focus
    short_term_score = base_score * 0.95  # Slightly lower (more uncertainty)
    medium_term_score = base_score  # Base score for medium-term
    long_term_score = base_score * 1.05  # Slightly higher (compounding benefits)

    # Weighted average across timeframes
    multi_timeframe_score = (
        short_term_score * 0.2 + medium_term_score * 0.3 + long_term_score * 0.5
    )

    breakdown["multi_timeframe"] = {
        "short_term_1y": round(short_term_score, 3),
        "medium_term_3y": round(medium_term_score, 3),
        "long_term_5y": round(long_term_score, 3),
        "weighted_score": round(multi_timeframe_score, 3),
    }

    return multi_timeframe_score, breakdown


async def evaluate_with_price_scenario(
    end_context: PortfolioContext,
    sequence: List[ActionCandidate],
    price_adjustments: Dict[str, float],
    transaction_cost_fixed: float = 2.0,
    transaction_cost_percent: float = 0.002,
    cost_penalty_factor: float = 0.0,
    metrics_cache=None,
    risk_profile=None,
) -> Tuple[float, Dict]:
    """
    Evaluate sequence with a specific price scenario.

    Used for stochastic evaluation where we test the sequence under
    different price conditions (e.g., +5% or -5% market moves).

    Args:
        end_context: Final portfolio state with adjusted prices
        sequence: Action sequence
        price_adjustments: Dict mapping symbol -> price multiplier
        transaction_cost_fixed: Fixed cost per trade
        transaction_cost_percent: Variable cost as fraction
        cost_penalty_factor: Cost penalty factor
        metrics_cache: Optional metrics cache
        risk_profile: Optional risk profile

    Returns:
        Tuple of (scenario_score, breakdown_with_scenario_info)
    """
    score, breakdown = await evaluate_end_state(
        end_context=end_context,
        sequence=sequence,
        transaction_cost_fixed=transaction_cost_fixed,
        transaction_cost_percent=transaction_cost_percent,
        cost_penalty_factor=cost_penalty_factor,
        metrics_cache=metrics_cache,
        risk_profile=risk_profile,
    )

    # Add price scenario info to breakdown
    breakdown["price_scenario"] = {
        "adjustments": {k: round(v, 3) for k, v in price_adjustments.items()},
    }

    return score, breakdown


def extract_multi_objective_metrics(breakdown: Dict) -> Dict[str, float]:
    """
    Extract multi-objective metrics from evaluation breakdown.

    Args:
        breakdown: Evaluation breakdown dict

    Returns:
        Dict with keys: end_score, diversification_score, risk_score, transaction_cost
    """
    mo_data = breakdown.get("multi_objective", {})
    return {
        "end_score": mo_data.get("end_score", 0.0),
        "diversification_score": mo_data.get("diversification_score", 0.5),
        "risk_score": mo_data.get("risk_score", 0.5),
        "transaction_cost": mo_data.get("transaction_cost", 0.0),
    }


def dominates(eval1: Dict[str, float], eval2: Dict[str, float]) -> bool:
    """
    Check if eval1 Pareto-dominates eval2.

    For multi-objective optimization, a solution dominates another if:
    - It's better or equal in all objectives
    - Strictly better in at least one objective

    Note: transaction_cost should be minimized (lower is better),
    while other scores should be maximized (higher is better).

    Args:
        eval1: First evaluation metrics
        eval2: Second evaluation metrics

    Returns:
        True if eval1 dominates eval2
    """
    # For maximization objectives (end_score, diversification, risk)
    better_in_end = eval1["end_score"] >= eval2["end_score"]
    better_in_div = eval1["diversification_score"] >= eval2["diversification_score"]
    better_in_risk = eval1["risk_score"] >= eval2["risk_score"]

    # For minimization objective (transaction_cost)
    better_in_cost = eval1["transaction_cost"] <= eval2["transaction_cost"]

    # All must be >= (or <= for cost)
    all_better_or_equal = (
        better_in_end and better_in_div and better_in_risk and better_in_cost
    )

    # At least one must be strictly better
    strictly_better = (
        (eval1["end_score"] > eval2["end_score"])
        or (eval1["diversification_score"] > eval2["diversification_score"])
        or (eval1["risk_score"] > eval2["risk_score"])
        or (eval1["transaction_cost"] < eval2["transaction_cost"])
    )

    return all_better_or_equal and strictly_better


def calculate_weighted_multi_objective_score(
    metrics: Dict[str, float],
    end_score_weight: float = 0.5,
    diversification_weight: float = 0.2,
    risk_weight: float = 0.2,
    cost_weight: float = 0.1,
) -> float:
    """
    Calculate weighted score from multi-objective metrics.

    Combines multiple objectives into a single score using weights.
    This is useful when we need a single ranking score for beam search.

    Args:
        metrics: Dict with multi-objective metrics
        end_score_weight: Weight for end_score (0-1)
        diversification_weight: Weight for diversification (0-1)
        risk_weight: Weight for risk (0-1)
        cost_weight: Weight for cost penalty (0-1)

    Returns:
        Weighted combined score (0-1)
    """
    # Normalize weights to sum to 1.0
    total_weight = end_score_weight + diversification_weight + risk_weight + cost_weight
    if total_weight == 0:
        return 0.0

    end_w = end_score_weight / total_weight
    div_w = diversification_weight / total_weight
    risk_w = risk_weight / total_weight
    cost_w = cost_weight / total_weight

    # Cost is minimized, so invert it (1 - normalized_cost)
    # Assume max reasonable cost is 100 EUR
    normalized_cost = min(1.0, metrics["transaction_cost"] / 100.0)
    cost_score = 1.0 - normalized_cost

    weighted_score = (
        metrics["end_score"] * end_w
        + metrics["diversification_score"] * div_w
        + metrics["risk_score"] * risk_w
        + cost_score * cost_w
    )

    return max(0.0, min(1.0, weighted_score))
