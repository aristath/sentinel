"""
Resumable backfill of historical HMM regime_states.

For each (date, symbol) with enough price history: runs current HMM model on
features truncated to that date and inserts one row into regime_states.
Resumable: skips existing (symbol, date).

Run from repo root with venv active:

    python scripts/backfill_regime_states.py
"""

import asyncio
import logging
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sentinel import Database
from sentinel.regime_hmm import RegimeDetector

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

LOOKBACK_DAYS = 504  # ~2 years for HMM feature extraction (align with RegimeDetector)


async def main() -> None:
    db = Database()
    await db.connect()
    try:
        # Date range from prices
        cursor = await db.conn.execute("SELECT MIN(date) AS min_date, MAX(date) AS max_date FROM prices")
        row = await cursor.fetchone()
        if not row or not row["min_date"] or not row["max_date"]:
            logger.error("No price data in database. Run price sync first.")
            return

        min_date = row["min_date"]
        max_date = row["max_date"]
        logger.info("Price date range: %s to %s", min_date, max_date)

        # Symbols: all with at least LOOKBACK_DAYS of prices (we'll skip per-date if insufficient)
        securities = await db.get_all_securities(active_only=False)
        symbols = [s["symbol"] for s in securities]
        logger.info("Symbols: %d", len(symbols))

        detector = RegimeDetector(lookback_days=LOOKBACK_DAYS)
        detector._db = db

        current = datetime.strptime(min_date, "%Y-%m-%d").date()
        end = datetime.strptime(max_date, "%Y-%m-%d").date()
        total_inserted = 0
        total_skipped = 0

        while current <= end:
            date_str = current.isoformat()

            for symbol in symbols:
                try:
                    # Resumability
                    cursor = await db.conn.execute(
                        "SELECT 1 FROM regime_states WHERE symbol = ? AND date = ?",
                        (symbol, date_str),
                    )
                    if await cursor.fetchone():
                        total_skipped += 1
                        continue

                    result = await detector.detect_regime_as_of(symbol, date_str)
                    if result is None:
                        continue
                    await detector.store_regime_state_for_date(
                        symbol,
                        date_str,
                        result["regime"],
                        result["regime_name"],
                        result["confidence"],
                    )
                    total_inserted += 1
                except Exception as e:
                    logger.warning("  %s @ %s: %s", symbol, date_str, e)

            await db.conn.commit()
            if current.day == 1 or (current - current.replace(day=1)).days < 2:
                logger.info("  Date %s: inserted=%d (total), skipped=%d", date_str, total_inserted, total_skipped)
            current = datetime.fromordinal(current.toordinal() + 1).date()

        logger.info("Done. Total inserted=%d, skipped (already exist)=%d", total_inserted, total_skipped)
    finally:
        await db.close()


if __name__ == "__main__":
    asyncio.run(main())
