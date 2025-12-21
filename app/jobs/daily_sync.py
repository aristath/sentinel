"""Daily sync jobs for portfolio and prices."""

import logging
from datetime import datetime

import aiosqlite

from app.config import settings
from app.services.tradernet import get_tradernet_client
from app.services import yahoo
from app.led.display import get_led_display, update_balance_display

logger = logging.getLogger(__name__)


async def sync_portfolio():
    """
    Sync portfolio positions from Tradernet to local database.

    This job:
    1. Fetches current positions from Tradernet
    2. Updates local positions table
    3. Creates a daily portfolio snapshot
    """
    logger.info("Starting portfolio sync")

    # Show syncing animation on LED
    display = get_led_display()
    if display.is_connected:
        display.show_syncing()
        display.set_system_status("syncing")

    client = get_tradernet_client()

    if not client.is_connected:
        if not client.connect():
            logger.error("Failed to connect to Tradernet, skipping sync")
            if display.is_connected:
                display.set_system_status("error")
            return

    try:
        # Get positions from Tradernet
        positions = client.get_portfolio()
        cash_balance = client.get_total_cash_eur()

        async with aiosqlite.connect(settings.database_path) as db:
            # Clear old positions
            await db.execute("DELETE FROM positions")

            # Insert current positions
            total_value = 0.0
            geo_values = {"EU": 0.0, "ASIA": 0.0, "US": 0.0}

            for pos in positions:
                await db.execute(
                    """
                    INSERT INTO positions
                    (symbol, quantity, avg_price, current_price, currency, currency_rate, market_value_eur, last_updated)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        pos.symbol,
                        pos.quantity,
                        pos.avg_price,
                        pos.current_price,
                        pos.currency,
                        pos.currency_rate,
                        pos.market_value_eur,
                        datetime.now().isoformat(),
                    ),
                )

                # Use market_value_eur (converted to EUR)
                market_value = pos.market_value_eur
                total_value += market_value

                # Determine geography from symbol suffix or stocks table
                geo = None
                cursor = await db.execute(
                    "SELECT geography FROM stocks WHERE symbol = ?",
                    (pos.symbol,)
                )
                row = await cursor.fetchone()
                if row:
                    geo = row[0]
                else:
                    # Infer geography from symbol suffix
                    symbol = pos.symbol.upper()
                    if symbol.endswith(".GR") or symbol.endswith(".DE") or symbol.endswith(".PA"):
                        geo = "EU"
                    elif symbol.endswith(".AS") or symbol.endswith(".HK") or symbol.endswith(".T"):
                        geo = "ASIA"
                    elif symbol.endswith(".US"):
                        geo = "US"

                if geo:
                    geo_values[geo] = geo_values.get(geo, 0) + market_value

            # Create daily snapshot
            today = datetime.now().strftime("%Y-%m-%d")
            await db.execute(
                """
                INSERT OR REPLACE INTO portfolio_snapshots
                (date, total_value, cash_balance, geo_eu_pct, geo_asia_pct, geo_us_pct)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    today,
                    total_value,
                    cash_balance,
                    geo_values["EU"] / total_value if total_value else 0,
                    geo_values["ASIA"] / total_value if total_value else 0,
                    geo_values["US"] / total_value if total_value else 0,
                ),
            )

            await db.commit()

            # Update LED with new balance
            await update_balance_display(db)

        logger.info(
            f"Portfolio sync complete: {len(positions)} positions, "
            f"total value: {total_value:.2f}, cash: {cash_balance:.2f}"
        )

        # Set LED status to OK
        if display.is_connected:
            display.set_system_status("ok")
            display.show_success()

    except Exception as e:
        logger.error(f"Portfolio sync failed: {e}")
        if display.is_connected:
            display.set_system_status("error")
        raise


async def sync_prices():
    """
    Sync current prices for all stocks in universe.

    This job:
    1. Fetches current prices from Yahoo Finance
    2. Updates positions with current prices
    """
    logger.info("Starting price sync")

    # Show syncing animation on LED
    display = get_led_display()
    if display.is_connected:
        display.show_syncing()
        display.set_system_status("syncing")

    try:
        async with aiosqlite.connect(settings.database_path) as db:
            # Get all active stocks
            cursor = await db.execute(
                "SELECT symbol FROM stocks WHERE active = 1"
            )
            rows = await cursor.fetchall()
            symbols = [row[0] for row in rows]

            if not symbols:
                logger.info("No stocks to sync")
                return

            # Get batch quotes from Yahoo Finance
            quotes = yahoo.get_batch_quotes(symbols)

            # Update positions with new prices
            updated = 0
            for symbol, price in quotes.items():
                result = await db.execute(
                    """
                    UPDATE positions
                    SET current_price = ?, last_updated = ?
                    WHERE symbol = ?
                    """,
                    (price, datetime.now().isoformat(), symbol),
                )
                if result.rowcount > 0:
                    updated += 1

            await db.commit()

            # Update LED with new balance
            await update_balance_display(db)

        logger.info(f"Price sync complete: {len(quotes)} quotes, {updated} positions updated")

        # Set LED status to OK
        if display.is_connected:
            display.set_system_status("ok")

    except Exception as e:
        logger.error(f"Price sync failed: {e}")
        if display.is_connected:
            display.set_system_status("error")
        raise
