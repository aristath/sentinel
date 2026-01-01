"""Dependency injection for Portfolio service."""

from functools import lru_cache

from app.modules.portfolio.services.local_portfolio_service import LocalPortfolioService


@lru_cache()
def get_portfolio_service() -> LocalPortfolioService:
    """
    Get Portfolio service instance.

    Returns:
        LocalPortfolioService instance (cached singleton)
    """
    return LocalPortfolioService()
