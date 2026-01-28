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

    def __init__(self):
        self._db = Database()
        self._settings = Settings()
        self._rates_cache: Optional[dict] = None

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
