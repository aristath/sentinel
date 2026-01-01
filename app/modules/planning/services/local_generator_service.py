"""Local Generator Service - Domain service wrapper for sequence generation."""

from typing import AsyncIterator, Dict, List, Optional

from app.domain.models import Security
from app.modules.planning.domain.holistic_planner import (
    _filter_correlation_aware_sequences,
    _generate_adaptive_patterns,
    _generate_constraint_relaxation_scenarios,
    _generate_market_regime_patterns,
    _generate_partial_execution_scenarios,
    generate_action_sequences,
)
from app.modules.planning.domain.models import ActionCandidate
from app.modules.scoring.domain.models import PortfolioContext
from services.generator.models import (
    ActionCandidateModel,
    GenerateSequencesRequest,
    SequenceBatch,
)


class LocalGeneratorService:
    """
    Service for generating and filtering action sequences.

    Wraps the sequence generation logic from holistic_planner.py
    for use by the Generator microservice.
    """

    def __init__(self):
        """Initialize the service."""
        pass

    async def generate_sequences_batched(
        self, request: GenerateSequencesRequest
    ) -> AsyncIterator[SequenceBatch]:
        """
        Generate action sequences from opportunities and yield in batches.

        Uses combinatorial generation with adaptive patterns, then applies
        filters (correlation-aware, feasibility), and yields results in
        batches for streaming to evaluators.

        Args:
            request: Opportunities, settings, and batch size

        Yields:
            SequenceBatch objects containing sequences
        """
        # Convert Pydantic opportunities to domain format
        opportunities: Dict[str, List[ActionCandidate]] = {
            "profit_taking": [
                self._action_candidate_from_model(a)
                for a in request.opportunities.profit_taking
            ],
            "averaging_down": [
                self._action_candidate_from_model(a)
                for a in request.opportunities.averaging_down
            ],
            "rebalance_sells": [
                self._action_candidate_from_model(a)
                for a in request.opportunities.rebalance_sells
            ],
            "rebalance_buys": [
                self._action_candidate_from_model(a)
                for a in request.opportunities.rebalance_buys
            ],
            "opportunity_buys": [
                self._action_candidate_from_model(a)
                for a in request.opportunities.opportunity_buys
            ],
        }

        # Convert securities if provided
        securities: Optional[List[Security]] = None
        securities_by_symbol: Optional[Dict[str, Security]] = None
        if request.securities:
            securities = self._to_securities(request.securities)
            securities_by_symbol = {s.symbol: s for s in securities}

        # Call domain logic to generate sequences
        all_sequences = await generate_action_sequences(
            opportunities=opportunities,
            available_cash=request.feasibility.available_cash,
            max_depth=request.combinatorial.max_depth,
            enable_combinatorial=request.combinatorial.enable_weighted_combinations,
            securities=securities,
        )

        # Generate adaptive patterns if portfolio context provided
        if (
            request.combinatorial.enable_adaptive_patterns
            and request.portfolio_context
            and securities_by_symbol
        ):
            portfolio_context = self._to_portfolio_context(request.portfolio_context)
            adaptive_patterns = _generate_adaptive_patterns(
                opportunities=opportunities,
                portfolio_context=portfolio_context,
                available_cash=request.feasibility.available_cash,
                max_steps=request.combinatorial.max_depth,
                max_opportunities_per_category=request.combinatorial.max_opportunities_per_category,
                securities_by_symbol=securities_by_symbol,
            )
            all_sequences.extend(adaptive_patterns)

        # Generate market regime patterns if enabled and market_regime provided
        if request.combinatorial.enable_market_regime and request.market_regime:
            regime_patterns = _generate_market_regime_patterns(
                opportunities=opportunities,
                market_regime=request.market_regime,
                available_cash=request.feasibility.available_cash,
                max_steps=request.combinatorial.max_depth,
                max_opportunities_per_category=request.combinatorial.max_opportunities_per_category,
            )
            all_sequences.extend(regime_patterns)

        # Filter sequences for correlation if enabled and securities provided
        if request.filters.enable_correlation_aware and securities:
            all_sequences = await _filter_correlation_aware_sequences(
                all_sequences, securities, request.combinatorial.max_depth
            )

        # Generate partial execution scenarios if enabled
        if request.combinatorial.enable_partial_execution:
            partial_sequences = _generate_partial_execution_scenarios(
                all_sequences, request.combinatorial.max_depth
            )
            all_sequences.extend(partial_sequences)

        # Generate constraint relaxation scenarios if enabled
        if request.combinatorial.enable_constraint_relaxation and request.positions:
            positions = self._to_positions(request.positions)
            relaxed_sequences = _generate_constraint_relaxation_scenarios(
                all_sequences, request.feasibility.available_cash, positions
            )
            all_sequences.extend(relaxed_sequences)

        # Convert positions for feasibility filtering
        positions = None
        if request.positions:
            positions = self._to_positions(request.positions)

        # Apply feasibility filtering
        feasible_sequences = self._apply_feasibility_filter(
            all_sequences, request.feasibility, securities, positions
        )

        # Yield in batches
        batch_size = request.batch_size
        total_batches = max(1, (len(feasible_sequences) + batch_size - 1) // batch_size)

        for batch_number in range(total_batches):
            start_idx = batch_number * batch_size
            end_idx = min(start_idx + batch_size, len(feasible_sequences))
            batch_sequences = feasible_sequences[start_idx:end_idx]

            # Convert domain models to Pydantic
            pydantic_sequences = [
                [self._action_candidate_to_model(action) for action in sequence]
                for sequence in batch_sequences
            ]

            yield SequenceBatch(
                batch_number=batch_number,
                sequences=pydantic_sequences,
                total_batches=total_batches,
                more_available=batch_number < total_batches - 1,
            )

    def _apply_feasibility_filter(
        self,
        sequences: List[List[ActionCandidate]],
        feasibility,
        securities: Optional[List[Security]] = None,
        positions=None,
    ) -> List[List[ActionCandidate]]:
        """
        Filter sequences by feasibility.

        Matches monolithic planner's comprehensive feasibility checks:
        - Priority threshold
        - Duplicate symbols
        - Allow_buy/allow_sell flags
        - Cash availability (running cash check)
        - Position quantity validation
        - Minimum trade value

        Args:
            sequences: Generated sequences
            feasibility: Feasibility settings
            securities: Optional securities for allow_buy/allow_sell checks
            positions: Optional positions for sell quantity validation

        Returns:
            Filtered sequences that are feasible
        """
        from app.domain.value_objects.trade_side import TradeSide

        # Build lookups
        securities_by_symbol = {}
        if securities:
            securities_by_symbol = {s.symbol: s for s in securities}

        positions_by_symbol = {}
        if positions:
            positions_by_symbol = {p.symbol: p for p in positions}

        feasible = []
        for sequence in sequences:
            # Skip empty sequences
            if not sequence:
                continue

            # Priority threshold check
            if sequence:
                avg_priority = sum(c.priority for c in sequence) / len(sequence)
                if avg_priority < feasibility.priority_threshold:
                    continue

            # Running cash and position validation
            is_feasible = True
            running_cash = feasibility.available_cash

            for action in sequence:
                # Get side
                side = (
                    action.side
                    if isinstance(action.side, TradeSide)
                    else TradeSide(action.side)
                )

                # Check allow_buy/allow_sell flags
                security = securities_by_symbol.get(action.symbol)

                if side == TradeSide.BUY:
                    if security and not security.allow_buy:
                        is_feasible = False
                        break

                    # Check minimum trade value
                    if action.value_eur < feasibility.min_trade_value:
                        is_feasible = False
                        break

                    # Calculate cost with transaction fees
                    trade_cost = (
                        feasibility.transaction_cost_fixed
                        + action.value_eur * feasibility.transaction_cost_percent
                    )
                    total_cost = action.value_eur + trade_cost

                    # Check if we have enough running cash
                    if total_cost > running_cash:
                        is_feasible = False
                        break

                    running_cash -= total_cost

                elif side == TradeSide.SELL:
                    if security and not security.allow_sell:
                        is_feasible = False
                        break

                    # Check minimum trade value
                    if action.value_eur < feasibility.min_trade_value:
                        is_feasible = False
                        break

                    # Check if we have the position to sell (only if positions provided)
                    if positions_by_symbol:
                        position = positions_by_symbol.get(action.symbol)
                        if position is None or position.quantity < action.quantity:
                            is_feasible = False
                            break

                    # Calculate proceeds after transaction fees
                    trade_cost = (
                        feasibility.transaction_cost_fixed
                        + action.value_eur * feasibility.transaction_cost_percent
                    )
                    proceeds = action.value_eur - trade_cost

                    running_cash += proceeds

            if is_feasible:
                feasible.append(sequence)

        return feasible

    def _to_portfolio_context(self, context_input) -> PortfolioContext:
        """Convert Pydantic portfolio context to domain model."""
        return PortfolioContext(
            total_value=context_input.total_value,
            positions=context_input.positions,
            country_weights=context_input.country_weights,
            industry_weights=context_input.industry_weights,
        )

    def _to_positions(self, positions_input):
        """Convert Pydantic positions to domain Position models."""
        from app.domain.models import Position

        return [
            Position(
                symbol=p.symbol,
                quantity=p.quantity,
                average_cost=p.avg_price,
                market_value_eur=p.market_value_eur,
                unrealized_gain_loss=0.0,  # Not needed for constraint relaxation
                unrealized_gain_loss_percent=0.0,
            )
            for p in positions_input
        ]

    def _to_securities(self, securities_input) -> List[Security]:
        """Convert Pydantic securities to domain Security models."""
        from app.domain.value_objects.product_type import ProductType

        return [
            Security(
                symbol=s.symbol,
                name=s.name,
                isin=None,
                country=s.country,
                industry=s.industry,
                allow_buy=s.allow_buy,
                allow_sell=s.allow_sell,
                product_type=ProductType.EQUITY,
            )
            for s in securities_input
        ]

    def _action_candidate_from_model(
        self, model: ActionCandidateModel
    ) -> ActionCandidate:
        """
        Convert Pydantic model to domain ActionCandidate.

        Args:
            model: Pydantic ActionCandidateModel

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
