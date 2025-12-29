"""Planner batch job - processes next batch of sequences every N seconds."""

import logging
from typing import Optional

import httpx

from app.application.services.recommendation.portfolio_context_builder import (
    build_portfolio_context,
)
from app.domain.planning.holistic_planner import create_holistic_plan_incremental
from app.domain.portfolio_hash import generate_portfolio_hash
from app.domain.services.exchange_rate_service import ExchangeRateService
from app.infrastructure.external.tradernet import TradernetClient
from app.repositories import (
    AllocationRepository,
    PlannerRepository,
    PositionRepository,
    SettingsRepository,
    StockRepository,
)

logger = logging.getLogger(__name__)


async def _trigger_next_batch_via_api(portfolio_hash: str, next_depth: int):
    """Trigger next batch via API endpoint."""
    base_url = "http://localhost:8000"
    url = f"{base_url}/api/status/jobs/planner-batch"

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            await client.post(
                url, json={"portfolio_hash": portfolio_hash, "depth": next_depth}
            )
    except Exception as e:
        logger.warning(f"Failed to trigger next batch via API: {e}")
        # Fallback: scheduler will pick it up


async def process_planner_batch_job(
    max_depth: int = 0, portfolio_hash: Optional[str] = None
):
    """
    Process next batch of sequences for holistic planner.

    This job runs every N seconds (configurable via planner_batch_interval_seconds setting)
    and processes the next batch of sequences from the database.

    Args:
        max_depth: Recursion depth (for API-driven mode, prevents infinite loops)
        portfolio_hash: Portfolio hash being processed (for API-driven mode)
    """
    try:
        # Get dependencies
        from app.infrastructure.database.manager import get_db_manager

        db_manager = get_db_manager()
        position_repo = PositionRepository()
        stock_repo = StockRepository()
        settings_repo = SettingsRepository()
        allocation_repo = AllocationRepository()
        tradernet_client = TradernetClient()
        exchange_rate_service = ExchangeRateService(db_manager)

        # Get current portfolio state
        positions = await position_repo.get_all()
        stocks = await stock_repo.get_all_active()

        # Generate portfolio hash if not provided
        if portfolio_hash is None:
            position_dicts = [
                {"symbol": p.symbol, "quantity": p.quantity} for p in positions
            ]
            portfolio_hash = generate_portfolio_hash(position_dicts, stocks)

        # Get settings
        # Use small batch size for API-driven mode, otherwise use configured size
        if max_depth > 0:
            batch_size = int(
                await settings_repo.get_float("planner_batch_size_api", 5.0)
            )
        else:
            batch_size = int(await settings_repo.get_float("planner_batch_size", 100.0))

        # Build portfolio context
        portfolio_context = await build_portfolio_context(
            position_repo=position_repo,
            stock_repo=stock_repo,
            allocation_repo=allocation_repo,
            db_manager=db_manager,
        )

        # Get available cash
        cash_balances = (
            tradernet_client.get_cash_balances()
            if tradernet_client.is_connected
            else []
        )
        available_cash = sum(b.amount for b in cash_balances if b.currency == "EUR")

        # Get optimizer target weights if available
        from app.application.services.optimization.portfolio_optimizer import (
            PortfolioOptimizer,
        )
        from app.repositories import GroupingRepository

        grouping_repo = GroupingRepository()
        optimizer = PortfolioOptimizer(grouping_repo=grouping_repo)

        target_weights: Optional[dict] = None
        current_prices: Optional[dict] = None

        try:
            # Note: optimize() requires many parameters, but existing code in
            # event_based_trading.py uses same pattern - keeping for consistency
            optimization_result = await optimizer.optimize()  # type: ignore[call-arg]
            if optimization_result and optimization_result.target_weights:
                target_weights = optimization_result.target_weights
                # Get current prices for target weights
                from app.infrastructure.external import yahoo_finance as yahoo

                symbols = list(target_weights.keys())
                # Use get_batch_quotes with symbol_yahoo_map
                yahoo_symbols: dict[str, Optional[str]] = {
                    s.symbol: s.yahoo_symbol for s in stocks if s.symbol in symbols
                }
                quotes = yahoo.get_batch_quotes(yahoo_symbols)
                current_prices = {symbol: price for symbol, price in quotes.items()}
        except Exception as e:
            logger.debug(f"Could not get optimizer weights: {e}")

        # Get planner settings
        max_plan_depth = int(await settings_repo.get_float("max_plan_depth", 5.0))
        max_opportunities_per_category = int(
            await settings_repo.get_float("max_opportunities_per_category", 5.0)
        )
        enable_combinatorial = (
            await settings_repo.get_float("enable_combinatorial_generation", 1.0) == 1.0
        )
        priority_threshold = await settings_repo.get_float(
            "priority_threshold_for_combinations", 0.3
        )
        combinatorial_max_combinations_per_depth = int(
            await settings_repo.get_float(
                "combinatorial_max_combinations_per_depth", 50.0
            )
        )
        combinatorial_max_sells = int(
            await settings_repo.get_float("combinatorial_max_sells", 4.0)
        )
        combinatorial_max_buys = int(
            await settings_repo.get_float("combinatorial_max_buys", 4.0)
        )
        combinatorial_max_candidates = int(
            await settings_repo.get_float("combinatorial_max_candidates", 12.0)
        )

        # Process batch
        plan = await create_holistic_plan_incremental(
            portfolio_context=portfolio_context,
            available_cash=available_cash,
            stocks=stocks,
            positions=positions,
            exchange_rate_service=exchange_rate_service,
            target_weights=target_weights,
            current_prices=current_prices,
            transaction_cost_fixed=await settings_repo.get_float(
                "transaction_cost_fixed", 2.0
            ),
            transaction_cost_percent=await settings_repo.get_float(
                "transaction_cost_percent", 0.002
            ),
            max_plan_depth=max_plan_depth,
            max_opportunities_per_category=max_opportunities_per_category,
            enable_combinatorial=enable_combinatorial,
            priority_threshold=priority_threshold,
            combinatorial_max_combinations_per_depth=combinatorial_max_combinations_per_depth,
            combinatorial_max_sells=combinatorial_max_sells,
            combinatorial_max_buys=combinatorial_max_buys,
            combinatorial_max_candidates=combinatorial_max_candidates,
            batch_size=batch_size,
        )

        if plan:
            logger.debug(
                f"Planner batch processed: best score {plan.end_state_score:.2f}, "
                f"{len(plan.steps)} steps"
            )
        else:
            logger.debug(
                "Planner batch processed: no plan yet (sequences still being evaluated)"
            )

        # Emit planner batch complete event with current status
        try:
            from app.infrastructure.events import SystemEvent, emit

            # Get current status to emit
            planner_repo = PlannerRepository()
            has_sequences = await planner_repo.has_sequences(portfolio_hash)
            total_sequences = await planner_repo.get_total_sequence_count(
                portfolio_hash
            )
            evaluated_count = await planner_repo.get_evaluation_count(portfolio_hash)
            is_finished = await planner_repo.are_all_sequences_evaluated(portfolio_hash)

            if total_sequences > 0:
                progress_percentage = (evaluated_count / total_sequences) * 100.0
            else:
                progress_percentage = 0.0

            # Check if planning is active
            # Since we're in a batch job, planning is active if there's more work to do
            # and the scheduler is running (which it must be for this job to run)
            is_planning = False
            if has_sequences and not is_finished:
                try:
                    from app.jobs.scheduler import get_scheduler

                    scheduler = get_scheduler()
                    if scheduler and scheduler.running:
                        jobs = scheduler.get_jobs()
                        planner_job = next(
                            (job for job in jobs if job.id == "planner_batch"), None
                        )
                        if planner_job:
                            is_planning = True
                except Exception:
                    # If we can't check scheduler, assume planning is active if there's work to do
                    is_planning = has_sequences and not is_finished

            status = {
                "has_sequences": has_sequences,
                "total_sequences": total_sequences,
                "evaluated_count": evaluated_count,
                "is_planning": is_planning,
                "is_finished": is_finished,
                "portfolio_hash": portfolio_hash[:8],
                "progress_percentage": round(progress_percentage, 1),
            }

            emit(SystemEvent.PLANNER_BATCH_COMPLETE, status=status)
        except Exception as e:
            logger.debug(f"Could not emit planner status event: {e}")

        # Check if more work remains and self-trigger next batch if in API-driven mode
        if max_depth > 0:
            planner_repo = PlannerRepository()
            if not await planner_repo.are_all_sequences_evaluated(portfolio_hash):
                # Self-trigger next batch via API
                if (
                    max_depth < 100000
                ):  # Safety limit (allows for 5000+ scenarios with 5 per batch)
                    await _trigger_next_batch_via_api(portfolio_hash, max_depth + 1)
                else:
                    logger.warning(
                        f"Max depth ({max_depth}) reached, stopping API-driven batch chain"
                    )

    except Exception as e:
        logger.error(f"Error in planner batch job: {e}", exc_info=True)
