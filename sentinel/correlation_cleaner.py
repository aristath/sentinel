"""
Correlation matrix noise filtering using Random Matrix Theory.
Removes spurious correlations via Marchenko-Pastur eigenvalue filtering.
"""

import numpy as np
from typing import Optional
from sentinel.database import Database
from sentinel.security import Security
import json
from datetime import datetime


class CorrelationCleaner:
    def __init__(self):
        self._db = Database()

    async def calculate_raw_correlation(self, symbols: list[str], days: int = 504) -> tuple[Optional[np.ndarray], Optional[list[str]]]:
        """Calculate raw correlation matrix from returns."""
        returns_matrix = []
        valid_symbols = []

        for symbol in symbols:
            security = Security(symbol)
            prices = await security.get_historical_prices(days=days)

            if len(prices) < days // 2:
                continue

            closes = np.array([p['close'] for p in reversed(prices)])
            returns = np.diff(np.log(closes))
            returns_matrix.append(returns)
            valid_symbols.append(symbol)

        if len(returns_matrix) < 2:
            return None, None

        # Pad to same length
        max_len = max(len(r) for r in returns_matrix)
        padded = []
        for r in returns_matrix:
            if len(r) < max_len:
                padded.append(np.pad(r, (max_len - len(r), 0), mode='edge'))
            else:
                padded.append(r[-max_len:])

        returns_array = np.array(padded)
        corr_matrix = np.corrcoef(returns_array)

        return corr_matrix, valid_symbols

    async def clean_correlation(self, corr_matrix: np.ndarray) -> np.ndarray:
        """Apply RMT filtering to remove noise."""
        N = corr_matrix.shape[0]
        T = corr_matrix.shape[0]  # Approximate

        # Calculate q ratio
        q = T / N if N > 0 else 1.0

        # Marchenko-Pastur bounds
        lambda_min, lambda_max = self._marchenko_pastur_bounds(q)

        # Eigenvalue decomposition
        eigvals, eigvecs = np.linalg.eigh(corr_matrix)

        # Filter eigenvalues
        filtered_eigvals = eigvals.copy()
        for i, eigval in enumerate(eigvals):
            if lambda_min <= eigval <= lambda_max:
                # Within random matrix bounds - set to average
                filtered_eigvals[i] = np.mean([lambda_min, lambda_max])

        # Reconstruct matrix
        cleaned = eigvecs @ np.diag(filtered_eigvals) @ eigvecs.T

        # Ensure valid correlation matrix
        np.fill_diagonal(cleaned, 1.0)
        cleaned = np.clip(cleaned, -1, 1)

        return cleaned

    def _marchenko_pastur_bounds(self, q: float) -> tuple[float, float]:
        """Calculate Marchenko-Pastur eigenvalue bounds."""
        lambda_min = (1 - np.sqrt(q)) ** 2
        lambda_max = (1 + np.sqrt(q)) ** 2
        return lambda_min, lambda_max

    async def store_matrices(self, raw: np.ndarray, cleaned: np.ndarray, symbols: list[str]):
        """Store correlation matrices in database."""
        timestamp = datetime.utcnow().isoformat()
        matrix_id_base = f"corr_{timestamp}"

        # Store raw
        await self._db.conn.execute(
            """INSERT INTO correlation_matrices
               (matrix_id, matrix_type, symbols, matrix_data, calculated_at, n_symbols, q_ratio)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                f"{matrix_id_base}_raw",
                "raw",
                json.dumps(symbols),
                json.dumps(raw.tolist()),
                timestamp,
                len(symbols),
                len(symbols) / len(symbols)  # Approximate
            )
        )

        # Store cleaned
        await self._db.conn.execute(
            """INSERT INTO correlation_matrices
               (matrix_id, matrix_type, symbols, matrix_data, calculated_at, n_symbols, q_ratio)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                f"{matrix_id_base}_cleaned",
                "cleaned",
                json.dumps(symbols),
                json.dumps(cleaned.tolist()),
                timestamp,
                len(symbols),
                len(symbols) / len(symbols)
            )
        )
        await self._db.conn.commit()

    async def get_latest_correlation(self, matrix_type: str = 'cleaned') -> tuple[Optional[np.ndarray], Optional[list[str]]]:
        """Get most recent correlation matrix."""
        cursor = await self._db.conn.execute(
            """SELECT symbols, matrix_data FROM correlation_matrices
               WHERE matrix_type = ?
               ORDER BY calculated_at DESC LIMIT 1""",
            (matrix_type,)
        )
        row = await cursor.fetchone()
        if not row:
            return None, None

        symbols = json.loads(row['symbols'])
        matrix = np.array(json.loads(row['matrix_data']))
        return matrix, symbols
