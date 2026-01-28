"""Production ML predictor with per-symbol models and wavelet score blending."""

import time
import numpy as np
from typing import Dict, Optional
from datetime import datetime
from pathlib import Path
import json
import logging

from sentinel.ml_ensemble import EnsembleBlender
from sentinel.ml_features import (
    FEATURE_NAMES,
    DEFAULT_FEATURES,
    features_to_array,
    validate_features,
)
from sentinel.ml_regime import get_regime_adjusted_return
from sentinel.database import Database
from sentinel.settings import Settings

logger = logging.getLogger(__name__)


class MLPredictor:
    """Production ML predictor with per-symbol model caching and blending."""

    def __init__(self):
        # Cache models per symbol: {symbol: EnsembleBlender}
        self._models: Dict[str, EnsembleBlender] = {}
        self._load_times: Dict[str, float] = {}
        self._cache_duration = 3600  # 1 hour

        self.db = Database()
        self.settings = Settings()

    async def predict_and_blend(
        self,
        symbol: str,
        date: str,
        wavelet_score: float,
        ml_enabled: bool,
        ml_blend_ratio: float,
        features: Optional[Dict[str, float]] = None,
    ) -> Dict[str, float]:
        """
        Predict return using ML and blend with wavelet score (cached for 12 hours).

        Args:
            symbol: Security ticker
            date: Current date
            wavelet_score: Wavelet-based score (0-1)
            ml_enabled: Whether ML is enabled for this security
            ml_blend_ratio: Blend ratio (0.0 = pure wavelet, 1.0 = pure ML)
            features: Pre-computed features (optional, uses defaults if None)

        Returns:
            {
                'ml_predicted_return': float,  # Raw ML prediction %
                'ml_score': float,  # Normalized 0-1
                'wavelet_score': float,
                'blend_ratio': float,
                'final_score': float,  # Blended score
            }
        """
        await self.db.connect()

        if not ml_enabled:
            return self._fallback_to_wavelet(wavelet_score)

        # Check cache first (12 hours = 43200 seconds)
        cache_key = f'ml:prediction:{symbol}:{date}'
        cached = await self.db.cache_get(cache_key)
        if cached is not None:
            logger.debug(f"{symbol}: Using cached ML prediction")
            return json.loads(cached)

        # Get model for this symbol
        ensemble = await self._get_model(symbol)

        if ensemble is None:
            # No model for this symbol, fallback to wavelet
            return self._fallback_to_wavelet(wavelet_score)

        # Use pre-computed features or defaults
        if features is None:
            logger.debug(f"{symbol}: No features provided, using defaults")
            features = DEFAULT_FEATURES.copy()

        # Validate and clean features
        features, warnings = validate_features(features)
        for warning in warnings:
            logger.warning(f"{symbol}: {warning}")

        # Convert to array using centralized function (ensures correct order)
        feature_array = features_to_array(features).reshape(1, -1)

        # Predict (time this)
        start_time = time.time()
        try:
            predicted_return = ensemble.predict(feature_array)[0]
            inference_time_ms = (time.time() - start_time) * 1000

            if inference_time_ms > 100:
                logger.warning(f"{symbol}: Slow inference ({inference_time_ms:.1f}ms)")

        except Exception as e:
            logger.error(f"{symbol}: ML prediction failed: {e}")
            return self._fallback_to_wavelet(wavelet_score)

        # Apply regime-based dampening
        adjusted_return, regime_score, dampening = await get_regime_adjusted_return(
            symbol, predicted_return, self.db
        )

        # Convert adjusted return to score (0-1)
        # Map returns: -10% → 0.0, 0% → 0.5, +10% → 1.0
        ml_score = self._normalize_return_to_score(adjusted_return)

        # Blend scores using per-security blend ratio
        final_score = (1 - ml_blend_ratio) * wavelet_score + ml_blend_ratio * ml_score

        # Store prediction (use adjusted return)
        await self._store_prediction(
            symbol, features, adjusted_return, ml_score,
            wavelet_score, ml_blend_ratio, final_score, inference_time_ms
        )

        result = {
            'ml_predicted_return': float(adjusted_return),
            'ml_raw_return': float(predicted_return),
            'regime_score': float(regime_score),
            'regime_dampening': float(dampening),
            'ml_score': float(ml_score),
            'wavelet_score': float(wavelet_score),
            'blend_ratio': float(ml_blend_ratio),
            'final_score': float(final_score),
        }

        # Cache result (12 hours = 43200 seconds)
        await self.db.cache_set(cache_key, json.dumps(result), ttl_seconds=43200)
        return result

    def _normalize_return_to_score(self, predicted_return: float) -> float:
        """
        Normalize predicted return to 0-1 score.

        Mapping:
        - -10% return → 0.0
        - 0% return → 0.5
        - +10% return → 1.0
        """
        # Linear mapping: score = 0.5 + (return * 5)
        score = 0.5 + (predicted_return * 5.0)

        # Clip to [0, 1]
        return float(np.clip(score, 0.0, 1.0))

    async def _get_model(self, symbol: str) -> Optional[EnsembleBlender]:
        """Get model for a symbol, loading if needed."""
        current_time = time.time()

        # Check if cached and still valid
        if symbol in self._models:
            if current_time - self._load_times.get(symbol, 0) < self._cache_duration:
                return self._models[symbol]

        # Check if model exists for this symbol
        if not EnsembleBlender.model_exists(symbol):
            logger.debug(f"{symbol}: No trained model available")
            return None

        # Load model
        try:
            ensemble = EnsembleBlender()
            ensemble.load(symbol)

            self._models[symbol] = ensemble
            self._load_times[symbol] = current_time

            logger.info(f"{symbol}: ML model loaded")
            return ensemble

        except Exception as e:
            logger.error(f"{symbol}: Failed to load ML model: {e}")
            return None

    def _fallback_to_wavelet(self, wavelet_score: float) -> Dict[str, float]:
        """Fallback to wavelet score if ML unavailable."""
        return {
            'ml_predicted_return': 0.0,
            'ml_score': wavelet_score,
            'wavelet_score': wavelet_score,
            'blend_ratio': 0.0,
            'final_score': wavelet_score,
        }

    async def _store_prediction(
        self, symbol, features, predicted_return, ml_score,
        wavelet_score, blend_ratio, final_score, inference_time_ms
    ):
        """Store prediction in database for tracking."""
        try:
            prediction_id = f"{symbol}_{datetime.now().isoformat()}"

            await self.db.conn.execute(
                """INSERT INTO ml_predictions
                   (prediction_id, symbol, model_version, predicted_at,
                    features, predicted_return, ml_score, wavelet_score,
                    blend_ratio, final_score, inference_time_ms)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    prediction_id, symbol, None,  # model_version no longer used
                    datetime.now().isoformat(),
                    json.dumps(features), predicted_return, ml_score,
                    wavelet_score, blend_ratio, final_score, inference_time_ms
                )
            )
            await self.db.conn.commit()
        except Exception as e:
            logger.error(f"Failed to store prediction for {symbol}: {e}")

    def clear_cache(self, symbol: str = None):
        """Clear model cache for a symbol or all symbols."""
        if symbol:
            self._models.pop(symbol, None)
            self._load_times.pop(symbol, None)
        else:
            self._models.clear()
            self._load_times.clear()
