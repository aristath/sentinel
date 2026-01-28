"""ML feature extraction for per-security predictions.

This module provides centralized feature definitions and extraction logic
for the ML prediction system. All feature names and their order are defined
here as the single source of truth.
"""

import logging
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import ta

logger = logging.getLogger(__name__)


# =============================================================================
# FEATURE DEFINITIONS - Single source of truth
# =============================================================================

# Feature names in the exact order used by the ML models
# Each security's ML model uses ONLY that security's own data - no cross-contamination
# Plus aggregate market context features for country and industry groups
FEATURE_NAMES: List[str] = [
    # Price & Returns (4 features)
    "return_1d",
    "return_5d",
    "return_20d",
    "return_60d",
    # Price position (1 feature)
    "price_normalized",
    # Volatility (3 features)
    "volatility_10d",
    "volatility_30d",
    "atr_14d",
    # Volume (2 features)
    "volume_normalized",
    "volume_trend",
    # Technical Indicators (3 features)
    "rsi_14",
    "macd",
    "bollinger_position",
    # Sentiment (1 feature)
    "sentiment_score",
    # Aggregate Market Context - Country (3 features)
    "country_agg_momentum",
    "country_agg_rsi",
    "country_agg_volatility",
    # Aggregate Market Context - Industry (3 features)
    "industry_agg_momentum",
    "industry_agg_rsi",
    "industry_agg_volatility",
]

# Total number of features (used by ml_ensemble.py)
NUM_FEATURES = len(FEATURE_NAMES)  # 20

# Default feature values for when data is insufficient
DEFAULT_FEATURES: Dict[str, float] = {
    "return_1d": 0.0,
    "return_5d": 0.0,
    "return_20d": 0.0,
    "return_60d": 0.0,
    "price_normalized": 0.0,
    "volatility_10d": 0.02,
    "volatility_30d": 0.02,
    "atr_14d": 0.02,
    "volume_normalized": 1.0,
    "volume_trend": 0.0,
    "rsi_14": 0.5,
    "macd": 0.0,
    "bollinger_position": 0.5,
    "sentiment_score": 0.5,
    # Aggregate market context defaults
    "country_agg_momentum": 0.0,
    "country_agg_rsi": 0.5,
    "country_agg_volatility": 0.02,
    "industry_agg_momentum": 0.0,
    "industry_agg_rsi": 0.5,
    "industry_agg_volatility": 0.02,
}


def features_to_array(features: Dict[str, float]) -> np.ndarray:
    """Convert feature dict to numpy array in correct order.

    Args:
        features: Dict mapping feature name to value

    Returns:
        1D numpy array of shape (NUM_FEATURES,)
    """
    return np.array([features.get(name, DEFAULT_FEATURES[name]) for name in FEATURE_NAMES])


def validate_features(features: Dict[str, float]) -> Tuple[Dict[str, float], List[str]]:
    """Validate and clean feature values.

    Handles NaN/Inf values and enforces physical constraints only.
    Does not clip "extreme" values - the model should see real market data.

    Args:
        features: Dict mapping feature name to value

    Returns:
        Tuple of (cleaned features dict, list of warnings)
    """
    # Physical constraints: features that have mathematical bounds
    NON_NEGATIVE = {
        "volatility_10d",
        "volatility_30d",
        "atr_14d",
        "volume_normalized",
        "country_agg_volatility",
        "industry_agg_volatility",
    }
    ZERO_TO_ONE = {"rsi_14", "sentiment_score", "country_agg_rsi", "industry_agg_rsi"}

    cleaned = {}
    warnings = []

    for name in FEATURE_NAMES:
        value = features.get(name, DEFAULT_FEATURES[name])
        default = DEFAULT_FEATURES[name]

        # Check for NaN or Inf
        if not np.isfinite(value):
            warnings.append(f"{name}: invalid value {value}, using default {default}")
            value = default

        # Enforce physical constraints only
        if name in NON_NEGATIVE and value < 0:
            warnings.append(f"{name}: negative value {value:.4f} is physically impossible, using 0")
            value = 0.0
        elif name in ZERO_TO_ONE:
            if value < 0 or value > 1:
                warnings.append(f"{name}: value {value:.4f} outside [0,1], clipping")
                value = np.clip(value, 0.0, 1.0)

        cleaned[name] = value

    return cleaned, warnings


class FeatureExtractor:
    """Extract ML features from market data."""

    def __init__(self, db=None):
        """Initialize feature extractor.

        Args:
            db: Optional Database instance for market context lookups
        """
        self.db = db
        self.feature_names = FEATURE_NAMES  # For backward compatibility
        self._market_cache: Dict[str, pd.DataFrame] = {}
        self._aggregate_cache: Dict[str, pd.DataFrame] = {}

    async def extract_features(
        self,
        symbol: str,
        date: str,
        price_data: pd.DataFrame,
        sentiment_score: Optional[float] = None,
        security_data: Optional[Dict] = None,
    ) -> Dict[str, float]:
        """
        Extract all 20 features for a security at a given date.

        Each security's ML model uses that security's own price/volume data,
        plus aggregate market context features for the security's country and industry.

        Args:
            symbol: Security ticker
            date: Date to extract features for
            price_data: DataFrame with columns [date, open, high, low, close, volume]
            sentiment_score: Optional sentiment score (0-1)
            security_data: Optional dict with 'geography' and 'industry' for aggregate features

        Returns:
            Dict mapping feature name to value (20 features)
        """
        if len(price_data) < 200:
            logger.warning(f"{symbol}: insufficient price data ({len(price_data)} rows), using defaults")
            return DEFAULT_FEATURES.copy()

        # Ensure data is sorted by date
        price_data = price_data.sort_values("date").reset_index(drop=True)
        features = {}

        try:
            # =====================================================================
            # Price & Returns (4 features)
            # =====================================================================
            features["return_1d"] = self._calculate_return(price_data, periods=1)
            features["return_5d"] = self._calculate_return(price_data, periods=5)
            features["return_20d"] = self._calculate_return(price_data, periods=20)
            features["return_60d"] = self._calculate_return(price_data, periods=60)

            # =====================================================================
            # Price Position (1 feature)
            # =====================================================================
            current_price = price_data["close"].iloc[-1]  # type: ignore[union-attr]
            ma_200 = price_data["close"].rolling(200).mean().iloc[-1]  # type: ignore[union-attr]
            if pd.notna(ma_200) and ma_200 > 0:
                features["price_normalized"] = (current_price - ma_200) / ma_200
            else:
                features["price_normalized"] = 0.0

            # =====================================================================
            # Volatility (3 features)
            # =====================================================================
            returns = price_data["close"].pct_change()

            vol_10 = returns.rolling(10).std().iloc[-1]
            features["volatility_10d"] = float(vol_10) if pd.notna(vol_10) else 0.02

            vol_30 = returns.rolling(30).std().iloc[-1]
            features["volatility_30d"] = float(vol_30) if pd.notna(vol_30) else 0.02

            # ATR (Average True Range)
            if "high" in price_data.columns and "low" in price_data.columns:
                try:
                    atr_indicator = ta.volatility.AverageTrueRange(  # type: ignore[attr-defined]
                        price_data["high"], price_data["low"], price_data["close"], window=14
                    )
                    atr_value = atr_indicator.average_true_range().iloc[-1]
                    if pd.notna(atr_value) and current_price > 0:
                        features["atr_14d"] = float(atr_value / current_price)
                    else:
                        features["atr_14d"] = 0.02
                except Exception as e:
                    logger.debug(f"{symbol}: ATR calculation failed: {e}")
                    features["atr_14d"] = 0.02
            else:
                features["atr_14d"] = 0.02

            # =====================================================================
            # Volume (2 features)
            # =====================================================================
            if "volume" in price_data.columns and price_data["volume"].notna().any():  # type: ignore[reportGeneralClassIssues]
                current_volume = price_data["volume"].iloc[-1]  # type: ignore[union-attr]
                avg_volume_20d = price_data["volume"].rolling(20).mean().iloc[-1]  # type: ignore[union-attr]

                if pd.notna(avg_volume_20d) and avg_volume_20d > 0 and pd.notna(current_volume):
                    features["volume_normalized"] = float(current_volume / avg_volume_20d)
                else:
                    features["volume_normalized"] = 1.0

                volume_ma_5 = price_data["volume"].rolling(5).mean().iloc[-1]  # type: ignore[union-attr]
                volume_ma_20 = price_data["volume"].rolling(20).mean().iloc[-1]  # type: ignore[union-attr]
                if pd.notna(volume_ma_5) and pd.notna(volume_ma_20) and volume_ma_20 > 0:
                    features["volume_trend"] = float((volume_ma_5 - volume_ma_20) / volume_ma_20)
                else:
                    features["volume_trend"] = 0.0
            else:
                features["volume_normalized"] = 1.0
                features["volume_trend"] = 0.0

            # =====================================================================
            # Technical Indicators (3 features)
            # =====================================================================
            # RSI
            try:
                rsi_indicator = ta.momentum.RSIIndicator(price_data["close"], window=14)  # type: ignore[attr-defined]
                rsi_value = rsi_indicator.rsi().iloc[-1]
                features["rsi_14"] = float(rsi_value / 100.0) if pd.notna(rsi_value) else 0.5
            except Exception as e:
                logger.debug(f"{symbol}: RSI calculation failed: {e}")
                features["rsi_14"] = 0.5

            # MACD
            try:
                macd_indicator = ta.trend.MACD(price_data["close"])  # type: ignore[attr-defined]
                macd_value = macd_indicator.macd_diff().iloc[-1]
                if pd.notna(macd_value) and current_price > 0:
                    normalized_macd = np.clip(macd_value / current_price, -0.1, 0.1) / 0.1
                    features["macd"] = float(normalized_macd)
                else:
                    features["macd"] = 0.0
            except Exception as e:
                logger.debug(f"{symbol}: MACD calculation failed: {e}")
                features["macd"] = 0.0

            # Bollinger Bands position
            try:
                bollinger = ta.volatility.BollingerBands(price_data["close"], window=20, window_dev=2)  # type: ignore[attr-defined]
                bb_high = bollinger.bollinger_hband().iloc[-1]
                bb_low = bollinger.bollinger_lband().iloc[-1]
                if pd.notna(bb_high) and pd.notna(bb_low) and bb_high > bb_low:
                    features["bollinger_position"] = float((current_price - bb_low) / (bb_high - bb_low))
                else:
                    features["bollinger_position"] = 0.5
            except Exception as e:
                logger.debug(f"{symbol}: Bollinger calculation failed: {e}")
                features["bollinger_position"] = 0.5

            # =====================================================================
            # Sentiment (1 feature)
            # =====================================================================
            if sentiment_score is not None and pd.notna(sentiment_score):
                features["sentiment_score"] = float(np.clip(sentiment_score, 0.0, 1.0))
            else:
                features["sentiment_score"] = 0.5  # Default neutral sentiment

            # =====================================================================
            # Aggregate Market Context (6 features)
            # =====================================================================
            agg_features = await self._extract_aggregate_features(security_data, date)
            features.update(agg_features)

        except Exception as e:
            logger.error(f"{symbol}: Feature extraction failed: {e}", exc_info=True)
            return DEFAULT_FEATURES.copy()

        # Validate and clean features
        cleaned, warnings = validate_features(features)
        for warning in warnings:
            logger.warning(f"{symbol}: {warning}")

        return cleaned

    def _calculate_return(self, price_data: pd.DataFrame, periods: int) -> float:
        """Calculate return over N periods."""
        if len(price_data) < periods + 1:
            return 0.0

        try:
            current = price_data["close"].iloc[-1]
            past = price_data["close"].iloc[-(periods + 1)]
            if pd.notna(current) and pd.notna(past) and past > 0:
                return float((current / past) - 1.0)
            return 0.0
        except Exception as e:
            logger.debug(f"Return calculation failed for {periods} periods: {e}")
            return 0.0

    def get_default_features(self) -> Dict[str, float]:
        """Return default feature values when data insufficient."""
        return DEFAULT_FEATURES.copy()

    # Backward compatibility alias
    _get_default_features = get_default_features

    async def _extract_aggregate_features(
        self,
        security_data: Optional[Dict],
        date: str,
    ) -> Dict[str, float]:
        """Extract aggregate market context features for country and industry.

        Args:
            security_data: Dict with 'geography' and 'industry' fields
            date: Date to extract features for

        Returns:
            Dict with 6 aggregate features
        """
        features = {
            "country_agg_momentum": 0.0,
            "country_agg_rsi": 0.5,
            "country_agg_volatility": 0.02,
            "industry_agg_momentum": 0.0,
            "industry_agg_rsi": 0.5,
            "industry_agg_volatility": 0.02,
        }

        if not security_data or not self.db:
            return features

        # Import here to avoid circular imports
        from sentinel.aggregates import AggregateComputer

        agg_computer = AggregateComputer(self.db)

        # Extract country aggregate features
        geography = security_data.get("geography", "")
        if geography:
            country_symbol = agg_computer.get_country_aggregate_symbol(geography)
            if country_symbol:
                country_features = await self._compute_aggregate_features(country_symbol, date, "country")
                features.update(country_features)

        # Extract industry aggregate features
        industry = security_data.get("industry", "")
        if industry:
            industry_symbol = agg_computer.get_industry_aggregate_symbol(industry)
            if industry_symbol:
                industry_features = await self._compute_aggregate_features(industry_symbol, date, "industry")
                features.update(industry_features)

        return features

    async def _compute_aggregate_features(
        self,
        agg_symbol: str,
        date: str,
        prefix: str,
    ) -> Dict[str, float]:
        """Compute momentum, RSI, and volatility for an aggregate symbol.

        Args:
            agg_symbol: Aggregate symbol (e.g., _AGG_COUNTRY_US)
            date: Date to compute features for
            prefix: Feature prefix ('country' or 'industry')

        Returns:
            Dict with 3 features: {prefix}_agg_momentum, {prefix}_agg_rsi, {prefix}_agg_volatility
        """
        features = {
            f"{prefix}_agg_momentum": 0.0,
            f"{prefix}_agg_rsi": 0.5,
            f"{prefix}_agg_volatility": 0.02,
        }

        # Check cache first
        if agg_symbol in self._aggregate_cache:
            price_data = self._aggregate_cache[agg_symbol]
        else:
            # Load aggregate price data
            if self.db is None:
                return features
            prices_bulk = await self.db.get_prices_bulk([agg_symbol])
            prices = prices_bulk.get(agg_symbol, [])

            if not prices:
                return features

            price_data = pd.DataFrame(prices)
            price_data = price_data.sort_values("date")
            self._aggregate_cache[agg_symbol] = price_data

        if len(price_data) < 30:
            return features

        # Filter to data up to the target date
        price_data = price_data[price_data["date"] <= date]
        if len(price_data) < 30:
            return features

        try:
            closes = price_data["close"].astype(float)

            # Momentum: 20-day return
            if len(closes) >= 21:
                current = closes.iloc[-1]  # type: ignore[union-attr]
                past = closes.iloc[-21]  # type: ignore[union-attr]
                if pd.notna(current) and pd.notna(past) and past > 0:
                    features[f"{prefix}_agg_momentum"] = float((current / past) - 1.0)

            # RSI-14 (normalized to 0-1)
            if len(closes) >= 15:
                rsi_indicator = ta.momentum.RSIIndicator(closes, window=14)  # type: ignore[attr-defined]
                rsi_value = rsi_indicator.rsi().iloc[-1]
                if pd.notna(rsi_value):
                    features[f"{prefix}_agg_rsi"] = float(rsi_value / 100.0)

            # Volatility: 20-day rolling std of returns
            if len(closes) >= 21:
                returns = closes.pct_change()  # type: ignore[union-attr]
                vol = returns.rolling(20).std().iloc[-1]
                if pd.notna(vol):
                    features[f"{prefix}_agg_volatility"] = float(vol)

        except Exception as e:
            logger.debug(f"Failed to compute aggregate features for {agg_symbol}: {e}")

        return features
