"""Centralized display update service.

All display updates should go through this service to ensure consistency
and proper resource management.
"""

import logging

from app.infrastructure.dependencies import (
    get_allocation_repository,
    get_portfolio_repository,
    get_position_repository,
    get_security_repository,
    get_settings_repository,
    get_ticker_content_service,
    get_tradernet_client,
)
from app.modules.display.services.display_service import set_text

logger = logging.getLogger(__name__)


async def update_display_ticker() -> None:
    """Update display ticker text using dependency injection.

    This is the single entry point for all ticker updates.
    Uses FastAPI dependency injection for proper resource management.
    """
    # Use dependency injection to get service
    portfolio_repo = get_portfolio_repository()
    position_repo = get_position_repository()
    security_repo = get_security_repository()
    settings_repo = get_settings_repository()
    allocation_repo = get_allocation_repository()
    tradernet_client = get_tradernet_client()

    ticker_service = get_ticker_content_service(
        portfolio_repo=portfolio_repo,
        position_repo=position_repo,
        security_repo=security_repo,
        settings_repo=settings_repo,
        allocation_repo=allocation_repo,
        tradernet_client=tradernet_client,
    )

    try:
        ticker_text = await ticker_service.generate_ticker_text()
        if ticker_text:
            logger.debug(f"Generated ticker text: '{ticker_text}'")
            set_text(ticker_text)
        else:
            logger.debug("Ticker service returned empty text (will use STATS mode)")
            set_text("")  # Empty string triggers STATS mode
    except Exception as e:
        logger.error(f"Failed to update display ticker: {e}", exc_info=True)
        set_text("")  # Empty string triggers STATS mode
