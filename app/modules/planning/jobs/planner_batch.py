"""Planner batch job - processes next batch of sequences every N seconds.

Supports both core and satellite buckets with bucket-specific configurations.
"""

import logging
from typing import Optional

import httpx

from app.domain.portfolio_hash import generate_portfolio_hash
from app.domain.services.exchange_rate_service import ExchangeRateService
from app.infrastructure.external.tradernet import TradernetClient
from app.modules.planning.database.planner_repository import PlannerRepository
from app.modules.planning.domain.planner import HolisticPlanner
from app.modules.planning.services.planner_factory import PlannerFactoryService
from app.modules.planning.services.planner_loader import get_planner_loader
from app.modules.planning.services.portfolio_context_builder import (
    build_portfolio_context,
)
from app.repositories import (
    AllocationRepository,
    PositionRepository,
    SecurityRepository,
    SettingsRepository,
    TradeRepository,
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
    max_depth: int = 0,
    portfolio_hash: Optional[str] = None,
    bucket_id: str = "core",
):
    """
    Process next batch of sequences for holistic planner.

    This job can run in two modes:
    1. API-driven mode (max_depth > 0): Triggered by event-based trading loop, self-triggers next batches
    2. Scheduled fallback mode (max_depth = 0): Runs every 30 minutes as fallback, only if API-driven batches are not active

    Supports both core and satellite buckets:
    - Core bucket: Uses existing settings from SettingsRepository
    - Satellite buckets: Uses bucket-specific configuration via PlannerFactoryService

    Args:
        max_depth: Recursion depth (for API-driven mode, prevents infinite loops)
                   If 0, this is scheduled fallback mode
        portfolio_hash: Portfolio hash being processed (for API-driven mode)
        bucket_id: ID of bucket to plan for ('core' or satellite ID, default 'core')
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
            # Allow negative cash for hypothetical planning scenarios
            adjusted_position_dicts, adjusted_cash_balances = (
                apply_pending_orders_to_portfolio(
                    position_dicts_for_adjustment,
                    cash_balances_dict,
                    pending_orders,
                    allow_negative_cash=True,
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

        logger.info(f"Processing planner batch for bucket: {bucket_id}")

        # Use factory service for satellite buckets to leverage bucket-specific configurations
        if bucket_id != "core":
            try:
                # Import satellite repository
                from app.modules.satellites.database.satellite_repository import (
                    SatelliteRepository,
                )

                # Load satellite settings
                satellite_repo = SatelliteRepository()
                satellite_settings = await satellite_repo.get_settings(bucket_id)

                if satellite_settings:
                    # Create planner using factory service
                    factory = PlannerFactoryService(
                        settings_repo=settings_repo, trade_repo=TradeRepository()
                    )
                    planner = factory.create_for_satellite_bucket(
                        bucket_id, satellite_settings
                    )

                    # Check if batch generation is enabled
                    if not planner.config.enable_batch_generation:
                        logger.info(
                            f"Batch generation disabled for satellite {bucket_id}, skipping"
                        )
                        return

                    # Use modular planner's incremental method
                    plan = await planner.create_plan_incremental(
                        portfolio_context=portfolio_context,
                        positions=positions,
                        securities=stocks,
                        available_cash=available_cash,
                        current_prices=current_prices,
                        target_weights=target_weights,
                        exchange_rate_service=exchange_rate_service,
                        batch_size=batch_size,
                    )

                    logger.info(
                        f"Used modular planner with factory for satellite {bucket_id}"
                    )
                else:
                    # Fallback: Load from default TOML if settings not found
                    logger.warning(
                        f"Satellite settings not found for {bucket_id}, loading default.toml"
                    )
                    from pathlib import Path

                    from app.modules.planning.domain.config.factory import (
                        ModularPlannerFactory,
                    )

                    config_path = Path("config/planner/default.toml")
                    if config_path.exists():
                        factory_fallback = ModularPlannerFactory.from_config_file(
                            config_path
                        )
                        if factory_fallback.config:
                            # Check if batch generation is enabled
                            if not factory_fallback.config.enable_batch_generation:
                                logger.info(
                                    f"Batch generation disabled in default.toml for satellite {bucket_id}, skipping"
                                )
                                return

                            planner_fallback = HolisticPlanner(
                                config=factory_fallback.config,
                                settings_repo=settings_repo,
                                trade_repo=TradeRepository(),
                            )
                            plan = await planner_fallback.create_plan_incremental(
                                portfolio_context=portfolio_context,
                                positions=positions,
                                securities=stocks,
                                available_cash=available_cash,
                                current_prices=current_prices,
                                target_weights=target_weights,
                                exchange_rate_service=exchange_rate_service,
                                batch_size=batch_size,
                            )
                        else:
                            logger.error("Failed to load default.toml, skipping batch")
                            return
                    else:
                        logger.error(
                            f"default.toml not found at {config_path}, skipping batch"
                        )
                        return
            except Exception as e:
                logger.error(
                    f"Failed to create satellite planner for {bucket_id}: {e}",
                    exc_info=True,
                )
                # Fallback: Load from default TOML
                logger.info(f"Falling back to default.toml for {bucket_id}")
                from pathlib import Path

                from app.modules.planning.domain.config.factory import (
                    ModularPlannerFactory,
                )

                config_path = Path("config/planner/default.toml")
                if config_path.exists():
                    factory_exc_fallback = ModularPlannerFactory.from_config_file(
                        config_path
                    )
                    if factory_exc_fallback.config:
                        # Check if batch generation is enabled
                        if not factory_exc_fallback.config.enable_batch_generation:
                            logger.info(
                                f"Batch generation disabled in default.toml for satellite {bucket_id}, skipping"
                            )
                            return

                        planner_exc_fallback = HolisticPlanner(
                            config=factory_exc_fallback.config,
                            settings_repo=settings_repo,
                            trade_repo=TradeRepository(),
                        )
                        plan = await planner_exc_fallback.create_plan_incremental(
                            portfolio_context=portfolio_context,
                            positions=positions,
                            securities=stocks,
                            available_cash=available_cash,
                            current_prices=current_prices,
                            target_weights=target_weights,
                            exchange_rate_service=exchange_rate_service,
                            batch_size=batch_size,
                        )
                    else:
                        logger.error("Failed to load default.toml in exception handler")
                        return
                else:
                    logger.error(f"default.toml not found at {config_path}")
                    return
        else:
            # Core bucket: Try database config first, fall back to file-based config
            planner_loader = get_planner_loader()
            modular_factory = await planner_loader.load_planner_for_bucket("core")

            if modular_factory and modular_factory.config:
                # Check if batch generation is enabled for this bucket
                if not modular_factory.config.enable_batch_generation:
                    logger.info("Batch generation disabled for core bucket, skipping")
                    return

                # Use database-configured modular planner
                logger.info("Using database planner config for core bucket")
                planner = HolisticPlanner(
                    config=modular_factory.config,
                    settings_repo=settings_repo,
                    trade_repo=TradeRepository(),
                )

                plan = await planner.create_plan_incremental(
                    portfolio_context=portfolio_context,
                    positions=positions,
                    securities=stocks,
                    available_cash=available_cash,
                    current_prices=current_prices,
                    target_weights=target_weights,
                    exchange_rate_service=exchange_rate_service,
                    batch_size=batch_size,
                )
            else:
                # Fallback to file-based config
                logger.info("No database config for core bucket, loading default.toml")
                from pathlib import Path

                from app.modules.planning.domain.config.factory import (
                    ModularPlannerFactory,
                )

                config_path = Path("config/planner/default.toml")
                if config_path.exists():
                    factory_core_fallback = ModularPlannerFactory.from_config_file(
                        config_path
                    )
                    if factory_core_fallback.config:
                        # Check if batch generation is enabled
                        if not factory_core_fallback.config.enable_batch_generation:
                            logger.info(
                                "Batch generation disabled in default.toml for core bucket, skipping"
                            )
                            return

                        planner_core_fallback = HolisticPlanner(
                            config=factory_core_fallback.config,
                            settings_repo=settings_repo,
                            trade_repo=TradeRepository(),
                        )
                        plan = await planner_core_fallback.create_plan_incremental(
                            portfolio_context=portfolio_context,
                            positions=positions,
                            securities=stocks,
                            available_cash=available_cash,
                            current_prices=current_prices,
                            target_weights=target_weights,
                            exchange_rate_service=exchange_rate_service,
                            batch_size=batch_size,
                        )
                    else:
                        logger.error("Failed to load default.toml for core fallback")
                        return
                else:
                    logger.error(f"default.toml not found at {config_path}")
                    return

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
