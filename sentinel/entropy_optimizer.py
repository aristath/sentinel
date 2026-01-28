"""
Entropy-based portfolio optimization using Shannon and Tsallis entropy.
Maximizes diversification while targeting expected returns.
"""

import numpy as np
from scipy.optimize import minimize
from typing import Dict, Optional
from sentinel.settings import Settings


class EntropyOptimizer:
    def __init__(self, method: str = 'shannon'):
        self.method = method

    async def optimize(
        self,
        expected_returns: Dict[str, float],
        constraints: Dict
    ) -> Dict[str, float]:
        """
        Optimize portfolio using entropy-based approach.

        Args:
            expected_returns: Dict of symbol -> expected return
            constraints: Dict with max_position, min_position, cash_target

        Returns:
            Dict of symbol -> allocation percentage
        """
        symbols = list(expected_returns.keys())
        returns_array = np.array([expected_returns[s] for s in symbols])

        # Filter to positive expected returns only
        positive_mask = returns_array > 0
        if not np.any(positive_mask):
            return {}

        symbols = [s for s, pos in zip(symbols, positive_mask) if pos]
        returns_array = returns_array[positive_mask]

        n = len(symbols)
        if n == 0:
            return {}

        # Get settings
        settings = Settings()
        entropy_weight = await settings.get('entropy_weight', 0.3)
        max_position = constraints.get('max_position', 20) / 100
        min_position = constraints.get('min_position', 2) / 100
        cash_target = constraints.get('cash_target', 5) / 100

        # Optimization bounds
        bounds = [(min_position, max_position) for _ in range(n)]

        # Constraints
        cons = [
            {'type': 'eq', 'fun': lambda w: np.sum(w) - (1 - cash_target)}  # Sum to target
        ]

        # Initial guess (equal weight)
        w0 = np.ones(n) / n * (1 - cash_target)

        # Objective: maximize return - entropy_weight * (-entropy)
        # Which is: minimize -return + entropy_weight * (-entropy)
        def objective(weights):
            ret = np.dot(weights, returns_array)

            if self.method == 'shannon':
                entropy = self._shannon_entropy(weights)
            else:
                q = 2.0  # Default q value for Tsallis
                entropy = self._tsallis_entropy(weights, q)

            # Maximize return and entropy
            return -ret + entropy_weight * (-entropy)

        # Optimize
        result = minimize(
            objective,
            w0,
            method='SLSQP',
            bounds=bounds,
            constraints=cons,
            options={'maxiter': 1000}
        )

        if not result.success:
            # Fall back to proportional allocation
            return await self._proportional_allocation(expected_returns, constraints)

        # Build result dict
        allocations = {}
        for symbol, weight in zip(symbols, result.x):
            if weight >= min_position:
                allocations[symbol] = float(weight)  # Keep as fraction (0-1)

        return allocations

    def _shannon_entropy(self, weights: np.ndarray) -> float:
        """Calculate Shannon entropy: -sum(w * log(w))."""
        # Normalize to ensure sum = 1
        w = weights / (np.sum(weights) + 1e-10)
        # Filter out zeros
        w_nonzero = w[w > 1e-10]
        if len(w_nonzero) == 0:
            return 0.0
        entropy = -np.sum(w_nonzero * np.log(w_nonzero))
        return entropy

    def _tsallis_entropy(self, weights: np.ndarray, q: float = 2.0) -> float:
        """Calculate Tsallis entropy: (1 - sum(w^q)) / (q-1)."""
        # Normalize
        w = weights / (np.sum(weights) + 1e-10)
        if q == 1.0:
            return self._shannon_entropy(weights)
        entropy = (1 - np.sum(w ** q)) / (q - 1)
        return entropy

    async def _proportional_allocation(
        self,
        expected_returns: Dict[str, float],
        constraints: Dict
    ) -> Dict[str, float]:
        """Fallback: simple proportional allocation."""
        # Filter positive
        positive_returns = {s: r for s, r in expected_returns.items() if r > 0}
        if not positive_returns:
            return {}

        # Normalize
        total = sum(positive_returns.values())
        allocations = {}

        max_pos = constraints.get('max_position', 20)
        min_pos = constraints.get('min_position', 2)
        cash_target = constraints.get('cash_target', 5)
        allocable = 100 - cash_target

        for symbol, ret in positive_returns.items():
            alloc = (ret / total) * allocable / 100  # Convert to fraction
            alloc = np.clip(alloc, min_pos / 100, max_pos / 100)
            if alloc >= min_pos / 100:
                allocations[symbol] = alloc

        # Renormalize
        total_alloc = sum(allocations.values())
        if total_alloc > 0:
            factor = (allocable / 100) / total_alloc
            allocations = {s: a * factor for s, a in allocations.items()}

        return allocations
