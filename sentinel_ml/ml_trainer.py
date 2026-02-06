"""Generate ML training data from historical market data."""

import logging
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import pandas as pd

from sentinel_ml.adapters import MonolithDBAdapter, MonolithSettingsAdapter
from sentinel_ml.clients.monolith_client import MonolithDataClient
from sentinel_ml.database.ml import MLDatabase
from sentinel_ml.ml_features import FeatureExtractor
from sentinel_ml.price_validator import PriceValidator

logger = logging.getLogger(__name__)


class TrainingDataGenerator:
    """Generate ML training data from historical price data."""

    def __init__(self, db=None, ml_db=None, settings=None):
        client = MonolithDataClient()
        self.db = db or MonolithDBAdapter(client)
        self.ml_db = ml_db or MLDatabase()
        self.feature_extractor = FeatureExtractor(db=self.db)
        self.settings = settings or MonolithSettingsAdapter(client)
        self.price_validator = PriceValidator()

    async def generate_training_data(
        self,
        start_date: str = "2006-01-01",
        end_date: str | None = None,
        symbols: Optional[List[str]] = None,
        prediction_horizon_days: int = 14,
    ) -> pd.DataFrame:
        """
        Generate training samples from historical data.

        Process:
        1. Get list of symbols (universe)
        2. For each symbol, create rolling windows
        3. For each window:
           a. Extract features at time T (price, volume, technical indicators, market context)
           b. Calculate actual return from T to T+14 days (label)
           c. Store sample
        4. Save to database

        Args:
            start_date: Start of historical data
            end_date: End of historical data (default: yesterday)
            symbols: List of symbols (default: get from database)
            prediction_horizon_days: Days ahead to predict (7 or 14)

        Returns:
            DataFrame with all training samples
        """
        await self.db.connect()
        await self.ml_db.connect()

        if end_date is None:
            end_date = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

        if symbols is None:
            symbols = await self._get_universe_symbols()

        all_samples = []
        total_symbols = len(symbols)

        logger.info(f"Generating training data for {total_symbols} symbols...")
        logger.info(f"Period: {start_date} to {end_date}")
        logger.info(f"Prediction horizon: {prediction_horizon_days} days")

        # Pre-fetch all security data for aggregate feature lookups
        all_securities = await self.db.get_all_securities(active_only=False)
        security_data_map = {s["symbol"]: s for s in all_securities}

        for idx, symbol in enumerate(symbols):
            if (idx + 1) % 10 == 0 or idx == 0:
                logger.info(f"[{idx + 1}/{total_symbols}] Processing {symbol}...")

            price_data = await self._get_price_data(symbol, start_date, end_date)
            if price_data is None or len(price_data) < 200:
                continue

            # Get security data for aggregate features
            security_data = security_data_map.get(symbol)

            # Create samples with rolling windows (every week)
            samples = await self._create_samples_for_symbol(
                symbol=symbol,
                price_data=price_data,
                prediction_horizon_days=prediction_horizon_days,
                security_data=security_data,
            )

            all_samples.extend(samples)

        # Convert to DataFrame
        df = pd.DataFrame(all_samples)

        if len(df) == 0:
            logger.warning("No training samples generated!")
            return df

        logger.info(f"\nGenerated {len(df)} training samples")
        logger.info(f"Symbols: {df['symbol'].nunique()}")

        # Store in database
        await self._store_training_data(df)

        # Save to CSV for inspection
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        from sentinel_ml.paths import DATA_DIR

        csv_path = str(DATA_DIR / f"ml_training_data_{timestamp}.csv")
        df.to_csv(csv_path, index=False)
        logger.info(f"Saved to {csv_path}")

        return df

    async def _create_sample_at_index(
        self,
        symbol: str,
        price_data,
        i: int,
        prediction_horizon_days: int,
        security_data: dict | None,
    ) -> dict | None:
        """Create a single training sample at index i in price_data.

        Returns sample dict or None if creation fails.
        """
        sample_date = price_data.iloc[i]["date"]
        window_data = price_data.iloc[: i + 1].copy()

        try:
            features = await self.feature_extractor.extract_features(
                symbol=symbol,
                date=sample_date,
                price_data=window_data,
                sentiment_score=None,
                security_data=security_data,
            )

            current_price = price_data.iloc[i]["close"]
            future_price = price_data.iloc[i + prediction_horizon_days]["close"]

            if pd.isna(current_price) or pd.isna(future_price) or current_price <= 0:
                return None

            future_return = (future_price / current_price) - 1.0

            # Convert sample_date to unix timestamp for ml.db
            if isinstance(sample_date, str):
                sample_date_ts = int(datetime.strptime(sample_date, "%Y-%m-%d").timestamp())
            else:
                sample_date_ts = int(sample_date)

            return {
                "sample_id": str(uuid.uuid4()),
                "symbol": symbol,
                "sample_date": sample_date_ts,
                **features,
                "future_return": future_return,
                "prediction_horizon_days": prediction_horizon_days,
                "created_at": int(datetime.now().timestamp()),
            }
        except Exception as e:
            logger.debug(f"{symbol} at {sample_date}: Feature extraction failed: {e}")
            return None

    async def _create_samples_for_symbol(
        self,
        symbol: str,
        price_data: pd.DataFrame,
        prediction_horizon_days: int,
        security_data: Optional[Dict] = None,
    ) -> List[Dict]:
        """
        Create training samples for one symbol.

        Each symbol is processed with its own price data plus aggregate market context.

        Args:
            symbol: Security ticker
            price_data: DataFrame with OHLCV data
            prediction_horizon_days: Days ahead to predict
            security_data: Optional dict with 'geography' and 'industry' for aggregate features
        """
        samples = []

        # Rolling windows (step = 7 days for weekly samples)
        for i in range(200, len(price_data) - prediction_horizon_days, 7):
            sample = await self._create_sample_at_index(symbol, price_data, i, prediction_horizon_days, security_data)
            if sample:
                samples.append(sample)

        return samples

    async def _get_price_data(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        """Get historical OHLCV data for symbol, validated and interpolated."""
        rows = await self.db.get_prices(symbol, days=36500, end_date=end_date)
        rows = [row for row in rows if start_date <= row["date"] <= end_date]
        if not rows:
            return pd.DataFrame()

        # Convert to list of dicts for validation (ascending date for validator)
        price_list = [dict(row) for row in reversed(rows)]

        # Convert numeric columns before validation
        for price in price_list:
            for col in ["open", "high", "low", "close", "volume"]:
                if col in price and price[col] is not None:
                    try:
                        price[col] = float(price[col])
                    except (ValueError, TypeError):
                        price[col] = 0.0

        # Validate and interpolate abnormal prices (spikes, crashes, etc.)
        validated_prices = self.price_validator.validate_and_interpolate(price_list)

        df = pd.DataFrame(validated_prices, columns=["date", "open", "high", "low", "close", "volume"])

        return df

    async def _get_universe_symbols(self) -> List[str]:
        """Get list of symbols in universe."""
        securities = await self.db.get_all_securities(active_only=True)
        return [s["symbol"] for s in securities]

    async def _store_training_data(self, df: pd.DataFrame):
        """Store training samples in ml.db via MLDatabase."""
        if len(df) == 0:
            return

        logger.info(f"Storing {len(df)} samples in ML database...")
        await self.ml_db.connect()
        await self.ml_db.store_training_samples(df)
        logger.info(f"Stored all {len(df)} samples successfully")

    async def generate_training_data_for_symbol(
        self,
        symbol: str,
        lookback_years: int = 8,
        prediction_horizon_days: int = 14,
    ) -> pd.DataFrame:
        """
        Generate training data for a single symbol.

        Args:
            symbol: Security ticker to generate training data for
            lookback_years: Years of historical data to use
            prediction_horizon_days: Days ahead to predict

        Returns:
            DataFrame with training samples for this symbol
        """
        await self.db.connect()
        await self.ml_db.connect()

        # Calculate date range
        end_date = (datetime.now() - timedelta(days=prediction_horizon_days)).strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=lookback_years * 365)).strftime("%Y-%m-%d")

        logger.info(f"Generating training data for {symbol}...")
        logger.info(f"Period: {start_date} to {end_date}")

        # Get price data for this symbol
        price_data = await self._get_price_data(symbol, start_date, datetime.now().strftime("%Y-%m-%d"))

        if len(price_data) < 200 + prediction_horizon_days:
            logger.warning(f"{symbol}: Insufficient price data ({len(price_data)} rows)")
            return pd.DataFrame()

        # Get security data for aggregate features
        security_data = await self.db.get_security(symbol)

        # Create samples with aggregate market context
        samples = await self._create_samples_for_symbol(
            symbol=symbol,
            price_data=price_data,
            prediction_horizon_days=prediction_horizon_days,
            security_data=security_data,
        )

        df = pd.DataFrame(samples)

        if len(df) > 0:
            await self._store_training_data(df)
            logger.info(f"Generated and stored {len(df)} samples for {symbol}")

        return df

    async def generate_incremental_samples(
        self,
        lookback_days: int = 90,
        prediction_horizon_days: int = 14,
        backfill_years: int | None = None,
    ) -> pd.DataFrame:
        """
        Generate training samples from recent data only.

        This is used by the weekly retrainer to add new samples without
        regenerating the entire dataset.

        Each symbol is processed independently - no cross-security data.

        Args:
            lookback_days: Number of days of history to use for feature extraction
            prediction_horizon_days: Days ahead to predict
            backfill_years: If set, backfill historical samples up to this many years ago

        Returns:
            DataFrame with new training samples
        """
        await self.db.connect()
        await self.ml_db.connect()

        # Calculate date range
        if backfill_years is not None and backfill_years > 0:
            current_year = datetime.now().year
            feature_start = f"{current_year - backfill_years}-01-01"
        else:
            feature_start = (datetime.now() - timedelta(days=lookback_days + prediction_horizon_days + 200)).strftime(
                "%Y-%m-%d"
            )

        symbols = await self._get_universe_symbols()

        # Pre-fetch all security data for aggregate feature lookups
        all_securities = await self.db.get_all_securities(active_only=False)
        security_data_map = {s["symbol"]: s for s in all_securities}

        all_samples = []
        logger.info(f"Generating incremental samples for {len(symbols)} symbols...")

        # Process each symbol with aggregate market context
        for symbol in symbols:
            price_data = await self._get_price_data(symbol, feature_start, datetime.now().strftime("%Y-%m-%d"))
            if len(price_data) < 200 + prediction_horizon_days:
                continue

            # Get security data for aggregate features
            security_data = security_data_map.get(symbol)

            # Only create samples for the lookback period unless backfilling
            if backfill_years is not None and backfill_years > 0:
                sample_start_idx = 200
            else:
                sample_start_idx = max(200, len(price_data) - lookback_days - prediction_horizon_days)
            sample_end_idx = len(price_data) - prediction_horizon_days

            for i in range(sample_start_idx, sample_end_idx, 7):
                sample = await self._create_sample_at_index(
                    symbol, price_data, i, prediction_horizon_days, security_data
                )
                if sample:
                    all_samples.append(sample)

        df = pd.DataFrame(all_samples)

        if len(df) > 0:
            await self._store_training_data(df)
            logger.info(f"Generated and stored {len(df)} incremental samples")

        return df
