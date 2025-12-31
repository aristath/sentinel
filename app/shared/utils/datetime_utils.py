"""Datetime parsing utilities."""

import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


def safe_parse_datetime_string(date_str: Optional[str]) -> Optional[datetime]:
    """
    Safely parse a datetime from an ISO format string.

    Args:
        date_str: ISO format datetime string (may include timezone)

    Returns:
        Parsed datetime (timezone removed) or None if invalid/missing
    """
    if not date_str:
        return None

    try:
        # Handle timezone suffix (replace Z with +00:00 for fromisoformat)
        normalized = date_str.replace("Z", "+00:00")
        date = datetime.fromisoformat(normalized)
        # Remove timezone info for consistency
        if date.tzinfo:
            date = date.replace(tzinfo=None)
        return date
    except (ValueError, TypeError) as e:
        logger.debug(f"Failed to parse datetime string '{date_str}': {e}")
        return None
