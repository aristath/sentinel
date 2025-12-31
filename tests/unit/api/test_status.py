"""Tests for status API endpoints.

These tests validate the system health monitoring and sync trigger endpoints.
Critical for ensuring the trading system operates correctly.
"""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI

from app.modules.system.api.status import (
    _calculate_data_dir_size,
    _get_backup_info,
    _get_core_db_sizes,
    _get_history_db_info,
    router,
)


@pytest.fixture
def app():
    """Create a test FastAPI app with the status router."""
    app = FastAPI()
    app.include_router(router, prefix="/status")
    return app


@pytest.fixture
def mock_portfolio_repo():
    """Mock portfolio repository."""
    repo = AsyncMock()
    return repo


@pytest.fixture
def mock_stock_repo():
    """Mock security repository."""
    repo = AsyncMock()
    return repo


@pytest.fixture
def mock_position_repo():
    """Mock position repository."""
    repo = AsyncMock()
    return repo


@pytest.fixture
def mock_settings_repo():
    """Mock settings repository."""
    repo = AsyncMock()
    return repo


class TestGetStatus:
    """Test the main system status endpoint."""

    @pytest.mark.asyncio
    async def test_returns_healthy_status_with_data(
        self, mock_portfolio_repo, mock_stock_repo, mock_position_repo
    ):
        """Test that status returns healthy with real data."""
        from app.modules.system.api.status import get_status

        # Setup mock data
        mock_snapshot = MagicMock()
        mock_snapshot.cash_balance = 5000.0
        mock_portfolio_repo.get_latest.return_value = mock_snapshot

        mock_position = MagicMock()
        mock_position.last_updated = "2024-01-15T10:30:00"
        mock_position_repo.get_all.return_value = [mock_position]

        mock_stock_repo.get_all_active.return_value = [MagicMock(), MagicMock()]

        result = await get_status(
            mock_portfolio_repo, mock_stock_repo, mock_position_repo
        )

        assert result["status"] == "healthy"
        assert result["cash_balance"] == 5000.0
        assert result["security_universe_count"] == 2
        assert result["active_positions"] == 1
        assert result["last_sync"] == "2024-01-15 10:30"

    @pytest.mark.asyncio
    async def test_handles_no_portfolio_snapshot(
        self, mock_portfolio_repo, mock_stock_repo, mock_position_repo
    ):
        """Test behavior when no portfolio snapshot exists."""
        from app.modules.system.api.status import get_status

        mock_portfolio_repo.get_latest.return_value = None
        mock_position_repo.get_all.return_value = []
        mock_stock_repo.get_all_active.return_value = []

        result = await get_status(
            mock_portfolio_repo, mock_stock_repo, mock_position_repo
        )

        assert result["cash_balance"] == 0
        assert result["active_positions"] == 0

    @pytest.mark.asyncio
    async def test_handles_no_positions(
        self, mock_portfolio_repo, mock_stock_repo, mock_position_repo
    ):
        """Test behavior when no positions exist."""
        from app.modules.system.api.status import get_status

        mock_snapshot = MagicMock()
        mock_snapshot.cash_balance = 10000.0
        mock_portfolio_repo.get_latest.return_value = mock_snapshot
        mock_position_repo.get_all.return_value = []
        mock_stock_repo.get_all_active.return_value = []

        result = await get_status(
            mock_portfolio_repo, mock_stock_repo, mock_position_repo
        )

        assert result["last_sync"] is None
        assert result["active_positions"] == 0

    @pytest.mark.asyncio
    async def test_handles_invalid_date_format(
        self, mock_portfolio_repo, mock_stock_repo, mock_position_repo
    ):
        """Test fallback when date parsing fails."""
        from app.modules.system.api.status import get_status

        mock_portfolio_repo.get_latest.return_value = None

        mock_position = MagicMock()
        mock_position.last_updated = "invalid-date-format-here"
        mock_position_repo.get_all.return_value = [mock_position]

        mock_stock_repo.get_all_active.return_value = []

        result = await get_status(
            mock_portfolio_repo, mock_stock_repo, mock_position_repo
        )

        # Should use truncation fallback
        assert result["last_sync"] == "invalid-date-for"

    @pytest.mark.asyncio
    async def test_handles_position_without_last_updated(
        self, mock_portfolio_repo, mock_stock_repo, mock_position_repo
    ):
        """Test handling of positions without last_updated field."""
        from app.modules.system.api.status import get_status

        mock_portfolio_repo.get_latest.return_value = None

        mock_position = MagicMock()
        mock_position.last_updated = None
        mock_position_repo.get_all.return_value = [mock_position]

        mock_stock_repo.get_all_active.return_value = []

        result = await get_status(
            mock_portfolio_repo, mock_stock_repo, mock_position_repo
        )

        assert result["last_sync"] is None

    @pytest.mark.asyncio
    async def test_finds_most_recent_position_update(
        self, mock_portfolio_repo, mock_stock_repo, mock_position_repo
    ):
        """Test that the most recent position update is found."""
        from app.modules.system.api.status import get_status

        mock_portfolio_repo.get_latest.return_value = None

        # Multiple positions with different timestamps
        pos1 = MagicMock()
        pos1.last_updated = "2024-01-10T08:00:00"
        pos2 = MagicMock()
        pos2.last_updated = "2024-01-15T12:30:00"  # Most recent
        pos3 = MagicMock()
        pos3.last_updated = "2024-01-12T15:00:00"

        mock_position_repo.get_all.return_value = [pos1, pos2, pos3]
        mock_stock_repo.get_all_active.return_value = []

        result = await get_status(
            mock_portfolio_repo, mock_stock_repo, mock_position_repo
        )

        assert result["last_sync"] == "2024-01-15 12:30"


class TestSyncTriggers:
    """Test the manual sync trigger endpoints."""

    @pytest.mark.asyncio
    async def test_portfolio_sync_success(self):
        """Test successful portfolio sync trigger."""
        from app.modules.system.api.status import trigger_portfolio_sync

        with patch(
            "app.jobs.daily_sync.sync_portfolio", new_callable=AsyncMock
        ) as mock_sync:
            result = await trigger_portfolio_sync()

        assert result["status"] == "success"
        mock_sync.assert_called_once()

    @pytest.mark.asyncio
    async def test_portfolio_sync_handles_error(self):
        """Test portfolio sync error handling."""
        from app.modules.system.api.status import trigger_portfolio_sync

        with patch(
            "app.jobs.daily_sync.sync_portfolio",
            new_callable=AsyncMock,
            side_effect=Exception("Sync failed"),
        ):
            result = await trigger_portfolio_sync()

        assert result["status"] == "error"
        assert "Sync failed" in result["message"]

    @pytest.mark.asyncio
    async def test_price_sync_success(self):
        """Test successful price sync trigger."""
        from app.modules.system.api.status import trigger_price_sync

        with patch(
            "app.jobs.daily_sync.sync_prices", new_callable=AsyncMock
        ) as mock_sync:
            result = await trigger_price_sync()

        assert result["status"] == "success"
        mock_sync.assert_called_once()

    @pytest.mark.asyncio
    async def test_price_sync_handles_error(self):
        """Test price sync error handling."""
        from app.modules.system.api.status import trigger_price_sync

        with patch(
            "app.jobs.daily_sync.sync_prices",
            new_callable=AsyncMock,
            side_effect=Exception("API timeout"),
        ):
            result = await trigger_price_sync()

        assert result["status"] == "error"
        assert "API timeout" in result["message"]

    @pytest.mark.asyncio
    async def test_historical_sync_success(self):
        """Test successful historical data sync trigger."""
        from app.modules.system.api.status import trigger_historical_sync

        with patch(
            "app.jobs.historical_data_sync.sync_historical_data", new_callable=AsyncMock
        ) as mock_sync:
            result = await trigger_historical_sync()

        assert result["status"] == "success"
        mock_sync.assert_called_once()

    @pytest.mark.asyncio
    async def test_daily_maintenance_success(self):
        """Test successful daily maintenance trigger."""
        from app.modules.system.api.status import trigger_daily_maintenance

        with patch(
            "app.jobs.maintenance.run_daily_maintenance", new_callable=AsyncMock
        ) as mock_maint:
            result = await trigger_daily_maintenance()

        assert result["status"] == "success"
        mock_maint.assert_called_once()


class TestTradernetStatus:
    """Test the Tradernet connection status endpoint."""

    @pytest.mark.asyncio
    async def test_connected_status(self):
        """Test status when connected to Tradernet."""
        from app.modules.system.api.status import get_tradernet_status

        mock_client = MagicMock()
        with patch(
            "app.infrastructure.external.tradernet_connection.ensure_tradernet_connected",
            new_callable=AsyncMock,
            return_value=mock_client,
        ):
            result = await get_tradernet_status()

        assert result["connected"] is True
        assert "Connected" in result["message"]

    @pytest.mark.asyncio
    async def test_disconnected_when_client_none(self):
        """Test status when Tradernet client is None."""
        from app.modules.system.api.status import get_tradernet_status

        with patch(
            "app.infrastructure.external.tradernet_connection.ensure_tradernet_connected",
            new_callable=AsyncMock,
            return_value=None,
        ):
            result = await get_tradernet_status()

        assert result["connected"] is False

    @pytest.mark.asyncio
    async def test_disconnected_on_exception(self):
        """Test status when connection throws exception."""
        from app.modules.system.api.status import get_tradernet_status

        with patch(
            "app.infrastructure.external.tradernet_connection.ensure_tradernet_connected",
            new_callable=AsyncMock,
            side_effect=Exception("Connection refused"),
        ):
            result = await get_tradernet_status()

        assert result["connected"] is False


class TestJobStatus:
    """Test the job status endpoint."""

    @pytest.mark.asyncio
    async def test_returns_job_health_status(self):
        """Test successful job status retrieval."""
        from app.modules.system.api.status import get_job_status

        mock_status = {
            "portfolio_sync": {"last_run": "2024-01-15T10:00:00", "healthy": True},
            "price_sync": {"last_run": "2024-01-15T10:05:00", "healthy": True},
        }

        with patch(
            "app.jobs.scheduler.get_job_health_status", return_value=mock_status
        ):
            result = await get_job_status()

        assert result["status"] == "ok"
        assert result["jobs"] == mock_status

    @pytest.mark.asyncio
    async def test_handles_error(self):
        """Test job status error handling."""
        from app.modules.system.api.status import get_job_status

        with patch(
            "app.jobs.scheduler.get_job_health_status",
            side_effect=Exception("Scheduler not running"),
        ):
            result = await get_job_status()

        assert result["status"] == "error"
        assert "Scheduler not running" in result["message"]


class TestDatabaseStats:
    """Test the database statistics endpoint."""

    @pytest.mark.asyncio
    async def test_returns_database_stats(self):
        """Test successful database stats retrieval."""
        from app.modules.system.api.status import get_database_stats

        mock_stats = {
            "total_stocks": 50,
            "total_positions": 25,
            "historical_data_days": 365,
        }

        with patch(
            "app.modules.system.jobs.health_check.get_database_stats",
            new_callable=AsyncMock,
            return_value=mock_stats,
        ):
            result = await get_database_stats()

        assert result["status"] == "ok"
        assert result["total_stocks"] == 50

    @pytest.mark.asyncio
    async def test_handles_error(self):
        """Test database stats error handling."""
        from app.modules.system.api.status import get_database_stats

        with patch(
            "app.modules.system.jobs.health_check.get_database_stats",
            new_callable=AsyncMock,
            side_effect=Exception("Database locked"),
        ):
            result = await get_database_stats()

        assert result["status"] == "error"
        assert "Database locked" in result["message"]


class TestDiskUsageHelpers:
    """Test the disk usage helper functions."""

    def test_calculate_data_dir_size_empty_dir(self, tmp_path):
        """Test size calculation for empty directory."""
        size = _calculate_data_dir_size(tmp_path)
        assert size == 0

    def test_calculate_data_dir_size_with_files(self, tmp_path):
        """Test size calculation with actual files."""
        # Create test files
        (tmp_path / "test1.db").write_bytes(b"x" * 1000)
        (tmp_path / "test2.db").write_bytes(b"y" * 500)

        size = _calculate_data_dir_size(tmp_path)
        assert size == 1500

    def test_calculate_data_dir_size_nonexistent(self, tmp_path):
        """Test size calculation for nonexistent directory."""
        nonexistent = tmp_path / "does_not_exist"
        size = _calculate_data_dir_size(nonexistent)
        assert size == 0

    def test_calculate_data_dir_size_nested_files(self, tmp_path):
        """Test size calculation with nested directories."""
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        (subdir / "nested.db").write_bytes(b"z" * 200)
        (tmp_path / "root.db").write_bytes(b"w" * 100)

        size = _calculate_data_dir_size(tmp_path)
        assert size == 300

    def test_get_core_db_sizes(self, tmp_path):
        """Test core database size retrieval."""
        (tmp_path / "config.db").write_bytes(b"x" * (1024 * 1024))  # 1 MB
        (tmp_path / "ledger.db").write_bytes(b"y" * (2 * 1024 * 1024))  # 2 MB

        sizes = _get_core_db_sizes(tmp_path)

        assert "config.db" in sizes
        assert sizes["config.db"] == pytest.approx(1.0, rel=0.01)
        assert "ledger.db" in sizes
        assert sizes["ledger.db"] == pytest.approx(2.0, rel=0.01)

    def test_get_core_db_sizes_missing_dbs(self, tmp_path):
        """Test core database sizes when some DBs don't exist."""
        (tmp_path / "config.db").write_bytes(b"x" * 1024)

        sizes = _get_core_db_sizes(tmp_path)

        assert "config.db" in sizes
        assert "ledger.db" not in sizes  # Doesn't exist

    def test_get_history_db_info(self, tmp_path):
        """Test history database info retrieval."""
        history_dir = tmp_path / "history"
        history_dir.mkdir()
        (history_dir / "AAPL.db").write_bytes(b"x" * 1000)
        (history_dir / "GOOGL.db").write_bytes(b"y" * 2000)

        count, size = _get_history_db_info(tmp_path)

        assert count == 2
        assert size == 3000

    def test_get_history_db_info_no_history_dir(self, tmp_path):
        """Test history info when history directory doesn't exist."""
        count, size = _get_history_db_info(tmp_path)

        assert count == 0
        assert size == 0

    def test_get_backup_info(self, tmp_path):
        """Test backup info retrieval."""
        backup_dir = tmp_path / "backups"
        backup_dir.mkdir()
        (backup_dir / "backup_2024_01.db").write_bytes(b"x" * 1000)

        history_backup = backup_dir / "history_2024_01"
        history_backup.mkdir()
        (history_backup / "AAPL.db").write_bytes(b"y" * 500)

        count, size = _get_backup_info(tmp_path)

        assert count == 2
        assert size == 1500

    def test_get_backup_info_no_backups(self, tmp_path):
        """Test backup info when no backups exist."""
        count, size = _get_backup_info(tmp_path)

        assert count == 0
        assert size == 0


class TestDiskUsageEndpoint:
    """Test the disk usage endpoint."""

    @pytest.mark.asyncio
    async def test_returns_disk_usage(self, tmp_path):
        """Test successful disk usage retrieval."""
        from app.modules.system.api.status import get_disk_usage

        # Create test files
        (tmp_path / "config.db").write_bytes(b"x" * 1024)

        with patch("app.api.status.settings") as mock_settings:
            mock_settings.data_dir = tmp_path
            result = await get_disk_usage()

        assert result["status"] == "ok"
        assert "disk" in result
        assert "total_mb" in result["disk"]
        assert "free_mb" in result["disk"]
        assert "used_percent" in result["disk"]

    @pytest.mark.asyncio
    async def test_handles_error(self):
        """Test disk usage error handling."""
        from app.modules.system.api.status import get_disk_usage

        with patch("app.api.status.settings") as mock_settings:
            mock_settings.data_dir = Path("/nonexistent/path")
            with patch("shutil.disk_usage", side_effect=OSError("Disk error")):
                result = await get_disk_usage()

        assert result["status"] == "error"
