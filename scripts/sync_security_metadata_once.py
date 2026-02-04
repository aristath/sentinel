"""
One-off script: populate securities.data (metadata) for all securities,
including inactive ones. Run from repo root with venv active:

    python scripts/sync_security_metadata_once.py
"""

import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sentinel import Broker, Database

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def main() -> None:
    db = Database()
    await db.connect()
    broker = Broker()
    if not await broker.connect():
        logger.error("Broker not connected (missing credentials?). Exiting.")
        return

    securities = await db.get_all_securities(active_only=False)
    # Only those missing metadata to avoid unnecessary API calls
    missing = [s for s in securities if not s.get("data")]

    if not missing:
        logger.info("All securities already have metadata. Nothing to do.")
        return

    logger.info("Syncing metadata for %d securities (missing data)", len(missing))
    synced = 0
    failed = 0

    for sec in missing:
        symbol = sec["symbol"]
        try:
            info = await broker.get_security_info(symbol)
            if info:
                market_id = str(info.get("mrkt", {}).get("mkt_id", ""))
                await db.update_security_metadata(symbol, info, market_id)
                synced += 1
                logger.info("  %s OK", symbol)
            else:
                failed += 1
                logger.warning("  %s no info from broker", symbol)
        except Exception as e:
            failed += 1
            logger.warning("  %s failed: %s", symbol, e)

    logger.info("Done. Synced=%d, failed=%d", synced, failed)


if __name__ == "__main__":
    asyncio.run(main())
