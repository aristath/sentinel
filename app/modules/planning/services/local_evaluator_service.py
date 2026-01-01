"""Local Evaluator Service - Domain service wrapper for sequence evaluation."""

from typing import List

from app.domain.models import Security
from app.modules.planning.domain.holistic_planner import simulate_sequence
from app.modules.planning.domain.models import ActionCandidate
from app.modules.scoring.domain.models import PortfolioContext
from services.evaluator.models import (
    ActionCandidateModel,
    EvaluateSequencesRequest,
    EvaluateSequencesResponse,
    SequenceEvaluationResult,
)


class LocalEvaluatorService:
    """
    Service for evaluating action sequences.

    Wraps the simulation and evaluation logic from holistic_planner.py
    for use by the Evaluator microservice.
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

        # Evaluate each sequence
        evaluated = []
        for pydantic_sequence in request.sequences:
            # Convert to domain models
            sequence = [self._action_candidate_from_model(a) for a in pydantic_sequence]

            # Simulate sequence
            final_context, final_cash = await simulate_sequence(
                sequence=sequence,
                portfolio_context=portfolio_context,
                available_cash=request.portfolio_context.total_value_eur
                * 0.05,  # Assume 5% cash
                securities=securities,
            )

            # Calculate scores (simplified for now - can be enhanced with full scoring logic)
            # TODO: Implement full scoring with diversification, risk, and end-state metrics
            end_state_score = 0.75  # Placeholder

            # Calculate transaction costs
            total_cost = sum(
                request.settings.transaction_cost_fixed
                + action.value_eur * request.settings.transaction_cost_percent
                for action in pydantic_sequence
            )

            # Calculate cash required
            cash_required = sum(
                action.value_eur
                + request.settings.transaction_cost_fixed
                + action.value_eur * request.settings.transaction_cost_percent
                for action in pydantic_sequence
                if action.side == "BUY"
            )

            # Simple scoring (can be enhanced)
            total_score = end_state_score

            evaluated.append(
                SequenceEvaluationResult(
                    sequence=pydantic_sequence,
                    end_state_score=end_state_score,
                    diversification_score=0.7,  # Placeholder
                    risk_score=0.8,  # Placeholder
                    total_score=total_score,
                    total_cost=total_cost,
                    cash_required=cash_required,
                    feasible=cash_required <= request.portfolio_context.total_value_eur,
                    metrics={},
                )
            )

        # Beam search: keep top K by total_score
        evaluated.sort(key=lambda x: x.total_score, reverse=True)
        top_k = evaluated[: request.settings.beam_width]

        return EvaluateSequencesResponse(
            top_sequences=top_k,
            total_evaluated=len(request.sequences),
            beam_width=request.settings.beam_width,
        )

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
        return [
            Security(
                symbol=s.symbol,
                name=s.name,
                country=s.country,
                industry=s.industry,
            )
            for s in securities_input
        ]

    def _action_candidate_to_model(
        self, action: ActionCandidate
    ) -> ActionCandidateModel:
        """
        Convert domain ActionCandidate to Pydantic model.

        Args:
            action: Domain ActionCandidate

        Returns:
            ActionCandidateModel for API response
        """
        return ActionCandidateModel(
            side=action.side.value if hasattr(action.side, "value") else action.side,
            symbol=action.symbol,
            name=action.name,
            quantity=action.quantity,
            price=action.price,
            value_eur=action.value_eur,
            currency=action.currency,
            priority=action.priority,
            reason=action.reason,
            tags=action.tags if hasattr(action, "tags") else [],
        )

    def _action_candidate_from_model(
        self, model: ActionCandidateModel
    ) -> ActionCandidate:
        """
        Convert Pydantic model to domain ActionCandidate.

        Args:
            model: ActionCandidateModel from API

        Returns:
            Domain ActionCandidate
        """
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
