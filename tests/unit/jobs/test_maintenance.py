"""Tests for maintenance jobs.

These tests validate database maintenance operations including
backup, cleanup, and WAL checkpoint operations.
"""

from unittest.mock import AsyncMock, patch

import pytest


class TestCreateBackup:
    """Test database backup functionality."""

    @pytest.mark.asyncio
    async def test_calls_internal_function(self):
        """Test that create_backup calls internal function with lock."""
        from app.jobs.maintenance import create_backup

        with patch(
            "app.jobs.maintenance._create_backup_internal",
            new_callable=AsyncMock,
        ) as mock_internal:
            with patch("app.jobs.maintenance.file_lock"):
                await create_backup()

        mock_internal.assert_called_once()


class TestCleanupOldBackups:
    """Test backup cleanup functionality."""

    @pytest.mark.asyncio
    async def test_removes_old_backup_files(self, tmp_path):
        """Test that old backup files are identified for removal."""
        from app.jobs.maintenance import _cleanup_old_backups

        backup_dir = tmp_path / "backups"
        backup_dir.mkdir()

        # Create old backup files
        old_backup = backup_dir / "config_20230101_000000.db"
        old_backup.write_bytes(b"old data")

        with patch("app.config.settings") as mock_settings:
            mock_settings.backup_retention_days = 7
            await _cleanup_old_backups(backup_dir)


class TestCheckpointWal:
    """Test WAL checkpoint functionality."""

    @pytest.mark.asyncio
    async def test_calls_internal_function(self):
        """Test that checkpoint_wal calls internal function with lock."""
        from app.jobs.maintenance import checkpoint_wal

        with patch(
            "app.jobs.maintenance._checkpoint_wal_internal",
            new_callable=AsyncMock,
        ) as mock_internal:
            with patch("app.jobs.maintenance.file_lock"):
                await checkpoint_wal()

        mock_internal.assert_called_once()


class TestIntegrityCheck:
    """Test database integrity check."""

    @pytest.mark.asyncio
    async def test_calls_internal_function(self):
        """Test that integrity_check calls internal function with lock."""
        from app.jobs.maintenance import integrity_check

        with patch(
            "app.jobs.maintenance._integrity_check_internal",
            new_callable=AsyncMock,
        ) as mock_internal:
            with patch("app.jobs.maintenance.file_lock"):
                await integrity_check()

        mock_internal.assert_called_once()


class TestCleanupExpiredCaches:
    """Test cache cleanup functionality."""

    @pytest.mark.asyncio
    async def test_calls_internal_function(self):
        """Test that cleanup_expired_caches calls internal function."""
        from app.jobs.maintenance import cleanup_expired_caches

        with patch(
            "app.jobs.maintenance._cleanup_expired_caches_internal",
            new_callable=AsyncMock,
        ) as mock_internal:
            with patch("app.jobs.maintenance.file_lock"):
                await cleanup_expired_caches()

        mock_internal.assert_called_once()


class TestRunDailyMaintenance:
    """Test daily maintenance job."""

    @pytest.mark.asyncio
    async def test_runs_all_daily_tasks(self):
        """Test that all daily maintenance tasks are run."""
        from app.jobs.maintenance import run_daily_maintenance

        with patch(
            "app.jobs.maintenance.create_backup", new_callable=AsyncMock
        ) as mock_backup:
            with patch(
                "app.jobs.maintenance.checkpoint_wal", new_callable=AsyncMock
            ) as mock_checkpoint:
                with patch(
                    "app.jobs.maintenance.cleanup_expired_caches",
                    new_callable=AsyncMock,
                ) as mock_cleanup:
                    with patch(
                        "app.jobs.maintenance.cleanup_old_daily_prices",
                        new_callable=AsyncMock,
                    ):
                        with patch(
                            "app.jobs.maintenance.cleanup_old_snapshots",
                            new_callable=AsyncMock,
                        ):
                            await run_daily_maintenance()

        mock_backup.assert_called_once()
        mock_checkpoint.assert_called_once()
        mock_cleanup.assert_called_once()


class TestRunWeeklyMaintenance:
    """Test weekly maintenance job."""

    @pytest.mark.asyncio
    async def test_runs_weekly_tasks(self):
        """Test that weekly maintenance tasks are run."""
        from app.jobs.maintenance import run_weekly_maintenance

        with patch(
            "app.jobs.maintenance.integrity_check", new_callable=AsyncMock
        ) as mock_integrity:
            await run_weekly_maintenance()

        mock_integrity.assert_called_once()
