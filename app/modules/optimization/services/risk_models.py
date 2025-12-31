"""
Risk Models for Portfolio Optimization.

Builds covariance matrices from historical price data using Ledoit-Wolf shrinkage
for robustness with limited sample sizes.
"""

import logging
from typing import Dict, List, Optional, Tuple

import pandas as pd
from pypfopt import risk_models as pypfopt_risk

from app.domain.scoring.constants import (
    COVARIANCE_LOOKBACK_DAYS,
    COVARIANCE_MIN_HISTORY,
)
from app.repositories.history import HistoryRepository

logger = logging.getLogger(__name__)


class RiskModelBuilder:
    """Build covariance matrices for portfolio optimization."""

    async def build_covariance_matrix(
        self,
        symbols: List[str],
        lookback_days: int = COVARIANCE_LOOKBACK_DAYS,
    ) -> Tuple[Optional[pd.DataFrame], pd.DataFrame]:
        """
        Build a covariance matrix from historical price data.

        Uses Ledoit-Wolf shrinkage for robustness with ~80 stocks and 252 trading days.

        Args:
            symbols: List of stock symbols
            lookback_days: Number of days of history to use

        Returns:
            Tuple of (covariance_matrix, returns_df)
            - covariance_matrix: DataFrame with symbols as index/columns, or None if insufficient data
            - returns_df: DataFrame of daily returns (for HRP)
        """
        # Fetch price data for all symbols
        prices_df = await self._fetch_prices(symbols, lookback_days)

        if prices_df.empty:
            logger.warning("No price data available for covariance calculation")
            return None, pd.DataFrame()

        # Filter to symbols with enough history
        valid_symbols = self._filter_valid_symbols(prices_df)
        if len(valid_symbols) < 2:
            logger.warning(f"Only {len(valid_symbols)} symbols have sufficient history")
            return None, pd.DataFrame()

        prices_df = prices_df[valid_symbols]

        # Calculate daily returns
        returns_df = prices_df.pct_change().dropna()

        if len(returns_df) < COVARIANCE_MIN_HISTORY:
            logger.warning(
                f"Only {len(returns_df)} days of returns, need {COVARIANCE_MIN_HISTORY}"
            )
            return None, returns_df

        # Build covariance matrix using Ledoit-Wolf shrinkage
        try:
            cov_matrix = pypfopt_risk.CovarianceShrinkage(prices_df).ledoit_wolf()
            logger.info(
                f"Built covariance matrix for {len(valid_symbols)} symbols "
                f"using {len(returns_df)} days of returns"
            )
            return cov_matrix, returns_df
        except Exception as e:
            logger.error(f"Error building covariance matrix: {e}")
            return None, returns_df

    async def _fetch_prices(
        self,
        symbols: List[str],
        lookback_days: int,
    ) -> pd.DataFrame:
        """
        Fetch daily closing prices for all symbols.

        Returns:
            DataFrame with dates as index and symbols as columns
        """
        all_prices = {}

        for symbol in symbols:
            try:
                history_repo = HistoryRepository(symbol)
                daily_prices = await history_repo.get_daily_prices(limit=lookback_days)

                if daily_prices:
                    # Convert to dict: date -> close_price
                    symbol_prices = {p.date: p.close_price for p in daily_prices}
                    all_prices[symbol] = symbol_prices
                else:
                    logger.debug(f"No price history for {symbol}")
            except Exception as e:
                logger.warning(f"Error fetching prices for {symbol}: {e}")

        if not all_prices:
            return pd.DataFrame()

        # Build DataFrame from all prices
        df = pd.DataFrame(all_prices)
        df.index = pd.to_datetime(df.index)
        df = df.sort_index()

        # Forward-fill then back-fill to handle different market holidays
        # This is standard practice: use last known price when market closed
        df = df.ffill().bfill()

        logger.debug(f"Fetched prices for {len(df.columns)} symbols, {len(df)} days")
        return df

    def _filter_valid_symbols(self, prices_df: pd.DataFrame) -> List[str]:
        """
        Filter to symbols with sufficient history.

        Args:
            prices_df: DataFrame with symbols as columns

        Returns:
            List of valid symbol names
        """
        valid = []
        for symbol in prices_df.columns:
            non_null_count = prices_df[symbol].notna().sum()
            if non_null_count >= COVARIANCE_MIN_HISTORY:
                valid.append(symbol)
            else:
                logger.debug(
                    f"Skipping {symbol}: only {non_null_count} price points "
                    f"(need {COVARIANCE_MIN_HISTORY})"
                )
        return valid

    def get_correlations(
        self,
        returns_df: pd.DataFrame,
        threshold: float = 0.80,
    ) -> List[Dict]:
        """
        Find highly correlated stock pairs.

        Args:
            returns_df: DataFrame of daily returns
            threshold: Correlation threshold (default 0.80)

        Returns:
            List of dicts with {symbol1, symbol2, correlation}
        """
        if returns_df.empty:
            return []

        corr_matrix = returns_df.corr()
        pairs = []

        symbols = list(corr_matrix.columns)
        for i, sym1 in enumerate(symbols):
            for sym2 in symbols[i + 1 :]:
                corr = corr_matrix.loc[sym1, sym2]
                if abs(corr) >= threshold:
                    pairs.append(
                        {
                            "symbol1": sym1,
                            "symbol2": sym2,
                            "correlation": round(corr, 3),
                        }
                    )

        return sorted(pairs, key=lambda x: abs(x["correlation"]), reverse=True)
