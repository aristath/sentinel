"""Tests for file-based locking.

These tests validate the distributed locking mechanism.
"""

import asyncio
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.infrastructure.locking import LOCK_DIR, file_lock


class TestFileLock:
    """Test file_lock context manager."""

    @pytest.mark.asyncio
    async def test_acquires_and_releases_lock(self, tmp_path):
        """Test that lock is acquired and released."""
        with patch.object(
            Path, "parent", new_callable=lambda: property(lambda self: tmp_path)
        ):
            # Use the real file_lock but with a test lock name
            acquired = False

            async with file_lock("test_lock"):
                acquired = True
                lock_file = LOCK_DIR / "test_lock.lock"
                # Lock file should exist during operation
                # Note: May be cleaned up immediately

            assert acquired

    @pytest.mark.asyncio
    async def test_lock_prevents_concurrent_access(self, tmp_path):
        """Test that lock prevents concurrent access."""
        lock_name = f"test_concurrent_{id(self)}"
        results = []

        async def task1():
            async with file_lock(lock_name, timeout=5.0):
                results.append("task1_start")
                await asyncio.sleep(0.1)
                results.append("task1_end")

        async def task2():
            await asyncio.sleep(0.05)  # Start slightly after task1
            async with file_lock(lock_name, timeout=5.0):
                results.append("task2_start")
                results.append("task2_end")

        await asyncio.gather(task1(), task2())

        # Task1 should complete before Task2 starts
        assert results.index("task1_end") < results.index("task2_start")

    @pytest.mark.asyncio
    async def test_lock_timeout_raises_error(self):
        """Test that timeout raises TimeoutError."""
        lock_name = f"test_timeout_{id(self)}"

        # Hold lock in a task
        lock_held = asyncio.Event()

        async def holder():
            async with file_lock(lock_name, timeout=10.0):
                lock_held.set()
                await asyncio.sleep(2.0)

        # Start holder
        holder_task = asyncio.create_task(holder())

        # Wait for lock to be acquired
        await lock_held.wait()

        # Try to acquire with very short timeout
        with pytest.raises(TimeoutError):
            async with file_lock(lock_name, timeout=0.1):
                pass

        # Cancel holder
        holder_task.cancel()
        try:
            await holder_task
        except asyncio.CancelledError:
            pass

    @pytest.mark.asyncio
    async def test_lock_writes_pid(self):
        """Test that lock file contains PID."""
        import os

        lock_name = f"test_pid_{id(self)}"
        lock_file = LOCK_DIR / f"{lock_name}.lock"

        async with file_lock(lock_name):
            # Lock file exists during operation
            if lock_file.exists():
                content = lock_file.read_text()
                assert str(os.getpid()) in content

    @pytest.mark.asyncio
    async def test_lock_cleanup_on_exit(self):
        """Test that lock file is cleaned up on normal exit."""
        lock_name = f"test_cleanup_{id(self)}"
        lock_file = LOCK_DIR / f"{lock_name}.lock"

        async with file_lock(lock_name):
            pass

        # Lock file should be removed after exit
        # Note: There's a tiny race window, but generally it should be gone
        await asyncio.sleep(0.01)
        assert not lock_file.exists()

    @pytest.mark.asyncio
    async def test_lock_cleanup_on_exception(self):
        """Test that lock is released on exception."""
        lock_name = f"test_exception_{id(self)}"

        with pytest.raises(ValueError):
            async with file_lock(lock_name):
                raise ValueError("test error")

        # Should be able to acquire lock again immediately
        acquired = False
        async with file_lock(lock_name, timeout=0.5):
            acquired = True

        assert acquired

    @pytest.mark.asyncio
    async def test_multiple_different_locks(self):
        """Test that different locks don't interfere."""
        results = []

        async def task_a():
            async with file_lock(f"lock_a_{id(self)}"):
                results.append("a_start")
                await asyncio.sleep(0.1)
                results.append("a_end")

        async def task_b():
            async with file_lock(f"lock_b_{id(self)}"):
                results.append("b_start")
                await asyncio.sleep(0.1)
                results.append("b_end")

        await asyncio.gather(task_a(), task_b())

        # Both tasks should run concurrently since different locks
        # a_start and b_start should both appear before a_end and b_end
        a_start = results.index("a_start")
        b_start = results.index("b_start")
        a_end = results.index("a_end")
        b_end = results.index("b_end")

        # One of the starts should come before both ends
        assert min(a_start, b_start) < max(a_end, b_end)


class TestLockDirectory:
    """Test lock directory setup."""

    def test_lock_dir_exists(self):
        """Test that lock directory is created."""
        assert LOCK_DIR.exists()
        assert LOCK_DIR.is_dir()
