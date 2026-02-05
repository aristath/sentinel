"""
Resumable backfill of historical ML predictions.

For each (date, symbol) with a trained model and ml_enabled: computes features and
wavelet score as of that date, runs the current ML model with historical regime from
OHLCV, and inserts one row into ml_predictions with predicted_at = end-of-day T.
Uses current model on historical features (no retraining). Resumable: skips existing
(symbol, predicted_at).

Run from repo root with venv active:

    python scripts/backfill_ml_predictions.py
"""

import asyncio
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))

from sentinel import Database
from sentinel.ml_ensemble import EnsembleBlender
from sentinel.ml_features import FeatureExtractor
from sentinel.ml_predictor import MLPredictor
from sentinel.price_validator import PriceValidator
from sentinel.regime_quote import quote_data_from_prices

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

MIN_DAYS = 200  # minimum price rows for feature extraction (align with ml_features)
LOOKBACK_DAYS = 10 * 252  # ~10 years when fetching prices up to end_date


def end_of_day_utc_ts(date_str: str) -> int:
    """Return Unix timestamp for end of date_str (YYYY-MM-DD) in UTC."""
    dt = datetime.strptime(date_str + " 23:59:59", "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    return int(dt.timestamp())


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

        # Symbols: ml_enabled and model exists
        securities = await db.get_all_securities(active_only=False)
        symbols_with_ml = []
        for s in securities:
            if not s.get("ml_enabled"):
                continue
            if not EnsembleBlender.model_exists(s["symbol"]):
                continue
            symbols_with_ml.append(s["symbol"])

        if not symbols_with_ml:
            logger.warning("No securities with ml_enabled and a trained model. Nothing to backfill.")
            return

        logger.info("Symbols with ML enabled and model: %d", len(symbols_with_ml))

        predictor = MLPredictor(db=db)
        feature_extractor = FeatureExtractor(db=db)
        price_validator = PriceValidator()

        current = datetime.strptime(min_date, "%Y-%m-%d").date()
        end = datetime.strptime(max_date, "%Y-%m-%d").date()
        total_inserted = 0
        total_skipped = 0

        while current <= end:
            date_str = current.isoformat()
            predicted_at_ts = end_of_day_utc_ts(date_str)

            for symbol in symbols_with_ml:
                try:
                    # Resumability
                    cursor = await db.conn.execute(
                        "SELECT 1 FROM ml_predictions WHERE symbol = ? AND predicted_at = ?",
                        (symbol, predicted_at_ts),
                    )
                    if await cursor.fetchone():
                        total_skipped += 1
                        continue

                    # Prices up to date_str
                    prices = await db.get_prices(symbol, days=LOOKBACK_DAYS, end_date=date_str)
                    if len(prices) < MIN_DAYS:
                        continue

                    # Validate and interpolate prices (match training pipeline)
                    # prices from DB are newest-first; validator expects oldest-first
                    validated = price_validator.validate_and_interpolate(list(reversed(prices)))
                    if len(validated) < MIN_DAYS:
                        continue

                    # Wavelet score as of date
                    wavelet_score = await db.get_score(symbol, as_of_date=predicted_at_ts)
                    if wavelet_score is None:
                        wavelet_score = 0.0

                    # Features: price_data chronological (oldest first) for extract_features
                    price_df = pd.DataFrame(
                        validated,
                        columns=["date", "open", "high", "low", "close", "volume"],
                    )

                    sec = await db.get_security(symbol)
                    security_data = (
                        {"geography": sec.get("geography", ""), "industry": sec.get("industry", "")} if sec else None
                    )

                    features = await feature_extractor.extract_features(
                        symbol=symbol,
                        date=date_str,
                        price_data=price_df,
                        sentiment_score=None,
                        security_data=security_data,
                    )
                    if features is None:
                        continue

                    # Regime from OHLCV (quote_data_from_prices expects newest-first)
                    quote_data = quote_data_from_prices(list(reversed(validated)))

                    ml_enabled = True
                    ml_blend_ratio = float(sec.get("ml_blend_ratio", 0.5)) if sec else 0.5

                    await predictor.predict_and_blend(
                        symbol=symbol,
                        date=date_str,
                        wavelet_score=wavelet_score,
                        ml_enabled=ml_enabled,
                        ml_blend_ratio=ml_blend_ratio,
                        features=features,
                        quote_data=quote_data,
                        predicted_at_ts=predicted_at_ts,
                        skip_cache=True,
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
