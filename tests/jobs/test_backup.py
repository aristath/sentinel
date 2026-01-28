"""Tests for backup task functions."""

import os
import tarfile
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from sentinel.jobs.tasks import (
    _create_archive,
    _prune_old_backups,
    backup_r2,
)


def test_create_archive():
    """_create_archive should produce a valid tar.gz containing the data dir."""
    with tempfile.TemporaryDirectory() as tmpdir:
        data_dir = Path(tmpdir) / "data"
        data_dir.mkdir()

        (data_dir / "test.txt").write_text("hello")

        dest = os.path.join(tmpdir, "backup.tar.gz")

        with patch("sentinel.jobs.tasks.DATA_DIR", data_dir):
            _create_archive(dest)

        assert os.path.exists(dest)
        assert os.path.getsize(dest) > 0

        with tarfile.open(dest, "r:gz") as tar:
            names = tar.getnames()
            assert any("test.txt" in n for n in names)


def test_create_archive_missing_dir():
    """_create_archive should raise if data dir doesn't exist."""
    with tempfile.TemporaryDirectory() as tmpdir:
        dest = os.path.join(tmpdir, "backup.tar.gz")
        missing = Path(tmpdir) / "nonexistent"

        with patch("sentinel.jobs.tasks.DATA_DIR", missing):
            with pytest.raises(FileNotFoundError):
                _create_archive(dest)


def test_prune_old_backups():
    """_prune_old_backups should delete objects older than retention period."""
    from datetime import datetime, timezone

    old_date = datetime(2020, 1, 1, tzinfo=timezone.utc)
    new_date = datetime(2099, 1, 1, tzinfo=timezone.utc)

    client = MagicMock()
    client.list_objects_v2.return_value = {
        "Contents": [
            {"Key": "backups/old.tar.gz", "LastModified": old_date},
            {"Key": "backups/new.tar.gz", "LastModified": new_date},
        ]
    }

    _prune_old_backups(client, "test-bucket", retention_days=30)

    client.delete_objects.assert_called_once()
    deleted_keys = client.delete_objects.call_args[1]["Delete"]["Objects"]
    assert len(deleted_keys) == 1
    assert deleted_keys[0]["Key"] == "backups/old.tar.gz"


def test_prune_no_old_backups():
    """_prune_old_backups should not call delete if nothing is old."""
    from datetime import datetime, timezone

    new_date = datetime(2099, 1, 1, tzinfo=timezone.utc)

    client = MagicMock()
    client.list_objects_v2.return_value = {
        "Contents": [
            {"Key": "backups/new.tar.gz", "LastModified": new_date},
        ]
    }

    _prune_old_backups(client, "test-bucket", retention_days=30)

    client.delete_objects.assert_not_called()


@pytest.mark.asyncio
async def test_backup_skips_without_credentials():
    """backup_r2 should skip gracefully when credentials are not configured."""
    mock_db = AsyncMock()

    with patch("sentinel.settings.Settings") as MockSettings:
        instance = MockSettings.return_value
        instance.get = AsyncMock(return_value="")
        await backup_r2(mock_db)


@pytest.mark.asyncio
async def test_backup_full_flow():
    """backup_r2 should create archive, upload, and prune."""
    mock_db = AsyncMock()
    mock_client = MagicMock()
    mock_client.list_objects_v2.return_value = {"Contents": []}

    async def mock_get(key, default=""):
        values = {
            "r2_account_id": "test-account",
            "r2_access_key": "test-key",
            "r2_secret_key": "test-secret",
            "r2_bucket_name": "test-bucket",
            "r2_backup_retention_days": 30,
        }
        return values.get(key, default)

    with (
        patch("sentinel.settings.Settings") as MockSettings,
        patch("sentinel.jobs.tasks._get_r2_client", return_value=mock_client),
        patch("sentinel.jobs.tasks._create_archive"),
        patch("sentinel.jobs.tasks._upload_archive") as mock_upload,
        patch("os.path.exists", return_value=True),
        patch("os.unlink"),
    ):
        instance = MockSettings.return_value
        instance.get = mock_get

        await backup_r2(mock_db)

        mock_upload.assert_called_once()
