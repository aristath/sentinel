"""Shared utilities for Tradernet client."""

import asyncio
import logging
from contextlib import contextmanager
from typing import Optional

from app.core.events import SystemEvent, emit
from app.domain.services.exchange_rate_service import ExchangeRateService

logger = logging.getLogger(__name__)

# Global ExchangeRateService instance (set by TradernetClient)
_exchange_rate_service: Optional[ExchangeRateService] = None


@contextmanager
def led_api_call():
    """Context manager to emit events during API calls for LED indication."""
    emit(SystemEvent.API_CALL_START)
    try:
        yield
    finally:
        emit(SystemEvent.API_CALL_END)


def get_exchange_rate_sync(from_currency: str, to_currency: str = "EUR") -> float:
    """Get exchange rate synchronously using ExchangeRateService.

    This is a sync wrapper around async ExchangeRateService.get_rate().
    Uses asyncio.run() to call the async method from sync code.
    Falls back to hardcoded rates if service unavailable or if called from async context.

    Args:
        from_currency: Source currency code
        to_currency: Target currency code (default: EUR)

    Returns:
        Exchange rate (amount of to_currency per 1 from_currency)
    """
    global _exchange_rate_service

    # Fallback rates
    fallback_rates = {
        ("HKD", "EUR"): 8.5,
        ("USD", "EUR"): 1.05,
        ("GBP", "EUR"): 0.85,
    }

    if _exchange_rate_service is None:
        return fallback_rates.get((from_currency, to_currency), 1.0)

    try:
        # Try to get the current event loop
        try:
            asyncio.get_running_loop()
            # If we're in an async context, we can't use asyncio.run()
            # Fall back to hardcoded rates
            logger.debug(
                f"Called get_exchange_rate_sync from async context, using fallback rate for {from_currency}/{to_currency}"
            )
            return fallback_rates.get((from_currency, to_currency), 1.0)
        except RuntimeError:
            # No running loop, safe to use asyncio.run()
            pass

        # Use asyncio.run() to call async method from sync context
        return asyncio.run(_exchange_rate_service.get_rate(from_currency, to_currency))
    except Exception as e:
        logger.warning(
            f"Failed to get exchange rate {from_currency}/{to_currency}: {e}"
        )
        return fallback_rates.get((from_currency, to_currency), 1.0)


def set_exchange_rate_service(service: Optional[ExchangeRateService]) -> None:
    """Set the global ExchangeRateService instance.

    Args:
        service: ExchangeRateService instance or None
    """
    global _exchange_rate_service
    _exchange_rate_service = service
