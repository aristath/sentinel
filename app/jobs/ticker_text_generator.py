"""Ticker text generator job for LED display.

Generates ticker text from portfolio value, cash balance, and recommendations,
then sets it via display_service.set_next_actions().
"""

import logging

from app.infrastructure.cache import cache
from app.infrastructure.hardware.display_service import set_next_actions
from app.repositories import (
    PortfolioRepository,
    SettingsRepository,
)

logger = logging.getLogger(__name__)


async def _get_portfolio_value_part(portfolio_repo, show_value: float) -> str:
    """Get portfolio value part of ticker text."""
    if show_value <= 0:
        return ""

    latest_snapshot = await portfolio_repo.get_latest()
    if not latest_snapshot:
        return ""

    total_value = latest_snapshot.total_value or 0
    return f"Portfolio EUR{int(total_value):,}"


async def _get_cash_balance_part(portfolio_repo, show_cash: float) -> str:
    """Get cash balance part of ticker text."""
    if show_cash <= 0:
        return ""

    latest_snapshot = await portfolio_repo.get_latest()
    if not latest_snapshot:
        return ""

    cash = latest_snapshot.cash_balance or 0
    return f"CASH EUR{int(cash):,}"


def _get_multi_step_recommendations(max_actions: int, show_amounts: float) -> list[str]:
    """Get recommendations from multi-step cache."""
    multi_step_data = None
    for depth in [5, 4, 3, 2, 1]:
        cache_key = f"multi_step_recommendations:diversification:{depth}:holistic"
        cached = cache.get(cache_key)
        if cached:
            multi_step_data = cached
            break

    if not multi_step_data or not multi_step_data.get("steps"):
        return []

    parts = []
    steps = multi_step_data["steps"][:max_actions]
    for step in steps:
        side = step.get("side", "").upper()
        symbol = step.get("symbol", "")
        symbol_short = symbol.split(".")[0]  # Remove .US/.EU suffix
        value = step.get("estimated_value", 0)

        if show_amounts > 0:
            parts.append(f"{side} {symbol_short} EUR{int(value)}")
        else:
            parts.append(f"{side} {symbol_short}")

    return parts


def _get_single_recommendations(max_actions: int, show_amounts: float) -> list[str]:
    """Get recommendations from single recommendation cache."""
    buy_recs = cache.get("recommendations:3")
    sell_recs = cache.get("sell_recommendations:3")

    parts = []
    action_count = 0

    if buy_recs and buy_recs.get("recommendations"):
        for rec in buy_recs["recommendations"][:max_actions]:
            if action_count >= max_actions:
                break
            symbol = rec.get("symbol", "")
            symbol_short = symbol.split(".")[0]
            amount = rec.get("amount", 0)
            if show_amounts > 0:
                parts.append(f"BUY {symbol_short} EUR{int(amount)}")
            else:
                parts.append(f"BUY {symbol_short}")
            action_count += 1

    if sell_recs and sell_recs.get("recommendations"):
        for rec in sell_recs["recommendations"][:max_actions]:
            if action_count >= max_actions:
                break
            symbol = rec.get("symbol", "")
            symbol_short = symbol.split(".")[0]
            value = rec.get("estimated_value", 0)
            if show_amounts > 0:
                parts.append(f"SELL {symbol_short} EUR{int(value)}")
            else:
                parts.append(f"SELL {symbol_short}")
            action_count += 1

    return parts


async def generate_ticker_text() -> str:
    """
    Generate ticker text from portfolio data and recommendations.

    Format: "Portfolio EUR12,345 | CASH EUR675 | BUY XIAO EUR855 | SELL ABC EUR200"
    """
    try:
        settings_repo = SettingsRepository()
        portfolio_repo = PortfolioRepository()

        show_value = await settings_repo.get_float("ticker_show_value", 1.0)
        show_cash = await settings_repo.get_float("ticker_show_cash", 1.0)
        show_actions = await settings_repo.get_float("ticker_show_actions", 1.0)
        show_amounts = await settings_repo.get_float("ticker_show_amounts", 1.0)
        max_actions = int(await settings_repo.get_float("ticker_max_actions", 3.0))

        parts = []

        value_part = await _get_portfolio_value_part(portfolio_repo, show_value)
        if value_part:
            parts.append(value_part)

        cash_part = await _get_cash_balance_part(portfolio_repo, show_cash)
        if cash_part:
            parts.append(cash_part)

        if show_actions > 0:
            action_parts = _get_multi_step_recommendations(max_actions, show_amounts)
            if not action_parts:
                action_parts = _get_single_recommendations(max_actions, show_amounts)
            parts.extend(action_parts)

        return " | ".join(parts) if parts else ""

    except Exception as e:
        logger.error(f"Failed to generate ticker text: {e}", exc_info=True)
        return ""


async def update_ticker_text():
    """Update the ticker text in the display service."""
    try:
        text = await generate_ticker_text()
        set_next_actions(text)

        if text:
            logger.debug(f"Ticker text updated: {text[:100]}...")
        else:
            logger.debug("Ticker text cleared (no data)")

    except Exception as e:
        logger.error(f"Failed to update ticker text: {e}", exc_info=True)
