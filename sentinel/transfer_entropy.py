"""
Transfer Entropy calculation for directional dependency analysis.
Identifies which securities influence others.
"""

import numpy as np
from typing import Optional
from sentinel.database import Database
from sentinel.security import Security
from datetime import datetime
import json


class TransferEntropyAnalyzer:
    def __init__(self, lag: int = 5, bins: int = 10):
        self._db = Database()
        self.lag = lag
        self.bins = bins

    async def calculate_matrix(self, symbols: list[str]) -> np.ndarray:
        """Calculate NxN transfer entropy matrix."""
        n = len(symbols)
        te_matrix = np.zeros((n, n))

        # Get all price series
        series_dict = {}
        for symbol in symbols:
            series = await self._get_returns_series(symbol)
            if series is not None:
                series_dict[symbol] = series

        # Calculate pairwise TE
        valid_symbols = list(series_dict.keys())
        for i, source in enumerate(valid_symbols):
            for j, target in enumerate(valid_symbols):
                if i != j:
                    te = self._transfer_entropy(
                        series_dict[source],
                        series_dict[target]
                    )
                    te_matrix[i, j] = te

        # Store in database
        await self._store_te_matrix(valid_symbols, te_matrix)

        return te_matrix

    async def calculate_pairwise(self, source: str, target: str) -> float:
        """Calculate transfer entropy from source to target."""
        source_series = await self._get_returns_series(source)
        target_series = await self._get_returns_series(target)

        if source_series is None or target_series is None:
            return 0.0

        # Align series to same length
        min_len = min(len(source_series), len(target_series))
        source_series = source_series[-min_len:]
        target_series = target_series[-min_len:]

        te = self._transfer_entropy(source_series, target_series)
        return te

    async def _get_returns_series(self, symbol: str, days: int = 504) -> Optional[np.ndarray]:
        """Get log returns series for a symbol."""
        security = Security(symbol)
        prices = await security.get_historical_prices(days=days)

        if len(prices) < 100:
            return None

        closes = np.array([p['close'] for p in reversed(prices)])
        returns = np.diff(np.log(closes))
        return returns

    def _transfer_entropy(self, source: np.ndarray, target: np.ndarray) -> float:
        """
        Calculate TE(Y->X) = H(X_t | X_t-1...t-k) - H(X_t | X_t-1...t-k, Y_t-1...t-k)
        """
        # Discretize series
        source_disc = self._discretize(source)
        target_disc = self._discretize(target)

        # Ensure same length
        min_len = min(len(source_disc), len(target_disc))
        source_disc = source_disc[-min_len:]
        target_disc = target_disc[-min_len:]

        # Calculate conditional entropies
        h_target = self._conditional_entropy(target_disc, self.lag)
        h_target_given_source = self._conditional_entropy_joint(
            target_disc, source_disc, self.lag
        )

        te = h_target - h_target_given_source
        return max(0.0, te)  # TE should be non-negative

    def _discretize(self, series: np.ndarray) -> np.ndarray:
        """Discretize continuous series into bins."""
        # Use quantile-based binning
        quantiles = np.linspace(0, 1, self.bins + 1)
        bin_edges = np.quantile(series, quantiles)
        discretized = np.digitize(series, bin_edges[1:-1])
        return discretized

    def _conditional_entropy(self, series: np.ndarray, lag: int) -> float:
        """Calculate H(X_t | X_t-1...t-k)."""
        if len(series) <= lag:
            return 0.0

        # Build history-current pairs
        pairs = []
        for i in range(lag, len(series)):
            history = tuple(series[i-lag:i])
            current = series[i]
            pairs.append((history, current))

        # Calculate joint and marginal probabilities
        joint_counts = {}
        history_counts = {}

        for history, current in pairs:
            joint_counts[(history, current)] = joint_counts.get((history, current), 0) + 1
            history_counts[history] = history_counts.get(history, 0) + 1

        total = len(pairs)
        h = 0.0

        for (history, current), count in joint_counts.items():
            p_joint = count / total
            p_history = history_counts[history] / total
            p_conditional = count / history_counts[history]
            h -= p_joint * np.log2(p_conditional + 1e-10)

        return h

    def _conditional_entropy_joint(self, target: np.ndarray, source: np.ndarray, lag: int) -> float:
        """Calculate H(X_t | X_t-1...t-k, Y_t-1...t-k)."""
        if len(target) <= lag or len(source) <= lag:
            return 0.0

        # Build history-current tuples including both series
        triplets = []
        for i in range(lag, min(len(target), len(source))):
            target_history = tuple(target[i-lag:i])
            source_history = tuple(source[i-lag:i])
            current = target[i]
            triplets.append((target_history, source_history, current))

        # Calculate probabilities
        joint_counts = {}
        context_counts = {}

        for target_hist, source_hist, current in triplets:
            context = (target_hist, source_hist)
            joint_counts[(context, current)] = joint_counts.get((context, current), 0) + 1
            context_counts[context] = context_counts.get(context, 0) + 1

        total = len(triplets)
        h = 0.0

        for (context, current), count in joint_counts.items():
            p_joint = count / total
            p_conditional = count / context_counts[context]
            h -= p_joint * np.log2(p_conditional + 1e-10)

        return h

    async def _store_te_matrix(self, symbols: list[str], matrix: np.ndarray):
        """Store transfer entropy values in database."""
        timestamp = datetime.utcnow().isoformat()

        for i, source in enumerate(symbols):
            for j, target in enumerate(symbols):
                if i != j:
                    await self._db.conn.execute(
                        """INSERT OR REPLACE INTO transfer_entropy
                           (source_symbol, target_symbol, te_value, calculated_at, lag)
                           VALUES (?, ?, ?, ?, ?)""",
                        (source, target, float(matrix[i, j]), timestamp, self.lag)
                    )
        await self._db.conn.commit()

    async def get_leading_indicators(self, symbol: str, limit: int = 5) -> list[dict]:
        """Get securities with highest TE to this symbol."""
        cursor = await self._db.conn.execute(
            """SELECT source_symbol, te_value, calculated_at
               FROM transfer_entropy
               WHERE target_symbol = ?
               ORDER BY te_value DESC LIMIT ?""",
            (symbol, limit)
        )
        rows = await cursor.fetchall()

        return [
            {
                'source': row['source_symbol'],
                'te_value': row['te_value'],
                'calculated_at': row['calculated_at']
            }
            for row in rows
        ]
