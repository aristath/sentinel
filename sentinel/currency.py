"""
Currency - Exchange rate management using Tradernet API.

Usage:
    currency = Currency()
    await currency.sync_rates()  # Fetch from Tradernet
    eur_value = await currency.to_eur(100, 'USD')
    rate = await currency.get_rate('GBP')
"""

import json
import logging
from typing import Optional

import requests

from sentinel.config.currencies import RATE_FETCH_CURRENCIES
from sentinel.database import Database
from sentinel.settings import Settings

logger = logging.getLogger(__name__)


class Currency:
    """Handles currency conversions using Tradernet rates."""

    CURRENCIES = RATE_FETCH_CURRENCIES
    _instance: "Currency | None" = None
    _db: "Database"
    _settings: "Settings"
    _rates_cache: dict | None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._db = Database()
            cls._instance._settings = Settings()
            cls._instance._rates_cache = None
        return cls._instance

    def __init__(self):
        pass  # All init done in __new__

    async def sync_rates(self) -> dict:
        """Fetch current exchange rates from Tradernet API."""
        try:
            params = {"cmd": "getCrossRatesForDate", "params": {"base_currency": "EUR", "currencies": self.CURRENCIES}}
            response = requests.get("https://tradernet.com/api/", params={"q": json.dumps(params)}, timeout=10)
            data = response.json()

            if "rates" in data:
                # Tradernet returns: 1 EUR = X other_currency
                # We need: 1 other_currency = Y EUR (invert the rates)
                rates = {"EUR": 1.0}
                for curr, rate in data["rates"].items():
                    if rate > 0:
                        rates[curr] = 1.0 / rate  # Invert: 1 USD = 1/1.17 EUR

                # Save to settings and cache (2 hours = 7200 seconds)
                await self._settings.set("exchange_rates", rates)
                await self._db.cache_set("currency:rates", json.dumps(rates), ttl_seconds=7200)
                self._rates_cache = rates
                return rates
        except Exception as e:
            logger.error(f"Failed to fetch exchange rates: {e}")

        # Return cached/default rates on failure
        return await self.get_rates()

    async def get_rates(self) -> dict:
        """Get all exchange rates to EUR (cached for 2 hours)."""
        if self._rates_cache:
            return self._rates_cache

        # Check DB cache first (2 hours = 7200 seconds)
        cached = await self._db.cache_get("currency:rates")
        if cached is not None:
            loaded = json.loads(cached)
            if isinstance(loaded, dict):
                self._rates_cache = loaded
                return self._rates_cache

        # Try to load from settings
        stored = await self._settings.get("exchange_rates")
        if stored and isinstance(stored, dict):
            self._rates_cache = stored
            # Store in cache for next time
            await self._db.cache_set("currency:rates", json.dumps(stored), ttl_seconds=7200)
        else:
            # Fallback defaults from config (single source of truth)
            from sentinel.config.currencies import DEFAULT_RATES

            self._rates_cache = DEFAULT_RATES.copy()

        return self._rates_cache

    async def get_rate(self, currency: str) -> float:
        """Get exchange rate for a currency to EUR."""
        rates = await self.get_rates()
        return rates.get(currency.upper(), 1.0)

    async def to_eur(self, amount: float, currency: str) -> float:
        """Convert amount from currency to EUR."""
        if currency.upper() == "EUR":
            return amount
        rate = await self.get_rate(currency)
        return amount * rate

    async def set_rate(self, currency: str, rate: float) -> None:
        """Manually set exchange rate for a currency."""
        rates = await self.get_rates()
        rates[currency.upper()] = rate
        await self._settings.set("exchange_rates", rates)
        self._rates_cache = rates

    def clear_cache(self) -> None:
        """Clear the rates cache."""
        self._rates_cache = None

    async def get_rate_for_date(self, currency: str, date: str) -> float:
        """
        Get exchange rate for a currency to EUR for a specific date.

        Args:
            currency: Currency code (USD, GBP, HKD, etc.)
            date: Date in YYYY-MM-DD format

        Returns:
            Exchange rate (1 currency = X EUR)
        """
        currency = currency.upper()
        if currency == "EUR":
            return 1.0

        # Check DB cache first
        cached = await self._get_cached_rate(currency, date)
        if cached is not None:
            return cached

        # Fetch from API
        rate = await self._fetch_historical_rate(currency, date)
        if rate is not None:
            await self._cache_rate(currency, date, rate)
            return rate

        # Fallback to current rate
        return await self.get_rate(currency)

    async def _get_cached_rate(self, currency: str, date: str) -> Optional[float]:
        """Get cached historical rate from database."""
        cursor = await self._db.conn.execute(
            "SELECT rate_to_eur FROM fx_rates_history WHERE date = ? AND currency = ?",
            (date, currency),
        )
        row = await cursor.fetchone()
        return row[0] if row else None

    async def _cache_rate(self, currency: str, date: str, rate: float) -> None:
        """Cache historical rate to database."""
        await self._db.conn.execute(
            "INSERT OR REPLACE INTO fx_rates_history (date, currency, rate_to_eur) VALUES (?, ?, ?)",
            (date, currency, rate),
        )
        await self._db.conn.commit()

    async def _fetch_historical_rate(self, currency: str, date: str) -> Optional[float]:
        """Fetch historical rate from Tradernet API."""
        try:
            params = {
                "cmd": "getCrossRatesForDate",
                "params": {
                    "base_currency": "EUR",
                    "currencies": [currency],
                    "date": date,
                },
            }
            response = requests.get(
                "https://tradernet.com/api/",
                params={"q": json.dumps(params)},
                timeout=10,
            )
            data = response.json()

            if "rates" in data and currency in data["rates"]:
                # Tradernet returns: 1 EUR = X currency
                # We need: 1 currency = Y EUR (invert)
                rate = data["rates"][currency]
                if rate > 0:
                    return 1.0 / rate
        except Exception as e:
            logger.warning(f"Failed to fetch historical rate for {currency} on {date}: {e}")

        return None

    async def to_eur_for_date(self, amount: float, currency: str, date: str) -> float:
        """Convert amount from currency to EUR using historical rate."""
        if currency.upper() == "EUR":
            return amount
        rate = await self.get_rate_for_date(currency, date)
        return amount * rate

    async def prefetch_rates_for_dates(self, currencies: list[str], dates: list[str]) -> None:
        """
        Prefetch and cache historical rates for multiple currencies and dates.
        This minimizes API calls by batching.
        """
        # Filter out EUR and get unique currencies
        currencies = list(set(c.upper() for c in currencies if c.upper() != "EUR"))
        if not currencies:
            return

        # Check which dates are missing from cache
        missing_dates = set()
        for date in dates:
            for currency in currencies:
                cached = await self._get_cached_rate(currency, date)
                if cached is None:
                    missing_dates.add(date)
                    break

        # Fetch missing dates (one API call per date for all currencies)
        for date in sorted(missing_dates):
            try:
                params = {
                    "cmd": "getCrossRatesForDate",
                    "params": {
                        "base_currency": "EUR",
                        "currencies": currencies,
                        "date": date,
                    },
                }
                response = requests.get(
                    "https://tradernet.com/api/",
                    params={"q": json.dumps(params)},
                    timeout=10,
                )
                data = response.json()

                if "rates" in data:
                    for curr, rate in data["rates"].items():
                        if rate > 0:
                            await self._cache_rate(curr, date, 1.0 / rate)
            except Exception as e:
                logger.warning(f"Failed to prefetch rates for {date}: {e}")
