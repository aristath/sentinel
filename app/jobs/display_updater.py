"""Periodic LED display updater job.

This job runs every 9.9 seconds to ensure the LED display always shows content,
even when no other events trigger display updates. It fetches current ticker
content and updates the display state, which triggers the DISPLAY_STATE_CHANGED
event that broadcasts to SSE subscribers.
"""

import logging

from app.infrastructure.hardware.display_service import set_next_actions

logger = logging.getLogger(__name__)


async def update_display_periodic():
    """Periodically update LED display with current ticker content.

    This function runs every 9.9 seconds to ensure the display always shows
    something, even when no other events occur. It generates ticker content
    using TickerContentService and updates the display state, which triggers
    the DISPLAY_STATE_CHANGED event that broadcasts to SSE subscribers.

    The ticker content service has a fallback to show "SYSTEM ONLINE" or "READY"
    when there's no portfolio data, ensuring the display is never blank.
    """
    try:
        from app.domain.services.ticker_content_service import TickerContentService
        from app.infrastructure.external.tradernet import get_tradernet_client
        from app.repositories import (
            AllocationRepository,
            PortfolioRepository,
            PositionRepository,
            SettingsRepository,
            StockRepository,
        )

        # Instantiate repositories and service
        portfolio_repo = PortfolioRepository()
        position_repo = PositionRepository()
        stock_repo = StockRepository()
        settings_repo = SettingsRepository()
        allocation_repo = AllocationRepository()
        tradernet_client = get_tradernet_client()

        ticker_service = TickerContentService(
            portfolio_repo=portfolio_repo,
            position_repo=position_repo,
            stock_repo=stock_repo,
            settings_repo=settings_repo,
            allocation_repo=allocation_repo,
            tradernet_client=tradernet_client,
        )

        # Generate ticker text (includes fallback to "SYSTEM ONLINE" or "READY")
        ticker_text = await ticker_service.generate_ticker_text()

        # Always update display (even if content hasn't changed)
        # This ensures the display receives periodic updates via SSE
        set_next_actions(ticker_text)

        logger.debug(f"Periodic display update: {ticker_text[:50]}...")

    except Exception as e:
        # Log error but don't crash the job
        logger.error(f"Periodic display update failed: {e}", exc_info=True)
