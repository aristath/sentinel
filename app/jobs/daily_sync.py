"""Daily sync jobs for portfolio and prices."""

import logging
from datetime import datetime

from app.config import settings
from app.infrastructure.external.tradernet import get_tradernet_client
from app.infrastructure.external import yahoo_finance as yahoo
from app.infrastructure.events import emit, SystemEvent
from app.infrastructure.hardware.led_display import set_activity
from app.infrastructure.locking import file_lock
from app.infrastructure.database.manager import get_db_manager
from app.domain.value_objects.currency import Currency
from app.domain.events import PositionUpdatedEvent, get_event_bus
from app.domain.models import Position

logger = logging.getLogger(__name__)


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


async def _sync_portfolio_internal():
    """Internal portfolio sync implementation."""
    logger.info("Starting portfolio sync")

    set_activity("SYNCING PORTFOLIO...", duration=30.0)
    emit(SystemEvent.SYNC_START)

    client = get_tradernet_client()

    if not client.is_connected:
        if not client.connect():
            logger.error("Failed to connect to Tradernet, skipping sync")
            emit(SystemEvent.ERROR_OCCURRED, message="BROKER CONNECTION FAILED")
            return

    try:
        # Get positions and cash balances from Tradernet
        positions = client.get_portfolio()
        cash_balances = client.get_cash_balances()

        db_manager = get_db_manager()

        async with db_manager.state.transaction():
            # Save Yahoo-derived prices before clearing (for price continuity)
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

            # Derive first_bought_at and last_sold_at from trades table
            cursor = await db_manager.ledger.execute("""
                SELECT
                    symbol,
                    MIN(CASE WHEN UPPER(side) = 'BUY' THEN executed_at END) as first_buy,
                    MAX(CASE WHEN UPPER(side) = 'SELL' THEN executed_at END) as last_sell
                FROM trades
                GROUP BY symbol
            """)
            trade_dates = {
                row[0]: {"first_bought_at": row[1], "last_sold_at": row[2]}
                for row in await cursor.fetchall()
            }

            # Clear existing positions
            await db_manager.state.execute("DELETE FROM positions")

            # Pre-fetch exchange rates for all currencies we'll need (positions + cash)
            currencies_needed = set()
            for pos in positions:
                currency = pos.currency or Currency.EUR
                if currency != Currency.EUR:
                    currencies_needed.add(str(currency))
            for cb in cash_balances:
                if cb.currency != "EUR":
                    currencies_needed.add(cb.currency)

            # Fetch rates with simple HTTP call and fallback
            exchange_rates = {"EUR": 1.0}
            if currencies_needed:
                try:
                    import httpx
                    async with httpx.AsyncClient() as client:
                        response = await client.get(
                            "https://api.exchangerate-api.com/v4/latest/EUR",
                            timeout=10.0
                        )
                        if response.status_code == 200:
                            api_rates = response.json().get("rates", {})
                            for curr in currencies_needed:
                                if curr in api_rates:
                                    exchange_rates[curr] = api_rates[curr]
                                    logger.info(f"Exchange rate {curr}/EUR: {api_rates[curr]}")
                except Exception as e:
                    logger.warning(f"Failed to fetch exchange rates: {e}")

            # Apply fallbacks for any missing rates
            fallback_rates = {"USD": 1.05, "HKD": 8.33, "GBP": 0.85}
            for curr in currencies_needed:
                if curr not in exchange_rates:
                    exchange_rates[curr] = fallback_rates.get(curr, 1.0)
                    logger.warning(f"Using fallback rate for {curr}: {exchange_rates[curr]}")

            # Calculate cash balance in EUR using fetched rates
            cash_balance = 0.0
            for cb in cash_balances:
                if cb.currency == "EUR":
                    cash_balance += cb.amount
                elif cb.amount > 0:
                    rate = exchange_rates.get(cb.currency, 1.0)
                    cash_balance += cb.amount / rate
            logger.info(f"Cash balance calculated: {cash_balance:.2f} EUR")

            # Insert current positions
            total_value = 0.0
            invested_value = 0.0
            unrealized_pnl = 0.0
            geo_values = {"EU": 0.0, "ASIA": 0.0, "US": 0.0}

            for pos in positions:
                price_data = saved_price_data.get(pos.symbol, {})
                dates = trade_dates.get(pos.symbol, {})

                current_price = price_data.get("current_price")
                market_value_eur = price_data.get("market_value_eur")

                # Use pre-fetched exchange rate
                currency = pos.currency or Currency.EUR
                exchange_rate = exchange_rates.get(str(currency), 1.0)

                if current_price and exchange_rate > 0:
                    market_value_eur = pos.quantity * current_price / exchange_rate

                # Calculate cost basis (invested value)
                cost_basis_eur = pos.quantity * pos.avg_price / exchange_rate if exchange_rate > 0 else pos.quantity * pos.avg_price
                invested_value += cost_basis_eur

                # Calculate unrealized P&L
                if current_price and exchange_rate > 0:
                    position_unrealized_pnl = (current_price - pos.avg_price) * pos.quantity / exchange_rate
                    unrealized_pnl += position_unrealized_pnl

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
                        exchange_rate,  # Use fresh rate from ExchangeRateService
                        market_value_eur,
                        datetime.now().isoformat(),
                        dates.get("first_bought_at"),
                        dates.get("last_sold_at"),
                    )
                )
                
                # Publish domain event for position update
                # Create Position object for event (with updated market_value_eur)
                updated_position = Position(
                    symbol=pos.symbol,
                    quantity=pos.quantity,
                    avg_price=pos.avg_price,
                    currency=pos.currency or Currency.EUR,
                    currency_rate=exchange_rate,  # Use fresh rate
                    current_price=current_price,
                    market_value_eur=market_value_eur,
                )
                event_bus = get_event_bus()
                event_bus.publish(PositionUpdatedEvent(position=updated_position))

                market_value = market_value_eur or 0
                total_value += market_value

                # Determine geography from config
                cursor = await db_manager.config.execute(
                    "SELECT geography FROM stocks WHERE symbol = ?",
                    (pos.symbol,)
                )
                row = await cursor.fetchone()
                if row:
                    geo = row[0]
                else:
                    symbol = pos.symbol.upper()
                    if symbol.endswith(".GR") or symbol.endswith(".DE") or symbol.endswith(".PA"):
                        geo = "EU"
                    elif symbol.endswith(".AS") or symbol.endswith(".HK") or symbol.endswith(".T"):
                        geo = "ASIA"
                    elif symbol.endswith(".US"):
                        geo = "US"
                    else:
                        geo = None

                if geo:
                    geo_values[geo] = geo_values.get(geo, 0) + market_value

            # Create daily snapshot
            today = datetime.now().strftime("%Y-%m-%d")
            position_count = len(positions)
            await db_manager.state.execute(
                """
                INSERT OR REPLACE INTO portfolio_snapshots
                (date, total_value, cash_balance, invested_value, unrealized_pnl,
                 geo_eu_pct, geo_asia_pct, geo_us_pct, position_count, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
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
                ),
            )

        logger.info(
            f"Portfolio sync complete: {len(positions)} positions, "
            f"total value: {total_value:.2f}, cash: {cash_balance:.2f}"
        )

        # Sync stock currencies
        await sync_stock_currencies()

        # Sync prices from Yahoo
        await _sync_prices_internal()

        emit(SystemEvent.SYNC_COMPLETE)

    except Exception as e:
        logger.error(f"Portfolio sync failed: {e}")
        emit(SystemEvent.SYNC_COMPLETE)
        emit(SystemEvent.ERROR_OCCURRED, message="PORTFOLIO SYNC FAILED")
        raise


async def sync_prices():
    """
    Sync current prices for all stocks in universe.

    Uses file locking to prevent concurrent syncs.
    """
    async with file_lock("price_sync", timeout=120.0):
        await _sync_prices_internal()


async def _sync_prices_internal():
    """Internal price sync implementation."""
    logger.info("Starting price sync")

    set_activity("UPDATING STOCK PRICES...", duration=60.0)
    emit(SystemEvent.SYNC_START)

    try:
        db_manager = get_db_manager()

        # Get active stocks from config
        cursor = await db_manager.config.execute(
            "SELECT symbol, yahoo_symbol FROM stocks WHERE active = 1"
        )
        rows = await cursor.fetchall()

        if not rows:
            logger.info("No stocks to sync")
            emit(SystemEvent.SYNC_COMPLETE)
            return

        symbol_yahoo_map = {row[0]: row[1] for row in rows}

        quotes = yahoo.get_batch_quotes(symbol_yahoo_map)

        updated = 0
        now = datetime.now().isoformat()

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

        logger.info(f"Price sync complete: {len(quotes)} quotes, {updated} positions updated")

        # Metrics in calculations.db will expire naturally via TTL
        # No manual invalidation needed
        logger.debug(f"Price sync complete for {len(quotes)} symbols")

        emit(SystemEvent.SYNC_COMPLETE)

    except Exception as e:
        logger.error(f"Price sync failed: {e}")
        emit(SystemEvent.SYNC_COMPLETE)
        emit(SystemEvent.ERROR_OCCURRED, message="PRICE SYNC FAILED")
        raise


async def sync_stock_currencies():
    """
    Fetch and store trading currency for all stocks from Tradernet.
    """
    logger.info("Starting stock currency sync")

    set_activity("SYNCING STOCK CURRENCIES...", duration=30.0)

    client = get_tradernet_client()

    if not client.is_connected:
        if not client.connect():
            logger.error("Failed to connect to Tradernet for currency sync")
            return

    try:
        db_manager = get_db_manager()

        # Get all active stock symbols from config
        cursor = await db_manager.config.execute(
            "SELECT symbol FROM stocks WHERE active = 1"
        )
        symbols = [row[0] for row in await cursor.fetchall()]

        if not symbols:
            logger.info("No stocks to sync currencies for")
            return

        # Fetch quotes to get x_curr
        quotes_response = client.get_quotes_raw(symbols)

        if isinstance(quotes_response, list):
            q_list = quotes_response
        elif isinstance(quotes_response, dict):
            q_list = quotes_response.get("result", {}).get("q", [])
            if not q_list:
                q_list = quotes_response.get("q", [])
        else:
            q_list = []

        updated = 0
        async with db_manager.config.transaction():
            for q in q_list:
                if isinstance(q, dict):
                    symbol = q.get("c")
                    currency = q.get("x_curr")
                    if symbol and currency:
                        await db_manager.config.execute(
                            "UPDATE stocks SET currency = ? WHERE symbol = ?",
                            (currency, symbol)
                        )
                        updated += 1

        logger.info(f"Stock currency sync complete: updated {updated} stocks")

    except Exception as e:
        logger.error(f"Stock currency sync failed: {e}")
        raise
