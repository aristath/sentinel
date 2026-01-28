"""
Modern portfolio optimization using skfolio library.
Provides multiple optimization methods: mean-variance, HRP, risk parity.
"""

import numpy as np
import pandas as pd
from typing import Dict, Optional
from sentinel.database import Database
from sentinel.security import Security
from sentinel.settings import Settings

# Conditional import - skfolio might not be installed
try:
    from skfolio import Portfolio
    from skfolio.optimization import MeanRisk, HierarchicalRiskParity, RiskBudgeting
    from skfolio.preprocessing import prices_to_returns
    SKFOLIO_AVAILABLE = True
except ImportError:
    SKFOLIO_AVAILABLE = False


class PortfolioOptimizer:
    def __init__(self):
        self._db = Database()

    async def optimize_with_skfolio(
        self,
        symbols: list[str],
        method: str = 'mean_variance',
        expected_returns: Optional[Dict[str, float]] = None,
        constraints: Optional[Dict] = None
    ) -> Dict[str, float]:
        """
        Optimize using skfolio library.

        Methods: 'mean_variance', 'hierarchical', 'risk_parity'
        """
        if not SKFOLIO_AVAILABLE:
            raise ImportError("skfolio not installed")

        # Get historical prices as DataFrame
        prices_df = await self._get_prices_dataframe(symbols, days=504)

        if prices_df is None or len(prices_df) < 100:
            return {}

        # Convert to returns
        returns = prices_to_returns(prices_df)

        # Get settings
        settings = Settings()
        max_pos = await settings.get('max_position_pct', 20) / 100
        min_pos = await settings.get('min_position_pct', 2) / 100

        # Choose optimizer
        if method == 'mean_variance':
            optimizer = MeanRisk(
                min_weights=min_pos,
                max_weights=max_pos,
            )
        elif method == 'hierarchical':
            optimizer = HierarchicalRiskParity()
        elif method == 'risk_parity':
            optimizer = RiskBudgeting()
        else:
            raise ValueError(f"Unknown method: {method}")

        # Fit and get weights
        optimizer.fit(returns)
        weights = optimizer.weights_

        # Convert to dict
        allocations = {}
        for symbol, weight in zip(symbols, weights):
            if weight >= min_pos:
                allocations[symbol] = float(weight)  # Keep as fraction (0-1)

        return allocations

    async def compare_methods(self, symbols: list[str]) -> Dict:
        """Compare different optimization methods."""
        results = {}

        methods = ['mean_variance', 'hierarchical', 'risk_parity']

        for method in methods:
            try:
                allocations = await self.optimize_with_skfolio(symbols, method=method)
                results[method] = allocations
            except Exception as e:
                results[method] = {'error': str(e)}

        return results

    async def _get_prices_dataframe(self, symbols: list[str], days: int) -> Optional[pd.DataFrame]:
        """Get historical prices as DataFrame."""
        prices_dict = {}

        for symbol in symbols:
            security = Security(symbol)
            prices = await security.get_historical_prices(days=days)

            if len(prices) < days // 2:
                continue

            # Build series
            dates = [p['date'] for p in reversed(prices)]
            closes = [p['close'] for p in reversed(prices)]

            prices_dict[symbol] = pd.Series(closes, index=dates)

        if not prices_dict:
            return None

        # Combine into DataFrame
        df = pd.DataFrame(prices_dict)

        # Forward fill missing values
        df = df.ffill()

        return df
