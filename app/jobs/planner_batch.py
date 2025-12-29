"""Planner batch job - processes next batch of sequences every N seconds."""

import logging
from typing import Optional

from app.application.services.recommendation.portfolio_context_builder import (
    build_portfolio_context,
)
from app.domain.planning.holistic_planner import create_holistic_plan_incremental
from app.domain.services.exchange_rate_service import ExchangeRateService
from app.infrastructure.external.tradernet import TradernetClient
from app.repositories import (
    AllocationRepository,
    PositionRepository,
    SettingsRepository,
    StockRepository,
)

logger = logging.getLogger(__name__)


async def process_planner_batch_job():
    """
    Process next batch of sequences for holistic planner.

    This job runs every N seconds (configurable via planner_batch_interval_seconds setting)
    and processes the next batch of sequences from the database.
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

        # Get settings
        batch_size = int(await settings_repo.get_float("planner_batch_size", 100.0))

        # Get current portfolio state
        positions = await position_repo.get_all()
        stocks = await stock_repo.get_all_active()

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
            optimization_result = await optimizer.optimize()
            if optimization_result and optimization_result.target_weights:
                target_weights = optimization_result.target_weights
                # Get current prices for target weights
                from app.infrastructure.external import yahoo_finance as yahoo

                symbols = list(target_weights.keys())
                quotes = await yahoo.get_quotes(symbols)
                current_prices = {
                    symbol: quote["price"] for symbol, quote in quotes.items()
                }
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

    except Exception as e:
        logger.error(f"Error in planner batch job: {e}", exc_info=True)
