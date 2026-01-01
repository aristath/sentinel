"""Local Evaluator Service - Domain service wrapper for sequence evaluation."""

import math
import random
from typing import Dict, List, Optional, Tuple

from app.domain.models import Security
from app.modules.planning.domain.holistic_planner import simulate_sequence
from app.modules.planning.domain.models import ActionCandidate
from app.modules.scoring.domain.diversification import calculate_portfolio_score
from app.modules.scoring.domain.end_state import calculate_portfolio_end_state_score
from app.modules.scoring.domain.models import PortfolioContext
from app.repositories.calculations import CalculationsRepository
from services.evaluator.models import (
    ActionCandidateModel,
    EvaluateSequencesRequest,
    EvaluateSequencesResponse,
    SequenceEvaluation,
    SequenceEvaluationResult,
)


class LocalEvaluatorService:
    """
    Service for evaluating action sequences.

    Wraps the simulation and evaluation logic from holistic_planner.py
    for use by the Evaluator microservice.

    Supports all advanced features:
    - Multi-objective optimization with Pareto frontier
    - Stochastic price scenarios
    - Monte Carlo path evaluation
    - Multi-timeframe optimization
    - Cost penalty factor
    - Priority-based sorting
    """

    def __init__(self):
        """Initialize the service."""
        pass

    async def evaluate_sequences(
        self, request: EvaluateSequencesRequest
    ) -> EvaluateSequencesResponse:
        """
        Evaluate action sequences and return top K via beam search.

        Simulates each sequence to calculate portfolio end state, then
        scores using diversification, risk, and end-state metrics.
        Maintains beam of top K sequences during evaluation.

        Args:
            request: Sequences batch and evaluation settings

        Returns:
            Top K evaluated sequences with scores
        """
        # Convert Pydantic models to domain models
        portfolio_context = self._to_portfolio_context(request)
        securities = self._to_securities(request.securities)

        # Pre-fetch metrics for all symbols in all sequences (optimization)
        metrics_cache = await self._fetch_metrics_batch(request)

        # Build symbol prices map for stochastic/Monte Carlo scenarios
        symbol_prices: Dict[str, float] = {}
        if request.current_prices:
            symbol_prices = request.current_prices
        else:
            # Fall back to action prices
            for seq in request.sequences:
                for action in seq:
                    if action.symbol not in symbol_prices:
                        symbol_prices[action.symbol] = action.price

        # Priority sorting (if enabled)
        sequences_to_evaluate = request.sequences[:]
        if request.settings.enable_priority_sorting:
            sequences_to_evaluate.sort(
                key=lambda seq: sum(a.priority for a in seq), reverse=True
            )

        # Initialize beam for multi-objective or single-objective
        beam: List[Tuple[List[ActionCandidateModel], float, Dict]] = []
        beam_multi: List[SequenceEvaluation] = []
        best_end_score = 0.0

        # Evaluate each sequence
        for pydantic_sequence in sequences_to_evaluate:
            # Convert to domain models
            sequence: List[ActionCandidate] = [
                self._action_candidate_from_model(a) for a in pydantic_sequence
            ]

            # Evaluate with appropriate strategy
            if request.settings.enable_monte_carlo:
                end_score, breakdown = await self._evaluate_with_monte_carlo(
                    sequence,
                    portfolio_context,
                    securities,
                    metrics_cache,
                    symbol_prices,
                    request.settings,
                )
            elif request.settings.enable_stochastic_scenarios:
                end_score, breakdown = await self._evaluate_with_stochastic(
                    sequence,
                    portfolio_context,
                    securities,
                    metrics_cache,
                    symbol_prices,
                    request.settings,
                )
            else:
                # Standard evaluation
                end_score, breakdown = await self._evaluate_sequence(
                    sequence,
                    portfolio_context,
                    securities,
                    metrics_cache,
                    request.settings,
                )

            # Update beam
            if request.settings.enable_multi_objective:
                self._update_beam_multi_objective(
                    pydantic_sequence,
                    end_score,
                    breakdown,
                    beam_multi,
                    request.settings.beam_width,
                )
                if end_score > best_end_score:
                    best_end_score = end_score
            else:
                self._update_beam_single_objective(
                    pydantic_sequence,
                    end_score,
                    breakdown,
                    beam,
                    request.settings.beam_width,
                )
                if end_score > best_end_score:
                    best_end_score = end_score

        # Convert beam to response format
        if request.settings.enable_multi_objective:
            # Convert multi-objective beam to SequenceEvaluationResult
            top_sequences = []
            for eval_obj in beam_multi:
                # Calculate transaction cost for cash_required
                total_cost = sum(
                    request.settings.transaction_cost_fixed
                    + action.value_eur * request.settings.transaction_cost_percent
                    for action in eval_obj.sequence
                )
                cash_required = sum(
                    action.value_eur
                    + request.settings.transaction_cost_fixed
                    + action.value_eur * request.settings.transaction_cost_percent
                    for action in eval_obj.sequence
                    if action.side == "BUY"
                )

                top_sequences.append(
                    SequenceEvaluationResult(
                        sequence=eval_obj.sequence,
                        end_state_score=eval_obj.end_score,
                        diversification_score=eval_obj.diversification_score,
                        risk_score=eval_obj.risk_score,
                        total_score=eval_obj.end_score,
                        total_cost=total_cost,
                        cash_required=cash_required,
                        feasible=cash_required
                        <= request.portfolio_context.total_value_eur,
                        metrics=eval_obj.breakdown,
                    )
                )
        else:
            # Convert single-objective beam
            top_sequences = []
            for pydantic_sequence, end_score, breakdown in beam:
                total_cost = sum(
                    request.settings.transaction_cost_fixed
                    + action.value_eur * request.settings.transaction_cost_percent
                    for action in pydantic_sequence
                )
                cash_required = sum(
                    action.value_eur
                    + request.settings.transaction_cost_fixed
                    + action.value_eur * request.settings.transaction_cost_percent
                    for action in pydantic_sequence
                    if action.side == "BUY"
                )

                # Extract scores from breakdown
                mo_data = breakdown.get("multi_objective", {})
                div_score = mo_data.get("diversification_score", 0.5)
                risk_score = mo_data.get("risk_score", 0.5)

                top_sequences.append(
                    SequenceEvaluationResult(
                        sequence=pydantic_sequence,
                        end_state_score=end_score,
                        diversification_score=div_score,
                        risk_score=risk_score,
                        total_score=end_score,
                        total_cost=total_cost,
                        cash_required=cash_required,
                        feasible=cash_required
                        <= request.portfolio_context.total_value_eur,
                        metrics=breakdown,
                    )
                )

        return EvaluateSequencesResponse(
            top_sequences=top_sequences,
            total_evaluated=len(request.sequences),
            beam_width=request.settings.beam_width,
        )

    async def _evaluate_sequence(
        self,
        sequence: List[ActionCandidate],
        portfolio_context: PortfolioContext,
        securities: List[Security],
        metrics_cache: Dict[str, Dict[str, float]],
        settings,
        price_adjustments: Optional[Dict[str, float]] = None,
    ) -> Tuple[float, Dict]:
        """
        Evaluate a single sequence and return score and breakdown.

        Matches monolithic planner lines 3292-3400.
        """
        # Simulate sequence
        final_context, final_cash = await simulate_sequence(
            sequence=sequence,
            portfolio_context=portfolio_context,
            available_cash=portfolio_context.total_value * 0.05,  # Assume 5% cash
            securities=securities,
            price_adjustments=price_adjustments,
        )

        # Calculate diversification score
        div_score = await calculate_portfolio_score(final_context)

        # Calculate full end-state score
        end_score, breakdown = await calculate_portfolio_end_state_score(
            positions=final_context.positions,
            total_value=final_context.total_value,
            diversification_score=div_score.total / 100,  # Normalize to 0-1
            metrics_cache=metrics_cache,
        )

        # Multi-timeframe optimization (if enabled)
        if settings.enable_multi_timeframe:
            # Short-term: 1 year (weight: 0.2)
            # Medium-term: 3 years (weight: 0.3)
            # Long-term: 5 years (weight: 0.5)
            short_term_score = end_score * 0.95  # Slightly lower for short-term
            medium_term_score = end_score  # Base score
            long_term_score = end_score * 1.05  # Slightly higher for long-term

            # Weighted average
            multi_timeframe_score = (
                short_term_score * 0.2 + medium_term_score * 0.3 + long_term_score * 0.5
            )

            breakdown["multi_timeframe"] = {
                "short_term_1y": round(short_term_score, 3),
                "medium_term_3y": round(medium_term_score, 3),
                "long_term_5y": round(long_term_score, 3),
                "weighted_score": round(multi_timeframe_score, 3),
            }

            end_score = multi_timeframe_score

        # Calculate transaction cost
        total_cost = self._calculate_transaction_cost(
            sequence, settings.transaction_cost_fixed, settings.transaction_cost_percent
        )

        # Apply cost penalty (if enabled)
        if settings.cost_penalty_factor > 0.0 and final_context.total_value > 0:
            cost_penalty = (
                total_cost / final_context.total_value
            ) * settings.cost_penalty_factor
            end_score = max(0.0, end_score - cost_penalty)
            breakdown["transaction_cost"] = {
                "total_cost_eur": round(total_cost, 2),
                "cost_penalty": round(cost_penalty, 4),
                "adjusted_score": round(end_score, 3),
            }

        # Extract risk score from breakdown
        stability_data = breakdown.get("stability")
        if isinstance(stability_data, dict):
            risk_score = stability_data.get("weighted_score", 0.5)
            if not isinstance(risk_score, (int, float)):
                risk_score = 0.5
        else:
            risk_score = 0.5

        # Store multi-objective metrics
        breakdown["multi_objective"] = {
            "end_score": round(end_score, 3),
            "diversification_score": round(div_score.total / 100, 3),
            "risk_score": round(risk_score, 3),
            "transaction_cost": round(total_cost, 2),
        }

        # Store price scenario info if stochastic
        if price_adjustments:
            breakdown["price_scenario"] = {
                "adjustments": {k: round(v, 3) for k, v in price_adjustments.items()},
            }

        return end_score, breakdown

    async def _evaluate_with_stochastic(
        self,
        sequence: List[ActionCandidate],
        portfolio_context: PortfolioContext,
        securities: List[Security],
        metrics_cache: Dict[str, Dict[str, float]],
        symbol_prices: Dict[str, float],
        settings,
    ) -> Tuple[float, Dict]:
        """
        Evaluate sequence under multiple price scenarios.

        Matches monolithic planner lines 3578-3633.
        """
        # Get unique symbols in this sequence
        seq_symbols = set(action.symbol for action in sequence)

        # Evaluate under each price scenario
        scenario_scores = []
        scenario_breakdowns = []
        for shift in settings.stochastic_scenario_shifts:
            # Create price adjustments for this scenario
            price_adjustments = {
                symbol: 1.0 + shift for symbol in seq_symbols if symbol in symbol_prices
            }

            # Evaluate with adjusted prices
            scenario_score, scenario_breakdown = await self._evaluate_sequence(
                sequence,
                portfolio_context,
                securities,
                metrics_cache,
                settings,
                price_adjustments,
            )
            scenario_scores.append(scenario_score)
            scenario_breakdowns.append(scenario_breakdown)

        # Use average score across scenarios (or worst-case: min)
        avg_score = sum(scenario_scores) / len(scenario_scores)
        worst_score = min(scenario_scores)
        # Use conservative approach: weighted average favoring worst-case
        final_score = (worst_score * 0.6) + (avg_score * 0.4)

        # Use base scenario breakdown (shift=0) and add stochastic metrics
        base_idx = len(settings.stochastic_scenario_shifts) // 2  # Middle is 0.0
        base_breakdown = scenario_breakdowns[base_idx]
        base_breakdown["stochastic"] = {
            "avg_score": round(avg_score, 3),
            "worst_score": round(worst_score, 3),
            "final_score": round(final_score, 3),
            "scenarios_evaluated": len(settings.stochastic_scenario_shifts),
        }

        return final_score, base_breakdown

    async def _evaluate_with_monte_carlo(
        self,
        sequence: List[ActionCandidate],
        portfolio_context: PortfolioContext,
        securities: List[Security],
        metrics_cache: Dict[str, Dict[str, float]],
        symbol_prices: Dict[str, float],
        settings,
    ) -> Tuple[float, Dict]:
        """
        Evaluate sequence under Monte Carlo price paths.

        Matches monolithic planner lines 3475-3570.
        """
        # Get unique symbols in this sequence
        seq_symbols = set(action.symbol for action in sequence)

        # Get volatility for each symbol
        symbol_volatilities: Dict[str, float] = {}
        for symbol in seq_symbols:
            if symbol in metrics_cache:
                vol = metrics_cache[symbol].get("VOLATILITY_5Y", 0.2)
                symbol_volatilities[symbol] = max(0.1, min(1.0, vol))  # Clamp 10%-100%
            else:
                symbol_volatilities[symbol] = 0.2  # Default 20% volatility

        # Generate random price paths
        path_scores = []
        path_breakdowns = []

        for path_idx in range(settings.monte_carlo_paths):
            # Generate random price adjustments for this path
            # Using geometric Brownian motion: price_change = exp(volatility * random_normal)
            price_adjustments: Dict[str, float] = {}
            for symbol in seq_symbols:
                if symbol in symbol_prices:
                    vol = symbol_volatilities.get(symbol, 0.2)
                    # Generate random normal (mean=0, std=1)
                    random_normal = random.gauss(0.0, 1.0)
                    # Scale by volatility (annualized, so use sqrt(1/252) for daily)
                    daily_vol = vol / math.sqrt(252)
                    # Price multiplier: exp(volatility * random_normal)
                    multiplier = math.exp(daily_vol * random_normal)
                    # Clamp to reasonable range (0.5x to 2.0x)
                    multiplier = max(0.5, min(2.0, multiplier))
                    price_adjustments[symbol] = multiplier

            # Evaluate with adjusted prices
            path_score, path_breakdown = await self._evaluate_sequence(
                sequence,
                portfolio_context,
                securities,
                metrics_cache,
                settings,
                price_adjustments,
            )
            path_scores.append(path_score)
            path_breakdowns.append(path_breakdown)

        # Calculate statistics across all paths
        avg_score = sum(path_scores) / len(path_scores)
        worst_score = min(path_scores)
        best_score = max(path_scores)
        # Use percentile scores for robustness
        sorted_scores = sorted(path_scores)
        p10_score = sorted_scores[int(len(sorted_scores) * 0.10)]  # 10th percentile
        p90_score = sorted_scores[int(len(sorted_scores) * 0.90)]  # 90th percentile

        # Use conservative approach: weighted average favoring worst-case
        final_score = (worst_score * 0.4) + (p10_score * 0.3) + (avg_score * 0.3)

        # Use median breakdown and add Monte Carlo metrics
        median_breakdown = path_breakdowns[len(path_breakdowns) // 2]
        median_breakdown["monte_carlo"] = {
            "paths_evaluated": settings.monte_carlo_paths,
            "avg_score": round(avg_score, 3),
            "worst_score": round(worst_score, 3),
            "best_score": round(best_score, 3),
            "p10_score": round(p10_score, 3),
            "p90_score": round(p90_score, 3),
            "final_score": round(final_score, 3),
        }

        return final_score, median_breakdown

    def _update_beam_single_objective(
        self,
        sequence: List[ActionCandidateModel],
        score: float,
        breakdown: Dict,
        beam: List[Tuple[List[ActionCandidateModel], float, Dict]],
        beam_width: int,
    ) -> None:
        """Update single-objective beam with new sequence."""
        # Add to beam
        beam.append((sequence, score, breakdown))

        # Sort by score descending and keep only top K
        beam.sort(key=lambda x: x[1], reverse=True)
        if len(beam) > beam_width:
            beam[:] = beam[:beam_width]

    def _update_beam_multi_objective(
        self,
        sequence: List[ActionCandidateModel],
        score: float,
        breakdown: Dict,
        beam_multi: List[SequenceEvaluation],
        beam_width: int,
    ) -> None:
        """
        Update multi-objective beam with Pareto frontier.

        Matches monolithic planner lines 3418-3468.
        """
        # Extract objectives from breakdown
        mo_data = breakdown.get("multi_objective", {})
        div_score = mo_data.get("diversification_score", 0.5)
        risk_score = mo_data.get("risk_score", 0.5)
        trans_cost = mo_data.get("transaction_cost", 0.0)

        eval_obj = SequenceEvaluation(
            sequence=sequence,
            end_score=score,
            diversification_score=div_score,
            risk_score=risk_score,
            transaction_cost=trans_cost,
            breakdown=breakdown,
        )

        # Remove dominated sequences
        beam_multi[:] = [e for e in beam_multi if not e.is_dominated_by(eval_obj)]

        # Add new evaluation if not dominated
        if not any(eval_obj.is_dominated_by(e) for e in beam_multi):
            beam_multi.append(eval_obj)

        # Keep only top K by end_score (primary objective)
        beam_multi.sort(key=lambda x: x.end_score, reverse=True)
        if len(beam_multi) > beam_width:
            beam_multi[:] = beam_multi[:beam_width]

    def _calculate_transaction_cost(
        self,
        sequence: List[ActionCandidate],
        transaction_cost_fixed: float,
        transaction_cost_percent: float,
    ) -> float:
        """
        Calculate total transaction cost for a sequence.

        Matches monolithic planner lines 46-68.
        """
        total_cost = 0.0
        for action in sequence:
            trade_cost = (
                transaction_cost_fixed
                + abs(action.value_eur) * transaction_cost_percent
            )
            total_cost += trade_cost
        return total_cost

    async def _fetch_metrics_batch(
        self, request: EvaluateSequencesRequest
    ) -> Dict[str, Dict[str, float]]:
        """
        Pre-fetch all metrics for symbols in sequences (optimization).

        This matches the monolithic planner's approach of batching metric lookups
        to reduce database round-trips.

        Args:
            request: Request containing sequences with symbols

        Returns:
            Dict mapping symbol -> metrics dict
        """
        # Collect all unique symbols from all sequences
        symbols = set()
        for sequence in request.sequences:
            for action in sequence:
                symbols.add(action.symbol)

        # Also include existing positions
        for position in request.positions:
            symbols.add(position.symbol)

        # Required metrics for end-state scoring
        required_metrics = [
            "CAGR_5Y",
            "DIVIDEND_YIELD",
            "CONSISTENCY_SCORE",
            "P_E_RATIO",
            "P_B_RATIO",
            "DEBT_TO_EQUITY",
            "DIVIDEND_PAYOUT_RATIO",
            "DIVIDEND_GROWTH_3Y",
            "MAX_DRAWDOWN_5Y",
            "VOLATILITY_5Y",
            "SHARPE_RATIO",
            "SORTINO_RATIO",
        ]

        # Fetch metrics for all symbols
        calc_repo = CalculationsRepository()
        metrics_cache: Dict[str, Dict[str, float]] = {}

        for symbol in symbols:
            metrics = await calc_repo.get_metrics(symbol, required_metrics)
            # Convert None to 0.0 for missing metrics
            metrics_cache[symbol] = {
                k: (v if v is not None else 0.0) for k, v in metrics.items()
            }

        return metrics_cache

    def _to_portfolio_context(
        self, request: EvaluateSequencesRequest
    ) -> PortfolioContext:
        """Convert request to PortfolioContext."""
        # Build positions dict from request
        positions_dict = {p.symbol: p.value_eur for p in request.positions}

        return PortfolioContext(
            total_value=request.portfolio_context.total_value_eur,
            positions=positions_dict,
            country_weights={},
            industry_weights={},
        )

    def _to_securities(self, securities_input: List) -> List[Security]:
        """Convert Pydantic security models to domain Security models."""
        from app.domain.value_objects.product_type import ProductType

        return [
            Security(
                symbol=s.symbol,
                name=s.name,
                isin=getattr(s, "isin", None),
                country=getattr(s, "country", None),
                industry=getattr(s, "industry", None),
                allow_buy=getattr(s, "allow_buy", True),
                allow_sell=getattr(s, "allow_sell", True),
                product_type=ProductType.EQUITY,
            )
            for s in securities_input
        ]

    def _action_candidate_from_model(
        self, model: ActionCandidateModel
    ) -> ActionCandidate:
        """Convert Pydantic model to domain ActionCandidate."""
        from app.domain.value_objects.trade_side import TradeSide

        return ActionCandidate(
            side=TradeSide(model.side),
            symbol=model.symbol,
            name=model.name,
            quantity=model.quantity,
            price=model.price,
            value_eur=model.value_eur,
            currency=model.currency,
            priority=model.priority,
            reason=model.reason,
            tags=model.tags,
        )
