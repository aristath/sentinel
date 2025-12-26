"""File-based locking for critical operations.

Provides distributed locks using file system to prevent concurrent execution
of critical operations like portfolio sync and rebalancing.
"""

import asyncio
import fcntl
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from app.config import settings

logger = logging.getLogger(__name__)

# Lock file directory
LOCK_DIR = Path(settings.database_path.parent) / "locks"
LOCK_DIR.mkdir(parents=True, exist_ok=True)


@asynccontextmanager
async def file_lock(lock_name: str, timeout: float = 300.0) -> AsyncIterator[None]:
    """
    Acquire a file-based lock for critical operations.

    Args:
        lock_name: Name of the lock (e.g., "portfolio_sync", "rebalance")
        timeout: Maximum time to wait for lock acquisition in seconds

    Raises:
        TimeoutError: If lock cannot be acquired within timeout

    Example:
        async with file_lock("portfolio_sync"):
            # Critical operation here
            await sync_portfolio()
    """
    lock_file = LOCK_DIR / f"{lock_name}.lock"

    # Open lock file
    lock_fd = None
    try:
        lock_fd = open(lock_file, "w")

        # Try to acquire lock with timeout
        start_time = asyncio.get_event_loop().time()
        acquired = False

        while not acquired:
            try:
                fcntl.flock(lock_fd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                acquired = True
                logger.debug(f"Acquired lock: {lock_name}")
            except BlockingIOError:
                # Lock is held by another process
                elapsed = asyncio.get_event_loop().time() - start_time
                if elapsed >= timeout:
                    raise TimeoutError(
                        f"Could not acquire lock '{lock_name}' within {timeout}s. "
                        "Another operation may be in progress."
                    )
                await asyncio.sleep(0.1)  # Wait 100ms before retry

        # Write PID to lock file for debugging
        import os

        lock_fd.write(str(os.getpid()))
        lock_fd.flush()

        try:
            yield
        finally:
            # Release lock
            try:
                fcntl.flock(lock_fd.fileno(), fcntl.LOCK_UN)
                logger.debug(f"Released lock: {lock_name}")
            except Exception as e:
                logger.warning(f"Error releasing lock {lock_name}: {e}")
    finally:
        if lock_fd:
            lock_fd.close()
            # Clean up lock file if it exists
            try:
                if lock_file.exists():
                    lock_file.unlink()
            except Exception:
                pass
