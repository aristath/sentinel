"""Logging context utilities for correlation IDs and structured logging."""

import logging
import uuid
from contextvars import ContextVar
from typing import Optional

# Context variable for correlation ID (thread-safe for async)
_correlation_id: ContextVar[Optional[str]] = ContextVar("correlation_id", default=None)


def get_correlation_id() -> Optional[str]:
    """Get the current correlation ID."""
    return _correlation_id.get()


def set_correlation_id(cid: Optional[str] = None) -> str:
    """
    Set a correlation ID for the current context.

    Args:
        cid: Optional correlation ID. If None, generates a new UUID.

    Returns:
        The correlation ID (newly generated or provided)
    """
    if cid is None:
        cid = str(uuid.uuid4())
    _correlation_id.set(cid)
    return cid


def clear_correlation_id():
    """Clear the current correlation ID."""
    _correlation_id.set(None)


class CorrelationIDFilter(logging.Filter):
    """Logging filter that adds correlation ID to log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        """Add correlation_id to log record if available."""
        record.correlation_id = get_correlation_id() or "none"
        return True


def setup_correlation_logging():
    """Set up correlation ID logging for the root logger."""
    root_logger = logging.getLogger()
    if not any(isinstance(f, CorrelationIDFilter) for f in root_logger.filters):
        root_logger.addFilter(CorrelationIDFilter())


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger with correlation ID support.

    Args:
        name: Logger name (typically __name__)

    Returns:
        Logger instance
    """
    setup_correlation_logging()
    return logging.getLogger(name)
