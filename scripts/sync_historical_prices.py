#!/usr/bin/env python3
"""One-off script to sync historical prices (20 years) for all or one security.

When syncing all symbols, requests are sent one symbol at a time with a delay
between each to avoid API limits.

Usage (from repo root with venv activated):
    python scripts/sync_historical_prices.py
    python scripts/sync_historical_prices.py --symbol AAPL.US
    python scripts/sync_historical_prices.py --delay 10
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

# Ensure project root is on path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sentinel.broker import Broker
from sentinel.cache import Cache
from sentinel.database import Database
from sentinel.settings import Settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


async def main() -> None:
    parser = argparse.ArgumentParser(description="Sync historical prices (20 years)")
    parser.add_argument("--symbol", type=str, help="Sync only this symbol (e.g. AAPL.US)")
    parser.add_argument(
        "--delay",
        type=float,
        default=10.0,
        help="Seconds to wait between each symbol when syncing all (default: 10)",
    )
    args = parser.parse_args()

    db = Database()
    await db.connect()
    logger.info("Database connected")

    settings = Settings()
    await settings.init_defaults()

    broker = Broker()
    if not await broker.connect():
        logger.error("Broker not connected (missing TraderNet credentials?). Aborting.")
        sys.exit(1)
    logger.info("Broker connected")

    if args.symbol:
        # Single symbol: fetch and save without clearing full caches
        symbol = args.symbol.strip()
        logger.info("Fetching 20 years of history for %s", symbol)
        prices = await broker.get_historical_prices_bulk([symbol], years=20)
        if symbol in prices and prices[symbol]:
            await db.save_prices(symbol, prices[symbol])
            logger.info("Saved %d rows for %s", len(prices[symbol]), symbol)
        else:
            logger.warning("No data returned for %s", symbol)
    else:
        # All symbols: one request per symbol with delay between
        cache = Cache("motion")
        cleared = cache.clear()
        logger.info("Cleared %d cached analyses before price sync", cleared)
        securities = await db.get_all_securities(active_only=True)
        symbols = [s["symbol"] for s in securities]
        total = len(symbols)
        logger.info("Syncing %d symbols one-by-one with %.1fs delay between requests", total, args.delay)

        synced = 0
        for i, symbol in enumerate(symbols, 1):
            logger.info("[%d/%d] Fetching 20 years for %s", i, total, symbol)
            prices = await broker.get_historical_prices_bulk([symbol], years=20)
            if symbol in prices and prices[symbol]:
                await db.save_prices(symbol, prices[symbol])
                synced += 1
                logger.info("Saved %d rows for %s", len(prices[symbol]), symbol)
            else:
                logger.warning("No data returned for %s", symbol)
            if i < total:
                await asyncio.sleep(args.delay)

        logger.info("Historical price sync finished: %d/%d securities updated", synced, total)

    await db.close()


if __name__ == "__main__":
    asyncio.run(main())
