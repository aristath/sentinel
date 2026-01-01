"""Dependency injection for Trading service."""

from functools import lru_cache

from app.modules.trading.services.local_trading_service import LocalTradingService


@lru_cache()
def get_trading_service() -> LocalTradingService:
    """
    Get Trading service instance.

    Returns:
        LocalTradingService instance (cached singleton)
    """
    return LocalTradingService()
