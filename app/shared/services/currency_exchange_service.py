"""Currency exchange service for Tradernet FX operations.

Handles currency conversions between EUR, USD, HKD, and GBP via Tradernet API.
"""

import asyncio
import logging
from dataclasses import dataclass
from typing import List, Optional

from app.infrastructure.external.tradernet import OrderResult, TradernetClient

logger = logging.getLogger(__name__)


def _find_rate_symbol(
    from_curr: str, to_curr: str, service
) -> tuple[Optional[str], bool]:
    """Find exchange rate symbol and whether it's inverse."""
    if (from_curr, to_curr) in service.RATE_SYMBOLS:
        return service.RATE_SYMBOLS[(from_curr, to_curr)], False
    elif (to_curr, from_curr) in service.RATE_SYMBOLS:
        return service.RATE_SYMBOLS[(to_curr, from_curr)], True
    return None, False


def _get_rate_via_path(from_curr: str, to_curr: str, service) -> Optional[float]:
    """Get exchange rate via conversion path."""
    path = service.get_conversion_path(from_curr, to_curr)
    if len(path) == 1:
        symbol = path[0].symbol
        quote = service.client.get_quote(symbol)
        return quote.price if quote and quote.price > 0 else None
    elif len(path) == 2:
        rate1 = service.get_rate(path[0].from_currency, path[0].to_currency)
        rate2 = service.get_rate(path[1].from_currency, path[1].to_currency)
        return rate1 * rate2 if rate1 and rate2 else None
    return None


@dataclass
class ExchangeRate:
    """Exchange rate data."""

    from_currency: str
    to_currency: str
    rate: float
    bid: float
    ask: float
    symbol: str


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

    # Direct currency pairs available on Tradernet
    # Format: (from_currency, to_currency) -> (symbol, action)
    DIRECT_PAIRS = {
        # EUR <-> USD (ITS_MONEY market)
        # To convert EUR to USD: SELL EURUSD (sell EUR, receive USD)
        # To convert USD to EUR: BUY EURUSD (buy EUR, pay USD)
        ("EUR", "USD"): ("EURUSD_T0.ITS", "SELL"),
        ("USD", "EUR"): ("EURUSD_T0.ITS", "BUY"),
        # EUR <-> GBP (ITS_MONEY market)
        # To convert EUR to GBP: SELL EURGBP (sell EUR, receive GBP)
        # To convert GBP to EUR: BUY EURGBP (buy EUR, pay GBP)
        ("EUR", "GBP"): ("EURGBP_T0.ITS", "SELL"),
        ("GBP", "EUR"): ("EURGBP_T0.ITS", "BUY"),
        # GBP <-> USD (ITS_MONEY market)
        # To convert GBP to USD: SELL GBPUSD (sell GBP, receive USD)
        # To convert USD to GBP: BUY GBPUSD (buy GBP, pay USD)
        ("GBP", "USD"): ("GBPUSD_T0.ITS", "SELL"),
        ("USD", "GBP"): ("GBPUSD_T0.ITS", "BUY"),
        # HKD <-> EUR (MONEY market, EXANTE)
        ("EUR", "HKD"): ("HKD/EUR", "BUY"),
        ("HKD", "EUR"): ("HKD/EUR", "SELL"),
        # HKD <-> USD (MONEY market, EXANTE)
        ("USD", "HKD"): ("HKD/USD", "BUY"),
        ("HKD", "USD"): ("HKD/USD", "SELL"),
    }

    # Symbols for rate lookups (base_currency -> quote_currency)
    RATE_SYMBOLS = {
        ("EUR", "USD"): "EURUSD_T0.ITS",
        ("EUR", "GBP"): "EURGBP_T0.ITS",
        ("GBP", "USD"): "GBPUSD_T0.ITS",
        ("HKD", "EUR"): "HKD/EUR",
        ("HKD", "USD"): "HKD/USD",
    }

    def __init__(self, client: TradernetClient):
        """Initialize the currency exchange service.

        Args:
            client: TradernetClient instance (required).
        """
        self._client = client

    @property
    def client(self) -> TradernetClient:
        """Get the Tradernet client."""
        return self._client

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

    def get_rate(self, from_currency: str, to_currency: str) -> Optional[float]:
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

        if not self.client.is_connected:
            if not self.client.connect():
                logger.error("Failed to connect to Tradernet for rate lookup")
                # Fallback to ExchangeRateService
                return self._get_rate_fallback(from_curr, to_curr)

        try:
            symbol, inverse = _find_rate_symbol(from_curr, to_curr, self)
            if not symbol:
                rate = _get_rate_via_path(from_curr, to_curr, self)
                if rate:
                    return rate
                # Fallback if path lookup fails
                return self._get_rate_fallback(from_curr, to_curr)

            quote = self.client.get_quote(symbol)
            if quote and quote.price > 0:
                return 1.0 / quote.price if inverse else quote.price

            # Quote lookup failed, use fallback
            logger.warning(
                f"Failed to get quote for {symbol}, using ExchangeRateService fallback"
            )
            return self._get_rate_fallback(from_curr, to_curr)
        except Exception as e:
            logger.error(f"Failed to get rate {from_curr}/{to_curr}: {e}")
            # Fallback on exception
            return self._get_rate_fallback(from_curr, to_curr)

    def _get_rate_fallback(self, from_curr: str, to_curr: str) -> Optional[float]:
        """Get rate from ExchangeRateService as fallback when Tradernet quote fails."""
        try:
            from app.core.database.manager import get_db_manager
            from app.domain.services.exchange_rate_service import ExchangeRateService

            db_manager = get_db_manager()
            exchange_rate_service = ExchangeRateService(db_manager)

            # Handle async call - check if we're in an event loop
            try:
                asyncio.get_running_loop()
                # We're in an async context, need to use a different approach
                # Use a thread pool to run the async function
                import concurrent.futures

                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(
                        lambda: (
                            asyncio.run(
                                exchange_rate_service.get_rate(from_curr, "EUR")
                            )
                            if to_curr == "EUR"
                            else (
                                asyncio.run(
                                    exchange_rate_service.get_rate(to_curr, "EUR")
                                )
                                if from_curr == "EUR"
                                else None
                            )
                        )
                    )
                    if to_curr == "EUR":
                        rate = future.result(timeout=5)
                        return 1.0 / rate if rate and rate > 0 else None
                    elif from_curr == "EUR":
                        rate = future.result(timeout=5)
                        return rate if rate and rate > 0 else None
                    else:
                        # Two-step conversion
                        future1 = executor.submit(
                            lambda: asyncio.run(
                                exchange_rate_service.get_rate(from_curr, "EUR")
                            )
                        )
                        future2 = executor.submit(
                            lambda: asyncio.run(
                                exchange_rate_service.get_rate(to_curr, "EUR")
                            )
                        )
                        rate1 = future1.result(timeout=5)
                        rate2 = future2.result(timeout=5)
                        if rate1 and rate2 and rate1 > 0 and rate2 > 0:
                            return rate2 / rate1
                        return None
            except RuntimeError:
                # No event loop running, can use asyncio.run()
                if to_curr == "EUR":
                    rate = asyncio.run(exchange_rate_service.get_rate(from_curr, "EUR"))
                    return 1.0 / rate if rate and rate > 0 else None
                elif from_curr == "EUR":
                    rate = asyncio.run(exchange_rate_service.get_rate(to_curr, "EUR"))
                    return rate if rate and rate > 0 else None
                else:
                    rate1 = asyncio.run(
                        exchange_rate_service.get_rate(from_curr, "EUR")
                    )
                    rate2 = asyncio.run(exchange_rate_service.get_rate(to_curr, "EUR"))
                    if rate1 and rate2 and rate1 > 0 and rate2 > 0:
                        return rate2 / rate1
                    return None
        except Exception as e:
            logger.error(f"Failed to get fallback rate {from_curr}/{to_curr}: {e}")
            return None

    def _validate_exchange_request(
        self, from_curr: str, to_curr: str, amount: float
    ) -> bool:
        """Validate exchange request parameters."""
        if from_curr == to_curr:
            logger.warning(f"Same currency exchange requested: {from_curr}")
            return False

        if amount <= 0:
            logger.error(f"Invalid exchange amount: {amount}")
            return False

        if not self.client.is_connected:
            if not self.client.connect():
                logger.error("Failed to connect to Tradernet for exchange")
                return False

        return True

    def _execute_multi_step_conversion(
        self, path: list, amount: float
    ) -> Optional[OrderResult]:
        """Execute multi-step currency conversion."""
        current_amount = amount
        last_result = None

        for step in path:
            result = self._execute_step(step, current_amount)
            if not result:
                logger.error(
                    f"Failed at step {step.from_currency} -> {step.to_currency}"
                )
                return None

            rate = self.get_rate(step.from_currency, step.to_currency)
            if rate:
                current_amount = current_amount * rate

            last_result = result

        return last_result

    def exchange(
        self, from_currency: str, to_currency: str, amount: float
    ) -> Optional[OrderResult]:
        """Execute a currency exchange.

        Args:
            from_currency: Source currency code
            to_currency: Target currency code
            amount: Amount in source currency to convert

        Returns:
            OrderResult if successful, None otherwise
        """
        from_curr = from_currency.upper()
        to_curr = to_currency.upper()

        if not self._validate_exchange_request(from_curr, to_curr, amount):
            return None

        try:
            path = self.get_conversion_path(from_curr, to_curr)

            if len(path) == 0:
                return None
            elif len(path) == 1:
                return self._execute_step(path[0], amount)
            else:
                return self._execute_multi_step_conversion(path, amount)
        except Exception as e:
            logger.error(f"Failed to exchange {from_curr} -> {to_curr}: {e}")
            return None

    def _execute_step(
        self, step: ConversionStep, amount: float
    ) -> Optional[OrderResult]:
        """Execute a single conversion step.

        Args:
            step: ConversionStep to execute
            amount: Amount to convert

        Returns:
            OrderResult if successful, None otherwise
        """
        logger.info(
            f"Executing FX: {step.action} {step.symbol} "
            f"(converting {amount:.2f} {step.from_currency} to {step.to_currency})"
        )

        return self.client.place_order(
            symbol=step.symbol,
            side=step.action,
            quantity=amount,
        )

    def _get_balances(self, currency: str, source_currency: str) -> tuple[float, float]:
        """Get current and source currency balances (including negative balances)."""
        balances = self.client.get_cash_balances()
        current_balance = 0.0
        source_balance = 0.0

        for bal in balances:
            if bal.currency == currency:
                current_balance = bal.amount
                # Log warning if negative balance detected
                if current_balance < 0:
                    logger.warning(
                        f"Negative balance detected for {currency}: {current_balance:.2f}"
                    )
            elif bal.currency == source_currency:
                source_balance = bal.amount
                # Log warning if negative balance detected
                if source_balance < 0:
                    logger.warning(
                        f"Negative balance detected for {source_currency}: {source_balance:.2f}"
                    )

        return current_balance, source_balance

    def _convert_for_balance(
        self, currency: str, source_currency: str, needed: float, source_balance: float
    ) -> bool:
        """Convert source currency to target currency to meet balance requirement."""
        # Safety check: block conversion if source balance is negative
        if source_balance < 0:
            logger.error(
                f"Cannot convert {source_currency} to {currency}: "
                f"source balance is negative ({source_balance:.2f})"
            )
            return False

        needed_with_buffer = needed * 1.02

        rate = self.get_rate(source_currency, currency)
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

        logger.info(
            f"Converting {source_amount_needed:.2f} {source_currency} "
            f"to {currency} (need {needed:.2f})"
        )
        result = self.exchange(source_currency, currency, source_amount_needed)

        if result:
            logger.info(f"Currency exchange completed: {result.order_id}")
            return True

        logger.error(f"Failed to convert {source_currency} to {currency}")
        return False

    def ensure_balance(
        self, currency: str, min_amount: float, source_currency: str = "EUR"
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

        if not self.client.is_connected:
            if not self.client.connect():
                logger.error("Failed to connect to Tradernet for balance check")
                return False

        try:
            current_balance, source_balance = self._get_balances(
                currency, source_currency
            )

            # Block conversion if source balance is negative
            if source_balance < 0:
                logger.error(
                    f"Cannot ensure {currency} balance: source currency {source_currency} "
                    f"has negative balance ({source_balance:.2f})"
                )
                return False

            if current_balance >= min_amount:
                logger.info(
                    f"Sufficient {currency} balance: {current_balance:.2f} >= {min_amount:.2f}"
                )
                return True

            needed = min_amount - current_balance
            return self._convert_for_balance(
                currency, source_currency, needed, source_balance
            )

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


# Note: Currency is now synced from Tradernet and stored in securities.currency
# No mapping function needed - currency comes directly from the security's currency field
