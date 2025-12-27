"""Tests for health check job.

These tests validate system health monitoring including
database stats and integrity checks.
"""

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestCheckDatabaseIntegrity:
    """Test database integrity checking."""

    @pytest.mark.asyncio
    async def test_returns_ok_for_healthy_db(self):
        """Test returning 'ok' for healthy database."""
        from app.jobs.health_check import _check_database_integrity

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"

            mock_cursor = AsyncMock()
            mock_cursor.fetchone.return_value = ("ok",)

            mock_db = AsyncMock()
            mock_db.execute.return_value = mock_cursor
            mock_db.__aenter__.return_value = mock_db
            mock_db.__aexit__.return_value = None

            with patch("aiosqlite.connect", return_value=mock_db):
                result = await _check_database_integrity(db_path)

            assert result == "ok"

    @pytest.mark.asyncio
    async def test_returns_error_for_corrupted_db(self):
        """Test returning error message for corrupted database."""
        from app.jobs.health_check import _check_database_integrity

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"

            mock_cursor = AsyncMock()
            mock_cursor.fetchone.return_value = ("database disk image is malformed",)

            mock_db = AsyncMock()
            mock_db.execute.return_value = mock_cursor
            mock_db.__aenter__.return_value = mock_db
            mock_db.__aexit__.return_value = None

            with patch("aiosqlite.connect", return_value=mock_db):
                result = await _check_database_integrity(db_path)

            assert result == "database disk image is malformed"

    @pytest.mark.asyncio
    async def test_returns_exception_message_on_error(self):
        """Test returning exception message when check fails."""
        from app.jobs.health_check import _check_database_integrity

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"

            with patch("aiosqlite.connect", side_effect=Exception("Connection failed")):
                result = await _check_database_integrity(db_path)

            assert "Connection failed" in result


class TestCheckCoreDatabases:
    """Test core database checking."""

    @pytest.mark.asyncio
    async def test_checks_all_core_databases(self):
        """Test that all core databases are checked."""
        from app.jobs.health_check import _check_core_databases

        issues = []

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test database files
            for db_file in ["config.db", "ledger.db", "state.db", "cache.db"]:
                (Path(tmpdir) / db_file).write_bytes(b"test")

            with (
                patch("app.jobs.health_check.settings") as mock_settings,
                patch(
                    "app.jobs.health_check._check_database_integrity"
                ) as mock_check,
            ):
                mock_settings.data_dir = Path(tmpdir)
                mock_check.return_value = "ok"

                await _check_core_databases(issues)

            assert len(issues) == 0
            assert mock_check.call_count == 4

    @pytest.mark.asyncio
    async def test_reports_corrupted_database(self):
        """Test that corrupted databases are reported."""
        from app.jobs.health_check import _check_core_databases

        issues = []

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create config.db
            (Path(tmpdir) / "config.db").write_bytes(b"test")

            with (
                patch("app.jobs.health_check.settings") as mock_settings,
                patch(
                    "app.jobs.health_check._check_database_integrity"
                ) as mock_check,
            ):
                mock_settings.data_dir = Path(tmpdir)
                mock_check.return_value = "database corrupted"

                await _check_core_databases(issues)

            assert len(issues) == 1
            assert issues[0]["database"] == "config.db"
            assert issues[0]["error"] == "database corrupted"


class TestCheckHistoryDatabases:
    """Test history database checking."""

    @pytest.mark.asyncio
    async def test_checks_history_databases(self):
        """Test that history databases are checked."""
        from app.jobs.health_check import _check_history_databases

        issues = []

        with tempfile.TemporaryDirectory() as tmpdir:
            history_dir = Path(tmpdir) / "history"
            history_dir.mkdir()
            (history_dir / "AAPL.US.db").write_bytes(b"test")

            with (
                patch("app.jobs.health_check.settings") as mock_settings,
                patch(
                    "app.jobs.health_check._check_database_integrity"
                ) as mock_check,
            ):
                mock_settings.data_dir = Path(tmpdir)
                mock_check.return_value = "ok"

                await _check_history_databases(issues)

            assert len(issues) == 0
            mock_check.assert_called_once()

    @pytest.mark.asyncio
    async def test_skips_when_no_history_dir(self):
        """Test that check is skipped when no history directory."""
        from app.jobs.health_check import _check_history_databases

        issues = []

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("app.jobs.health_check.settings") as mock_settings:
                mock_settings.data_dir = Path(tmpdir)

                await _check_history_databases(issues)

            assert len(issues) == 0


class TestRunHealthCheckInternal:
    """Test internal health check function."""

    @pytest.mark.asyncio
    async def test_completes_successfully_when_healthy(self):
        """Test successful health check completion."""
        from app.jobs.health_check import _run_health_check_internal

        with (
            patch("app.jobs.health_check._check_core_databases"),
            patch("app.jobs.health_check._check_history_databases"),
            patch("app.jobs.health_check._check_legacy_database"),
            patch("app.jobs.health_check.set_processing"),
            patch("app.jobs.health_check.clear_processing"),
        ):
            await _run_health_check_internal()

    @pytest.mark.asyncio
    async def test_reports_issues_when_found(self):
        """Test reporting issues when found."""
        from app.jobs.health_check import _run_health_check_internal

        async def add_issue(issues):
            issues.append(
                {
                    "database": "test.db",
                    "description": "Test database",
                    "error": "corrupted",
                    "recoverable": True,
                }
            )

        with (
            patch(
                "app.jobs.health_check._check_core_databases", side_effect=add_issue
            ),
            patch("app.jobs.health_check._check_history_databases"),
            patch("app.jobs.health_check._check_legacy_database"),
            patch("app.jobs.health_check._report_issues") as mock_report,
            patch("app.jobs.health_check.set_processing"),
            patch("app.jobs.health_check.set_error"),
            patch("app.jobs.health_check.emit"),
            patch("app.jobs.health_check.clear_processing"),
        ):
            await _run_health_check_internal()

            mock_report.assert_called_once()


class TestReportIssues:
    """Test issue reporting."""

    @pytest.mark.asyncio
    async def test_logs_recovered_issues(self):
        """Test logging recovered issues."""
        from app.jobs.health_check import _report_issues

        issues = [
            {
                "database": "cache.db",
                "description": "Cache database",
                "error": "corrupted",
                "recoverable": True,
            }
        ]

        await _report_issues(issues)

    @pytest.mark.asyncio
    async def test_logs_critical_issues(self):
        """Test logging critical issues."""
        from app.jobs.health_check import _report_issues

        issues = [
            {
                "database": "config.db",
                "description": "Config database",
                "error": "corrupted",
                "recoverable": False,
            }
        ]

        await _report_issues(issues)


class TestGetDatabaseStats:
    """Test database statistics collection."""

    @pytest.mark.asyncio
    async def test_returns_database_statistics(self, tmp_path):
        """Test that database stats are returned correctly."""
        from app.jobs.health_check import get_database_stats

        # Create a test database file
        test_db = tmp_path / "config.db"
        test_db.write_bytes(b"test data " * 100)

        with patch("app.config.settings") as mock_settings:
            mock_settings.data_dir = tmp_path

            # Mock aiosqlite to avoid real DB access
            with patch("aiosqlite.connect") as mock_connect:
                mock_db = AsyncMock()
                mock_cursor = AsyncMock()
                mock_cursor.fetchone.return_value = (5,)
                mock_db.execute.return_value = mock_cursor
                mock_db.__aenter__.return_value = mock_db
                mock_db.__aexit__.return_value = None
                mock_connect.return_value = mock_db

                result = await get_database_stats()

        assert isinstance(result, dict)
        assert "config.db" in result


class TestRunHealthCheck:
    """Test main health check job."""

    @pytest.mark.asyncio
    async def test_calls_internal_function(self):
        """Test that run_health_check calls internal function with lock."""
        from app.jobs.health_check import run_health_check

        with patch(
            "app.jobs.health_check._run_health_check_internal",
            new_callable=AsyncMock,
        ) as mock_internal:
            with patch("app.jobs.health_check.file_lock"):
                await run_health_check()

        mock_internal.assert_called_once()


class TestCheckWalStatus:
    """Test WAL status checking."""

    @pytest.mark.asyncio
    async def test_checks_wal_files(self, tmp_path):
        """Test that WAL files are checked."""
        from app.jobs.health_check import check_wal_status

        # Create test database files
        config_db = tmp_path / "config.db"
        config_db.write_bytes(b"test")
        config_wal = tmp_path / "config.db-wal"
        config_wal.write_bytes(b"wal data " * 10)

        with patch("app.config.settings") as mock_settings:
            mock_settings.data_dir = tmp_path

            # Should run without error
            await check_wal_status()

    @pytest.mark.asyncio
    async def test_handles_missing_wal(self, tmp_path):
        """Test that missing WAL files are handled gracefully."""
        from app.jobs.health_check import check_wal_status

        # Create test database without WAL
        config_db = tmp_path / "config.db"
        config_db.write_bytes(b"test")
        # No WAL file - should not crash

        with patch("app.config.settings") as mock_settings:
            mock_settings.data_dir = tmp_path

            # Should run without error even with no WAL files
            await check_wal_status()

class TestCheckLegacyDatabase:
    """Test legacy database checking."""

    @pytest.mark.asyncio
    async def test_skips_when_no_legacy_db(self, tmp_path):
        """Test skipping when legacy database doesn't exist."""
        from app.jobs.health_check import _check_legacy_database

        issues = []

        with patch("app.jobs.health_check.settings") as mock_settings:
            mock_settings.database_path = tmp_path / "trader.db"

            await _check_legacy_database(issues)

        assert len(issues) == 0

    @pytest.mark.asyncio
    async def test_reports_corrupted_legacy_db(self, tmp_path):
        """Test reporting corrupted legacy database."""
        from app.jobs.health_check import _check_legacy_database

        # Create legacy database
        legacy_db = tmp_path / "trader.db"
        legacy_db.write_bytes(b"test")

        issues = []

        with (
            patch("app.jobs.health_check.settings") as mock_settings,
            patch(
                "app.jobs.health_check._check_database_integrity"
            ) as mock_check,
        ):
            mock_settings.database_path = legacy_db
            mock_check.return_value = "database corrupted"

            await _check_legacy_database(issues)

        assert len(issues) == 1
        assert issues[0]["database"] == "trader.db (legacy)"
        assert issues[0]["recoverable"] is False


class TestRebuildCacheDb:
    """Test cache database rebuild."""

    @pytest.mark.asyncio
    async def test_rebuilds_cache_database(self, tmp_path):
        """Test rebuilding corrupted cache database."""
        from app.jobs.health_check import _rebuild_cache_db

        # Create corrupted cache.db
        cache_db = tmp_path / "cache.db"
        cache_db.write_bytes(b"corrupted data")

        mock_db = AsyncMock()
        mock_db.__aenter__.return_value = mock_db
        mock_db.__aexit__.return_value = None

        with (
            patch("aiosqlite.connect", return_value=mock_db),
            patch("app.jobs.health_check.emit"),
        ):
            await _rebuild_cache_db(cache_db)

        # Original should be renamed to .corrupted
        assert not cache_db.exists() or (
            list(tmp_path.glob("*.corrupted.*.db"))
        )

    @pytest.mark.asyncio
    async def test_handles_rebuild_failure(self, tmp_path):
        """Test handling rebuild failure."""
        from app.jobs.health_check import _rebuild_cache_db

        # Create corrupted cache.db
        cache_db = tmp_path / "cache.db"
        cache_db.write_bytes(b"corrupted data")

        with patch("aiosqlite.connect", side_effect=Exception("DB error")):
            # Should not raise
            await _rebuild_cache_db(cache_db)


class TestRebuildSymbolHistory:
    """Test symbol history database rebuild."""

    @pytest.mark.asyncio
    async def test_rebuilds_history_database(self, tmp_path):
        """Test rebuilding corrupted history database."""
        from app.jobs.health_check import _rebuild_symbol_history

        # Create corrupted history db
        history_db = tmp_path / "AAPL.US.db"
        history_db.write_bytes(b"corrupted data")

        mock_db = AsyncMock()
        mock_db.__aenter__.return_value = mock_db
        mock_db.__aexit__.return_value = None

        with (
            patch("aiosqlite.connect", return_value=mock_db),
            patch("app.jobs.health_check.emit"),
        ):
            await _rebuild_symbol_history(history_db, "AAPL.US")

        # Original should be renamed to .corrupted
        assert not history_db.exists() or (
            list(tmp_path.glob("*.corrupted.*.db"))
        )

    @pytest.mark.asyncio
    async def test_handles_history_rebuild_failure(self, tmp_path):
        """Test handling history rebuild failure."""
        from app.jobs.health_check import _rebuild_symbol_history

        # Create corrupted history db
        history_db = tmp_path / "AAPL.US.db"
        history_db.write_bytes(b"corrupted data")

        with patch("aiosqlite.connect", side_effect=Exception("DB error")):
            # Should not raise
            await _rebuild_symbol_history(history_db, "AAPL.US")


class TestHistoryDatabasesWithIssues:
    """Test history database checking with issues."""

    @pytest.mark.asyncio
    async def test_reports_and_rebuilds_corrupted_history(self, tmp_path):
        """Test reporting and rebuilding corrupted history database."""
        from app.jobs.health_check import _check_history_databases

        history_dir = tmp_path / "history"
        history_dir.mkdir()
        (history_dir / "AAPL.US.db").write_bytes(b"test")

        issues = []

        with (
            patch("app.jobs.health_check.settings") as mock_settings,
            patch(
                "app.jobs.health_check._check_database_integrity"
            ) as mock_check,
            patch(
                "app.jobs.health_check._rebuild_symbol_history"
            ) as mock_rebuild,
        ):
            mock_settings.data_dir = tmp_path
            mock_check.return_value = "database corrupted"

            await _check_history_databases(issues)

        assert len(issues) == 1
        assert issues[0]["recoverable"] is True
        mock_rebuild.assert_called_once()


class TestCoreDatabasesWithCacheRebuild:
    """Test core database checking with cache rebuild."""

    @pytest.mark.asyncio
    async def test_rebuilds_corrupted_cache(self, tmp_path):
        """Test that corrupted cache.db is rebuilt."""
        from app.jobs.health_check import _check_core_databases

        # Create cache.db
        (tmp_path / "cache.db").write_bytes(b"test")

        issues = []

        with (
            patch("app.jobs.health_check.settings") as mock_settings,
            patch(
                "app.jobs.health_check._check_database_integrity"
            ) as mock_check,
            patch(
                "app.jobs.health_check._rebuild_cache_db"
            ) as mock_rebuild,
        ):
            mock_settings.data_dir = tmp_path
            mock_check.return_value = "database corrupted"

            await _check_core_databases(issues)

        # cache.db should trigger rebuild
        mock_rebuild.assert_called_once()
