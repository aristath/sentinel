"""
Market regime detection using Hidden Markov Models.
Identifies bull, bear, and sideways market conditions.
"""

import base64
import json
import pickle
from datetime import datetime, timedelta, timezone
from typing import Optional

import numpy as np
import pandas as pd
import ta
from hmmlearn import hmm

from sentinel.database import Database
from sentinel.security import Security


class RegimeDetector:
    def __init__(self, n_states: int = 3, lookback_days: int = 504):
        self._db = Database()
        self.n_states = n_states
        self.lookback_days = lookback_days
        self._model: Optional[hmm.GaussianHMM] = None

    async def train_model(self, symbols: list[str]) -> Optional[hmm.GaussianHMM]:
        """Train HMM on market data."""
        # Collect features from all symbols
        all_features = []

        for symbol in symbols:
            features = await self._extract_features(symbol)
            if features is not None and len(features) > 100:
                all_features.append(features)

        if not all_features:
            return None

        # Concatenate all features
        X = np.vstack(all_features)

        # Train HMM
        model = hmm.GaussianHMM(n_components=self.n_states, covariance_type="full", n_iter=100, random_state=42)
        model.fit(X)

        self._model = model

        # Store model
        await self._store_model(model, symbols)

        return model

    async def _extract_features(self, symbol: str) -> Optional[np.ndarray]:
        """Extract features for HMM: returns, volatility, momentum."""
        security = Security(symbol)
        prices = await security.get_historical_prices(days=self.lookback_days)

        if len(prices) < 100:
            return None

        closes = np.array([p["close"] for p in reversed(prices)])
        returns = np.diff(np.log(closes))

        # Feature 1: Returns
        # Feature 2: Rolling volatility (20-day)
        vol = np.array(
            [
                np.std(returns[max(0, i - 20) : i + 1]) if i >= 20 else np.std(returns[: i + 1])
                for i in range(len(returns))
            ]
        )

        # Feature 3: RSI momentum
        rsi_indicator = ta.momentum.RSIIndicator(close=pd.Series(closes), window=14)
        rsi = rsi_indicator.rsi().fillna(50).values
        # Align with returns (which has len(closes) - 1 elements)
        rsi = rsi[1:]

        # Combine features
        features = np.column_stack([returns, vol, rsi])
        return features

    async def detect_current_regime(self, symbol: str) -> dict:
        """Detect current regime for a symbol."""
        # Load model if not loaded
        if self._model is None:
            await self._load_model()

        if self._model is None:
            return {"regime": 1, "regime_name": "Sideways", "confidence": 0.5}

        # Extract recent features
        features = await self._extract_features(symbol)
        if features is None:
            return {"regime": 1, "regime_name": "Sideways", "confidence": 0.5}

        # Predict regime
        regime = self._model.predict(features)[-1]

        # Get confidence (probability of most likely state)
        probs = self._model.predict_proba(features)[-1]
        confidence = np.max(probs)

        # Map regime to name
        regime_name = self._map_regime_to_name(regime, features)

        # Store regime state
        await self._store_regime_state(symbol, regime, regime_name, confidence)

        return {"regime": int(regime), "regime_name": regime_name, "confidence": float(confidence)}

    def _map_regime_to_name(self, regime: int, features: np.ndarray) -> str:
        """Map regime number to descriptive name based on characteristics."""
        # Calculate average return for this regime's periods
        if self._model is None:
            return "Sideways"

        predicted_regimes = self._model.predict(features)
        regime_mask = predicted_regimes == regime
        regime_returns = features[regime_mask, 0]

        if len(regime_returns) == 0:
            return "Sideways"

        avg_return = np.mean(regime_returns)

        if avg_return > 0.001:
            return "Bull"
        elif avg_return < -0.001:
            return "Bear"
        else:
            return "Sideways"

    async def get_regime_history(self, symbol: str, days: int = 90) -> list[dict]:
        """Get historical regime states."""
        date_threshold = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

        cursor = await self._db.conn.execute(
            """SELECT date, regime, regime_name, confidence
               FROM regime_states
               WHERE symbol = ? AND date >= ?
               ORDER BY date DESC""",
            (symbol, date_threshold),
        )
        rows = await cursor.fetchall()

        return [
            {
                "date": row["date"],
                "regime": row["regime"],
                "regime_name": row["regime_name"],
                "confidence": row["confidence"],
            }
            for row in rows
        ]

    async def _store_model(self, model: hmm.GaussianHMM, symbols: list[str]):
        """Store trained model in database."""
        model_bytes = pickle.dumps(model)
        model_b64 = base64.b64encode(model_bytes).decode("utf-8")

        model_id = f"hmm_{datetime.now(timezone.utc).isoformat()}"

        await self._db.conn.execute(
            """INSERT INTO regime_models
               (model_id, symbols, n_states, trained_at, model_params)
               VALUES (?, ?, ?, ?, ?)""",
            (model_id, json.dumps(symbols), self.n_states, datetime.now(timezone.utc).isoformat(), model_b64),
        )
        await self._db.conn.commit()

    async def _load_model(self):
        """Load most recent model from database."""
        cursor = await self._db.conn.execute(
            """SELECT model_params FROM regime_models
               ORDER BY trained_at DESC LIMIT 1"""
        )
        row = await cursor.fetchone()

        if row:
            model_b64 = row["model_params"]
            model_bytes = base64.b64decode(model_b64)
            self._model = pickle.loads(model_bytes)  # noqa: S301

    async def _store_regime_state(self, symbol: str, regime: int, regime_name: str, confidence: float):
        """Store regime state for a symbol."""
        await self._db.conn.execute(
            """INSERT OR REPLACE INTO regime_states
               (symbol, date, regime, regime_name, confidence)
               VALUES (?, ?, ?, ?, ?)""",
            (symbol, datetime.now(timezone.utc).date().isoformat(), regime, regime_name, confidence),
        )
        await self._db.conn.commit()
