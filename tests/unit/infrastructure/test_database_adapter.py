"""Tests for database adapter.

These tests validate the DatabaseAdapter wrapper around aiosqlite connections,
ensuring proper execution of queries and result handling.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.repositories.base import DatabaseAdapter


class TestDatabaseAdapter:
    """Test DatabaseAdapter class."""

    @pytest.fixture
    def mock_connection(self):
        """Mock aiosqlite connection."""
        conn = AsyncMock()
        return conn

    @pytest.fixture
    def adapter(self, mock_connection):
        """Create DatabaseAdapter with mocked connection."""
        return DatabaseAdapter(mock_connection)

    @pytest.mark.asyncio
    async def test_execute_runs_query(self, adapter, mock_connection):
        """Test that execute runs a SQL query."""
        mock_connection.execute = AsyncMock()
        mock_connection.commit = AsyncMock()

        await adapter.execute("SELECT 1", ())

        mock_connection.execute.assert_called_once()
        mock_connection.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_with_parameters(self, adapter, mock_connection):
        """Test that execute passes parameters correctly."""
        mock_connection.execute = AsyncMock()
        mock_connection.commit = AsyncMock()

        params = ("value1", "value2")
        await adapter.execute("INSERT INTO test (col1, col2) VALUES (?, ?)", params)

        # Verify execute was called with query and params
        call_args = mock_connection.execute.call_args
        assert call_args is not None
        assert params in call_args[0] or params == call_args[0][1]

    @pytest.mark.asyncio
    async def test_fetchone_returns_single_row(self, adapter, mock_connection):
        """Test that fetchone returns a single row."""
        mock_row = MagicMock()
        mock_cursor = AsyncMock()
        mock_cursor.fetchone = AsyncMock(return_value=mock_row)
        mock_connection.execute = AsyncMock(return_value=mock_cursor)

        result = await adapter.fetchone("SELECT * FROM test WHERE id = ?", (1,))

        assert result == mock_row
        mock_cursor.fetchone.assert_called_once()

    @pytest.mark.asyncio
    async def test_fetchone_returns_none_when_no_results(
        self, adapter, mock_connection
    ):
        """Test that fetchone returns None when no results."""
        mock_cursor = AsyncMock()
        mock_cursor.fetchone = AsyncMock(return_value=None)
        mock_connection.execute = AsyncMock(return_value=mock_cursor)

        result = await adapter.fetchone("SELECT * FROM test WHERE id = ?", (999,))

        assert result is None

    @pytest.mark.asyncio
    async def test_fetchall_returns_all_rows(self, adapter, mock_connection):
        """Test that fetchall returns all rows."""
        mock_rows = [MagicMock(), MagicMock()]
        mock_cursor = AsyncMock()
        mock_cursor.fetchall = AsyncMock(return_value=mock_rows)
        mock_connection.execute = AsyncMock(return_value=mock_cursor)

        result = await adapter.fetchall("SELECT * FROM test")

        assert result == mock_rows
        assert len(result) == 2
        mock_cursor.fetchall.assert_called_once()

    @pytest.mark.asyncio
    async def test_fetchall_returns_empty_list_when_no_results(
        self, adapter, mock_connection
    ):
        """Test that fetchall returns empty list when no results."""
        mock_cursor = AsyncMock()
        mock_cursor.fetchall = AsyncMock(return_value=[])
        mock_connection.execute = AsyncMock(return_value=mock_cursor)

        result = await adapter.fetchall("SELECT * FROM test WHERE id = 999")

        assert result == []
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_commit_commits_transaction(self, adapter, mock_connection):
        """Test that commit commits the transaction."""
        mock_connection.commit = AsyncMock()

        await adapter.commit()

        mock_connection.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_transaction_context_manager(self, adapter, mock_connection):
        """Test that transaction context manager works correctly."""
        mock_connection.commit = AsyncMock()
        mock_connection.rollback = AsyncMock()

        async with adapter.transaction() as conn:
            assert conn == mock_connection

        mock_connection.commit.assert_called_once()
        mock_connection.rollback.assert_not_called()

    @pytest.mark.asyncio
    async def test_transaction_rolls_back_on_exception(self, adapter, mock_connection):
        """Test that transaction rolls back on exception."""
        mock_connection.commit = AsyncMock()
        mock_connection.rollback = AsyncMock()

        with pytest.raises(ValueError):
            async with adapter.transaction():
                raise ValueError("Test exception")

        mock_connection.commit.assert_not_called()
        mock_connection.rollback.assert_called_once()
