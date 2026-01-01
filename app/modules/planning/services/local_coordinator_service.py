"""Local Coordinator Service - Orchestrates planning workflow."""

import time
from typing import List

from app.infrastructure.http_clients.evaluator_client import EvaluatorHTTPClient
from app.infrastructure.http_clients.generator_client import GeneratorHTTPClient
from app.infrastructure.http_clients.opportunity_client import OpportunityHTTPClient
from services.coordinator.models import (
    CreatePlanRequest,
    CreatePlanResponse,
    ExecutionStats,
    HolisticPlanModel,
    HolisticStepModel,
)
from services.evaluator.models import EvaluateSequencesRequest, EvaluationSettings
from services.evaluator.models import PortfolioContextInput as EvalPortfolioContext
from services.evaluator.models import PositionInput as EvalPosition
from services.evaluator.models import SecurityInput as EvalSecurity
from services.evaluator.models import SequenceEvaluationResult
from services.generator.models import (
    CombinatorialSettings,
    FeasibilitySettings,
    FilterSettings,
    GenerateSequencesRequest,
    OpportunitiesInput,
)
from services.opportunity.models import IdentifyOpportunitiesRequest
from services.opportunity.models import PortfolioContextInput as OppPortfolioContext
from services.opportunity.models import PositionInput as OppPosition
from services.opportunity.models import SecurityInput as OppSecurity


class LocalCoordinatorService:
    """
    Service for orchestrating the planning workflow across microservices.

    Coordinates: Opportunity → Generator → Evaluator(s) → Plan Building
    """

    def __init__(self):
        """Initialize the service."""
        self.current_evaluator_idx = 0

    async def create_plan(self, request: CreatePlanRequest) -> CreatePlanResponse:
        """
        Create a holistic plan by orchestrating microservices.

        Workflow:
        1. Call Opportunity Service to identify opportunities
        2. Stream sequences from Generator Service in batches
        3. Distribute batches to Evaluator instances (round-robin)
        4. Aggregate results in global beam
        5. Build final plan from best sequence

        Args:
            request: Plan creation request

        Returns:
            Complete plan with execution statistics
        """
        start_time = time.time()

        # Initialize HTTP clients
        opportunity_client = OpportunityHTTPClient(
            base_url="http://localhost:8008", service_name="opportunity"
        )
        generator_client = GeneratorHTTPClient(
            base_url="http://localhost:8009", service_name="generator"
        )

        # Initialize evaluator clients from config
        evaluator_clients = [
            EvaluatorHTTPClient(base_url=url, service_name=f"evaluator-{i+1}")
            for i, url in enumerate(request.evaluator_config.urls)
        ]

        # Step 1: Identify opportunities
        # Convert PortfolioContext to Opportunity format (different field names)
        opp_portfolio_ctx = OppPortfolioContext(
            total_value=request.portfolio_context.total_value_eur,
            positions={},  # Will be computed from positions list
            country_weights={},  # Not needed for opportunity identification
            industry_weights={},
        )

        opp_request = IdentifyOpportunitiesRequest(
            portfolio_context=opp_portfolio_ctx,
            positions=[
                OppPosition(
                    symbol=p.symbol,
                    quantity=p.quantity,
                    avg_price=p.average_cost,
                    market_value_eur=p.value_eur,
                    unrealized_pnl_pct=p.unrealized_gain_loss_percent,
                )
                for p in request.positions
            ],
            securities=[
                OppSecurity(
                    symbol=s.symbol,
                    name=s.name,
                    isin="",  # Not available in Coordinator's SecurityInput
                    country=getattr(s, "country", None),
                    industry=s.industry,
                    allow_buy=True,
                    allow_sell=True,
                )
                for s in request.securities
            ],
            available_cash=request.available_cash,
            target_weights=request.target_weights,
            current_prices=request.current_prices,
            transaction_cost_fixed=request.parameters.transaction_cost_fixed,
            transaction_cost_percent=request.parameters.transaction_cost_percent,
        )
        opportunities = await opportunity_client.identify_opportunities(opp_request)

        # Step 2: Generate sequences (streaming)
        gen_request = GenerateSequencesRequest(
            opportunities=OpportunitiesInput(**opportunities.model_dump()),
            feasibility=FeasibilitySettings(
                available_cash=request.available_cash,
                transaction_cost_fixed=request.parameters.transaction_cost_fixed,
                transaction_cost_percent=request.parameters.transaction_cost_percent,
            ),
            combinatorial=CombinatorialSettings(
                max_depth=request.parameters.max_depth,
            ),
            filters=FilterSettings(
                enable_correlation_aware=request.parameters.enable_correlation_aware,
            ),
            batch_size=request.parameters.batch_size,
        )

        # Step 3: Evaluate batches in parallel
        global_beam: List[SequenceEvaluationResult] = []
        batches_processed = 0
        sequences_generated = 0
        sequences_evaluated = 0

        # Early termination tracking
        best_end_score = 0.0
        plateau_count = 0

        async for batch in generator_client.generate_sequences_streaming(gen_request):
            batches_processed += 1
            sequences_generated += len(batch.sequences)

            # Get next evaluator (round-robin)
            evaluator = self._get_next_evaluator(evaluator_clients)

            # Evaluate batch
            # Convert Generator's ActionCandidateModel to Evaluator's ActionCandidateModel
            from services.evaluator.models import (
                ActionCandidateModel as EvalActionCandidate,
            )

            eval_sequences = [
                [EvalActionCandidate(**action.model_dump()) for action in sequence]
                for sequence in batch.sequences
            ]

            # Convert models explicitly to avoid type mismatch
            eval_portfolio_ctx = EvalPortfolioContext(
                **request.portfolio_context.model_dump()
            )
            eval_positions = [EvalPosition(**p.model_dump()) for p in request.positions]
            eval_securities = [
                EvalSecurity(**s.model_dump()) for s in request.securities
            ]

            eval_request = EvaluateSequencesRequest(
                sequences=eval_sequences,
                portfolio_context=eval_portfolio_ctx,
                positions=eval_positions,
                securities=eval_securities,
                settings=EvaluationSettings(
                    beam_width=request.parameters.beam_width,
                    enable_monte_carlo=request.parameters.enable_monte_carlo,
                    transaction_cost_fixed=request.parameters.transaction_cost_fixed,
                    transaction_cost_percent=request.parameters.transaction_cost_percent,
                ),
            )

            try:
                batch_results = await evaluator.evaluate_sequences(eval_request)
                sequences_evaluated += batch_results.total_evaluated

                # Track beam before update for early termination
                old_beam_size = len(global_beam)

                # Merge into global beam
                global_beam.extend(batch_results.top_sequences)
                global_beam.sort(key=lambda x: x.total_score, reverse=True)
                if len(global_beam) > request.parameters.beam_width:
                    global_beam = global_beam[: request.parameters.beam_width]

                # Check if beam improved (for early termination)
                beam_improved = False
                if global_beam:
                    new_best_score = global_beam[0].total_score
                    if new_best_score > best_end_score:
                        best_end_score = new_best_score
                        plateau_count = 0
                        beam_improved = True
                        print(
                            f"Batch {batches_processed} -> NEW BEST (score: {new_best_score:.3f}, "
                            f"beam size: {len(global_beam)})"
                        )
                    elif len(global_beam) > old_beam_size:
                        # Beam grew, so improvement
                        beam_improved = True
                        plateau_count = 0
                        print(
                            f"Batch {batches_processed} added to beam "
                            f"(score: {new_best_score:.3f}, beam size: {len(global_beam)})"
                        )

                # Early termination check
                if not beam_improved:
                    plateau_count += 1

                if (
                    request.parameters.enable_early_termination
                    and batches_processed >= request.parameters.min_batches_to_evaluate
                    and plateau_count >= request.parameters.plateau_threshold
                ):
                    print(
                        f"Early termination: Beam converged (no improvement in {plateau_count} "
                        f"consecutive batches, evaluated {batches_processed} batches, "
                        f"beam size: {len(global_beam)})"
                    )
                    break

            except Exception as e:
                # Log error but continue with other batches
                print(f"Error evaluating batch {batches_processed}: {e}")
                continue

        # Step 4: Build plan from best sequence
        if not global_beam:
            # No sequences evaluated successfully
            return CreatePlanResponse(
                plan=HolisticPlanModel(
                    steps=[],
                    narrative="No feasible plan could be created.",
                    total_score=0.0,
                    end_state_score=0.0,
                    diversification_score=0.0,
                    risk_score=0.0,
                    total_cost=0.0,
                    cash_required=0.0,
                    feasible=False,
                    metadata={},
                ),
                stats=ExecutionStats(
                    total_time_seconds=time.time() - start_time,
                    opportunities_identified=sum(
                        [
                            len(opportunities.profit_taking),
                            len(opportunities.averaging_down),
                            len(opportunities.rebalance_sells),
                            len(opportunities.rebalance_buys),
                            len(opportunities.opportunity_buys),
                        ]
                    ),
                    sequences_generated=sequences_generated,
                    sequences_evaluated=sequences_evaluated,
                    batches_processed=batches_processed,
                    evaluators_used=len(evaluator_clients),
                ),
            )

        best_result = global_beam[0]

        # Convert to HolisticSteps
        # First convert Evaluator's ActionCandidateModel to Coordinator's ActionCandidateModel
        from services.coordinator.models import (
            ActionCandidateModel as CoordActionCandidate,
        )

        steps = []
        cumulative_cost = 0.0
        cumulative_cash_change = 0.0

        for idx, eval_action in enumerate(best_result.sequence):
            # Convert from evaluator's to coordinator's model
            action = CoordActionCandidate(**eval_action.model_dump())

            step_cost = (
                request.parameters.transaction_cost_fixed
                + action.value_eur * request.parameters.transaction_cost_percent
            )
            cumulative_cost += step_cost

            if action.side == "BUY":
                cumulative_cash_change -= action.value_eur + step_cost
            else:  # SELL
                cumulative_cash_change += action.value_eur - step_cost

            # Note: Narrative generation can be enhanced using narrative.py
            step_narrative = f"{action.side} {action.quantity} shares of {action.name} ({action.symbol})"

            steps.append(
                HolisticStepModel(
                    step_number=idx + 1,
                    action=action,
                    narrative=step_narrative,
                    reason=action.reason,
                    cumulative_cost=cumulative_cost,
                    cumulative_cash_change=cumulative_cash_change,
                )
            )

        # Note: Plan narrative can be enhanced using narrative.py
        plan_narrative = f"Execute {len(steps)} trades to optimize portfolio."

        plan = HolisticPlanModel(
            steps=steps,
            narrative=plan_narrative,
            total_score=best_result.total_score,
            end_state_score=best_result.end_state_score,
            diversification_score=best_result.diversification_score,
            risk_score=best_result.risk_score,
            total_cost=best_result.total_cost,
            cash_required=best_result.cash_required,
            feasible=best_result.feasible,
            metadata={
                "beam_size": len(global_beam),
                "best_sequence_length": len(best_result.sequence),
            },
        )

        stats = ExecutionStats(
            total_time_seconds=time.time() - start_time,
            opportunities_identified=sum(
                [
                    len(opportunities.profit_taking),
                    len(opportunities.averaging_down),
                    len(opportunities.rebalance_sells),
                    len(opportunities.rebalance_buys),
                    len(opportunities.opportunity_buys),
                ]
            ),
            sequences_generated=sequences_generated,
            sequences_evaluated=sequences_evaluated,
            batches_processed=batches_processed,
            evaluators_used=len(evaluator_clients),
        )

        return CreatePlanResponse(plan=plan, stats=stats)

    def _get_next_evaluator(
        self, evaluators: List[EvaluatorHTTPClient]
    ) -> EvaluatorHTTPClient:
        """
        Round-robin load balancing across evaluators.

        Args:
            evaluators: List of evaluator clients

        Returns:
            Next evaluator to use
        """
        evaluator = evaluators[self.current_evaluator_idx]
        self.current_evaluator_idx = (self.current_evaluator_idx + 1) % len(evaluators)
        return evaluator
