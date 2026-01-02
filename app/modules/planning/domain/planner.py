"""Modular Holistic Planner - Orchestrates all planning modules.

This is the main planner class that uses the modular architecture.
It replaces the monolithic holistic_planner.py functions with a composable,
registry-based approach.
"""

import gc
import logging
from typing import Dict, List, Optional, Set, Tuple

try:
    import psutil

    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

from app.domain.models import Position, Security
from app.modules.planning.domain.calculations.context import (
    EvaluationContext,
    OpportunityContext,
)
from app.modules.planning.domain.calculations.evaluation import (
    evaluate_end_state,
    evaluate_with_multi_timeframe,
)
from app.modules.planning.domain.calculations.filters.base import (
    sequence_filter_registry,
)
from app.modules.planning.domain.calculations.opportunities.base import (
    opportunity_calculator_registry,
)
from app.modules.planning.domain.calculations.patterns.base import (
    pattern_generator_registry,
)
from app.modules.planning.domain.calculations.sequences.base import (
    sequence_generator_registry,
)
from app.modules.planning.domain.calculations.simulation import (
    check_sequence_feasibility,
    simulate_sequence,
)
from app.modules.planning.domain.calculations.utils import compute_ineligible_symbols
from app.modules.planning.domain.config.models import PlannerConfiguration
from app.modules.planning.domain.holistic_planner import (
    ActionCandidate,
    HolisticPlan,
    HolisticStep,
)
from app.modules.planning.infrastructure.go_evaluation_client import (
    GoEvaluationClient,
    GoEvaluationError,
)
from app.modules.scoring.domain.diversification import calculate_portfolio_score
from app.modules.scoring.domain.models import PortfolioContext

logger = logging.getLogger(__name__)


class HolisticPlanner:
    """
    Modular holistic planner that orchestrates all planning modules.

    This class coordinates:
    1. Opportunity identification (via OpportunityCalculators)
    2. Sequence generation (via PatternGenerators and SequenceGenerators)
    3. Sequence filtering (via SequenceFilters)
    4. Simulation and evaluation
    5. Best sequence selection

    The planner is configured via PlannerConfiguration which controls
    which modules are enabled and their parameters.
    """

    def __init__(
        self,
        config: PlannerConfiguration,
        settings_repo=None,
        trade_repo=None,
        metrics_cache=None,
    ):
        """
        Initialize the planner with configuration.

        Args:
            config: Planner configuration controlling module behavior
            settings_repo: Repository for settings lookup
            trade_repo: Repository for trade history
            metrics_cache: Optional cache for metrics
        """
        self.config = config
        self.settings_repo = settings_repo
        self.trade_repo = trade_repo
        self.metrics_cache = metrics_cache

        # Load enabled modules from registries
        self._load_modules()

    def _load_modules(self):
        """Load enabled modules from registries based on configuration."""
        # Load opportunity calculators
        self.calculators = []
        for name in self.config.get_enabled_calculators():
            calculator = opportunity_calculator_registry.get(name)
            if calculator:
                self.calculators.append(calculator)
            else:
                logger.warning(f"Calculator '{name}' not found in registry")

        # Load pattern generators
        self.patterns = []
        for name in self.config.get_enabled_patterns():
            pattern = pattern_generator_registry.get(name)
            if pattern:
                self.patterns.append(pattern)
            else:
                logger.warning(f"Pattern '{name}' not found in registry")

        # Load sequence generators
        self.generators = []
        for name in self.config.get_enabled_generators():
            generator = sequence_generator_registry.get(name)
            if generator:
                self.generators.append(generator)
            else:
                logger.warning(f"Generator '{name}' not found in registry")

        # Load filters
        self.filters = []
        for name in self.config.get_enabled_filters():
            filt = sequence_filter_registry.get(name)
            if filt:
                self.filters.append(filt)
            else:
                logger.warning(f"Filter '{name}' not found in registry")

        logger.info(
            f"Loaded modules: {len(self.calculators)} calculators, "
            f"{len(self.patterns)} patterns, {len(self.generators)} generators, "
            f"{len(self.filters)} filters"
        )

    async def create_plan(
        self,
        portfolio_context: PortfolioContext,
        positions: List[Position],
        securities: List[Security],
        available_cash: float,
        current_prices: Dict[str, float],
        target_weights: Optional[Dict[str, float]] = None,
        exchange_rate_service=None,
    ) -> HolisticPlan:
        """
        Create a holistic plan by orchestrating all modules.

        This is the main entry point that coordinates the entire planning process:
        1. Build context
        2. Identify opportunities
        3. Generate sequences
        4. Filter sequences
        5. Simulate and evaluate
        6. Select best

        Args:
            portfolio_context: Current portfolio state
            positions: Current positions
            securities: Available securities
            available_cash: Available cash in EUR
            current_prices: Current prices by symbol
            target_weights: Optional optimizer target weights
            exchange_rate_service: Optional exchange rate service

        Returns:
            HolisticPlan with the best sequence
        """
        # Step 1: Build context
        opp_context = await self._build_opportunity_context(
            portfolio_context=portfolio_context,
            positions=positions,
            securities=securities,
            available_cash=available_cash,
            current_prices=current_prices,
            target_weights=target_weights,
            exchange_rate_service=exchange_rate_service,
        )

        # Step 2: Identify opportunities using all enabled calculators
        opportunities = await self._identify_opportunities(opp_context)

        # Step 3: Generate sequences using patterns
        sequences = await self._generate_sequences(opportunities, opp_context)

        # Step 4: Apply sequence generators (combinatorial, etc.)
        # Flatten opportunities for generators that need them
        flat_opportunities = []
        for category_opps in opportunities.values():
            flat_opportunities.extend(category_opps)
        sequences = await self._apply_sequence_generators(
            sequences, flat_opportunities, opp_context
        )

        # Step 5: Filter sequences
        sequences = await self._filter_sequences(sequences, opp_context)

        # Step 6: Early feasibility filtering
        sequences = self._filter_feasible(sequences, opp_context)

        logger.info(f"After all filtering: {len(sequences)} sequences to evaluate")

        if not sequences:
            # Return empty plan
            return await self._create_empty_plan(portfolio_context)

        # Step 7: Simulate and evaluate sequences
        eval_context = self._build_evaluation_context(opp_context)
        best_sequence, best_score, best_breakdown = await self._evaluate_sequences(
            sequences, eval_context
        )

        # Step 8: Build final plan
        plan = await self._build_plan(
            sequence=best_sequence,
            score=best_score,
            breakdown=best_breakdown,
            current_context=portfolio_context,
            available_cash=available_cash,
            all_opportunities=opportunities,
        )

        return plan

    async def _build_opportunity_context(
        self,
        portfolio_context: PortfolioContext,
        positions: List[Position],
        securities: List[Security],
        available_cash: float,
        current_prices: Dict[str, float],
        target_weights: Optional[Dict[str, float]],
        exchange_rate_service,
    ) -> OpportunityContext:
        """Build OpportunityContext with all necessary data."""
        securities_by_symbol = {s.symbol: s for s in securities}

        # Compute constraints
        ineligible_symbols: Set[str] = set()
        recently_sold: Set[str] = set()

        if self.trade_repo and self.settings_repo:
            # Get recently sold symbols
            sell_cooldown_days = await self.settings_repo.get_int(
                "sell_cooldown_days", 180
            )
            recently_sold = await self.trade_repo.get_recently_sold_symbols(
                sell_cooldown_days
            )

            # Compute ineligible symbols
            ineligible_symbols = await compute_ineligible_symbols(
                positions=positions,
                securities_by_symbol=securities_by_symbol,
                trade_repo=self.trade_repo,
                settings_repo=self.settings_repo,
            )

        return OpportunityContext(
            portfolio_context=portfolio_context,
            positions=positions,
            securities=securities,
            available_cash_eur=available_cash,
            total_portfolio_value_eur=portfolio_context.total_value,
            current_prices=current_prices,
            stocks_by_symbol=securities_by_symbol,
            target_weights=target_weights,
            ineligible_symbols=ineligible_symbols,
            recently_sold=recently_sold,
            transaction_cost_fixed=self.config.transaction_cost_fixed,
            transaction_cost_percent=self.config.transaction_cost_percent,
            allow_sell=self.config.allow_sell,
            allow_buy=self.config.allow_buy,
            exchange_rate_service=exchange_rate_service,
        )

    async def _identify_opportunities(
        self, context: OpportunityContext
    ) -> Dict[str, List[ActionCandidate]]:
        """
        Identify opportunities using all enabled calculators.

        Returns:
            Dict mapping category to list of opportunities
        """
        all_opportunities: Dict[str, List[ActionCandidate]] = {}

        for calculator in self.calculators:
            params = self.config.get_calculator_params(calculator.name)
            logger.debug(f"Running calculator: {calculator.name} with params {params}")

            try:
                opportunities = await calculator.calculate(context, params)
                if opportunities:
                    # Merge with existing opportunities for this category
                    category = calculator.name
                    if category not in all_opportunities:
                        all_opportunities[category] = []
                    all_opportunities[category].extend(opportunities)
                    logger.info(
                        f"Calculator '{calculator.name}' found {len(opportunities)} opportunities"
                    )
            except Exception as e:
                logger.error(
                    f"Error in calculator '{calculator.name}': {e}", exc_info=True
                )

        # Limit opportunities per category
        for category, opps in all_opportunities.items():
            if len(opps) > self.config.max_opportunities_per_category:
                # Sort by priority and keep top N
                opps.sort(key=lambda x: x.priority, reverse=True)
                all_opportunities[category] = opps[
                    : self.config.max_opportunities_per_category
                ]

        total_opps = sum(len(opps) for opps in all_opportunities.values())
        logger.info(f"Total opportunities identified: {total_opps}")

        return all_opportunities

    async def _generate_sequences(
        self,
        opportunities: Dict[str, List[ActionCandidate]],
        context: OpportunityContext,
    ) -> List[List[ActionCandidate]]:
        """
        Generate action sequences using all enabled pattern generators.

        Returns:
            List of action sequences
        """
        all_sequences: List[List[ActionCandidate]] = []

        # Flatten opportunities for pattern generators
        flat_opportunities: List[ActionCandidate] = []
        for category_opps in opportunities.values():
            flat_opportunities.extend(category_opps)

        for pattern in self.patterns:
            params = self.config.get_pattern_params(pattern.name)
            logger.debug(f"Running pattern: {pattern.name} with params {params}")

            try:
                sequences = await pattern.generate(
                    opportunities=flat_opportunities,
                    opportunities_by_category=opportunities,
                    available_cash=context.available_cash_eur,
                    params=params,
                )
                if sequences:
                    all_sequences.extend(sequences)
                    logger.info(
                        f"Pattern '{pattern.name}' generated {len(sequences)} sequences"
                    )
            except Exception as e:
                logger.error(f"Error in pattern '{pattern.name}': {e}", exc_info=True)

        logger.info(f"Total sequences from patterns: {len(all_sequences)}")
        return all_sequences

    async def _apply_sequence_generators(
        self,
        base_sequences: List[List[ActionCandidate]],
        opportunities: List[ActionCandidate],
        context: OpportunityContext,
    ) -> List[List[ActionCandidate]]:
        """
        Apply sequence generators to create variations.

        Args:
            base_sequences: Base sequences from patterns
            opportunities: All opportunities (for generators that need them)
            context: Opportunity context

        Returns:
            Extended list of sequences
        """
        all_sequences = list(base_sequences)

        for generator in self.generators:
            params = self.config.get_generator_params(generator.name)
            logger.debug(f"Running generator: {generator.name} with params {params}")

            try:
                # Note: Most generators work on base sequences, but some (like
                # combinatorial) may work directly on opportunities
                new_sequences = generator.generate(opportunities, params)
                if new_sequences:
                    all_sequences.extend(new_sequences)
                    logger.info(
                        f"Generator '{generator.name}' created {len(new_sequences)} sequences"
                    )
            except Exception as e:
                logger.error(
                    f"Error in generator '{generator.name}': {e}", exc_info=True
                )

        logger.info(f"Total sequences after generators: {len(all_sequences)}")
        return all_sequences

    async def _filter_sequences(
        self,
        sequences: List[List[ActionCandidate]],
        context: OpportunityContext,
    ) -> List[List[ActionCandidate]]:
        """
        Apply all enabled filters to sequences.

        Args:
            sequences: Sequences to filter
            context: Opportunity context (may contain filter-specific data)

        Returns:
            Filtered list of sequences
        """
        filtered = sequences

        for filt in self.filters:
            params = self.config.get_filter_params(filt.name)
            logger.debug(f"Running filter: {filt.name} with params {params}")

            try:
                filtered = await filt.filter(filtered, params)
                logger.info(
                    f"Filter '{filt.name}': {len(sequences)} -> {len(filtered)} sequences"
                )
            except Exception as e:
                logger.error(f"Error in filter '{filt.name}': {e}", exc_info=True)

        return filtered

    def _filter_feasible(
        self,
        sequences: List[List[ActionCandidate]],
        context: OpportunityContext,
    ) -> List[List[ActionCandidate]]:
        """
        Fast feasibility check to remove impossible sequences.

        Checks:
        - Priority threshold
        - Duplicate symbols
        - Cash availability
        - allow_buy/allow_sell flags

        Args:
            sequences: Sequences to filter
            context: Opportunity context with constraints

        Returns:
            Feasible sequences only
        """
        feasible = []
        filtered_priority = 0
        filtered_duplicates = 0
        filtered_cash = 0

        for sequence in sequences:
            if not sequence:
                continue

            # Check for duplicate symbols
            symbols = [c.symbol for c in sequence]
            if len(symbols) != len(set(symbols)):
                filtered_duplicates += 1
                continue

            # Check average priority
            avg_priority = sum(c.priority for c in sequence) / len(sequence)
            if avg_priority < self.config.priority_threshold:
                filtered_priority += 1
                continue

            # Check cash feasibility
            if not check_sequence_feasibility(
                sequence, context.available_cash_eur, context.portfolio_context
            ):
                filtered_cash += 1
                continue

            feasible.append(sequence)

        logger.info(
            f"Feasibility filtering: {len(sequences)} -> {len(feasible)} "
            f"(priority: {filtered_priority}, duplicates: {filtered_duplicates}, cash: {filtered_cash})"
        )

        return feasible

    def _build_evaluation_context(
        self, opp_context: OpportunityContext
    ) -> EvaluationContext:
        """Build EvaluationContext from OpportunityContext."""
        return EvaluationContext(
            portfolio_context=opp_context.portfolio_context,
            positions=opp_context.positions,
            securities=opp_context.securities,
            available_cash_eur=opp_context.available_cash_eur,
            total_portfolio_value_eur=opp_context.total_portfolio_value_eur,
            current_prices=opp_context.current_prices,
            stocks_by_symbol=opp_context.stocks_by_symbol,
            transaction_cost_fixed=opp_context.transaction_cost_fixed,
            transaction_cost_percent=opp_context.transaction_cost_percent,
            exchange_rate_service=opp_context.exchange_rate_service,
        )

    async def _evaluate_sequences(
        self,
        sequences: List[List[ActionCandidate]],
        eval_context: EvaluationContext,
    ) -> Tuple[List[ActionCandidate], float, Dict]:
        """
        Evaluate all sequences and return the best one.

        Uses Go evaluation service for 10-100x performance improvement.
        Falls back to Python if Go service unavailable.

        Args:
            sequences: Sequences to evaluate
            eval_context: Evaluation context

        Returns:
            Tuple of (best_sequence, best_score, best_breakdown)
        """
        if not sequences:
            return [], 0.0, {}

        # Arduino-Q reliability: Monitor memory state to detect potential OOM issues
        if PSUTIL_AVAILABLE:
            mem = psutil.virtual_memory()
            logger.info(
                f"Starting sequence evaluation: {len(sequences)} sequences, "
                f"Memory: {mem.percent:.1f}% used ({mem.used / 1024**3:.2f}GB / {mem.total / 1024**3:.2f}GB)"
            )

        # Try Go evaluation service first (10-100x faster)
        try:
            logger.info(
                f"Evaluating {len(sequences)} sequences using Go service (parallel)..."
            )

            async with GoEvaluationClient() as client:
                results = await client.evaluate_batch(
                    sequences=sequences,
                    portfolio_context=eval_context.portfolio_context,
                    available_cash_eur=eval_context.available_cash_eur,
                    securities=eval_context.securities,
                    transaction_cost_fixed=eval_context.transaction_cost_fixed,
                    transaction_cost_percent=eval_context.transaction_cost_percent,
                )

            # Find best sequence from Go results
            best_sequence = []
            best_score = 0.0
            best_breakdown = {}

            for result in results:
                if result["feasible"] and result["score"] > best_score:
                    best_score = result["score"]
                    best_sequence = result["sequence"]
                    # Convert Go result to ActionCandidate objects
                    best_sequence = [
                        ActionCandidate(
                            side=action["side"],
                            symbol=action["symbol"],
                            name=action["name"],
                            quantity=action["quantity"],
                            price=action["price"],
                            value_eur=action["value_eur"],
                            currency=action["currency"],
                            priority=action["priority"],
                            reason=action["reason"],
                            tags=action["tags"],
                        )
                        for action in result["sequence"]
                    ]
                    best_breakdown = {
                        "go_evaluation": True,
                        "end_cash_eur": result["end_cash_eur"],
                        "transaction_costs": result["transaction_costs"],
                        "feasible": result["feasible"],
                    }

            logger.info(
                f"Go evaluation complete: Best sequence score: {best_score:.3f} "
                f"(from {len(sequences)} sequences)"
            )

        except GoEvaluationError as e:
            # Fall back to Python evaluation if Go service fails
            logger.info(
                f"Go evaluation failed ({e}), falling back to Python evaluation"
            )
            return await self._evaluate_sequences_python(sequences, eval_context)

        # Final cleanup: Full GC to reclaim memory
        gc.collect()

        if PSUTIL_AVAILABLE:
            mem = psutil.virtual_memory()
            logger.info(
                f"Final memory state: {mem.percent:.1f}% used "
                f"({mem.used / 1024**3:.2f}GB / {mem.total / 1024**3:.2f}GB)"
            )

        return best_sequence, best_score, best_breakdown

    async def _evaluate_sequences_python(
        self,
        sequences: List[List[ActionCandidate]],
        eval_context: EvaluationContext,
    ) -> Tuple[List[ActionCandidate], float, Dict]:
        """
        Python fallback evaluation (original sequential implementation).

        Used when Go service is unavailable. This is slower but more reliable
        as a fallback.

        Args:
            sequences: Sequences to evaluate
            eval_context: Evaluation context

        Returns:
            Tuple of (best_sequence, best_score, best_breakdown)
        """
        logger.info("Using Python evaluation (sequential)")
        best_sequence = []
        best_score = 0.0
        best_breakdown = {}

        # Performance optimization: Fetch multi-timeframe setting once
        enable_multi_timeframe = False
        if self.settings_repo:
            enable_multi_timeframe = (
                await self.settings_repo.get_float("enable_multi_timeframe", 0.0) == 1.0
            )

        for i, sequence in enumerate(sequences):
            # Simulate sequence
            end_context, end_cash = await simulate_sequence(
                sequence=sequence,
                portfolio_context=eval_context.portfolio_context,
                available_cash=eval_context.available_cash_eur,
                securities=eval_context.securities,
            )

            # Evaluate end state
            score, breakdown = await evaluate_end_state(
                end_context=end_context,
                sequence=sequence,
                transaction_cost_fixed=eval_context.transaction_cost_fixed,
                transaction_cost_percent=eval_context.transaction_cost_percent,
                metrics_cache=self.metrics_cache,
            )

            # Apply multi-timeframe if enabled
            if enable_multi_timeframe:
                score, breakdown = await evaluate_with_multi_timeframe(
                    end_context=end_context,
                    sequence=sequence,
                    base_score=score,
                    breakdown=breakdown,
                    transaction_cost_fixed=eval_context.transaction_cost_fixed,
                    transaction_cost_percent=eval_context.transaction_cost_percent,
                )

            # Track best
            if score > best_score:
                best_score = score
                best_sequence = sequence
                best_breakdown = breakdown

            # Progress logging every 100 sequences
            if (i + 1) % 100 == 0:
                progress_pct = ((i + 1) / len(sequences)) * 100
                logger.info(
                    f"Progress: {i + 1}/{len(sequences)} ({progress_pct:.1f}%), "
                    f"Best score: {best_score:.3f}"
                )

            # Minor GC every 50 sequences
            if (i + 1) % 50 == 0:
                gc.collect(generation=0)

        logger.info(
            f"Python evaluation complete: Best sequence score: {best_score:.3f} "
            f"(from {len(sequences)} sequences)"
        )

        return best_sequence, best_score, best_breakdown

    async def _build_plan(
        self,
        sequence: List[ActionCandidate],
        score: float,
        breakdown: Dict,
        current_context: PortfolioContext,
        available_cash: float,
        all_opportunities: Optional[Dict[str, List[ActionCandidate]]] = None,
    ) -> HolisticPlan:
        """
        Build final HolisticPlan from best sequence.

        Args:
            sequence: Best action sequence
            score: End-state score
            breakdown: Score breakdown
            current_context: Current portfolio context
            available_cash: Available cash

        Returns:
            Complete HolisticPlan
        """
        from app.modules.planning.domain.narrative import (
            generate_plan_narrative,
            generate_step_narrative,
        )

        # Calculate current score
        current_score_obj = await calculate_portfolio_score(current_context)
        current_score = current_score_obj.total / 100  # Normalize to 0-1

        # Build steps
        steps = []
        cash_required = 0.0
        cash_generated = 0.0

        for i, action in enumerate(sequence):
            from app.domain.value_objects.trade_side import TradeSide

            if action.side == TradeSide.SELL:
                cash_generated += action.value_eur
            else:
                cash_required += action.value_eur

            narrative = generate_step_narrative(
                action, current_context, all_opportunities or {}
            )

            step = HolisticStep(
                step_number=i + 1,
                side=action.side,
                symbol=action.symbol,
                name=action.name,
                quantity=action.quantity,
                estimated_price=action.price,
                estimated_value=action.value_eur,
                currency=action.currency,
                reason=action.reason,
                narrative=narrative,
                is_windfall="windfall" in action.tags,
                is_averaging_down="averaging_down" in action.tags,
                contributes_to=action.tags,
            )
            steps.append(step)

        # Generate narrative
        narrative_summary = generate_plan_narrative(
            steps, current_score, score, all_opportunities or {}
        )

        # Check feasibility
        feasible = cash_required <= (available_cash + cash_generated)

        improvement = score - current_score

        return HolisticPlan(
            steps=steps,
            current_score=current_score,
            end_state_score=score,
            improvement=improvement,
            narrative_summary=narrative_summary,
            score_breakdown=breakdown,
            cash_required=cash_required,
            cash_generated=cash_generated,
            feasible=feasible,
        )

    async def create_plan_incremental(
        self,
        portfolio_context: PortfolioContext,
        positions: List[Position],
        securities: List[Security],
        available_cash: float,
        current_prices: Optional[Dict[str, float]] = None,
        target_weights: Optional[Dict[str, float]] = None,
        exchange_rate_service=None,
        batch_size: int = 100,
    ) -> Optional[HolisticPlan]:
        """
        Create plan using incremental processing (batch-by-batch evaluation).

        This method processes sequences in batches, storing intermediate results
        in the database. It can be called repeatedly to process the next batch.

        TODO: Implement modular incremental processing
        - Use PlannerRepository for sequence storage
        - Generate sequences using modular pattern generators
        - Evaluate batches using modular evaluation
        - Support resume from previous batch
        - Track progress in database

        For now, this delegates to the existing incremental implementation.

        Args:
            portfolio_context: Current portfolio state
            positions: Current positions
            securities: Available securities
            available_cash: Available cash in EUR
            current_prices: Current prices for all securities
            target_weights: Optional optimizer target weights
            exchange_rate_service: Optional exchange rate service
            batch_size: Number of sequences to process per batch

        Returns:
            HolisticPlan with best sequence found so far, or None if no sequences evaluated yet
        """
        # TODO: Replace with modular implementation
        # For now, delegate to existing incremental function
        from app.modules.planning.domain.holistic_planner import (
            create_holistic_plan_incremental,
        )

        return await create_holistic_plan_incremental(
            portfolio_context=portfolio_context,
            available_cash=available_cash,
            securities=securities,
            positions=positions,
            exchange_rate_service=exchange_rate_service,
            target_weights=target_weights,
            current_prices=current_prices,
            transaction_cost_fixed=self.config.transaction_cost_fixed,
            transaction_cost_percent=self.config.transaction_cost_percent,
            max_plan_depth=self.config.max_depth,
            max_opportunities_per_category=self.config.max_opportunities_per_category,
            enable_combinatorial=True,  # TODO: Get from config
            priority_threshold=self.config.priority_threshold,
            batch_size=batch_size,
        )

    async def _create_empty_plan(
        self, current_context: PortfolioContext
    ) -> HolisticPlan:
        """Create an empty plan when no opportunities found."""
        current_score_obj = await calculate_portfolio_score(current_context)
        current_score = current_score_obj.total / 100

        return HolisticPlan(
            steps=[],
            current_score=current_score,
            end_state_score=current_score,
            improvement=0.0,
            narrative_summary="No actionable opportunities found. Portfolio is well-balanced.",
            score_breakdown={},
            cash_required=0.0,
            cash_generated=0.0,
            feasible=True,
        )
