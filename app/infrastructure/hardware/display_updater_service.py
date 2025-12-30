"""Centralized display update service.

All display updates should go through this service to ensure consistency
and proper resource management.
"""

from app.infrastructure.dependencies import (
    get_allocation_repository,
    get_portfolio_repository,
    get_position_repository,
    get_settings_repository,
    get_stock_repository,
    get_ticker_content_service,
    get_tradernet_client,
)
from app.infrastructure.hardware.display_service import set_text


async def update_display_ticker() -> None:
    """Update display ticker text using dependency injection.

    This is the single entry point for all ticker updates.
    Uses FastAPI dependency injection for proper resource management.
    """
    # Use dependency injection to get service
    portfolio_repo = get_portfolio_repository()
    position_repo = get_position_repository()
    stock_repo = get_stock_repository()
    settings_repo = get_settings_repository()
    allocation_repo = get_allocation_repository()
    tradernet_client = get_tradernet_client()

    ticker_service = get_ticker_content_service(
        portfolio_repo=portfolio_repo,
        position_repo=position_repo,
        stock_repo=stock_repo,
        settings_repo=settings_repo,
        allocation_repo=allocation_repo,
        tradernet_client=tradernet_client,
    )

    ticker_text = await ticker_service.generate_ticker_text()
    set_text(ticker_text)
