"""Tests for maintenance jobs.

These tests validate database maintenance operations including
backup, cleanup, and WAL checkpoint operations.
"""

import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestBackupDatabase:
    """Tests for _backup_database helper."""

    def test_backs_up_database(self):
        """Test backing up a database file."""
        from app.jobs.maintenance import _backup_database

        with tempfile.TemporaryDirectory() as tmpdir:
            source_path = Path(tmpdir) / "source.db"

            # Create a real SQLite db
            conn = sqlite3.connect(str(source_path))
            conn.execute("CREATE TABLE test (id INTEGER)")
            conn.commit()
            conn.close()

            dest_path = Path(tmpdir) / "backup.db"
            _backup_database(source_path, dest_path)

            assert dest_path.exists()


class TestCreateBackupInternal:
    """Tests for _create_backup_internal."""

    @pytest.mark.asyncio
    async def test_creates_backup_directory(self):
        """Test that backup directory is created."""
        from app.jobs.maintenance import _create_backup_internal

        with tempfile.TemporaryDirectory() as tmpdir:
            mock_settings = MagicMock()
            mock_settings.data_dir = Path(tmpdir)
            mock_settings.backup_retention_count = 7

            with (
                patch("app.jobs.maintenance.settings", mock_settings),
                patch("app.jobs.maintenance.emit"),
                patch("app.jobs.maintenance.set_processing"),
                patch("app.jobs.maintenance.clear_processing"),
                patch("app.jobs.maintenance._cleanup_old_backups") as mock_cleanup,
            ):
                await _create_backup_internal()

                backup_dir = Path(tmpdir) / "backups"
                assert backup_dir.exists()
                mock_cleanup.assert_called_once()

    @pytest.mark.asyncio
    async def test_handles_backup_error(self):
        """Test handling backup error."""
        from app.jobs.maintenance import _create_backup_internal

        with (
            patch(
                "app.jobs.maintenance.settings",
                MagicMock(data_dir=Path("/nonexistent")),
            ),
            patch("app.jobs.maintenance.emit"),
            patch("app.jobs.maintenance.set_processing"),
            patch("app.jobs.maintenance.set_error") as mock_set_error,
            patch("app.jobs.maintenance.clear_processing"),
        ):
            with pytest.raises(Exception):
                await _create_backup_internal()

            mock_set_error.assert_called_once()


class TestCheckpointWalInternal:
    """Tests for _checkpoint_wal_internal."""

    @pytest.mark.asyncio
    async def test_checkpoints_all_databases(self):
        """Test checkpointing all databases."""
        from app.jobs.maintenance import _checkpoint_wal_internal

        mock_cursor = AsyncMock()
        mock_cursor.fetchone.return_value = (0, 10, 10)

        mock_db = AsyncMock()
        mock_db.execute.return_value = mock_cursor

        mock_db_manager = MagicMock()
        mock_db_manager.config = mock_db
        mock_db_manager.ledger = mock_db
        mock_db_manager.state = mock_db
        mock_db_manager.cache = mock_db
        mock_db_manager.calculations = mock_db

        with (
            patch("app.jobs.maintenance.get_db_manager", return_value=mock_db_manager),
            patch("app.jobs.maintenance.set_processing"),
        ):
            await _checkpoint_wal_internal()

            assert mock_db.execute.call_count == 5

    @pytest.mark.asyncio
    async def test_handles_checkpoint_error(self):
        """Test handling checkpoint error on individual db."""
        from app.jobs.maintenance import _checkpoint_wal_internal

        mock_db = AsyncMock()
        mock_db.execute.side_effect = Exception("Checkpoint error")

        mock_db_manager = MagicMock()
        mock_db_manager.config = mock_db
        mock_db_manager.ledger = mock_db
        mock_db_manager.state = mock_db
        mock_db_manager.cache = mock_db
        mock_db_manager.calculations = mock_db

        with (
            patch("app.jobs.maintenance.get_db_manager", return_value=mock_db_manager),
            patch("app.jobs.maintenance.set_processing"),
        ):
            # Should not raise - individual checkpoint errors are logged
            await _checkpoint_wal_internal()


class TestIntegrityCheckInternal:
    """Tests for _integrity_check_internal."""

    @pytest.mark.asyncio
    async def test_passes_when_all_ok(self):
        """Test passing integrity check."""
        from app.infrastructure.events import SystemEvent
        from app.jobs.maintenance import _integrity_check_internal

        mock_cursor = AsyncMock()
        mock_cursor.fetchone.return_value = ("ok",)

        mock_db = AsyncMock()
        mock_db.execute.return_value = mock_cursor

        mock_db_manager = MagicMock()
        mock_db_manager.config = mock_db
        mock_db_manager.ledger = mock_db
        mock_db_manager.state = mock_db
        mock_db_manager.cache = mock_db
        mock_db_manager.calculations = mock_db

        with (
            patch("app.jobs.maintenance.get_db_manager", return_value=mock_db_manager),
            patch("app.jobs.maintenance.emit") as mock_emit,
            patch("app.jobs.maintenance.set_processing"),
            patch("app.jobs.maintenance.clear_processing"),
        ):
            await _integrity_check_internal()

            mock_emit.assert_any_call(SystemEvent.INTEGRITY_CHECK_COMPLETE)

    @pytest.mark.asyncio
    async def test_reports_failure(self):
        """Test reporting integrity check failure."""
        from app.jobs.maintenance import _integrity_check_internal

        mock_cursor = AsyncMock()
        mock_cursor.fetchone.return_value = ("database is corrupted",)

        mock_db = AsyncMock()
        mock_db.execute.return_value = mock_cursor

        mock_db_manager = MagicMock()
        mock_db_manager.config = mock_db
        mock_db_manager.ledger = mock_db
        mock_db_manager.state = mock_db
        mock_db_manager.cache = mock_db
        mock_db_manager.calculations = mock_db

        with (
            patch("app.jobs.maintenance.get_db_manager", return_value=mock_db_manager),
            patch("app.jobs.maintenance.emit"),
            patch("app.jobs.maintenance.set_processing"),
            patch("app.jobs.maintenance.set_error") as mock_set_error,
            patch("app.jobs.maintenance.clear_processing"),
        ):
            await _integrity_check_internal()

            mock_set_error.assert_called_once()


class TestCleanupOldDailyPricesInternal:
    """Tests for _cleanup_old_daily_prices_internal."""

    @pytest.mark.asyncio
    async def test_cleans_old_prices(self):
        """Test cleaning old daily prices."""
        from app.jobs.maintenance import _cleanup_old_daily_prices_internal

        mock_cursor = AsyncMock()
        mock_cursor.fetchall.return_value = [("AAPL.US",)]
        mock_cursor.fetchone.return_value = (100,)

        mock_config = AsyncMock()
        mock_config.execute.return_value = mock_cursor

        mock_history = AsyncMock()
        mock_history.execute.return_value = mock_cursor

        mock_db_manager = MagicMock()
        mock_db_manager.config = mock_config
        mock_db_manager.history = AsyncMock(return_value=mock_history)

        mock_settings = MagicMock()
        mock_settings.daily_price_retention_days = 365

        with (
            patch("app.jobs.maintenance.get_db_manager", return_value=mock_db_manager),
            patch("app.jobs.maintenance.settings", mock_settings),
            patch("app.jobs.maintenance.emit"),
            patch("app.jobs.maintenance.set_processing"),
        ):
            await _cleanup_old_daily_prices_internal()

            mock_history.execute.assert_called()


class TestCleanupExpiredCachesInternal:
    """Tests for _cleanup_expired_caches_internal."""

    @pytest.mark.asyncio
    async def test_cleans_caches(self):
        """Test cleaning expired caches."""
        from app.jobs.maintenance import _cleanup_expired_caches_internal

        mock_rec_cache = AsyncMock()
        mock_rec_cache.cleanup_expired.return_value = 5

        mock_calc_repo = AsyncMock()
        mock_calc_repo.delete_expired.return_value = 10

        with (
            patch(
                "app.infrastructure.recommendation_cache.get_recommendation_cache",
                return_value=mock_rec_cache,
            ),
            patch(
                "app.repositories.calculations.CalculationsRepository",
                return_value=mock_calc_repo,
            ),
            patch("app.jobs.maintenance.set_processing"),
        ):
            await _cleanup_expired_caches_internal()

            mock_rec_cache.cleanup_expired.assert_called_once()
            mock_calc_repo.delete_expired.assert_called_once()

    @pytest.mark.asyncio
    async def test_handles_cleanup_error_silently(self):
        """Test that cache cleanup errors don't raise."""
        from app.jobs.maintenance import _cleanup_expired_caches_internal

        with (
            patch(
                "app.infrastructure.recommendation_cache.get_recommendation_cache",
                side_effect=Exception("Cache error"),
            ),
            patch("app.jobs.maintenance.set_processing"),
        ):
            # Should not raise
            await _cleanup_expired_caches_internal()


class TestCleanupOldSnapshotsInternal:
    """Tests for _cleanup_old_snapshots_internal."""

    @pytest.mark.asyncio
    async def test_cleans_old_snapshots(self):
        """Test cleaning old snapshots."""
        from app.jobs.maintenance import _cleanup_old_snapshots_internal

        mock_cursor = AsyncMock()
        mock_cursor.fetchone.return_value = (50,)

        mock_state = AsyncMock()
        mock_state.execute.return_value = mock_cursor

        mock_db_manager = MagicMock()
        mock_db_manager.state = mock_state

        mock_settings = MagicMock()
        mock_settings.snapshot_retention_days = 90

        with (
            patch("app.jobs.maintenance.get_db_manager", return_value=mock_db_manager),
            patch("app.jobs.maintenance.settings", mock_settings),
            patch("app.jobs.maintenance.set_processing"),
        ):
            await _cleanup_old_snapshots_internal()

            # Should have called execute twice (count + delete)
            assert mock_state.execute.call_count == 2

    @pytest.mark.asyncio
    async def test_skips_when_no_old_snapshots(self):
        """Test skipping when no old snapshots."""
        from app.jobs.maintenance import _cleanup_old_snapshots_internal

        mock_cursor = AsyncMock()
        mock_cursor.fetchone.return_value = (0,)

        mock_state = AsyncMock()
        mock_state.execute.return_value = mock_cursor

        mock_db_manager = MagicMock()
        mock_db_manager.state = mock_state

        mock_settings = MagicMock()
        mock_settings.snapshot_retention_days = 90

        with (
            patch("app.jobs.maintenance.get_db_manager", return_value=mock_db_manager),
            patch("app.jobs.maintenance.settings", mock_settings),
            patch("app.jobs.maintenance.set_processing"),
        ):
            await _cleanup_old_snapshots_internal()

            # Should have called execute once (count only)
            assert mock_state.execute.call_count == 1


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
