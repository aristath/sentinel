"""Ticker content generation service.

Generates text content for the LED matrix ticker display, including
portfolio value, cash balance, and trading recommendations.
"""

import logging
from typing import Protocol

from app.core.cache.cache import cache
from app.domain.portfolio_hash import generate_recommendation_cache_key
from app.domain.repositories.protocols import (
    IAllocationRepository,
    IPositionRepository,
    ISettingsRepository,
    IStockRepository,
)
from app.domain.services.settings_service import SettingsService
from app.infrastructure.external.tradernet import TradernetClient
from app.infrastructure.market_hours import format_market_status_for_display

logger = logging.getLogger(__name__)


class IPortfolioRepository(Protocol):
    """Protocol for portfolio repository."""

    async def get_latest(self):
        """Get latest portfolio snapshot."""
        ...


class TickerContentService:
    """Service for generating ticker display content."""

    def __init__(
        self,
        portfolio_repo: IPortfolioRepository,
        position_repo: IPositionRepository,
        stock_repo: IStockRepository,
        settings_repo: ISettingsRepository,
        allocation_repo: IAllocationRepository,
        tradernet_client: TradernetClient,
    ) -> None:
        """Initialize ticker content service.

        Args:
            portfolio_repo: Portfolio repository
            position_repo: Position repository
            stock_repo: Stock repository
            settings_repo: Settings repository
            allocation_repo: Allocation repository
            tradernet_client: Tradernet client for cash balances
        """
        self._portfolio_repo = portfolio_repo
        self._position_repo = position_repo
        self._stock_repo = stock_repo
        self._settings_repo = settings_repo
        self._allocation_repo = allocation_repo
        self._tradernet_client = tradernet_client
        self._settings_service = SettingsService(settings_repo)

    async def generate_ticker_text(self) -> str:
        """Generate ticker text for the LED display.

        Returns:
            Formatted ticker text with portfolio value, cash balance, and recommendations.
            Returns empty string on error.
        """
        try:
            show_value = await self._settings_repo.get_float("ticker_show_value", 1.0)
            show_cash = await self._settings_repo.get_float("ticker_show_cash", 1.0)
            show_actions = await self._settings_repo.get_float(
                "ticker_show_actions", 1.0
            )
            show_amounts = await self._settings_repo.get_float(
                "ticker_show_amounts", 1.0
            )

            parts = []

            # Portfolio value
            if show_value > 0:
                latest_snapshot = await self._portfolio_repo.get_latest()
                if latest_snapshot and latest_snapshot.total_value:
                    parts.append(f"PORTFOLIO €{int(latest_snapshot.total_value):,}")

            # Cash balance
            if show_cash > 0:
                latest_snapshot = await self._portfolio_repo.get_latest()
                if latest_snapshot and latest_snapshot.cash_balance:
                    parts.append(f"CASH €{int(latest_snapshot.cash_balance):,}")

            # Recommendations - read from primary cache (show ALL)
            has_recommendations = False
            if show_actions > 0:
                # Generate portfolio hash to read from primary cache
                positions = await self._position_repo.get_all()
                stocks = await self._stock_repo.get_all_active()
                settings = await self._settings_service.get_settings()
                allocations = await self._allocation_repo.get_all()
                position_dicts = [
                    {"symbol": p.symbol, "quantity": p.quantity} for p in positions
                ]
                cash_balances = (
                    {
                        b.currency: b.amount
                        for b in self._tradernet_client.get_cash_balances()
                    }
                    if self._tradernet_client.is_connected
                    else {}
                )

                # Fetch pending orders for cache key
                pending_orders = []
                if self._tradernet_client.is_connected:
                    try:
                        pending_orders = self._tradernet_client.get_pending_orders()
                    except Exception as e:
                        logger.warning(f"Failed to fetch pending orders: {e}")

                portfolio_cache_key = generate_recommendation_cache_key(
                    position_dicts,
                    settings.to_dict(),
                    stocks,
                    cash_balances,
                    allocations,
                    pending_orders,
                )
                cache_key = f"recommendations:{portfolio_cache_key}"

                cached = cache.get(cache_key)
                if cached and cached.get("steps"):
                    has_recommendations = True
                    for step in cached["steps"]:  # ALL recommendations, no limit
                        side = step.get("side", "").upper()
                        symbol = step.get("symbol", "").split(".")[0]
                        value = step.get("estimated_value", 0)
                        if show_amounts > 0:
                            parts.append(f"{side} {symbol} €{int(value)}")
                        else:
                            parts.append(f"{side} {symbol}")

            # Add market status (always append)
            # Include "NO PENDING OPPORTUNITIES" only if no recommendations exist
            market_status_text = await format_market_status_for_display(
                has_recommendations
            )
            if market_status_text:
                parts.append(market_status_text)

            if parts:
                return " * ".join(parts)

            # Fallback to system status when no content available
            # Check if Tradernet is connected as a simple health indicator
            if self._tradernet_client.is_connected:
                return "SYSTEM ONLINE"
            else:
                return "READY"

        except Exception as e:
            logger.error(f"Failed to generate ticker text: {e}")
            # Return system status even on error
            try:
                if self._tradernet_client.is_connected:
                    return "SYSTEM ONLINE"
                else:
                    return "READY"
            except Exception:
                return "READY"
