"""Planner batch job - processes next batch of sequences every N seconds."""

import logging
from typing import Optional

import httpx

from app.domain.portfolio_hash import generate_portfolio_hash
from app.domain.services.exchange_rate_service import ExchangeRateService
from app.infrastructure.external.tradernet import TradernetClient
from app.modules.planning.database.planner_repository import PlannerRepository
from app.modules.planning.domain.holistic_planner import (
    create_holistic_plan_incremental,
)
from app.modules.planning.services.portfolio_context_builder import (
    build_portfolio_context,
)
from app.repositories import (
    AllocationRepository,
    PositionRepository,
    SecurityRepository,
    SettingsRepository,
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

    This job can run in two modes:
    1. API-driven mode (max_depth > 0): Triggered by event-based trading loop, self-triggers next batches
    2. Scheduled fallback mode (max_depth = 0): Runs every 30 minutes as fallback, only if API-driven batches are not active

    Args:
        max_depth: Recursion depth (for API-driven mode, prevents infinite loops)
                   If 0, this is scheduled fallback mode
        portfolio_hash: Portfolio hash being processed (for API-driven mode)
    """
    try:
        # Get dependencies
        from app.core.database.manager import get_db_manager

        db_manager = get_db_manager()
        position_repo = PositionRepository()
        security_repo = SecurityRepository()
        settings_repo = SettingsRepository()
        allocation_repo = AllocationRepository()
        tradernet_client = TradernetClient()
        exchange_rate_service = ExchangeRateService(db_manager)

        # Get current portfolio state
        positions = await position_repo.get_all()
        stocks = await security_repo.get_all_active()

        # Fetch pending orders
        pending_orders = []
        if tradernet_client.is_connected:
            try:
                pending_orders = tradernet_client.get_pending_orders()
            except Exception as e:
                logger.warning(f"Failed to fetch pending orders: {e}")

        # Generate portfolio hash if not provided
        if portfolio_hash is None:
            position_dicts = [
                {"symbol": p.symbol, "quantity": p.quantity} for p in positions
            ]
            cash_balances = (
                {b.currency: b.amount for b in tradernet_client.get_cash_balances()}
                if tradernet_client.is_connected
                else {}
            )
            portfolio_hash = generate_portfolio_hash(
                position_dicts, stocks, cash_balances, pending_orders
            )

        # Skip scheduled job if API-driven batches are active
        # (API-driven batches have max_depth > 0 and self-trigger)
        if max_depth == 0:
            planner_repo = PlannerRepository()
            # Check if there are sequences that are not fully evaluated
            # If yes, assume API-driven batches are handling it and skip
            if await planner_repo.has_sequences(portfolio_hash):
                if not await planner_repo.are_all_sequences_evaluated(portfolio_hash):
                    logger.debug(
                        f"Skipping scheduled planner batch - API-driven batches are active "
                        f"(sequences exist but not all evaluated for portfolio {portfolio_hash[:8]}...)"
                    )
                    return

        # Get batch size
        # API-driven mode uses small batches (5), scheduled fallback uses larger batches (50)
        if max_depth > 0:
            batch_size = 5  # API-driven mode: small batches for faster processing
        else:
            batch_size = 50  # Scheduled fallback: larger batches, runs every 30 minutes

        # Build portfolio context
        portfolio_context = await build_portfolio_context(
            position_repo=position_repo,
            security_repo=security_repo,
            allocation_repo=allocation_repo,
            db_manager=db_manager,
        )

        # Ensure Tradernet is connected before getting cash balances
        available_cash = 0.0

        # Always try to get cash from portfolio snapshot first as fallback
        from app.modules.portfolio.database.portfolio_repository import (
            PortfolioRepository,
        )

        portfolio_repo = PortfolioRepository()
        latest_snapshot = await portfolio_repo.get_latest()
        snapshot_cash = latest_snapshot.cash_balance if latest_snapshot else 0.0

        if not tradernet_client.is_connected:
            logger.info("Tradernet not connected, attempting to connect...")
            if not tradernet_client.connect():
                logger.warning(
                    "Failed to connect to Tradernet, using portfolio snapshot cash: {:.2f} EUR".format(
                        snapshot_cash
                    )
                )
                available_cash = snapshot_cash
            else:
                logger.info("Successfully connected to Tradernet")

        # Get available cash (convert all currencies to EUR)
        cash_balances_raw = None
        cash_balances_dict = {}
        if tradernet_client.is_connected:
            cash_balances_raw = tradernet_client.get_cash_balances()
            logger.info(
                f"Tradernet connected: {tradernet_client.is_connected}, "
                f"cash_balances count: {len(cash_balances_raw) if cash_balances_raw else 0}"
            )
            if cash_balances_raw:
                cash_balances_dict = {b.currency: b.amount for b in cash_balances_raw}
                logger.info(f"Cash amounts by currency: {cash_balances_dict}")
                amounts_in_eur = await exchange_rate_service.batch_convert_to_eur(
                    cash_balances_dict
                )
                logger.info(f"Cash amounts in EUR: {amounts_in_eur}")
                available_cash = sum(amounts_in_eur.values())
            else:
                logger.warning(
                    "Tradernet connected but no cash balances returned, using snapshot: {:.2f} EUR".format(
                        snapshot_cash
                    )
                )
                available_cash = snapshot_cash
        else:
            # Use snapshot if not connected
            if available_cash == 0.0:
                logger.info(
                    "Using portfolio snapshot cash: {:.2f} EUR".format(snapshot_cash)
                )
                available_cash = snapshot_cash

        # Apply pending orders to positions and cash
        if pending_orders:
            from app.domain.models import Position
            from app.domain.portfolio_hash import apply_pending_orders_to_portfolio

            # Convert positions to dict format for adjustment
            position_dicts_for_adjustment = [
                {"symbol": p.symbol, "quantity": p.quantity} for p in positions
            ]

            # Apply pending orders
            adjusted_position_dicts, adjusted_cash_balances = (
                apply_pending_orders_to_portfolio(
                    position_dicts_for_adjustment, cash_balances_dict, pending_orders
                )
            )

            # Convert adjusted position dicts back to Position objects
            position_map = {p.symbol: p for p in positions}
            adjusted_positions = []
            for pos_dict in adjusted_position_dicts:
                symbol = pos_dict["symbol"]
                quantity = pos_dict["quantity"]
                if symbol in position_map:
                    original = position_map[symbol]
                    adjusted_positions.append(
                        Position(
                            symbol=original.symbol,
                            quantity=quantity,
                            avg_price=original.avg_price,
                            isin=original.isin,
                            currency=original.currency,
                            currency_rate=original.currency_rate,
                            current_price=original.current_price,
                            market_value_eur=(
                                original.market_value_eur
                                * (quantity / original.quantity)
                                if original.quantity > 0 and original.market_value_eur
                                else None
                            ),
                            cost_basis_eur=(
                                original.cost_basis_eur * (quantity / original.quantity)
                                if original.quantity > 0 and original.cost_basis_eur
                                else None
                            ),
                            unrealized_pnl=original.unrealized_pnl,
                            unrealized_pnl_pct=original.unrealized_pnl_pct,
                            last_updated=original.last_updated,
                            first_bought_at=original.first_bought_at,
                            last_sold_at=original.last_sold_at,
                        )
                    )
                else:
                    # New position from pending BUY order
                    # Find the order to get the price for avg_price
                    order_price = None
                    order_currency = None
                    for order in pending_orders:
                        if (
                            order.get("symbol", "").upper() == symbol
                            and order.get("side", "").lower() == "buy"
                        ):
                            order_price = float(order.get("price", 0))
                            order_currency = order.get("currency", "EUR")
                            break

                    # Use order price as avg_price (required by Position validation)
                    avg_price = order_price if order_price and order_price > 0 else 0.01

                    from app.shared.domain.value_objects.currency import Currency

                    currency = (
                        Currency.from_string(order_currency)
                        if order_currency
                        else Currency.EUR
                    )

                    adjusted_positions.append(
                        Position(
                            symbol=symbol,
                            quantity=quantity,
                            avg_price=avg_price,
                            currency=currency,
                            currency_rate=1.0,
                        )
                    )

            positions = adjusted_positions

            # Recalculate available_cash from adjusted cash balances
            if adjusted_cash_balances:
                amounts_in_eur = await exchange_rate_service.batch_convert_to_eur(
                    adjusted_cash_balances
                )
                available_cash = sum(amounts_in_eur.values())
                logger.info(
                    f"Adjusted available_cash for pending orders: {available_cash:.2f} EUR"
                )
            else:
                available_cash = 0.0
                logger.info("No cash balances after applying pending orders")

        # Get optimizer target weights if available
        from app.modules.optimization.services.portfolio_optimizer import (
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
            from app.core.events import SystemEvent, emit

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
