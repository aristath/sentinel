"""Tests for logging context infrastructure.

These tests validate correlation ID functionality for structured logging.
"""

import logging

from app.core.logging import (
    CorrelationIDFilter,
    clear_correlation_id,
    get_correlation_id,
    get_logger,
    set_correlation_id,
    setup_correlation_logging,
)


class TestCorrelationID:
    """Test correlation ID functions."""

    def test_get_correlation_id_returns_none_initially(self):
        """Test that get_correlation_id returns None initially."""
        clear_correlation_id()
        assert get_correlation_id() is None

    def test_set_correlation_id_generates_uuid_when_none(self):
        """Test that set_correlation_id generates UUID when None provided."""
        clear_correlation_id()
        cid = set_correlation_id()
        assert cid is not None
        assert isinstance(cid, str)
        assert len(cid) > 0

    def test_set_correlation_id_uses_provided_value(self):
        """Test that set_correlation_id uses provided value."""
        clear_correlation_id()
        cid = set_correlation_id("test-correlation-id")
        assert cid == "test-correlation-id"
        assert get_correlation_id() == "test-correlation-id"

    def test_clear_correlation_id_removes_id(self):
        """Test that clear_correlation_id removes the correlation ID."""
        set_correlation_id("test-id")
        assert get_correlation_id() == "test-id"

        clear_correlation_id()
        assert get_correlation_id() is None

    def test_multiple_sets_overwrite_previous(self):
        """Test that setting correlation ID multiple times overwrites previous."""
        set_correlation_id("first-id")
        assert get_correlation_id() == "first-id"

        set_correlation_id("second-id")
        assert get_correlation_id() == "second-id"


class TestCorrelationIDFilter:
    """Test CorrelationIDFilter class."""

    def test_filter_adds_correlation_id_to_record(self):
        """Test that filter adds correlation_id to log record."""
        filter_obj = CorrelationIDFilter()

        # Set a correlation ID
        set_correlation_id("test-cid")

        # Create a mock log record
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        # Filter should add correlation_id
        result = filter_obj.filter(record)
        assert result is True
        assert hasattr(record, "correlation_id")
        assert record.correlation_id == "test-cid"

    def test_filter_uses_none_when_no_correlation_id(self):
        """Test that filter uses 'none' when no correlation ID is set."""
        filter_obj = CorrelationIDFilter()
        clear_correlation_id()

        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        result = filter_obj.filter(record)
        assert result is True
        assert record.correlation_id == "none"


class TestSetupCorrelationLogging:
    """Test setup_correlation_logging function."""

    def test_setup_adds_filter_to_root_logger(self):
        """Test that setup_correlation_logging adds filter to root logger."""
        root_logger = logging.getLogger()

        # Remove any existing CorrelationIDFilter
        root_logger.filters = [
            f for f in root_logger.filters if not isinstance(f, CorrelationIDFilter)
        ]

        setup_correlation_logging()

        # Check that filter was added
        assert any(isinstance(f, CorrelationIDFilter) for f in root_logger.filters)

    def test_setup_idempotent(self):
        """Test that setup_correlation_logging is idempotent."""
        root_logger = logging.getLogger()

        # Remove any existing CorrelationIDFilter
        root_logger.filters = [
            f for f in root_logger.filters if not isinstance(f, CorrelationIDFilter)
        ]

        setup_correlation_logging()
        filter_count_1 = sum(
            1 for f in root_logger.filters if isinstance(f, CorrelationIDFilter)
        )

        setup_correlation_logging()
        filter_count_2 = sum(
            1 for f in root_logger.filters if isinstance(f, CorrelationIDFilter)
        )

        # Should still have only one filter
        assert filter_count_1 == filter_count_2 == 1


class TestGetLogger:
    """Test get_logger function."""

    def test_get_logger_returns_logger(self):
        """Test that get_logger returns a logger instance."""
        logger = get_logger("test.logger")
        assert isinstance(logger, logging.Logger)
        assert logger.name == "test.logger"

    def test_get_logger_sets_up_correlation_logging(self):
        """Test that get_logger sets up correlation logging."""
        root_logger = logging.getLogger()

        # Remove any existing CorrelationIDFilter
        root_logger.filters = [
            f for f in root_logger.filters if not isinstance(f, CorrelationIDFilter)
        ]

        get_logger("test.logger")

        # Check that filter was added
        assert any(isinstance(f, CorrelationIDFilter) for f in root_logger.filters)
