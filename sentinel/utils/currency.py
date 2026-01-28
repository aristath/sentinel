"""
Currency Converter - Single source of truth for currency conversions.

Usage:
    converter = CurrencyConverter()
    eur_value = await converter.to_eur(100, 'USD')
    usd_value = await converter.from_eur(85, 'USD')
    converted = await converter.convert(100, 'USD', 'GBP')
"""

from typing import Optional


class CurrencyConverter:
    """Handles all currency conversions using a rates provider."""

    def __init__(self, rates_provider=None):
        """
        Initialize the converter.

        Args:
            rates_provider: Object with get_rate(currency) method.
                           If None, uses sentinel.currency.Currency.
        """
        self._rates_provider = rates_provider
        self._currency_instance = None

    async def _get_provider(self):
        """Lazy-load the rates provider."""
        if self._rates_provider is not None:
            return self._rates_provider

        if self._currency_instance is None:
            from sentinel.currency import Currency
            self._currency_instance = Currency()

        return self._currency_instance

    async def get_rate(self, currency: str) -> float:
        """
        Get exchange rate for a currency to EUR.

        Args:
            currency: Currency code (e.g., 'USD', 'GBP')

        Returns:
            Exchange rate (1 currency = X EUR)
        """
        provider = await self._get_provider()
        return await provider.get_rate(currency)

    async def to_eur(self, amount: float, from_currency: str) -> float:
        """
        Convert amount from a currency to EUR.

        Args:
            amount: Amount in source currency
            from_currency: Source currency code

        Returns:
            Equivalent amount in EUR
        """
        if from_currency.upper() == 'EUR':
            return amount
        rate = await self.get_rate(from_currency)
        return amount * rate

    async def from_eur(self, amount: float, to_currency: str) -> float:
        """
        Convert amount from EUR to another currency.

        Args:
            amount: Amount in EUR
            to_currency: Target currency code

        Returns:
            Equivalent amount in target currency
        """
        if to_currency.upper() == 'EUR':
            return amount
        rate = await self.get_rate(to_currency)
        if rate == 0:
            return 0
        return amount / rate

    async def convert(self, amount: float, from_currency: str, to_currency: str) -> float:
        """
        Convert amount between any two currencies.

        Args:
            amount: Amount in source currency
            from_currency: Source currency code
            to_currency: Target currency code

        Returns:
            Equivalent amount in target currency
        """
        if from_currency.upper() == to_currency.upper():
            return amount

        # Convert to EUR first, then to target currency
        eur_amount = await self.to_eur(amount, from_currency)
        return await self.from_eur(eur_amount, to_currency)
