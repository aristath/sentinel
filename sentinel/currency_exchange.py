"""Currency exchange service for Tradernet FX operations.

Ported from sentinel-old/app/application/services/currency_exchange_service.py.

Handles currency conversions between EUR, USD, HKD, and GBP via Tradernet API.
"""

import logging
from dataclasses import dataclass
from typing import Optional, List

from sentinel.broker import Broker
from sentinel.database import Database
from sentinel.config.currencies import DIRECT_PAIRS, RATE_SYMBOLS

logger = logging.getLogger(__name__)


@dataclass
class ConversionStep:
    """A single step in a currency conversion path."""
    from_currency: str
    to_currency: str
    symbol: str
    action: str  # "BUY" or "SELL"


class CurrencyExchangeService:
    """Handles currency conversions via Tradernet FX pairs.

    Supports direct conversions between EUR, USD, HKD, and GBP.
    For pairs without direct instruments (GBP<->HKD), routes via EUR.
    """

    DIRECT_PAIRS = DIRECT_PAIRS
    RATE_SYMBOLS = RATE_SYMBOLS

    _instance: Optional['CurrencyExchangeService'] = None

    def __new__(cls):
        """Singleton pattern."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._broker = Broker()
        self._db = Database()

    def get_conversion_path(
        self, from_currency: str, to_currency: str
    ) -> List[ConversionStep]:
        """Get the conversion path between two currencies.

        Args:
            from_currency: Source currency code (EUR, USD, HKD, GBP)
            to_currency: Target currency code

        Returns:
            List of ConversionStep objects representing the path

        Raises:
            ValueError: If no conversion path exists
        """
        from_curr = from_currency.upper()
        to_curr = to_currency.upper()

        if from_curr == to_curr:
            return []

        # Check for direct pair
        pair_key = (from_curr, to_curr)
        if pair_key in self.DIRECT_PAIRS:
            symbol, action = self.DIRECT_PAIRS[pair_key]
            return [ConversionStep(from_curr, to_curr, symbol, action)]

        # GBP <-> HKD requires routing via EUR
        if {from_curr, to_curr} == {"GBP", "HKD"}:
            steps = []
            # Step 1: from_currency -> EUR
            step1_key = (from_curr, "EUR")
            if step1_key in self.DIRECT_PAIRS:
                symbol1, action1 = self.DIRECT_PAIRS[step1_key]
                steps.append(ConversionStep(from_curr, "EUR", symbol1, action1))

            # Step 2: EUR -> to_currency
            step2_key = ("EUR", to_curr)
            if step2_key in self.DIRECT_PAIRS:
                symbol2, action2 = self.DIRECT_PAIRS[step2_key]
                steps.append(ConversionStep("EUR", to_curr, symbol2, action2))

            if len(steps) == 2:
                return steps

        raise ValueError(f"No conversion path from {from_curr} to {to_curr}")

    async def get_rate(self, from_currency: str, to_currency: str) -> Optional[float]:
        """Get the current exchange rate between two currencies.

        Args:
            from_currency: Source currency code
            to_currency: Target currency code

        Returns:
            Exchange rate (how many units of to_currency per 1 from_currency),
            or None if rate cannot be fetched
        """
        from_curr = from_currency.upper()
        to_curr = to_currency.upper()

        if from_curr == to_curr:
            return 1.0

        if not self._broker.connected:
            logger.error("Broker not connected for rate lookup")
            return None

        try:
            # Find the symbol for this pair
            symbol = None
            inverse = False

            # Check direct lookup
            if (from_curr, to_curr) in self.RATE_SYMBOLS:
                symbol = self.RATE_SYMBOLS[(from_curr, to_curr)]
            elif (to_curr, from_curr) in self.RATE_SYMBOLS:
                symbol = self.RATE_SYMBOLS[(to_curr, from_curr)]
                inverse = True

            if not symbol:
                # Try via conversion path
                path = self.get_conversion_path(from_curr, to_curr)
                if len(path) == 1:
                    symbol = path[0].symbol
                elif len(path) == 2:
                    # Multi-step: calculate combined rate
                    rate1 = await self.get_rate(path[0].from_currency, path[0].to_currency)
                    rate2 = await self.get_rate(path[1].from_currency, path[1].to_currency)
                    if rate1 and rate2:
                        return rate1 * rate2
                    return None

            if not symbol:
                return None

            # Fetch quote
            quote = await self._broker.get_quote(symbol)
            if quote and quote.get('price', 0) > 0:
                rate = quote['price']
                return 1.0 / rate if inverse else rate

            return None
        except Exception as e:
            logger.error(f"Failed to get rate {from_curr}/{to_curr}: {e}")
            return None

    async def exchange(
        self,
        from_currency: str,
        to_currency: str,
        amount: float
    ) -> Optional[dict]:
        """Execute a currency exchange.

        Args:
            from_currency: Source currency code
            to_currency: Target currency code
            amount: Amount in source currency to convert

        Returns:
            Order result dict if successful, None otherwise
        """
        from_curr = from_currency.upper()
        to_curr = to_currency.upper()

        if from_curr == to_curr:
            logger.warning(f"Same currency exchange requested: {from_curr}")
            return None

        if amount <= 0:
            logger.error(f"Invalid exchange amount: {amount}")
            return None

        if not self._broker.connected:
            logger.error("Broker not connected for exchange")
            return None

        try:
            path = self.get_conversion_path(from_curr, to_curr)

            if len(path) == 0:
                return None
            elif len(path) == 1:
                # Direct conversion
                step = path[0]
                return await self._execute_step(step, amount)
            else:
                # Multi-step conversion (GBP <-> HKD via EUR)
                current_amount = amount
                last_result = None

                for step in path:
                    result = await self._execute_step(step, current_amount)
                    if not result:
                        logger.error(f"Failed at step {step.from_currency} -> {step.to_currency}")
                        return None

                    # Get the converted amount for next step
                    rate = await self.get_rate(step.from_currency, step.to_currency)
                    if rate:
                        current_amount = current_amount * rate

                    last_result = result

                return last_result

        except Exception as e:
            logger.error(f"Failed to exchange {from_curr} -> {to_curr}: {e}")
            return None

    async def _execute_step(self, step: ConversionStep, amount: float) -> Optional[dict]:
        """Execute a single conversion step.

        Args:
            step: ConversionStep to execute
            amount: Amount to convert

        Returns:
            Order result dict if successful, None otherwise
        """
        logger.info(
            f"Executing FX: {step.action} {step.symbol} "
            f"(converting {amount:.2f} {step.from_currency} to {step.to_currency})"
        )

        # FX orders use amount as quantity (the amount to exchange)
        if step.action == "BUY":
            order_id = await self._broker.buy(step.symbol, int(amount))
        else:
            order_id = await self._broker.sell(step.symbol, int(amount))

        if order_id:
            return {'order_id': order_id, 'symbol': step.symbol, 'action': step.action, 'amount': amount}
        return None

    async def ensure_balance(
        self,
        currency: str,
        min_amount: float,
        source_currency: str = "EUR"
    ) -> bool:
        """Ensure we have at least min_amount in the target currency.

        If insufficient balance, converts from source_currency.

        Args:
            currency: Target currency to ensure balance for
            min_amount: Minimum amount needed
            source_currency: Currency to convert from if needed (default: EUR)

        Returns:
            True if balance is sufficient (or conversion succeeded), False otherwise
        """
        currency = currency.upper()
        source_currency = source_currency.upper()

        if currency == source_currency:
            return True

        if not self._broker.connected:
            logger.error("Broker not connected for balance check")
            return False

        try:
            # Get current balances from database
            balances = await self._db.get_cash_balances()
            current_balance = balances.get(currency, 0)
            source_balance = balances.get(source_currency, 0)

            if current_balance >= min_amount:
                logger.info(f"Sufficient {currency} balance: {current_balance:.2f} >= {min_amount:.2f}")
                return True

            # Calculate how much we need to convert
            needed = min_amount - current_balance

            # Add 2% buffer for rate fluctuations and fees
            needed_with_buffer = needed * 1.02

            # Get exchange rate to calculate source amount needed
            rate = await self.get_rate(source_currency, currency)
            if not rate:
                logger.error(f"Could not get rate for {source_currency}/{currency}")
                return False

            source_amount_needed = needed_with_buffer / rate

            if source_balance < source_amount_needed:
                logger.warning(
                    f"Insufficient {source_currency} to convert: "
                    f"need {source_amount_needed:.2f}, have {source_balance:.2f}"
                )
                return False

            # Execute conversion
            logger.info(
                f"Converting {source_amount_needed:.2f} {source_currency} "
                f"to {currency} (need {min_amount:.2f})"
            )
            result = await self.exchange(source_currency, currency, source_amount_needed)

            if result:
                logger.info(f"Currency exchange completed")
                return True
            else:
                logger.error("Currency exchange failed")
                return False

        except Exception as e:
            logger.error(f"Failed to ensure {currency} balance: {e}")
            return False

    def get_available_currencies(self) -> List[str]:
        """Get list of currencies that can be exchanged."""
        currencies = set()
        for from_curr, to_curr in self.DIRECT_PAIRS.keys():
            currencies.add(from_curr)
            currencies.add(to_curr)
        return sorted(currencies)


def get_stock_currency(geography: str) -> str:
    """Get the trading currency for a stock based on its geography.

    Args:
        geography: Stock geography code (EU, US, ASIA, UK, Greece, Europe, China)

    Returns:
        Currency code (EUR, USD, HKD, GBP)
    """
    from sentinel.config.currencies import get_currency_for_geography
    return get_currency_for_geography(geography)
