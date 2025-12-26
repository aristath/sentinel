"""Exchange rate service - single source of truth for currency conversion.

This service handles all exchange rate lookups and conversions, with:
- Database-backed caching (1 hour TTL)
- Fallback rates when API is unavailable
- Async implementation using existing database infrastructure
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple

import httpx

from app.infrastructure.database.manager import DatabaseManager

logger = logging.getLogger(__name__)

# Fallback rates (used when API is unavailable)
# Format: (from, to) -> rate where conversion is: amount_to = amount_from / rate
# These match API format: 1 EUR = X foreign
FALLBACK_RATES: Dict[Tuple[str, str], float] = {
    ("USD", "EUR"): 1.05,  # 1 EUR = 1.05 USD, so 100 USD / 1.05 = 95.24 EUR
    ("HKD", "EUR"): 8.33,  # 1 EUR = 8.33 HKD, so 100 HKD / 8.33 = 12.00 EUR
    ("GBP", "EUR"): 0.85,  # 1 EUR = 0.85 GBP, so 100 GBP / 0.85 = 117.6 EUR
    ("EUR", "USD"): 0.95,  # Inverse: 100 EUR / 0.95 = 105.3 USD
    ("EUR", "HKD"): 0.12,  # Inverse: 100 EUR / 0.12 = 833 HKD
    ("EUR", "GBP"): 1.17,  # Inverse: 100 EUR / 1.17 = 85.5 GBP
}

# Default TTL for exchange rates (1 hour)
EXCHANGE_RATE_TTL_SECONDS = 3600


class ExchangeRateService:
    """Centralized service for exchange rate lookups and conversions.

    Features:
    - Database-backed caching with configurable TTL
    - Fallback rates when external API fails
    - Async implementation for consistency with codebase
    - Batch conversion support
    """

    def __init__(
        self, db_manager: DatabaseManager, ttl_seconds: int = EXCHANGE_RATE_TTL_SECONDS
    ):
        """Initialize the exchange rate service.

        Args:
            db_manager: Database manager for cache access
            ttl_seconds: Cache TTL in seconds (default: 1 hour)
        """
        self._db_manager = db_manager
        self._ttl_seconds = ttl_seconds
        self._memory_cache: Dict[str, Tuple[float, datetime]] = {}
        self._lock = asyncio.Lock()

    async def get_rate(self, from_currency: str, to_currency: str = "EUR") -> float:
        """Get exchange rate from one currency to another.

        Args:
            from_currency: Source currency code (USD, HKD, GBP, EUR)
            to_currency: Target currency code (default: EUR)

        Returns:
            Exchange rate (how much to_currency per 1 from_currency)

        Note:
            For conversions, use: amount_in_to_currency = amount / rate
            Example: 100 USD to EUR = 100 / 1.05 = 95.24 EUR
        """
        # Normalize currency codes
        from_curr = str(from_currency).upper()
        to_curr = str(to_currency).upper()

        # Same currency = no conversion
        if from_curr == to_curr:
            return 1.0

        cache_key = f"{from_curr}_{to_curr}"

        async with self._lock:
            # Check memory cache first
            if cache_key in self._memory_cache:
                rate, cached_at = self._memory_cache[cache_key]
                if datetime.now() - cached_at < timedelta(seconds=self._ttl_seconds):
                    return rate

            # Check database cache
            cached_rate = await self._get_from_db_cache(from_curr, to_curr)
            if cached_rate is not None:
                rate = cached_rate
                self._memory_cache[cache_key] = (rate, datetime.now())
                return rate

            # Fetch fresh rate from API
            fetched_rate = await self._fetch_rate_from_api(from_curr, to_curr)
            if fetched_rate is not None:
                rate = fetched_rate
                await self._store_in_db_cache(from_curr, to_curr, rate)
                self._memory_cache[cache_key] = (rate, datetime.now())
                return rate

            # Use fallback rate
            rate = self._get_fallback_rate(from_curr, to_curr)
            logger.warning(f"Using fallback rate for {from_curr}/{to_curr}: {rate}")
            return rate

    async def convert(
        self, amount: float, from_currency: str, to_currency: str = "EUR"
    ) -> float:
        """Convert an amount from one currency to another.

        Args:
            amount: Amount in source currency
            from_currency: Source currency code
            to_currency: Target currency code (default: EUR)

        Returns:
            Amount in target currency
        """
        if amount == 0:
            return 0.0

        rate = await self.get_rate(from_currency, to_currency)
        if rate <= 0:
            logger.error(f"Invalid rate {rate} for {from_currency}/{to_currency}")
            return amount  # Return original as fallback

        # Rate represents: 1 from_currency = (1/rate) to_currency
        # So: amount_in_to = amount / rate
        return amount / rate

    async def batch_convert_to_eur(self, amounts: Dict[str, float]) -> Dict[str, float]:
        """Convert multiple amounts to EUR.

        Args:
            amounts: Dictionary of currency -> amount

        Returns:
            Dictionary of currency -> amount_in_eur
        """
        result = {}
        for currency, amount in amounts.items():
            result[currency] = await self.convert(amount, currency, "EUR")
        return result

    async def refresh_rates(self, currencies: Optional[list] = None) -> None:
        """Refresh exchange rates for given currencies.

        Args:
            currencies: List of currency codes to refresh (default: all supported)
        """
        if currencies is None:
            currencies = ["USD", "HKD", "GBP"]

        for curr in currencies:
            if curr != "EUR":
                rate = await self._fetch_rate_from_api(curr, "EUR")
                if rate is not None:
                    await self._store_in_db_cache(curr, "EUR", rate)
                    async with self._lock:
                        self._memory_cache[f"{curr}_EUR"] = (rate, datetime.now())

    async def _get_from_db_cache(
        self, from_currency: str, to_currency: str
    ) -> Optional[float]:
        """Get rate from database cache if not expired."""
        try:
            row = await self._db_manager.cache.fetchone(
                """
                SELECT rate, expires_at FROM exchange_rates
                WHERE from_currency = ? AND to_currency = ?
                """,
                (from_currency, to_currency),
            )

            if row:
                expires_at = datetime.fromisoformat(row["expires_at"])
                if datetime.now() < expires_at:
                    return row["rate"]

            return None
        except Exception as e:
            logger.debug(f"DB cache lookup failed: {e}")
            return None

    async def _store_in_db_cache(
        self, from_currency: str, to_currency: str, rate: float
    ) -> None:
        """Store rate in database cache."""
        try:
            now = datetime.now()
            expires_at = now + timedelta(seconds=self._ttl_seconds)

            await self._db_manager.cache.execute(
                """
                INSERT OR REPLACE INTO exchange_rates
                (from_currency, to_currency, rate, fetched_at, expires_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    from_currency,
                    to_currency,
                    rate,
                    now.isoformat(),
                    expires_at.isoformat(),
                ),
            )
            await self._db_manager.cache.commit()
        except Exception as e:
            logger.warning(f"Failed to store rate in DB cache: {e}")

    async def _fetch_rate_from_api(
        self, from_currency: str, to_currency: str
    ) -> Optional[float]:
        """Fetch exchange rate from external API."""
        try:
            # Use exchangerate-api.com (free tier)
            url = f"https://api.exchangerate-api.com/v4/latest/{to_currency}"
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    url, timeout=15.0
                )  # Increased for slow connections

            if response.status_code == 200:
                data = response.json()
                rates = data.get("rates", {})

                if from_currency in rates:
                    rate = float(rates[from_currency])
                    logger.debug(f"Fetched rate {from_currency}/{to_currency}: {rate}")

                    # Also cache other rates while we have them
                    await self._cache_all_rates_from_response(to_currency, rates)

                    return rate

            logger.warning(
                f"API returned {response.status_code} for {from_currency}/{to_currency}"
            )
            return None

        except httpx.TimeoutException:
            logger.warning(f"Timeout fetching rate for {from_currency}/{to_currency}")
            return None
        except Exception as e:
            logger.error(f"Failed to fetch rate for {from_currency}/{to_currency}: {e}")
            return None

    async def _cache_all_rates_from_response(
        self, base_currency: str, rates: Dict[str, float]
    ) -> None:
        """Cache all rates from API response for efficiency."""
        supported_currencies = ["USD", "HKD", "GBP", "EUR"]

        for curr, rate in rates.items():
            if curr in supported_currencies and curr != base_currency:
                cache_key = f"{curr}_{base_currency}"
                async with self._lock:
                    self._memory_cache[cache_key] = (rate, datetime.now())
                await self._store_in_db_cache(curr, base_currency, rate)

    def _get_fallback_rate(self, from_currency: str, to_currency: str) -> float:
        """Get fallback rate when API is unavailable."""
        # Direct lookup
        key = (from_currency, to_currency)
        if key in FALLBACK_RATES:
            return FALLBACK_RATES[key]

        # Try reverse
        reverse_key = (to_currency, from_currency)
        if reverse_key in FALLBACK_RATES:
            return 1.0 / FALLBACK_RATES[reverse_key]

        # Try via EUR
        if to_currency != "EUR" and from_currency != "EUR":
            from_eur = self._get_fallback_rate(from_currency, "EUR")
            to_eur = self._get_fallback_rate(to_currency, "EUR")
            if from_eur > 0 and to_eur > 0:
                return from_eur / to_eur

        # Ultimate fallback: 1.0 (no conversion)
        logger.error(f"No fallback rate for {from_currency}/{to_currency}, using 1.0")
        return 1.0
