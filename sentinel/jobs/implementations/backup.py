"""Backup job implementation - Cloudflare R2."""

from __future__ import annotations

import logging
import os
import tarfile
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sentinel.jobs.types import BaseJob, MarketTiming

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent.parent.parent / "data"


@dataclass
class BackupR2Job(BaseJob):
    """Backup data folder to Cloudflare R2."""

    _db: object = field(default=None, repr=False)

    def __init__(self, db):
        super().__init__(
            _id="backup:r2",
            _job_type="backup:r2",
            _timeout=timedelta(minutes=30),
            _market_timing=MarketTiming.ANY_TIME,
        )
        self._db = db

    async def execute(self) -> None:
        """Create tar.gz of data/ and upload to R2."""
        from sentinel.settings import Settings

        settings = Settings()
        account_id = await settings.get("r2_account_id", "")
        access_key = await settings.get("r2_access_key", "")
        secret_key = await settings.get("r2_secret_key", "")
        bucket_name = await settings.get("r2_bucket_name", "")
        retention_days = await settings.get("r2_backup_retention_days", 30)

        if not all([account_id, access_key, secret_key, bucket_name]):
            logger.warning("R2 backup skipped: credentials not configured")
            return

        # Create tar.gz archive
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d-%H%M%S")
        archive_key = f"backups/sentinel-{timestamp}.tar.gz"

        with tempfile.NamedTemporaryFile(suffix=".tar.gz", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            _create_archive(tmp_path)
            client = _get_r2_client(account_id, access_key, secret_key)
            _upload_archive(client, bucket_name, archive_key, tmp_path)
            logger.info(f"Backup uploaded: {archive_key}")

            if retention_days > 0:
                _prune_old_backups(client, bucket_name, retention_days)
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)


def _get_r2_client(account_id: str, access_key: str, secret_key: str):
    """Create a boto3 S3 client pointed at Cloudflare R2."""
    import boto3

    return boto3.client(
        "s3",
        endpoint_url=f"https://{account_id}.r2.cloudflarestorage.com",
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name="auto",
    )


def _create_archive(dest_path: str) -> None:
    """Create a tar.gz archive of the data directory."""
    if not DATA_DIR.exists():
        raise FileNotFoundError(f"Data directory not found: {DATA_DIR}")

    with tarfile.open(dest_path, "w:gz") as tar:
        tar.add(str(DATA_DIR), arcname="data")

    size_mb = os.path.getsize(dest_path) / (1024 * 1024)
    logger.info(f"Archive created: {size_mb:.1f} MB")


def _upload_archive(client, bucket: str, key: str, file_path: str) -> None:
    """Upload archive to R2 bucket."""
    client.upload_file(file_path, bucket, key)


def _prune_old_backups(client, bucket: str, retention_days: int) -> None:
    """Delete backups older than retention period."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)

    try:
        response = client.list_objects_v2(Bucket=bucket, Prefix="backups/")
        contents = response.get("Contents", [])

        to_delete = [obj["Key"] for obj in contents if obj.get("LastModified") and obj["LastModified"] < cutoff]

        if to_delete:
            client.delete_objects(
                Bucket=bucket,
                Delete={"Objects": [{"Key": k} for k in to_delete]},
            )
            logger.info(f"Pruned {len(to_delete)} old backups")
    except Exception as e:
        logger.warning(f"Failed to prune old backups: {e}")
