"""Generate ML training data from historical market data."""

import logging
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import pandas as pd

from sentinel.analyzer import Analyzer
from sentinel.database import Database
from sentinel.ml_features import FeatureExtractor
from sentinel.price_validator import PriceValidator
from sentinel.settings import Settings

logger = logging.getLogger(__name__)


class TrainingDataGenerator:
    """Generate ML training data from historical price data."""

    def __init__(self):
        self.db = Database()
        self.feature_extractor = FeatureExtractor(db=self.db)
        self.settings = Settings()
        self.analyzer = Analyzer()

    async def generate_training_data(
        self,
        start_date: str = "2017-01-01",
        end_date: str = None,
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
        from sentinel.paths import DATA_DIR

        csv_path = str(DATA_DIR / f"ml_training_data_{timestamp}.csv")
        df.to_csv(csv_path, index=False)
        logger.info(f"Saved to {csv_path}")

        return df

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
            sample_date = price_data.iloc[i]["date"]

            # Extract features at this point in time
            window_data = price_data.iloc[: i + 1].copy()  # Only data up to this point

            try:
                # Extract features (per-security with aggregate market context)
                features = await self.feature_extractor.extract_features(
                    symbol=symbol,
                    date=sample_date,
                    price_data=window_data,
                    sentiment_score=None,
                    security_data=security_data,
                )

                # Calculate label (future return)
                current_price = price_data.iloc[i]["close"]
                future_price = price_data.iloc[i + prediction_horizon_days]["close"]

                if pd.isna(current_price) or pd.isna(future_price) or current_price <= 0:
                    continue

                future_return = (future_price / current_price) - 1.0

                # Create sample
                sample = {
                    "sample_id": str(uuid.uuid4()),
                    "symbol": symbol,
                    "sample_date": sample_date,
                    **features,
                    "future_return": future_return,
                    "prediction_horizon_days": prediction_horizon_days,
                    "created_at": datetime.now().isoformat(),
                }

                samples.append(sample)

            except Exception as e:
                logger.debug(f"{symbol} at {sample_date}: Feature extraction failed: {e}")
                continue

        return samples

    async def _get_price_data(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        """Get historical OHLCV data for symbol, validated and interpolated."""
        query = """
            SELECT date, open, high, low, close, volume
            FROM prices
            WHERE symbol = ? AND date >= ? AND date <= ?
            ORDER BY date ASC
        """
        cursor = await self.db.conn.execute(query, (symbol, start_date, end_date))
        rows = await cursor.fetchall()

        if not rows:
            return pd.DataFrame()

        # Convert to list of dicts for validation
        price_list = [dict(row) for row in rows]

        # Convert numeric columns before validation
        for price in price_list:
            for col in ["open", "high", "low", "close", "volume"]:
                if col in price and price[col] is not None:
                    try:
                        price[col] = float(price[col])
                    except (ValueError, TypeError):
                        price[col] = 0.0

        # Validate and interpolate abnormal prices (spikes, crashes, etc.)
        validator = PriceValidator()
        validated_prices = validator.validate_and_interpolate(price_list)

        df = pd.DataFrame(validated_prices, columns=["date", "open", "high", "low", "close", "volume"])

        return df

    async def _get_universe_symbols(self) -> List[str]:
        """Get list of symbols in universe."""
        securities = await self.db.get_all_securities(active_only=True)
        return [s["symbol"] for s in securities]

    async def _store_training_data(self, df: pd.DataFrame):
        """Store training samples in database."""
        if len(df) == 0:
            return

        logger.info(f"Storing {len(df)} samples in database...")

        # 20 features per security (14 core + 6 aggregate market context)
        db_columns = [
            "sample_id",
            "symbol",
            "sample_date",
            "return_1d",
            "return_5d",
            "return_20d",
            "return_60d",
            "price_normalized",
            "volatility_10d",
            "volatility_30d",
            "atr_14d",
            "volume_normalized",
            "volume_trend",
            "rsi_14",
            "macd",
            "bollinger_position",
            "sentiment_score",
            "country_agg_momentum",
            "country_agg_rsi",
            "country_agg_volatility",
            "industry_agg_momentum",
            "industry_agg_rsi",
            "industry_agg_volatility",
            "future_return",
            "prediction_horizon_days",
            "created_at",
        ]

        # Batch insert
        batch_size = 30
        insert_sql = f"""
            INSERT OR REPLACE INTO ml_training_samples
            ({", ".join(db_columns)})
            VALUES ({", ".join(["?" for _ in db_columns])})
        """  # noqa: S608

        for i in range(0, len(df), batch_size):
            batch = df.iloc[i : i + batch_size]

            for _, row in batch.iterrows():
                values = [row.get(col, 0.0) for col in db_columns]
                await self.db.conn.execute(insert_sql, tuple(values))

            await self.db.conn.commit()

            if (i + batch_size) % 1000 == 0:
                logger.info(f"  Stored {i + batch_size}/{len(df)} samples...")

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
    ) -> pd.DataFrame:
        """
        Generate training samples from recent data only.

        This is used by the weekly retrainer to add new samples without
        regenerating the entire dataset.

        Each symbol is processed independently - no cross-security data.

        Args:
            lookback_days: Number of days of history to use for feature extraction
            prediction_horizon_days: Days ahead to predict

        Returns:
            DataFrame with new training samples
        """
        await self.db.connect()

        # Calculate date range
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

            # Only create samples for the lookback period
            sample_start_idx = max(200, len(price_data) - lookback_days - prediction_horizon_days)
            sample_end_idx = len(price_data) - prediction_horizon_days

            for i in range(sample_start_idx, sample_end_idx, 7):
                sample_date = price_data.iloc[i]["date"]
                window_data = price_data.iloc[: i + 1].copy()

                try:
                    # Extract features (per-security with aggregate market context)
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
                        continue

                    future_return = (future_price / current_price) - 1.0

                    sample = {
                        "sample_id": str(uuid.uuid4()),
                        "symbol": symbol,
                        "sample_date": sample_date,
                        **features,
                        "future_return": future_return,
                        "prediction_horizon_days": prediction_horizon_days,
                        "created_at": datetime.now().isoformat(),
                    }
                    all_samples.append(sample)

                except Exception as e:
                    logger.debug(f"{symbol}: Sample creation failed: {e}")
                    continue

        df = pd.DataFrame(all_samples)

        if len(df) > 0:
            await self._store_training_data(df)
            logger.info(f"Generated and stored {len(df)} incremental samples")

        return df
