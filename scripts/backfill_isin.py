"""
Backfill ISIN for existing securities.

This script fetches ISIN (International Securities Identification Number) from
Tradernet's security_info API for all securities that don't have ISIN set.

ISIN is used as a universal identifier for Yahoo Finance lookups, especially
for securities with ambiguous Tradernet symbols (like .EU securities).

Run this script after adding the ISIN column to the securities table.
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.config import settings  # noqa: E402
from app.core.database.manager import init_databases  # noqa: E402
from app.infrastructure.external.tradernet import get_tradernet_client  # noqa: E402
from app.modules.universe.database.security_repository import (  # noqa: E402
    SecurityRepository,
)
from app.modules.universe.domain.symbol_resolver import is_isin  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def backfill_isin():
    """Fetch and update ISIN for all securities missing ISIN."""
    logger.info("Starting ISIN backfill...")

    # Initialize database manager
    db_manager = await init_databases(settings.data_dir)
    security_repo = SecurityRepository()

    # Connect to Tradernet
    tradernet = get_tradernet_client()
    if not tradernet.connect():
        logger.error("Failed to connect to Tradernet API")
        await db_manager.close_all()
        return

    try:
        # Get all active securities
        securities = await security_repo.get_all_active()
        logger.info(f"Found {len(securities)} active securities")

        # Filter to securities without ISIN
        stocks_without_isin = [s for s in securities if not s.isin]
        logger.info(f"{len(stocks_without_isin)} securities need ISIN lookup")

        if not stocks_without_isin:
            logger.info("All securities already have ISIN, nothing to do")
            return

        # Fetch ISIN for each security using get_quotes_raw (ISIN is in issue_nb field)
        success_count = 0
        failure_count = 0

        for security in stocks_without_isin:
            try:
                logger.info(f"Fetching ISIN for {security.symbol}...")
                response = tradernet.get_quotes_raw([security.symbol])

                # Response format: {'result': {'q': [quote_data, ...]}}
                if response and isinstance(response, dict):
                    quotes_list = response.get("result", {}).get("q", [])
                    if quotes_list and len(quotes_list) > 0:
                        quote_data = quotes_list[0]
                        isin = quote_data.get("issue_nb")
                        if isin and is_isin(isin):
                            # Update security with ISIN
                            await security_repo.update(security.symbol, isin=isin)
                            logger.info(f"  {security.symbol} -> {isin}")
                            success_count += 1
                        else:
                            logger.warning(
                                f"  {security.symbol}: No valid ISIN in response"
                            )
                            failure_count += 1
                    else:
                        logger.warning(f"  {security.symbol}: No quote data returned")
                        failure_count += 1
                else:
                    logger.warning(f"  {security.symbol}: Invalid response format")
                    failure_count += 1

            except Exception as e:
                logger.error(f"  {security.symbol}: Error fetching ISIN: {e}")
                failure_count += 1

        logger.info(
            f"ISIN backfill complete: {success_count} updated, {failure_count} failed"
        )

    except Exception as e:
        logger.error(f"Backfill failed: {e}", exc_info=True)
        raise
    finally:
        await db_manager.close_all()


if __name__ == "__main__":
    asyncio.run(backfill_isin())
