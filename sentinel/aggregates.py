"""Aggregate price series computation for country and industry groups.

Computes equal-weighted aggregate price series for market context features.
Aggregates are stored as synthetic securities in the prices table.
"""

import logging
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from sentinel.database import Database

logger = logging.getLogger(__name__)

# Aggregate symbol prefixes
COUNTRY_AGG_PREFIX = "_AGG_COUNTRY_"
INDUSTRY_AGG_PREFIX = "_AGG_INDUSTRY_"

# Minimum securities required to compute an aggregate
MIN_SECURITIES_FOR_AGGREGATE = 3


class AggregateComputer:
    """Compute aggregate price series for country and industry groups."""

    def __init__(self, db: Optional[Database] = None):
        """Initialize aggregate computer.

        Args:
            db: Optional Database instance (creates one if not provided)
        """
        self.db = db or Database()

    async def compute_all_aggregates(self) -> Dict[str, int]:
        """Compute all country and industry aggregates.

        Returns:
            Dict with counts: {"country": N, "industry": M}
        """
        await self.db.connect()

        country_count = await self.compute_country_aggregates()
        industry_count = await self.compute_industry_aggregates()

        return {
            "country": country_count,
            "industry": industry_count,
        }

    async def compute_country_aggregates(self) -> int:
        """Compute aggregate price series for each country/geography.

        Returns:
            Number of aggregates computed
        """
        await self.db.connect()

        # Get distinct geographies
        categories = await self.db.get_categories()
        geographies = categories.get("geographies", [])

        computed = 0
        for geography in geographies:
            if not geography:
                continue

            # Get securities for this geography (primary only)
            symbols = await self._get_symbols_for_category("geography", geography)

            if len(symbols) < MIN_SECURITIES_FOR_AGGREGATE:
                logger.debug(
                    f"Skipping {geography}: only {len(symbols)} securities (need {MIN_SECURITIES_FOR_AGGREGATE})"
                )
                continue

            # Compute aggregate
            agg_symbol = f"{COUNTRY_AGG_PREFIX}{geography.upper().replace(' ', '_')}"
            success = await self._compute_and_store_aggregate(agg_symbol, symbols)

            if success:
                computed += 1
                logger.info(f"Computed aggregate {agg_symbol} from {len(symbols)} securities")

        return computed

    async def compute_industry_aggregates(self) -> int:
        """Compute aggregate price series for each industry/sector.

        Returns:
            Number of aggregates computed
        """
        await self.db.connect()

        # Get distinct industries
        categories = await self.db.get_categories()
        industries = categories.get("industries", [])

        computed = 0
        for industry in industries:
            if not industry:
                continue

            # Get securities for this industry (primary only)
            symbols = await self._get_symbols_for_category("industry", industry)

            if len(symbols) < MIN_SECURITIES_FOR_AGGREGATE:
                logger.debug(
                    f"Skipping {industry}: only {len(symbols)} securities (need {MIN_SECURITIES_FOR_AGGREGATE})"
                )
                continue

            # Compute aggregate
            agg_symbol = f"{INDUSTRY_AGG_PREFIX}{industry.upper().replace(' ', '_')}"
            success = await self._compute_and_store_aggregate(agg_symbol, symbols)

            if success:
                computed += 1
                logger.info(f"Computed aggregate {agg_symbol} from {len(symbols)} securities")

        return computed

    async def _get_symbols_for_category(self, category_type: str, category_value: str) -> List[str]:
        """Get symbols that have the given category as their primary category.

        For multi-category securities (comma-separated), only the first value is used.

        Args:
            category_type: 'geography' or 'industry'
            category_value: The category value to match

        Returns:
            List of matching symbols
        """
        securities = await self.db.get_all_securities(active_only=True)
        matching = []

        for sec in securities:
            # Skip aggregate symbols
            if sec["symbol"].startswith("_AGG_"):
                continue

            raw_value = sec.get(category_type, "")
            if not raw_value:
                continue

            # Use primary category only (first value if comma-separated)
            primary = raw_value.split(",")[0].strip()
            if primary == category_value:
                matching.append(sec["symbol"])

        return matching

    async def _compute_and_store_aggregate(self, agg_symbol: str, symbols: List[str]) -> bool:
        """Compute aggregate price series and store in database.

        Args:
            agg_symbol: Symbol name for the aggregate (e.g., _AGG_COUNTRY_US)
            symbols: List of constituent security symbols

        Returns:
            True if successful, False otherwise
        """
        # Load price data for all symbols
        prices_bulk = await self.db.get_prices_bulk(symbols)

        # Build DataFrames for each symbol
        dfs = {}
        for symbol in symbols:
            prices = prices_bulk.get(symbol, [])
            if not prices:
                continue

            df = pd.DataFrame(prices)
            if "close" not in df.columns or "date" not in df.columns:
                continue

            df = df[["date", "close"]].copy()
            df = df.sort_values(by="date")  # type: ignore[call-overload]
            df = df.set_index("date")
            df = df.rename(columns={"close": symbol})
            dfs[symbol] = df

        if len(dfs) < MIN_SECURITIES_FOR_AGGREGATE:
            logger.debug(f"Insufficient price data for {agg_symbol}: only {len(dfs)} symbols have data")
            return False

        # Build aggregate series
        agg_prices = self._build_aggregate_series(dfs)

        if agg_prices is None or len(agg_prices) < 200:
            logger.debug(f"Insufficient aligned data for {agg_symbol}")
            return False

        # Store in prices table
        price_records = [
            {
                "date": date,
                "open": row["close"],  # Use close for all OHLC
                "high": row["close"],
                "low": row["close"],
                "close": row["close"],
                "volume": 0,
            }
            for date, row in agg_prices.iterrows()
        ]

        await self.db.save_prices(agg_symbol, price_records)
        return True

    def _build_aggregate_series(self, dfs: Dict[str, pd.DataFrame]) -> Optional[pd.DataFrame]:
        """Build equal-weighted aggregate price series from constituent DataFrames.

        Process:
        1. Align by date (inner join - only dates where all have data)
        2. Compute daily returns: (close[t] / close[t-1]) - 1
        3. Average returns across symbols (equal weight)
        4. Build price series: price[0] = 100, price[t] = price[t-1] * (1 + avg_return[t])

        Args:
            dfs: Dict mapping symbol to DataFrame with 'close' column indexed by date

        Returns:
            DataFrame with 'close' column indexed by date, or None if insufficient data
        """
        if not dfs:
            return None

        # Concatenate all price series
        combined = pd.concat(dfs.values(), axis=1, join="inner")

        if len(combined) < 200:
            return None

        # Compute daily returns for each symbol
        returns = combined.pct_change()

        # Drop first row (NaN from pct_change)
        returns = returns.iloc[1:]

        if len(returns) < 200:
            return None

        # Average returns across symbols (equal weight)
        avg_returns = returns.mean(axis=1)

        # Handle NaN in computation - skip those dates
        avg_returns = avg_returns.dropna()

        if len(avg_returns) < 200:
            return None

        # Build price series starting at 100
        prices = [100.0]
        for ret in avg_returns.values:
            if np.isfinite(ret):
                prices.append(prices[-1] * (1 + ret))
            else:
                prices.append(prices[-1])  # Carry forward if NaN

        # Create DataFrame (first price is for the day before returns start)
        dates = [avg_returns.index[0]] + list(avg_returns.index)
        # Actually we need dates aligned with prices
        # The first return is for avg_returns.index[0], so we need the previous date
        # Let's just use the return dates and drop the initial 100
        prices = prices[1:]  # Drop the initial 100, use computed prices
        dates = list(avg_returns.index)

        result = pd.DataFrame({"close": prices}, index=pd.Index(dates))
        return result

    async def get_aggregate_price_data(self, agg_symbol: str, days: int = 250) -> Optional[pd.DataFrame]:
        """Get price data for an aggregate symbol.

        Args:
            agg_symbol: Aggregate symbol (e.g., _AGG_COUNTRY_US)
            days: Number of days of history to fetch

        Returns:
            DataFrame with OHLCV columns, or None if not found
        """
        await self.db.connect()

        prices_bulk = await self.db.get_prices_bulk([agg_symbol], days=days)
        prices = prices_bulk.get(agg_symbol, [])

        if not prices:
            return None

        df = pd.DataFrame(prices)
        df = df.sort_values(by="date")
        return df

    def get_country_aggregate_symbol(self, geography: str) -> str:
        """Get the aggregate symbol for a country/geography.

        Args:
            geography: Geography name (e.g., 'US', 'Europe')

        Returns:
            Aggregate symbol (e.g., '_AGG_COUNTRY_US')
        """
        if not geography:
            return ""
        primary = geography.split(",")[0].strip()
        return f"{COUNTRY_AGG_PREFIX}{primary.upper().replace(' ', '_')}"

    def get_industry_aggregate_symbol(self, industry: str) -> str:
        """Get the aggregate symbol for an industry/sector.

        Args:
            industry: Industry name (e.g., 'Technology', 'Semiconductors')

        Returns:
            Aggregate symbol (e.g., '_AGG_INDUSTRY_TECHNOLOGY')
        """
        if not industry:
            return ""
        primary = industry.split(",")[0].strip()
        return f"{INDUSTRY_AGG_PREFIX}{primary.upper().replace(' ', '_')}"
