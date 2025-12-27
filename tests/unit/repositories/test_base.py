"""Tests for base repository utilities.

These tests validate the common database utility functions.
"""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.repositories.base import (
    DatabaseAdapter,
    safe_get,
    safe_get_bool,
    safe_get_datetime,
    safe_get_float,
    safe_get_int,
    transaction_context,
)


class TestSafeGet:
    """Test safe_get function."""

    def test_gets_value_from_dict(self):
        """Test getting value from a dict."""
        row = {"name": "test", "value": 123}
        assert safe_get(row, "name") == "test"
        assert safe_get(row, "value") == 123

    def test_returns_default_when_key_missing(self):
        """Test returning default when key is missing."""
        row = {"name": "test"}
        assert safe_get(row, "missing") is None
        assert safe_get(row, "missing", "default") == "default"

    def test_handles_row_with_keys_method(self):
        """Test handling row with keys() method."""
        mock_row = MagicMock()
        mock_row.keys.return_value = ["name", "value"]
        mock_row.__getitem__.side_effect = lambda k: {"name": "test", "value": 123}[k]

        assert safe_get(mock_row, "name") == "test"

    def test_handles_row_without_keys_but_with_getitem(self):
        """Test handling row without keys() but with __getitem__."""
        mock_row = MagicMock(spec=["__getitem__"])
        mock_row.__getitem__.return_value = "value"

        assert safe_get(mock_row, "key") == "value"

    def test_returns_default_for_non_subscriptable(self):
        """Test returning default for non-subscriptable objects."""

        class NoGetItem:
            pass

        obj = NoGetItem()
        assert safe_get(obj, "key", "default") == "default"

    def test_handles_keyerror(self):
        """Test handling KeyError."""
        row = {}
        assert safe_get(row, "missing") is None

    def test_handles_indexerror(self):
        """Test handling IndexError."""
        row = []
        assert safe_get(row, 0, "default") == "default"


class TestTransactionContext:
    """Test transaction_context function."""

    @pytest.mark.asyncio
    async def test_uses_transaction_method_if_available(self):
        """Test using transaction method when available."""
        mock_conn = MagicMock()

        # Create a proper async context manager mock
        class MockTransactionCM:
            async def __aenter__(self):
                return mock_conn

            async def __aexit__(self, exc_type, exc_val, exc_tb):
                return False

        mock_db = MagicMock()
        mock_db.transaction.return_value = MockTransactionCM()

        async with transaction_context(mock_db) as conn:
            assert conn == mock_conn

    @pytest.mark.asyncio
    async def test_uses_raw_connection_when_no_transaction_method(self):
        """Test using raw connection when no transaction method."""
        mock_conn = AsyncMock()
        del mock_conn.transaction  # Remove transaction method

        async with transaction_context(mock_conn) as conn:
            assert conn == mock_conn

        mock_conn.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_rollback_on_exception_for_raw_connection(self):
        """Test rollback on exception for raw connection."""
        mock_conn = AsyncMock()
        del mock_conn.transaction

        with pytest.raises(ValueError):
            async with transaction_context(mock_conn):
                raise ValueError("test error")

        mock_conn.rollback.assert_called_once()


class TestSafeGetDatetime:
    """Test safe_get_datetime function."""

    def test_returns_none_for_missing_key(self):
        """Test returning None when key is missing."""
        row = {}
        assert safe_get_datetime(row, "date") is None

    def test_returns_datetime_directly(self):
        """Test returning datetime directly when already datetime."""
        now = datetime.now()
        row = {"date": now}
        assert safe_get_datetime(row, "date") == now

    def test_parses_iso_format_string(self):
        """Test parsing ISO format string."""
        row = {"date": "2024-01-15T10:30:00"}
        result = safe_get_datetime(row, "date")

        assert result.year == 2024
        assert result.month == 1
        assert result.day == 15

    def test_returns_none_for_invalid_string(self):
        """Test returning None for invalid datetime string."""
        row = {"date": "not a date"}
        assert safe_get_datetime(row, "date") is None

    def test_returns_none_for_empty_value(self):
        """Test returning None for empty value."""
        row = {"date": ""}
        assert safe_get_datetime(row, "date") is None

    def test_returns_none_for_none_value(self):
        """Test returning None for None value."""
        row = {"date": None}
        assert safe_get_datetime(row, "date") is None


class TestSafeGetBool:
    """Test safe_get_bool function."""

    def test_returns_bool_directly(self):
        """Test returning bool directly."""
        row = {"flag": True}
        assert safe_get_bool(row, "flag") is True

        row = {"flag": False}
        assert safe_get_bool(row, "flag") is False

    def test_converts_int_to_bool(self):
        """Test converting integer to bool."""
        row = {"flag": 1}
        assert safe_get_bool(row, "flag") is True

        row = {"flag": 0}
        assert safe_get_bool(row, "flag") is False

    def test_converts_string_to_bool(self):
        """Test converting string to bool."""
        for true_val in ["true", "TRUE", "1", "yes", "on"]:
            row = {"flag": true_val}
            assert safe_get_bool(row, "flag") is True

        row = {"flag": "false"}
        assert safe_get_bool(row, "flag") is False

    def test_returns_default_for_missing_key(self):
        """Test returning default for missing key."""
        row = {}
        assert safe_get_bool(row, "missing") is False
        assert safe_get_bool(row, "missing", True) is True

    def test_handles_none_value(self):
        """Test handling None value."""
        row = {"flag": None}
        assert safe_get_bool(row, "flag", True) is True


class TestSafeGetFloat:
    """Test safe_get_float function."""

    def test_returns_float_directly(self):
        """Test returning float directly."""
        row = {"value": 3.14}
        assert safe_get_float(row, "value") == 3.14

    def test_converts_int_to_float(self):
        """Test converting integer to float."""
        row = {"value": 42}
        assert safe_get_float(row, "value") == 42.0

    def test_converts_string_to_float(self):
        """Test converting string to float."""
        row = {"value": "3.14"}
        assert safe_get_float(row, "value") == 3.14

    def test_returns_default_for_invalid_string(self):
        """Test returning default for invalid string."""
        row = {"value": "not a number"}
        assert safe_get_float(row, "value", 0.0) == 0.0

    def test_returns_default_for_missing_key(self):
        """Test returning default for missing key."""
        row = {}
        assert safe_get_float(row, "missing") is None
        assert safe_get_float(row, "missing", 0.0) == 0.0

    def test_returns_default_for_none_value(self):
        """Test returning default for None value."""
        row = {"value": None}
        assert safe_get_float(row, "value", 1.0) == 1.0


class TestSafeGetInt:
    """Test safe_get_int function."""

    def test_returns_int_directly(self):
        """Test returning int directly."""
        row = {"value": 42}
        assert safe_get_int(row, "value") == 42

    def test_converts_float_to_int(self):
        """Test converting float to int."""
        row = {"value": 42.9}
        assert safe_get_int(row, "value") == 42

    def test_converts_string_to_int(self):
        """Test converting string to int."""
        row = {"value": "42"}
        assert safe_get_int(row, "value") == 42

    def test_converts_float_string_to_int(self):
        """Test converting float string to int."""
        row = {"value": "42.9"}
        assert safe_get_int(row, "value") == 42

    def test_returns_default_for_invalid_string(self):
        """Test returning default for invalid string."""
        row = {"value": "not a number"}
        assert safe_get_int(row, "value", 0) == 0

    def test_returns_default_for_missing_key(self):
        """Test returning default for missing key."""
        row = {}
        assert safe_get_int(row, "missing") is None
        assert safe_get_int(row, "missing", 0) == 0

    def test_returns_default_for_none_value(self):
        """Test returning default for None value."""
        row = {"value": None}
        assert safe_get_int(row, "value", 1) == 1


class TestDatabaseAdapter:
    """Test DatabaseAdapter class."""

    @pytest.mark.asyncio
    async def test_fetchone_executes_and_returns(self):
        """Test fetchone executes SQL and returns result."""
        mock_conn = AsyncMock()
        mock_cursor = AsyncMock()
        mock_cursor.fetchone.return_value = {"id": 1}
        mock_conn.execute.return_value = mock_cursor

        adapter = DatabaseAdapter(mock_conn)
        result = await adapter.fetchone("SELECT * FROM test WHERE id = ?", (1,))

        assert result == {"id": 1}
        mock_conn.execute.assert_called_with("SELECT * FROM test WHERE id = ?", (1,))

    @pytest.mark.asyncio
    async def test_fetchall_executes_and_returns(self):
        """Test fetchall executes SQL and returns all results."""
        mock_conn = AsyncMock()
        mock_cursor = AsyncMock()
        mock_cursor.fetchall.return_value = [{"id": 1}, {"id": 2}]
        mock_conn.execute.return_value = mock_cursor

        adapter = DatabaseAdapter(mock_conn)
        result = await adapter.fetchall("SELECT * FROM test")

        assert result == [{"id": 1}, {"id": 2}]

    @pytest.mark.asyncio
    async def test_execute_runs_sql(self):
        """Test execute runs SQL statement."""
        mock_conn = AsyncMock()

        adapter = DatabaseAdapter(mock_conn)
        await adapter.execute("INSERT INTO test VALUES (?)", (1,))

        mock_conn.execute.assert_called_with("INSERT INTO test VALUES (?)", (1,))

    @pytest.mark.asyncio
    async def test_commit_commits_connection(self):
        """Test commit commits the connection."""
        mock_conn = AsyncMock()

        adapter = DatabaseAdapter(mock_conn)
        await adapter.commit()

        mock_conn.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_transaction_yields_connection_and_commits(self):
        """Test transaction yields connection and commits on success."""
        mock_conn = AsyncMock()

        adapter = DatabaseAdapter(mock_conn)

        async with adapter.transaction() as conn:
            assert conn == mock_conn

        mock_conn.commit.assert_called()

    @pytest.mark.asyncio
    async def test_transaction_rollback_on_exception(self):
        """Test transaction rollback on exception."""
        mock_conn = AsyncMock()

        adapter = DatabaseAdapter(mock_conn)

        with pytest.raises(ValueError):
            async with adapter.transaction():
                raise ValueError("test error")

        mock_conn.rollback.assert_called_once()
