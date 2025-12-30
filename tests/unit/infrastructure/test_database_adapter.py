"""Tests for database adapter.

These tests validate the DatabaseAdapter wrapper around aiosqlite connections,
ensuring proper execution of queries and result handling.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


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
        from app.infrastructure.database.adapter import DatabaseAdapter

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
    async def test_fetchone_returns_none_when_no_results(self, adapter, mock_connection):
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
    async def test_fetchall_returns_empty_list_when_no_results(self, adapter, mock_connection):
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
    async def test_rollback_rolls_back_transaction(self, adapter, mock_connection):
        """Test that rollback rolls back the transaction."""
        mock_connection.rollback = AsyncMock()

        await adapter.rollback()

        mock_connection.rollback.assert_called_once()

    @pytest.mark.asyncio
    async def test_executescript_runs_script(self, adapter, mock_connection):
        """Test that executescript runs a SQL script."""
        mock_connection.executescript = AsyncMock()

        script = "CREATE TABLE test (id INTEGER); INSERT INTO test VALUES (1);"
        await adapter.executescript(script)

        mock_connection.executescript.assert_called_once_with(script)

    @pytest.mark.asyncio
    async def test_close_closes_connection(self, adapter, mock_connection):
        """Test that close closes the connection."""
        mock_connection.close = AsyncMock()

        await adapter.close()

        mock_connection.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_context_manager_closes_on_exit(self, mock_connection):
        """Test that adapter can be used as context manager."""
        from app.infrastructure.database.adapter import DatabaseAdapter

        mock_connection.close = AsyncMock()

        async with DatabaseAdapter(mock_connection) as adapter:
            assert adapter is not None

        mock_connection.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_context_manager_closes_on_exception(self, mock_connection):
        """Test that adapter closes connection even on exception."""
        from app.infrastructure.database.adapter import DatabaseAdapter

        mock_connection.close = AsyncMock()

        with pytest.raises(ValueError):
            async with DatabaseAdapter(mock_connection) as adapter:
                raise ValueError("Test exception")

        mock_connection.close.assert_called_once()

