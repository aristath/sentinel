"""
One-off script: backfill historical scores for all securities (active and inactive).

For each date in the price range, runs scoring on prices up to that date and inserts
a row into scores. Resumable (skips existing symbol+date). No regime/ML in v1.

Run from repo root with venv active:

    python scripts/backfill_scores.py
"""

import asyncio
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sentinel import Database
from sentinel.analyzer import Analyzer
from sentinel.price_validator import PriceValidator

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

MIN_DAYS = 252  # ~1 year of data required for scoring
LOOKBACK_DAYS = 10 * 252  # 10 years when fetching prices up to end_date


def end_of_day_utc_ts(date_str: str) -> int:
    """Return Unix timestamp for end of date_str (YYYY-MM-DD) in UTC."""
    dt = datetime.strptime(date_str + " 23:59:59", "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    return int(dt.timestamp())


async def main() -> None:
    db = Database()
    await db.connect()
    try:
        analyzer = Analyzer(db=db)
        price_validator = PriceValidator()

        # Date range from prices
        cursor = await db.conn.execute("SELECT MIN(date) AS min_date, MAX(date) AS max_date FROM prices")
        row = await cursor.fetchone()
        if not row or not row["min_date"] or not row["max_date"]:
            logger.error("No price data in database. Run price sync first.")
            return

        min_date = row["min_date"]
        max_date = row["max_date"]
        logger.info("Price date range: %s to %s", min_date, max_date)

        securities = await db.get_all_securities(active_only=False)
        symbols = [s["symbol"] for s in securities]
        logger.info("Securities: %d (all)", len(symbols))

        # Iterate dates (chronological)
        current = datetime.strptime(min_date, "%Y-%m-%d").date()
        end = datetime.strptime(max_date, "%Y-%m-%d").date()
        total_inserted = 0
        total_skipped = 0

        while current <= end:
            date_str = current.isoformat()
            calculated_at = end_of_day_utc_ts(date_str)

            for symbol in symbols:
                try:
                    prices = await db.get_prices(symbol, days=LOOKBACK_DAYS, end_date=date_str)
                    if len(prices) < MIN_DAYS:
                        continue

                    # Validate and interpolate prices (match training pipeline)
                    # prices from DB are newest-first; validator expects oldest-first
                    validated = price_validator.validate_and_interpolate(list(reversed(prices)))
                    if len(validated) < MIN_DAYS:
                        continue

                    # analyze_prices expects newest-first
                    result = await analyzer.analyze_prices(symbol, list(reversed(validated)))
                    if result is None:
                        continue
                    score, components = result
                    # Store only serializable components (exclude numpy arrays)
                    serializable = {
                        k: v
                        for k, v in components.items()
                        if k
                        not in (
                            "long_term_component",
                            "medium_term_component",
                            "short_term_component",
                            "noise_component",
                        )
                    }
                    # Resumable: skip if we already have this (symbol, calculated_at)
                    cursor = await db.conn.execute(
                        "SELECT 1 FROM scores WHERE symbol = ? AND calculated_at = ?",
                        (symbol, calculated_at),
                    )
                    if await cursor.fetchone():
                        total_skipped += 1
                        continue
                    await db.conn.execute(
                        """INSERT INTO scores (symbol, score, components, calculated_at)
                           VALUES (?, ?, ?, ?)""",
                        (symbol, score, json.dumps(serializable), calculated_at),
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
