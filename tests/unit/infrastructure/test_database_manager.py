"""Tests for database manager.

These tests validate the centralized database management system.
"""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestDatabaseInit:
    """Test Database class initialization."""

    def test_init_sets_path(self):
        """Test that path is set correctly."""
        from app.core.database.manager import Database

        path = Path("/tmp/test.db")
        db = Database(path)

        assert db.path == path
        assert db.readonly is False

    def test_init_readonly(self):
        """Test readonly mode initialization."""
        from app.core.database.manager import Database

        path = Path("/tmp/test.db")
        db = Database(path, readonly=True)

        assert db.readonly is True

    def test_name_property(self):
        """Test name property returns stem."""
        from app.core.database.manager import Database

        db = Database(Path("/tmp/mydb.db"))
        assert db.name == "mydb"


class TestDatabaseConnect:
    """Test database connection."""

    @pytest.mark.asyncio
    async def test_connect_creates_directory(self):
        """Test that connect creates parent directory."""
        from app.core.database.manager import Database

        with patch("app.core.database.manager.aiosqlite") as mock_aiosqlite:
            mock_conn = AsyncMock()
            mock_aiosqlite.connect = AsyncMock(return_value=mock_conn)
            mock_aiosqlite.Row = object

            path = Path("/tmp/subdir/test.db")
            with patch.object(Path, "mkdir") as mock_mkdir:
                db = Database(path)
                await db.connect()

                mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)

    @pytest.mark.asyncio
    async def test_connect_readonly_uses_uri(self):
        """Test readonly connection uses URI mode."""
        from app.core.database.manager import Database

        with patch("app.core.database.manager.aiosqlite") as mock_aiosqlite:
            mock_conn = AsyncMock()
            mock_aiosqlite.connect = AsyncMock(return_value=mock_conn)
            mock_aiosqlite.Row = object

            path = Path("/tmp/test.db")
            db = Database(path, readonly=True)

            with patch.object(Path, "mkdir"):
                await db.connect()

            mock_aiosqlite.connect.assert_called_once_with(
                f"file:{path}?mode=ro", uri=True
            )

    @pytest.mark.asyncio
    async def test_connect_configures_pragmas(self):
        """Test that connection configures SQLite pragmas."""
        from app.core.database.manager import Database

        with patch("app.core.database.manager.aiosqlite") as mock_aiosqlite:
            mock_conn = AsyncMock()
            mock_conn.execute = AsyncMock()
            mock_aiosqlite.connect = AsyncMock(return_value=mock_conn)
            mock_aiosqlite.Row = object

            path = Path("/tmp/test.db")
            db = Database(path)

            with patch.object(Path, "mkdir"):
                await db.connect()

            # Check that key pragmas were set
            execute_calls = [str(c) for c in mock_conn.execute.call_args_list]
            assert any("journal_mode=WAL" in str(c) for c in execute_calls)
            assert any("busy_timeout=60000" in str(c) for c in execute_calls)

    @pytest.mark.asyncio
    async def test_connect_returns_same_connection(self):
        """Test that connect returns cached connection."""
        from app.core.database.manager import Database

        with patch("app.core.database.manager.aiosqlite") as mock_aiosqlite:
            mock_conn = AsyncMock()
            mock_aiosqlite.connect = AsyncMock(return_value=mock_conn)
            mock_aiosqlite.Row = object

            path = Path("/tmp/test.db")
            db = Database(path)

            with patch.object(Path, "mkdir"):
                conn1 = await db.connect()
                conn2 = await db.connect()

            assert conn1 is conn2
            # Should only connect once
            assert mock_aiosqlite.connect.call_count == 1


class TestDatabaseClose:
    """Test database close operations."""

    @pytest.mark.asyncio
    async def test_close_closes_connection(self):
        """Test that close closes the connection."""
        from app.core.database.manager import Database

        with patch("app.core.database.manager.aiosqlite") as mock_aiosqlite:
            mock_conn = AsyncMock()
            mock_aiosqlite.connect = AsyncMock(return_value=mock_conn)
            mock_aiosqlite.Row = object

            db = Database(Path("/tmp/test.db"))

            with patch.object(Path, "mkdir"):
                await db.connect()
                await db.close()

            mock_conn.close.assert_called_once()
            assert db._connection is None

    @pytest.mark.asyncio
    async def test_close_when_not_connected(self):
        """Test close when not connected does nothing."""
        from app.core.database.manager import Database

        db = Database(Path("/tmp/test.db"))
        # Should not raise
        await db.close()
        assert db._connection is None


class TestDatabaseTransaction:
    """Test transaction context manager."""

    @pytest.mark.asyncio
    async def test_transaction_commits_on_success(self):
        """Test that transaction commits on success."""
        from app.core.database.manager import Database

        with patch("app.core.database.manager.aiosqlite") as mock_aiosqlite:
            mock_conn = AsyncMock()
            mock_aiosqlite.connect = AsyncMock(return_value=mock_conn)
            mock_aiosqlite.Row = object

            db = Database(Path("/tmp/test.db"))

            with patch.object(Path, "mkdir"):
                async with db.transaction() as conn:
                    await conn.execute("INSERT INTO test VALUES (1)")

            mock_conn.commit.assert_called_once()
            mock_conn.rollback.assert_not_called()

    @pytest.mark.asyncio
    async def test_transaction_rollback_on_error(self):
        """Test that transaction rolls back on error."""
        from app.core.database.manager import Database

        with patch("app.core.database.manager.aiosqlite") as mock_aiosqlite:
            mock_conn = AsyncMock()
            mock_aiosqlite.connect = AsyncMock(return_value=mock_conn)
            mock_aiosqlite.Row = object

            db = Database(Path("/tmp/test.db"))

            with patch.object(Path, "mkdir"):
                with pytest.raises(ValueError):
                    async with db.transaction():
                        raise ValueError("test error")

            mock_conn.rollback.assert_called_once()


class TestDatabaseOperations:
    """Test database SQL operations."""

    @pytest.mark.asyncio
    async def test_execute(self):
        """Test execute method."""
        from app.core.database.manager import Database

        with patch("app.core.database.manager.aiosqlite") as mock_aiosqlite:
            mock_cursor = AsyncMock()
            mock_conn = AsyncMock()
            mock_conn.execute = AsyncMock(return_value=mock_cursor)
            mock_aiosqlite.connect = AsyncMock(return_value=mock_conn)
            mock_aiosqlite.Row = object

            db = Database(Path("/tmp/test.db"))

            with patch.object(Path, "mkdir"):
                result = await db.execute("SELECT 1", ())

            assert result == mock_cursor

    @pytest.mark.asyncio
    async def test_executemany(self):
        """Test executemany method."""
        from app.core.database.manager import Database

        with patch("app.core.database.manager.aiosqlite") as mock_aiosqlite:
            mock_cursor = AsyncMock()
            mock_conn = AsyncMock()
            mock_conn.executemany = AsyncMock(return_value=mock_cursor)
            mock_aiosqlite.connect = AsyncMock(return_value=mock_conn)
            mock_aiosqlite.Row = object

            db = Database(Path("/tmp/test.db"))

            with patch.object(Path, "mkdir"):
                await db.executemany("INSERT INTO t VALUES (?)", [(1,), (2,)])

            mock_conn.executemany.assert_called_once()

    @pytest.mark.asyncio
    async def test_executescript(self):
        """Test executescript method."""
        from app.core.database.manager import Database

        with patch("app.core.database.manager.aiosqlite") as mock_aiosqlite:
            mock_conn = AsyncMock()
            mock_aiosqlite.connect = AsyncMock(return_value=mock_conn)
            mock_aiosqlite.Row = object

            db = Database(Path("/tmp/test.db"))

            with patch.object(Path, "mkdir"):
                await db.executescript("CREATE TABLE t(id); CREATE TABLE t2(id);")

            mock_conn.executescript.assert_called_once()

    @pytest.mark.asyncio
    async def test_commit(self):
        """Test commit method."""
        from app.core.database.manager import Database

        with patch("app.core.database.manager.aiosqlite") as mock_aiosqlite:
            mock_conn = AsyncMock()
            mock_aiosqlite.connect = AsyncMock(return_value=mock_conn)
            mock_aiosqlite.Row = object

            db = Database(Path("/tmp/test.db"))

            with patch.object(Path, "mkdir"):
                await db.commit()

            mock_conn.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_fetchone(self):
        """Test fetchone method."""
        from app.core.database.manager import Database

        with patch("app.core.database.manager.aiosqlite") as mock_aiosqlite:
            mock_row = {"id": 1}
            mock_cursor = AsyncMock()
            mock_cursor.fetchone = AsyncMock(return_value=mock_row)
            mock_conn = AsyncMock()
            mock_conn.execute = AsyncMock(return_value=mock_cursor)
            mock_aiosqlite.connect = AsyncMock(return_value=mock_conn)
            mock_aiosqlite.Row = object

            db = Database(Path("/tmp/test.db"))

            with patch.object(Path, "mkdir"):
                result = await db.fetchone("SELECT * FROM t WHERE id=?", (1,))

            assert result == mock_row

    @pytest.mark.asyncio
    async def test_fetchall(self):
        """Test fetchall method."""
        from app.core.database.manager import Database

        with patch("app.core.database.manager.aiosqlite") as mock_aiosqlite:
            mock_rows = [{"id": 1}, {"id": 2}]
            mock_cursor = AsyncMock()
            mock_cursor.fetchall = AsyncMock(return_value=mock_rows)
            mock_conn = AsyncMock()
            mock_conn.execute = AsyncMock(return_value=mock_cursor)
            mock_aiosqlite.connect = AsyncMock(return_value=mock_conn)
            mock_aiosqlite.Row = object

            db = Database(Path("/tmp/test.db"))

            with patch.object(Path, "mkdir"):
                result = await db.fetchall("SELECT * FROM t")

            assert result == mock_rows

    @pytest.mark.asyncio
    async def test_integrity_check(self):
        """Test integrity_check method."""
        from app.core.database.manager import Database

        with patch("app.core.database.manager.aiosqlite") as mock_aiosqlite:
            mock_cursor = AsyncMock()
            mock_cursor.fetchone = AsyncMock(return_value=["ok"])
            mock_conn = AsyncMock()
            mock_conn.execute = AsyncMock(return_value=mock_cursor)
            mock_aiosqlite.connect = AsyncMock(return_value=mock_conn)
            mock_aiosqlite.Row = object

            db = Database(Path("/tmp/test.db"))

            with patch.object(Path, "mkdir"):
                result = await db.integrity_check()

            assert result == "ok"

    @pytest.mark.asyncio
    async def test_integrity_check_no_result(self):
        """Test integrity_check when no result."""
        from app.core.database.manager import Database

        with patch("app.core.database.manager.aiosqlite") as mock_aiosqlite:
            mock_cursor = AsyncMock()
            mock_cursor.fetchone = AsyncMock(return_value=None)
            mock_conn = AsyncMock()
            mock_conn.execute = AsyncMock(return_value=mock_cursor)
            mock_aiosqlite.connect = AsyncMock(return_value=mock_conn)
            mock_aiosqlite.Row = object

            db = Database(Path("/tmp/test.db"))

            with patch.object(Path, "mkdir"):
                result = await db.integrity_check()

            assert result == "unknown"

    @pytest.mark.asyncio
    async def test_checkpoint(self):
        """Test checkpoint method."""
        from app.core.database.manager import Database

        with patch("app.core.database.manager.aiosqlite") as mock_aiosqlite:
            mock_conn = AsyncMock()
            mock_aiosqlite.connect = AsyncMock(return_value=mock_conn)
            mock_aiosqlite.Row = object

            db = Database(Path("/tmp/test.db"))

            with patch.object(Path, "mkdir"):
                await db.checkpoint()

            assert any(
                "wal_checkpoint" in str(c) for c in mock_conn.execute.call_args_list
            )


class TestDatabaseManager:
    """Test DatabaseManager class."""

    def test_init_creates_databases(self):
        """Test that init creates all database instances."""
        from app.core.database.manager import DatabaseManager

        data_dir = Path("/tmp/test_data")
        manager = DatabaseManager(data_dir)

        assert manager.config.path == data_dir / "config.db"
        assert manager.ledger.path == data_dir / "ledger.db"
        assert manager.state.path == data_dir / "state.db"
        assert manager.cache.path == data_dir / "cache.db"
        assert manager.calculations.path == data_dir / "calculations.db"
        assert manager.history_dir == data_dir / "history"


class TestDatabaseManagerHistory:
    """Test per-symbol history database access."""

    @pytest.mark.asyncio
    async def test_history_creates_database(self):
        """Test that history creates per-symbol database."""
        from app.core.database.manager import DatabaseManager

        data_dir = Path("/tmp/test_data")
        manager = DatabaseManager(data_dir)

        with (
            patch.object(Path, "mkdir"),
            patch(
                "app.modules.portfolio.database.schemas.init_history_schema",
                new_callable=AsyncMock,
            ),
        ):
            db = await manager.history("AAPL.US")

        assert db.path == data_dir / "history" / "AAPL_US.db"

    @pytest.mark.asyncio
    async def test_history_caches_database(self):
        """Test that history returns cached database."""
        from app.core.database.manager import DatabaseManager

        data_dir = Path("/tmp/test_data")
        manager = DatabaseManager(data_dir)

        with (
            patch.object(Path, "mkdir"),
            patch(
                "app.modules.portfolio.database.schemas.init_history_schema",
                new_callable=AsyncMock,
            ) as mock_init,
        ):
            db1 = await manager.history("AAPL.US")
            db2 = await manager.history("AAPL.US")

        assert db1 is db2
        # Should only initialize once
        assert mock_init.call_count == 1

    @pytest.mark.asyncio
    async def test_history_sanitizes_symbol(self):
        """Test that history sanitizes symbol for filename."""
        from app.core.database.manager import DatabaseManager

        data_dir = Path("/tmp/test_data")
        manager = DatabaseManager(data_dir)

        with (
            patch.object(Path, "mkdir"),
            patch(
                "app.modules.portfolio.database.schemas.init_history_schema",
                new_callable=AsyncMock,
            ),
        ):
            db = await manager.history("NOVO-B.CO")

        assert db.path == data_dir / "history" / "NOVO_B_CO.db"


class TestDatabaseManagerCloseAll:
    """Test closing all databases."""

    @pytest.mark.asyncio
    async def test_close_all_closes_core_databases(self):
        """Test that close_all closes all core databases."""
        from app.core.database.manager import DatabaseManager

        data_dir = Path("/tmp/test_data")
        manager = DatabaseManager(data_dir)

        # Mock the close methods
        manager.config.close = AsyncMock()
        manager.ledger.close = AsyncMock()
        manager.state.close = AsyncMock()
        manager.cache.close = AsyncMock()
        manager.calculations.close = AsyncMock()

        await manager.close_all()

        manager.config.close.assert_called_once()
        manager.ledger.close.assert_called_once()
        manager.state.close.assert_called_once()
        manager.cache.close.assert_called_once()
        manager.calculations.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_all_closes_history_databases(self):
        """Test that close_all closes history databases."""
        from app.core.database.manager import DatabaseManager

        data_dir = Path("/tmp/test_data")
        manager = DatabaseManager(data_dir)

        # Create mock history database
        mock_history_db = AsyncMock()
        manager._history["AAPL.US"] = mock_history_db

        # Mock core database closes
        manager.config.close = AsyncMock()
        manager.ledger.close = AsyncMock()
        manager.state.close = AsyncMock()
        manager.cache.close = AsyncMock()
        manager.calculations.close = AsyncMock()

        await manager.close_all()

        mock_history_db.close.assert_called_once()


class TestDatabaseManagerIntegrityCheck:
    """Test integrity check on all databases."""

    @pytest.mark.asyncio
    async def test_integrity_check_all(self):
        """Test that integrity_check_all checks all databases."""
        from app.core.database.manager import DatabaseManager

        data_dir = Path("/tmp/test_data")
        manager = DatabaseManager(data_dir)

        # Mock integrity checks
        manager.config.integrity_check = AsyncMock(return_value="ok")
        manager.ledger.integrity_check = AsyncMock(return_value="ok")
        manager.state.integrity_check = AsyncMock(return_value="ok")
        manager.cache.integrity_check = AsyncMock(return_value="ok")
        manager.calculations.integrity_check = AsyncMock(return_value="ok")

        results = await manager.integrity_check_all()

        assert results["config"] == "ok"
        assert results["ledger"] == "ok"
        assert results["state"] == "ok"
        assert results["cache"] == "ok"
        assert results["calculations"] == "ok"

    @pytest.mark.asyncio
    async def test_integrity_check_handles_errors(self):
        """Test that integrity_check_all handles errors."""
        from app.core.database.manager import DatabaseManager

        data_dir = Path("/tmp/test_data")
        manager = DatabaseManager(data_dir)

        manager.config.integrity_check = AsyncMock(return_value="ok")
        manager.ledger.integrity_check = AsyncMock(side_effect=Exception("Disk error"))
        manager.state.integrity_check = AsyncMock(return_value="ok")
        manager.cache.integrity_check = AsyncMock(return_value="ok")
        manager.calculations.integrity_check = AsyncMock(return_value="ok")

        results = await manager.integrity_check_all()

        assert results["config"] == "ok"
        assert "error" in results["ledger"]
        assert "Disk error" in results["ledger"]

    @pytest.mark.asyncio
    async def test_integrity_check_includes_history(self):
        """Test that integrity_check_all checks history databases."""
        from app.core.database.manager import DatabaseManager

        data_dir = Path("/tmp/test_data")
        manager = DatabaseManager(data_dir)

        # Mock core databases
        for db in [
            manager.config,
            manager.ledger,
            manager.state,
            manager.cache,
            manager.calculations,
        ]:
            db.integrity_check = AsyncMock(return_value="ok")

        # Add history database
        mock_history = AsyncMock()
        mock_history.integrity_check = AsyncMock(return_value="ok")
        manager._history["AAPL.US"] = mock_history

        results = await manager.integrity_check_all()

        assert results["history/AAPL.US"] == "ok"


class TestDatabaseManagerCheckpointAll:
    """Test checkpointing all databases."""

    @pytest.mark.asyncio
    async def test_checkpoint_all(self):
        """Test that checkpoint_all checkpoints all databases."""
        from app.core.database.manager import DatabaseManager

        data_dir = Path("/tmp/test_data")
        manager = DatabaseManager(data_dir)

        # Mock checkpoints
        manager.config.checkpoint = AsyncMock()
        manager.ledger.checkpoint = AsyncMock()
        manager.state.checkpoint = AsyncMock()
        manager.cache.checkpoint = AsyncMock()
        manager.calculations.checkpoint = AsyncMock()

        await manager.checkpoint_all()

        manager.config.checkpoint.assert_called_once()
        manager.ledger.checkpoint.assert_called_once()
        manager.state.checkpoint.assert_called_once()
        manager.cache.checkpoint.assert_called_once()
        manager.calculations.checkpoint.assert_called_once()

    @pytest.mark.asyncio
    async def test_checkpoint_all_includes_history(self):
        """Test that checkpoint_all checkpoints history databases."""
        from app.core.database.manager import DatabaseManager

        data_dir = Path("/tmp/test_data")
        manager = DatabaseManager(data_dir)

        # Mock core database checkpoints
        for db in [
            manager.config,
            manager.ledger,
            manager.state,
            manager.cache,
            manager.calculations,
        ]:
            db.checkpoint = AsyncMock()

        # Add history database
        mock_history = AsyncMock()
        mock_history.checkpoint = AsyncMock()
        manager._history["AAPL.US"] = mock_history

        await manager.checkpoint_all()

        mock_history.checkpoint.assert_called_once()


class TestDatabaseManagerGetHistorySymbols:
    """Test getting history symbols."""

    def test_get_history_symbols_no_directory(self):
        """Test get_history_symbols when directory doesn't exist."""
        from app.core.database.manager import DatabaseManager

        data_dir = Path("/tmp/nonexistent_" + str(id(self)))
        manager = DatabaseManager(data_dir)

        symbols = manager.get_history_symbols()

        assert symbols == []

    def test_get_history_symbols_with_files(self):
        """Test get_history_symbols with database files."""
        from app.core.database.manager import DatabaseManager

        data_dir = Path("/tmp/test_data")
        manager = DatabaseManager(data_dir)

        mock_paths = [
            MagicMock(stem="AAPL_US"),
            MagicMock(stem="MSFT_US"),
        ]

        with (
            patch.object(Path, "exists", return_value=True),
            patch.object(Path, "glob", return_value=mock_paths),
        ):
            symbols = manager.get_history_symbols()

        assert "AAPL.US" in symbols
        assert "MSFT.US" in symbols


class TestGetDbManager:
    """Test get_db_manager function."""

    def test_raises_when_not_initialized(self):
        """Test that get_db_manager raises when not initialized."""
        import app.core.database.manager as module

        # Save and clear the global
        original = module._db_manager
        module._db_manager = None

        try:
            from app.core.database.manager import get_db_manager

            with pytest.raises(RuntimeError) as exc_info:
                get_db_manager()

            assert "not initialized" in str(exc_info.value)
        finally:
            # Restore
            module._db_manager = original


class TestInitDatabases:
    """Test init_databases function."""

    @pytest.mark.asyncio
    async def test_initializes_manager(self):
        """Test that init_databases creates and returns manager."""
        import app.core.database.manager as module

        original = module._db_manager

        try:
            with (
                patch(
                    "app.core.database.schemas.init_config_schema",
                    new_callable=AsyncMock,
                ),
                patch(
                    "app.core.database.schemas.init_ledger_schema",
                    new_callable=AsyncMock,
                ),
                patch(
                    "app.core.database.schemas.init_state_schema",
                    new_callable=AsyncMock,
                ),
                patch(
                    "app.core.database.schemas.init_cache_schema",
                    new_callable=AsyncMock,
                ),
                patch(
                    "app.core.database.schemas.init_calculations_schema",
                    new_callable=AsyncMock,
                ),
            ):
                from app.core.database.manager import init_databases

                manager = await init_databases(Path("/tmp/test_data"))

                assert manager is not None
                assert module._db_manager is manager
        finally:
            module._db_manager = original


class TestShutdownDatabases:
    """Test shutdown_databases function."""

    @pytest.mark.asyncio
    async def test_shutdown_closes_and_clears_manager(self):
        """Test that shutdown_databases closes and clears manager."""
        import app.core.database.manager as module

        mock_manager = AsyncMock()
        original = module._db_manager
        module._db_manager = mock_manager

        try:
            from app.core.database.manager import shutdown_databases

            await shutdown_databases()

            mock_manager.close_all.assert_called_once()
            assert module._db_manager is None
        finally:
            module._db_manager = original

    @pytest.mark.asyncio
    async def test_shutdown_when_not_initialized(self):
        """Test shutdown when not initialized does nothing."""
        import app.core.database.manager as module

        original = module._db_manager
        module._db_manager = None

        try:
            from app.core.database.manager import shutdown_databases

            # Should not raise
            await shutdown_databases()
        finally:
            module._db_manager = original
