"""Market hours module for checking exchange trading hours.

This module provides functions to check if markets are open,
filter securities by open markets, and group securities by geography.
Uses the exchange_calendars library for accurate market hours
including holidays, early closes, and lunch breaks.
"""

import logging
from datetime import datetime
from functools import lru_cache
from typing import Any, Optional
from zoneinfo import ZoneInfo

import exchange_calendars as xcals
import pandas as pd

logger = logging.getLogger(__name__)

# Mapping of database fullExchangeName to exchange_calendars codes
# Maps Yahoo Finance exchange names (as stored in database) to exchange_calendars codes
EXCHANGE_NAME_TO_CODE = {
    "Amsterdam": "XAMS",
    "Athens": "ASEX",
    "Copenhagen": "XCSE",
    "HKSE": "XHKG",
    "LSE": "XLON",  # Direct match
    "Milan": "XMIL",
    "NasdaqCM": "XNAS",  # Use XNAS (same calendar as NasdaqGS)
    "NasdaqGS": "XNAS",
    "NYSE": "XNYS",  # Direct match
    "Paris": "XPAR",
    "Shenzhen": "XSHG",
    "XETRA": "XETR",
    # Legacy mappings for backwards compatibility
    "NASDAQ": "XNAS",
    "XETR": "XETR",
    "XHKG": "XHKG",
    "TSE": "XTSE",
    "ASX": "XASX",
}

# Cache of available exchange_calendars codes
_AVAILABLE_CALENDARS: Optional[set[str]] = None

# Exchanges that require strict market hours checks for all orders (both BUY and SELL)
# These markets do not accept orders when closed
# Can be extended in the future for Middle East or other markets with similar restrictions
# Include both canonical codes and aliases (some are valid calendar codes)
STRICT_MARKET_HOURS_EXCHANGE_CODES = {"XHKG", "XSHG", "XTSE", "XASX", "ASX", "TSE"}


def _get_available_calendars() -> set[str]:
    """Get set of all available exchange_calendars codes (cached)."""
    global _AVAILABLE_CALENDARS
    if _AVAILABLE_CALENDARS is None:
        _AVAILABLE_CALENDARS = set(xcals.get_calendar_names())
    return _AVAILABLE_CALENDARS


def validate_exchange_code(code: str) -> bool:
    """Check if an exchange code exists in exchange_calendars.

    Args:
        code: Exchange calendar code to validate

    Returns:
        True if code exists, False otherwise
    """
    return code in _get_available_calendars()


def _get_current_time() -> datetime:
    """Get current UTC time. Extracted for testing."""
    return datetime.now(ZoneInfo("UTC"))


async def get_exchanges_from_database() -> list[str]:
    """
    Get distinct exchange names from the securities table in the database.

    Returns:
        List of unique fullExchangeName values from active securities
    """
    try:
        from app.core.database import get_db_manager

        db_manager = get_db_manager()
        rows = await db_manager.config.fetchall(
            "SELECT DISTINCT fullExchangeName FROM securities "
            "WHERE fullExchangeName IS NOT NULL AND active = 1 "
            "ORDER BY fullExchangeName"
        )
        return [row["fullExchangeName"] for row in rows if row["fullExchangeName"]]
    except Exception as e:
        logger.warning(f"Failed to get exchanges from database: {e}")
        return []


def _get_exchange_code(full_exchange_name: str) -> str:
    """
    Get exchange_calendars code for a database exchange name.

    Args:
        full_exchange_name: Exchange name from database (e.g., "NYSE", "Athens", "XETRA")

    Returns:
        Exchange calendar code (defaults to "XNYS" if not found)
    """
    # First check if it's already a valid calendar code
    if validate_exchange_code(full_exchange_name):
        return full_exchange_name

    # Look up in mapping
    exchange_code = EXCHANGE_NAME_TO_CODE.get(full_exchange_name, "XNYS")

    # Validate the mapped code exists
    if not validate_exchange_code(exchange_code):
        logger.warning(
            f"Exchange code {exchange_code} for {full_exchange_name} not found in exchange_calendars. "
            f"Using default XNYS."
        )
        return "XNYS"

    return exchange_code


def requires_strict_market_hours(full_exchange_name: str) -> bool:
    """
    Check if an exchange requires strict market hours (all orders only when market is open).

    Args:
        full_exchange_name: Exchange name from database (e.g., "NYSE", "HKSE", "XETRA")

    Returns:
        True if the exchange requires strict market hours, False otherwise
    """
    exchange_code = _get_exchange_code(full_exchange_name)
    return exchange_code in STRICT_MARKET_HOURS_EXCHANGE_CODES


@lru_cache(maxsize=10)
def get_calendar(full_exchange_name: str) -> Any:
    """
    Get the exchange calendar for a fullExchangeName.

    Args:
        full_exchange_name: Exchange name from database (e.g., "NYSE", "Athens", "XETRA")

    Returns:
        Exchange calendar object
    """
    exchange_code = _get_exchange_code(full_exchange_name)
    return xcals.get_calendar(exchange_code)


def should_check_market_hours(full_exchange_name: str, side: str) -> bool:
    """
    Determine if market hours check is required for a trade.

    Rules:
    - SELL orders: Always check market hours (all markets)
    - BUY orders: Only check if exchange requires strict market hours

    Args:
        full_exchange_name: Exchange name from database (e.g., "NYSE", "HKSE", "XETRA")
        side: Trade side ("BUY" or "SELL")

    Returns:
        True if market hours check is required, False otherwise
    """
    side_upper = side.upper()
    if side_upper == "SELL":
        return True
    if side_upper == "BUY":
        return requires_strict_market_hours(full_exchange_name)
    # Unknown side, default to checking (safe default)
    return True


def is_market_open(full_exchange_name: str) -> bool:
    """
    Check if a market is currently open for trading.

    Accounts for:
    - Regular trading hours
    - Weekends
    - Holidays
    - Early closes
    - Lunch breaks (for Asian markets)

    Args:
        full_exchange_name: Exchange name from Yahoo Finance (e.g., "NASDAQ", "NYSE", "XETR")

    Returns:
        True if the market is currently open
    """
    try:
        calendar = get_calendar(full_exchange_name)
        now = _get_current_time()

        # Convert to pandas Timestamp in market timezone
        market_tz = calendar.tz
        now_market = pd.Timestamp(now).tz_convert(market_tz)
        today_str = now_market.strftime("%Y-%m-%d")

        # Check if today is a trading session
        if not calendar.is_session(today_str):
            return False

        # Get the schedule for today
        schedule = calendar.schedule.loc[today_str]
        open_time = schedule["open"]
        close_time = schedule["close"]

        # Check if we're within trading hours
        if not (open_time <= now_market <= close_time):
            return False

        # Check for lunch break (mainly for Asian markets)
        if "break_start" in schedule and pd.notna(schedule["break_start"]):
            break_start = schedule["break_start"]
            break_end = schedule["break_end"]
            if break_start <= now_market <= break_end:
                return False

        return True

    except Exception as e:
        logger.warning(f"Error checking market hours for {full_exchange_name}: {e}")
        # Default to closed on error
        return False


async def get_open_markets() -> list[str]:
    """
    Get list of currently open exchanges (only those where we have securities).

    Returns:
        List of exchange names that are currently open
    """
    exchanges = await get_exchanges_from_database()
    return [exch for exch in exchanges if is_market_open(exch)]


async def get_market_status() -> dict[str, dict[str, Any]]:
    """
    Get detailed status for all markets where we have securities.

    Returns:
        Dict mapping exchange name to status dict containing:
        - open: bool
        - exchange: str (exchange code)
        - timezone: str
        - closes_at: str (if open)
        - opens_at: str (if closed)
    """
    status = {}
    now = _get_current_time()

    # Get exchanges from database (only where we have securities)
    exchange_names = await get_exchanges_from_database()

    for exchange_name in exchange_names:
        try:
            calendar = get_calendar(exchange_name)
            exchange_code = _get_exchange_code(exchange_name)
            market_tz = calendar.tz
            # Get timezone from calendar object (no hardcoded dict needed)
            timezone_str = str(market_tz)

            now_market = pd.Timestamp(now).tz_convert(market_tz)
            today_str = now_market.strftime("%Y-%m-%d")

            is_open = is_market_open(exchange_name)

            market_info = {
                "open": is_open,
                "exchange": exchange_code,
                "timezone": timezone_str,
            }

            if is_open:
                # Get closing time for today
                schedule = calendar.schedule.loc[today_str]
                close_time = schedule["close"]
                market_info["closes_at"] = close_time.strftime("%H:%M")
            else:
                # Find next trading session
                try:
                    # Try to get next session
                    next_sessions = calendar.sessions_in_range(
                        today_str,
                        (pd.Timestamp(today_str) + pd.Timedelta(days=7)).strftime(
                            "%Y-%m-%d"
                        ),
                    )
                    if len(next_sessions) > 0:
                        # Check if today is a session but we're outside hours
                        if calendar.is_session(today_str):
                            schedule = calendar.schedule.loc[today_str]
                            if now_market < schedule["open"]:
                                # Market opens later today
                                market_info["opens_at"] = schedule["open"].strftime(
                                    "%H:%M"
                                )
                            else:
                                # Market closed for today, get next session
                                for session in next_sessions:
                                    if session.strftime("%Y-%m-%d") != today_str:
                                        next_schedule = calendar.schedule.loc[
                                            session.strftime("%Y-%m-%d")
                                        ]
                                        market_info["opens_at"] = next_schedule[
                                            "open"
                                        ].strftime("%H:%M")
                                        market_info["opens_date"] = session.strftime(
                                            "%Y-%m-%d"
                                        )
                                        break
                        else:
                            # Today is not a session, find next one
                            for session in next_sessions:
                                next_schedule = calendar.schedule.loc[
                                    session.strftime("%Y-%m-%d")
                                ]
                                market_info["opens_at"] = next_schedule[
                                    "open"
                                ].strftime("%H:%M")
                                market_info["opens_date"] = session.strftime("%Y-%m-%d")
                                break
                except Exception:
                    market_info["opens_at"] = "Unknown"

            status[exchange_name] = market_info

        except Exception as e:
            logger.warning(f"Error getting market status for {exchange_name}: {e}")
            exchange_code = _get_exchange_code(exchange_name)
            status[exchange_name] = {
                "open": False,
                "exchange": exchange_code,
                "timezone": "Unknown",
                "error": str(e),
            }

    return status


async def filter_stocks_by_open_markets(securities: list) -> list:
    """
    Filter securities to only those whose markets are currently open.

    Args:
        securities: List of security objects with 'fullExchangeName' attribute

    Returns:
        Filtered list of securities with open markets
    """
    open_markets = await get_open_markets()
    return [
        s for s in securities if getattr(s, "fullExchangeName", None) in open_markets
    ]


def group_stocks_by_exchange(securities: list) -> dict[str, list]:
    """
    Group securities by their exchange.

    Args:
        securities: List of security objects with 'fullExchangeName' attribute

    Returns:
        Dict mapping exchange name to list of securities
    """
    grouped: dict[str, list] = {}

    for security in securities:
        exchange = getattr(security, "fullExchangeName", None)
        if exchange:
            if exchange not in grouped:
                grouped[exchange] = []
            grouped[exchange].append(security)

    return grouped


async def format_market_status_for_display(has_recommendations: bool = False) -> str:
    """
    Format market status for LED display ticker.

    Args:
        has_recommendations: Whether there are pending recommendations

    Returns:
        Formatted string like "XNYS OPEN, XETR OPEN, NO PENDING OPPORTUNITIES"
        or "XNYS OPEN, XETR OPEN" (if recommendations exist)
        or "ALL MARKETS CLOSED"
    """
    try:
        market_status = await get_market_status()
        open_markets = []

        for exchange_name, status in market_status.items():
            if status.get("open", False):
                exchange_code = status.get("exchange", "")
                if exchange_code:
                    open_markets.append(exchange_code)

        if open_markets:
            # Format: "XNYS OPEN, XETR OPEN"
            market_text = ", ".join(f"{code} OPEN" for code in sorted(open_markets))
            if not has_recommendations:
                return f"{market_text}, NO PENDING OPPORTUNITIES"
            else:
                return market_text
        else:
            if not has_recommendations:
                return "ALL MARKETS CLOSED, NO PENDING OPPORTUNITIES"
            else:
                return "ALL MARKETS CLOSED"
    except Exception as e:
        logger.warning(f"Failed to format market status: {e}")
        return "ALL MARKETS CLOSED"
