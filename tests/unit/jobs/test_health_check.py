"""Tests for health check job.

These tests validate system health monitoring including
database stats and integrity checks.
"""

from unittest.mock import AsyncMock, patch

import pytest


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
