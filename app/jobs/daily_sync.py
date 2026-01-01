"""Daily sync jobs for portfolio and prices."""

import logging
from datetime import datetime
from typing import Optional

from app.core.database.manager import get_db_manager
from app.core.events import SystemEvent, emit
from app.domain.events import PositionUpdatedEvent, get_event_bus
from app.domain.models import Position
from app.domain.services.exchange_rate_service import ExchangeRateService
from app.infrastructure.dependencies import get_exchange_rate_service
from app.infrastructure.external import yahoo_finance as yahoo
from app.infrastructure.external.tradernet import get_tradernet_client
from app.infrastructure.locking import file_lock
from app.modules.display.services.display_service import set_led3, set_led4
from app.modules.universe.database.security_repository import SecurityRepository
from app.shared.domain.value_objects.currency import Currency

logger = logging.getLogger(__name__)


def _extract_quotes_list(quotes_response) -> list:
    """Extract quotes list from Tradernet response."""
    if isinstance(quotes_response, list):
        return quotes_response
    elif isinstance(quotes_response, dict):
        q_list = quotes_response.get("result", {}).get("q", [])
        if not q_list:
            q_list = quotes_response.get("q", [])
        return q_list
    return []


async def sync_portfolio():
    """
    Sync portfolio positions from Tradernet to local database.

    This job:
    1. Fetches current positions from Tradernet
    2. Updates local positions table
    3. Creates a daily portfolio snapshot

    Uses file locking to prevent concurrent syncs.
    """
    async with file_lock("portfolio_sync", timeout=60.0):
        await _sync_portfolio_internal()


async def _calculate_cash_balance_eur(
    cash_balances: list, exchange_rate_service: ExchangeRateService
) -> float:
    """Calculate total cash balance in EUR using ExchangeRateService."""
    logger.info(f"Calculating cash balance for {len(cash_balances)} currencies...")
    amounts_by_currency = {cb.currency: cb.amount for cb in cash_balances}
    logger.info(f"Amounts by currency: {amounts_by_currency}")
    logger.info("Calling exchange_rate_service.batch_convert_to_eur()...")
    amounts_in_eur = await exchange_rate_service.batch_convert_to_eur(
        amounts_by_currency
    )
    logger.info(f"Converted amounts: {amounts_in_eur}")
    total = sum(amounts_in_eur.values())
    logger.info(f"Total cash balance: {total:.2f} EUR")
    return total


async def _determine_country(symbol: str, db_manager) -> Optional[str]:
    """Determine country for a symbol."""
    cursor = await db_manager.config.execute(
        "SELECT country FROM securities WHERE symbol = ?", (symbol,)
    )
    row = await cursor.fetchone()
    if row:
        return row[0]

    symbol_upper = symbol.upper()
    if symbol_upper.endswith((".GR", ".DE", ".PA")):
        return "EU"
    elif symbol_upper.endswith((".AS", ".HK", ".T")):
        return "ASIA"
    elif symbol_upper.endswith(".US"):
        return "US"
    return None


async def _insert_position(
    pos,
    current_price: Optional[float],
    market_value_eur: Optional[float],
    exchange_rate: float,
    dates: dict,
    db_manager,
    event_bus,
) -> float:
    """Insert a position and return its market value."""
    await db_manager.state.execute(
        """
        INSERT INTO positions
        (symbol, quantity, avg_price, current_price, currency,
         currency_rate, market_value_eur, last_updated,
         first_bought_at, last_sold_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            pos.symbol,
            pos.quantity,
            pos.avg_price,
            current_price,
            pos.currency or Currency.EUR,
            exchange_rate,
            market_value_eur,
            datetime.now().isoformat(),
            dates.get("first_bought_at"),
            dates.get("last_sold_at"),
        ),
    )

    updated_position = Position(
        symbol=pos.symbol,
        quantity=pos.quantity,
        avg_price=pos.avg_price,
        currency=pos.currency or Currency.EUR,
        currency_rate=exchange_rate,
        current_price=current_price,
        market_value_eur=market_value_eur,
    )
    event_bus.publish(PositionUpdatedEvent(position=updated_position))

    return market_value_eur or 0.0


async def _process_positions(
    positions: list,
    saved_price_data: dict,
    trade_dates: dict,
    exchange_rate_service: ExchangeRateService,
    db_manager,
    event_bus,
) -> tuple[float, float, float, dict]:
    """Process all positions and return totals and geo values."""
    total_value = 0.0
    invested_value = 0.0
    unrealized_pnl = 0.0
    geo_values = {"EU": 0.0, "ASIA": 0.0, "US": 0.0}

    for pos in positions:
        price_data = saved_price_data.get(pos.symbol, {})
        dates = trade_dates.get(pos.symbol, {})

        current_price = price_data.get("current_price")
        market_value_eur = price_data.get("market_value_eur")

        currency = pos.currency or Currency.EUR
        exchange_rate = await exchange_rate_service.get_rate(str(currency), "EUR")

        if current_price and exchange_rate > 0:
            market_value_eur = pos.quantity * current_price / exchange_rate

        cost_basis_eur = (
            pos.quantity * pos.avg_price / exchange_rate
            if exchange_rate > 0
            else pos.quantity * pos.avg_price
        )
        invested_value += cost_basis_eur

        if current_price and exchange_rate > 0:
            position_unrealized_pnl = (
                (current_price - pos.avg_price) * pos.quantity / exchange_rate
            )
            unrealized_pnl += position_unrealized_pnl

        market_value = await _insert_position(
            pos,
            current_price,
            market_value_eur,
            exchange_rate,
            dates,
            db_manager,
            event_bus,
        )
        total_value += market_value

        country = await _determine_country(pos.symbol, db_manager)
        if country:
            geo_values[country] = geo_values.get(country, 0) + market_value

    return total_value, invested_value, unrealized_pnl, geo_values


async def _create_portfolio_snapshot(
    total_value: float,
    cash_balance: float,
    invested_value: float,
    unrealized_pnl: float,
    geo_values: dict,
    position_count: int,
    db_manager,
) -> None:
    """Create daily portfolio snapshot."""
    from app.application.services.turnover_tracker import TurnoverTracker

    today = datetime.now().strftime("%Y-%m-%d")

    # Calculate annual turnover
    turnover_tracker = TurnoverTracker(db_manager)
    annual_turnover = await turnover_tracker.calculate_annual_turnover(end_date=today)

    await db_manager.state.execute(
        """
        INSERT OR REPLACE INTO portfolio_snapshots
        (date, total_value, cash_balance, invested_value, unrealized_pnl,
         geo_eu_pct, geo_asia_pct, geo_us_pct, position_count, annual_turnover, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
        """,
        (
            today,
            total_value,
            cash_balance,
            invested_value,
            unrealized_pnl,
            geo_values["EU"] / total_value if total_value else 0,
            geo_values["ASIA"] / total_value if total_value else 0,
            geo_values["US"] / total_value if total_value else 0,
            position_count,
            annual_turnover,
        ),
    )


async def _sync_portfolio_internal():
    """Internal portfolio sync implementation."""
    logger.info("Starting portfolio sync")

    set_led3(0, 0, 255)  # Blue for sync
    emit(SystemEvent.SYNC_START)

    client = get_tradernet_client()

    if not client.is_connected:
        if not client.connect():
            logger.error("Failed to connect to Tradernet, skipping sync")
            error_msg = "BROKER CONNECTION FAILED"
            emit(SystemEvent.ERROR_OCCURRED, message=error_msg)
            return

    try:
        # Get portfolio hash before sync for cache invalidation comparison
        from app.domain.portfolio_hash import generate_portfolio_hash
        from app.repositories import PositionRepository, SecurityRepository

        position_repo = PositionRepository()
        security_repo = SecurityRepository()

        positions_before = await position_repo.get_all()
        securities = await security_repo.get_all_active()
        cash_balances_before_raw = client.get_cash_balances()
        cash_balances_before = (
            {b.currency: b.amount for b in cash_balances_before_raw}
            if cash_balances_before_raw
            else {}
        )
        position_dicts_before = [
            {"symbol": p.symbol, "quantity": p.quantity} for p in positions_before
        ]

        # Fetch pending orders to include in hash calculation
        try:
            pending_orders = client.get_pending_orders()
            logger.info(f"Found {len(pending_orders)} pending orders")
        except Exception as e:
            logger.warning(f"Failed to fetch pending orders: {e}")
            pending_orders = []

        hash_before = generate_portfolio_hash(
            position_dicts_before, securities, cash_balances_before, pending_orders
        )
        logger.debug(f"Portfolio hash before sync: {hash_before}")

        # Get positions and cash balances from Tradernet
        logger.info("Calling client.get_portfolio()...")
        positions = client.get_portfolio()
        logger.info(f"get_portfolio() returned {len(positions)} positions")

        logger.info("Calling client.get_cash_balances()...")
        cash_balances = client.get_cash_balances()
        logger.info(f"get_cash_balances() returned {len(cash_balances)} balances")

        db_manager = get_db_manager()
        exchange_rate_service = get_exchange_rate_service(db_manager)
        logger.info("Got db_manager and exchange_rate_service")

        logger.info("Starting database transaction...")
        async with db_manager.state.transaction():
            # Save Yahoo-derived prices before clearing (for price continuity)
            logger.info("Querying existing positions for price continuity...")
            cursor = await db_manager.state.execute(
                "SELECT symbol, current_price, market_value_eur FROM positions"
            )
            saved_price_data = {
                row[0]: {
                    "current_price": row[1],
                    "market_value_eur": row[2],
                }
                for row in await cursor.fetchall()
            }
            logger.info(f"Saved price data for {len(saved_price_data)} positions")

            # Derive first_bought_at (most recent buy) and last_sold_at from trades table
            logger.info("Querying trades table for buy/sell dates...")
            cursor = await db_manager.ledger.execute(
                """
                SELECT
                    symbol,
                    MAX(CASE WHEN UPPER(side) = 'BUY' THEN executed_at END) as first_buy,
                    MAX(CASE WHEN UPPER(side) = 'SELL' THEN executed_at END) as last_sell
                FROM trades
                GROUP BY symbol
            """
            )
            trade_dates = {
                row[0]: {"first_bought_at": row[1], "last_sold_at": row[2]}
                for row in await cursor.fetchall()
            }
            logger.info(f"Found trade dates for {len(trade_dates)} symbols")

            # Clear existing positions
            logger.info("Clearing existing positions...")
            await db_manager.state.execute("DELETE FROM positions")
            logger.info("Positions cleared")

            cash_balance = await _calculate_cash_balance_eur(
                cash_balances, exchange_rate_service
            )
            logger.info(f"Cash balance calculated: {cash_balance:.2f} EUR")

            event_bus = get_event_bus()
            total_value, invested_value, unrealized_pnl, geo_values = (
                await _process_positions(
                    positions,
                    saved_price_data,
                    trade_dates,
                    exchange_rate_service,
                    db_manager,
                    event_bus,
                )
            )

            await _create_portfolio_snapshot(
                total_value,
                cash_balance,
                invested_value,
                unrealized_pnl,
                geo_values,
                len(positions),
                db_manager,
            )

        logger.info(
            f"Portfolio sync complete: {len(positions)} positions, "
            f"total value: {total_value:.2f}, cash: {cash_balance:.2f}"
        )

        # Check and add missing portfolio securities to universe
        await _ensure_portfolio_securities_in_universe(positions, client, security_repo)

        # Sync security currencies
        await sync_security_currencies()

        # Sync prices from Yahoo
        await _sync_prices_internal()

        # Calculate portfolio hash after sync and invalidate caches if changed
        positions_after = await position_repo.get_all()
        cash_balances_after_raw = client.get_cash_balances()
        cash_balances_after = (
            {b.currency: b.amount for b in cash_balances_after_raw}
            if cash_balances_after_raw
            else {}
        )
        position_dicts_after = [
            {"symbol": p.symbol, "quantity": p.quantity} for p in positions_after
        ]
        # Use same pending_orders as before (they should still be pending)
        hash_after = generate_portfolio_hash(
            position_dicts_after, securities, cash_balances_after, pending_orders
        )
        logger.debug(f"Portfolio hash after sync: {hash_after}")

        # Only invalidate recommendation caches if portfolio hash changed
        if hash_before != hash_after:
            logger.info(
                f"Portfolio hash changed ({hash_before} -> {hash_after}), "
                "invalidating recommendation caches"
            )
            from app.infrastructure.cache_invalidation import (
                get_cache_invalidation_service,
            )

            cache_service = get_cache_invalidation_service()
            cache_service.invalidate_recommendation_caches()
        else:
            logger.debug(
                "Portfolio hash unchanged, skipping recommendation cache invalidation"
            )

        emit(SystemEvent.SYNC_COMPLETE)

    except Exception as e:
        logger.error(f"Portfolio sync failed: {e}")
        emit(SystemEvent.SYNC_COMPLETE)
        error_msg = "PORTFOLIO SYNC FAILED"
        emit(SystemEvent.ERROR_OCCURRED, message=error_msg)
        raise
    finally:
        set_led3(0, 0, 0)  # Clear LED when done
        set_led4(0, 0, 0)  # Clear LED when done


async def sync_prices():
    """
    Sync current prices for all securities in universe.

    Uses file locking to prevent concurrent syncs.
    """
    async with file_lock("price_sync", timeout=120.0):
        await _sync_prices_internal()


async def _sync_prices_internal():
    """Internal price sync implementation."""
    from app.repositories import SecurityRepository

    logger.info("Starting price sync")

    set_led3(0, 0, 255)  # Blue for sync
    emit(SystemEvent.SYNC_START)

    try:
        # Note: Direct DB access here is a known architecture violation.
        # This could use SecurityRepository.get_all_active() but needs yahoo_symbol field.
        # See README.md Architecture section for details.
        security_repo = SecurityRepository()
        securities = await security_repo.get_all_active()

        # Extract symbols and yahoo_symbols
        rows = [
            (security.symbol, security.yahoo_symbol)
            for security in securities
            if security.yahoo_symbol
        ]

        if not rows:
            logger.info("No securities to sync")
            emit(SystemEvent.SYNC_COMPLETE)
            return

        symbol_yahoo_map = {row[0]: row[1] for row in rows}

        quotes = yahoo.get_batch_quotes(symbol_yahoo_map)

        updated = 0
        now = datetime.now().isoformat()

        # Note: Direct DB access here is a known architecture violation.
        # This job needs to update positions directly. See README.md Architecture section for details.
        db_manager = get_db_manager()
        async with db_manager.state.transaction():
            for symbol, price in quotes.items():
                result = await db_manager.state.execute(
                    """
                    UPDATE positions
                    SET current_price = ?,
                        market_value_eur = quantity * ? / currency_rate,
                        last_updated = ?
                    WHERE symbol = ?
                    """,
                    (price, price, now, symbol),
                )
                if result.rowcount > 0:
                    updated += 1

        logger.info(
            f"Price sync complete: {len(quotes)} quotes, {updated} positions updated"
        )

        # Metrics in calculations.db will expire naturally via TTL
        # No manual invalidation needed
        logger.debug(f"Price sync complete for {len(quotes)} symbols")

        emit(SystemEvent.SYNC_COMPLETE)

    except Exception as e:
        logger.error(f"Price sync failed: {e}")
        emit(SystemEvent.SYNC_COMPLETE)
        error_msg = "PRICE SYNC FAILED"
        emit(SystemEvent.ERROR_OCCURRED, message=error_msg)
        raise


async def sync_security_currencies():
    """
    Fetch and store trading currency for all securities from Tradernet.
    """
    from app.repositories import SecurityRepository

    logger.info("Starting security currency sync")

    set_led3(0, 0, 255)  # Blue for sync

    client = get_tradernet_client()

    if not client.is_connected:
        if not client.connect():
            logger.error("Failed to connect to Tradernet for currency sync")
            return

    try:
        # Note: Using SecurityRepository instead of direct DB access
        security_repo = SecurityRepository()
        securities = await security_repo.get_all_active()
        symbols = [security.symbol for security in securities]

        if not symbols:
            logger.info("No securities to sync currencies for")
            return

        quotes_response = client.get_quotes_raw(symbols)
        q_list = _extract_quotes_list(quotes_response)

        updated = 0
        # Note: Direct DB access here is a known architecture violation.
        # This job needs to update security currency directly. See README.md Architecture section for details.
        db_manager = get_db_manager()
        async with db_manager.config.transaction():
            for q in q_list:
                if isinstance(q, dict):
                    symbol = q.get("c")
                    currency = q.get("x_curr")
                    if symbol and currency:
                        await db_manager.config.execute(
                            "UPDATE securities SET currency = ? WHERE symbol = ?",
                            (currency, symbol),
                        )
                        updated += 1

        logger.info(f"Security currency sync complete: updated {updated} securities")

    except Exception as e:
        logger.error(f"Security currency sync failed: {e}")
        raise


async def _ensure_portfolio_securities_in_universe(
    positions: list, client, security_repo: SecurityRepository
) -> None:
    """Ensure all portfolio securities are in the universe.

    For each position, checks if the security exists in the universe.
    If not, adds it using stock_setup_service which will:
    1. Get ISIN and Yahoo symbol from Tradernet
    2. Fetch data from Yahoo Finance (country, exchange, industry)
    3. Create the security in the database
    4. Fetch historical price data (10 years initial seed)
    5. Calculate and save the initial security score

    Args:
        positions: List of Position objects from Tradernet
        client: TradernetClient instance
        security_repo: SecurityRepository instance
    """
    if not positions:
        logger.debug("No positions to check for universe membership")
        return

    logger.info("Checking portfolio securities against universe...")

    # Get all position symbols
    position_symbols = [pos.symbol for pos in positions]
    logger.info(f"Checking {len(position_symbols)} portfolio symbols")

    # Check which securities are missing from universe
    missing_symbols = []
    for symbol in position_symbols:
        existing = await security_repo.get_by_symbol(symbol)
        if not existing:
            missing_symbols.append(symbol)
            logger.info(f"Portfolio security {symbol} not in universe - will add")

    if not missing_symbols:
        logger.info("All portfolio securities are already in universe")
        return

    logger.info(f"Adding {len(missing_symbols)} missing securities to universe...")

    # Import here to avoid circular dependencies
    from app.infrastructure.dependencies import (
        get_db_manager,
        get_score_repository,
        get_scoring_service,
    )
    from app.modules.universe.services.security_setup_service import (
        SecuritySetupService,
    )

    db_manager = get_db_manager()
    score_repo = get_score_repository()
    scoring_service = get_scoring_service(
        security_repo=security_repo,
        score_repo=score_repo,
        db_manager=db_manager,
    )
    stock_setup_service = SecuritySetupService(
        security_repo=security_repo,
        scoring_service=scoring_service,
        tradernet_client=client,
        db_manager=db_manager,
    )

    added_count = 0
    failed_count = 0

    for symbol in missing_symbols:
        try:
            logger.info(f"Adding {symbol} to universe...")
            security = await stock_setup_service.add_security_by_identifier(
                identifier=symbol,
                min_lot=1,
                allow_buy=True,
                allow_sell=True,
            )
            logger.info(
                f"Successfully added {symbol} to universe "
                f"(ISIN: {security.isin}, Yahoo: {security.yahoo_symbol})"
            )
            added_count += 1
        except ValueError as e:
            # Security already exists (race condition) or invalid identifier
            logger.warning(f"Could not add {symbol}: {e}")
            failed_count += 1
        except Exception as e:
            logger.error(f"Failed to add {symbol} to universe: {e}", exc_info=True)
            failed_count += 1

    logger.info(f"Universe update complete: {added_count} added, {failed_count} failed")

    if added_count > 0:
        logger.info(
            f"Added {added_count} new securities to universe. "
            "Historical data sync will populate price histories."
        )
