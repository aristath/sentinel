"""Tests for job_schedules database operations."""

import os
import tempfile
from datetime import datetime

import pytest
import pytest_asyncio

from sentinel.database import Database


@pytest_asyncio.fixture
async def db():
    """Create test database with job_schedules table."""
    # Create a temporary database file
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    # Create database instance
    database = Database(path)
    await database.connect()

    yield database

    # Cleanup
    await database.close()
    database.remove_from_cache()
    if os.path.exists(path):
        os.remove(path)


@pytest.mark.asyncio
async def test_get_job_schedules_returns_all(db):
    """get_job_schedules should return all schedules."""
    # Insert test data directly
    now = int(datetime.now().timestamp())
    await db.conn.execute(
        """INSERT INTO job_schedules
           (job_type, interval_minutes, description, category, created_at, updated_at)
           VALUES (?, 30, 'Test job 1', 'sync', ?, ?)""",
        ("sync:test1", now, now),
    )
    await db.conn.execute(
        """INSERT INTO job_schedules
           (job_type, interval_minutes, description, category, created_at, updated_at)
           VALUES (?, 60, 'Test job 2', 'analytics', ?, ?)""",
        ("analytics:test2", now, now),
    )
    await db.conn.commit()

    schedules = await db.get_job_schedules()
    assert len(schedules) == 2
    job_types = [s["job_type"] for s in schedules]
    assert "sync:test1" in job_types
    assert "analytics:test2" in job_types


@pytest.mark.asyncio
async def test_get_job_schedules_empty_when_no_data(db):
    """get_job_schedules should return empty list when no schedules."""
    schedules = await db.get_job_schedules()
    assert schedules == []


@pytest.mark.asyncio
async def test_get_job_schedule_returns_single(db):
    """get_job_schedule should return single schedule by job_type."""
    now = int(datetime.now().timestamp())
    await db.conn.execute(
        """INSERT INTO job_schedules
           (job_type, interval_minutes, interval_market_open_minutes,
            market_timing, description, category, created_at, updated_at)
           VALUES (?, 30, 5, 0, 'Sync portfolio', 'sync', ?, ?)""",
        ("sync:portfolio", now, now),
    )
    await db.conn.commit()

    schedule = await db.get_job_schedule("sync:portfolio")
    assert schedule is not None
    assert schedule["job_type"] == "sync:portfolio"
    assert schedule["interval_minutes"] == 30
    assert schedule["interval_market_open_minutes"] == 5
    assert schedule["market_timing"] == 0
    assert schedule["description"] == "Sync portfolio"
    assert schedule["category"] == "sync"


@pytest.mark.asyncio
async def test_get_job_schedule_returns_none_for_unknown(db):
    """get_job_schedule should return None for unknown job_type."""
    schedule = await db.get_job_schedule("unknown:job")
    assert schedule is None


@pytest.mark.asyncio
async def test_upsert_job_schedule_inserts_new(db):
    """upsert_job_schedule should insert new schedule."""
    await db.upsert_job_schedule(
        job_type="sync:test",
        interval_minutes=60,
        interval_market_open_minutes=15,
        market_timing=1,
        description="Test sync job",
        category="sync",
    )

    schedule = await db.get_job_schedule("sync:test")
    assert schedule is not None
    assert schedule["job_type"] == "sync:test"
    assert schedule["interval_minutes"] == 60
    assert schedule["interval_market_open_minutes"] == 15
    assert schedule["market_timing"] == 1
    assert schedule["description"] == "Test sync job"
    assert schedule["category"] == "sync"


@pytest.mark.asyncio
async def test_upsert_job_schedule_updates_existing(db):
    """upsert_job_schedule should update existing schedule."""
    # Insert initial
    await db.upsert_job_schedule(
        job_type="sync:test",
        interval_minutes=30,
        description="Original description",
        category="sync",
    )

    # Update
    await db.upsert_job_schedule(
        job_type="sync:test",
        interval_minutes=60,
        description="Updated description",
    )

    schedule = await db.get_job_schedule("sync:test")
    assert schedule["interval_minutes"] == 60
    assert schedule["description"] == "Updated description"
    assert schedule["category"] == "sync"  # Not updated, should remain


@pytest.mark.asyncio
async def test_upsert_job_schedule_sets_updated_at(db):
    """upsert_job_schedule should update updated_at timestamp."""
    # Insert initial
    await db.upsert_job_schedule(
        job_type="sync:test",
        interval_minutes=30,
    )
    first = await db.get_job_schedule("sync:test")
    first_updated = first["updated_at"]

    # Small delay
    import asyncio

    await asyncio.sleep(0.01)

    # Update
    await db.upsert_job_schedule(
        job_type="sync:test",
        interval_minutes=60,
    )
    second = await db.get_job_schedule("sync:test")
    second_updated = second["updated_at"]

    assert second_updated >= first_updated


@pytest.mark.asyncio
async def test_upsert_job_schedule_partial_update(db):
    """upsert_job_schedule should only update provided fields."""
    # Insert initial with all fields
    await db.upsert_job_schedule(
        job_type="sync:test",
        interval_minutes=30,
        interval_market_open_minutes=5,
        market_timing=0,
        description="Original",
        category="sync",
    )

    # Update only interval_minutes
    await db.upsert_job_schedule(
        job_type="sync:test",
        interval_minutes=60,
    )

    schedule = await db.get_job_schedule("sync:test")
    assert schedule["interval_minutes"] == 60
    # Other fields unchanged
    assert schedule["interval_market_open_minutes"] == 5
    assert schedule["market_timing"] == 0
    assert schedule["description"] == "Original"
    assert schedule["category"] == "sync"


@pytest.mark.asyncio
async def test_seed_default_job_schedules_inserts_all(db):
    """seed_default_job_schedules should insert all default schedules."""
    await db.seed_default_job_schedules()

    schedules = await db.get_job_schedules()
    assert len(schedules) == 15

    # Check some specific defaults
    portfolio = await db.get_job_schedule("sync:portfolio")
    assert portfolio is not None
    assert portfolio["interval_minutes"] == 30
    assert portfolio["interval_market_open_minutes"] == 5
    assert portfolio["category"] == "sync"

    # Check trading:rebalance is now included
    rebalance = await db.get_job_schedule("trading:rebalance")
    assert rebalance is not None
    assert rebalance["category"] == "trading"


@pytest.mark.asyncio
async def test_seed_default_job_schedules_idempotent(db):
    """seed_default_job_schedules should not duplicate on second call."""
    await db.seed_default_job_schedules()
    first_count = len(await db.get_job_schedules())

    await db.seed_default_job_schedules()
    second_count = len(await db.get_job_schedules())

    assert second_count == first_count


@pytest.mark.asyncio
async def test_get_last_job_completion_by_prefix(db):
    """get_last_job_completion_by_prefix should find most recent matching job."""
    now = int(datetime.now().timestamp())

    # Insert job history with different job_ids but same prefix
    await db.conn.execute(
        """INSERT INTO job_history
           (job_id, job_type, status, duration_ms, executed_at)
           VALUES (?, ?, 'completed', 100, ?)""",
        ("sync:prices:AAPL.US", "sync:prices", now - 3600),  # 1 hour ago
    )
    await db.conn.execute(
        """INSERT INTO job_history
           (job_id, job_type, status, duration_ms, executed_at)
           VALUES (?, ?, 'completed', 100, ?)""",
        ("sync:prices:MSFT.US", "sync:prices", now - 1800),  # 30 min ago
    )
    await db.conn.execute(
        """INSERT INTO job_history
           (job_id, job_type, status, duration_ms, executed_at)
           VALUES (?, ?, 'completed', 100, ?)""",
        ("sync:prices:GOOG.US", "sync:prices", now - 600),  # 10 min ago (most recent)
    )
    await db.conn.commit()

    last = await db.get_last_job_completion_by_prefix("sync:prices")
    assert last is not None
    # Should return the most recent (GOOG.US, 10 min ago)
    assert (now - last.timestamp()) < 700  # Within ~11 minutes


@pytest.mark.asyncio
async def test_get_last_job_completion_by_prefix_no_match(db):
    """get_last_job_completion_by_prefix should return None when no matching jobs."""
    last = await db.get_last_job_completion_by_prefix("nonexistent:job")
    assert last is None


@pytest.mark.asyncio
async def test_get_job_history_for_type(db):
    """get_job_history_for_type should return history for job type prefix."""
    now = int(datetime.now().timestamp())

    # Insert job history
    await db.conn.execute(
        """INSERT INTO job_history
           (job_id, job_type, status, error, duration_ms, executed_at)
           VALUES (?, ?, 'completed', NULL, 100, ?)""",
        ("sync:portfolio", "sync:portfolio", now - 3600),
    )
    await db.conn.execute(
        """INSERT INTO job_history
           (job_id, job_type, status, error, duration_ms, executed_at)
           VALUES (?, ?, 'failed', 'Error message', 50, ?)""",
        ("sync:portfolio", "sync:portfolio", now - 1800),
    )
    await db.conn.execute(
        """INSERT INTO job_history
           (job_id, job_type, status, error, duration_ms, executed_at)
           VALUES (?, ?, 'completed', NULL, 200, ?)""",
        ("analytics:correlation", "analytics:correlation", now - 600),
    )
    await db.conn.commit()

    history = await db.get_job_history_for_type("sync:portfolio")
    assert len(history) == 2
    assert history[0]["job_id"] == "sync:portfolio"
    assert history[0]["status"] == "failed"  # Most recent first
    assert history[1]["status"] == "completed"


@pytest.mark.asyncio
async def test_get_job_history_for_type_respects_limit(db):
    """get_job_history_for_type should respect limit parameter."""
    now = int(datetime.now().timestamp())

    # Insert 5 job history entries
    for i in range(5):
        await db.conn.execute(
            """INSERT INTO job_history
               (job_id, job_type, status, duration_ms, executed_at)
               VALUES (?, ?, 'completed', 100, ?)""",
            ("sync:test", "sync:test", now - (i * 100)),
        )
    await db.conn.commit()

    history = await db.get_job_history_for_type("sync:test", limit=2)
    assert len(history) == 2


@pytest.mark.asyncio
async def test_get_job_history_for_type_with_prefix(db):
    """get_job_history_for_type should match prefix for parameterized jobs."""
    now = int(datetime.now().timestamp())

    # Insert parameterized job history
    await db.conn.execute(
        """INSERT INTO job_history
           (job_id, job_type, status, duration_ms, executed_at)
           VALUES (?, ?, 'completed', 100, ?)""",
        ("sync:prices:AAPL.US", "sync:prices", now - 3600),
    )
    await db.conn.execute(
        """INSERT INTO job_history
           (job_id, job_type, status, duration_ms, executed_at)
           VALUES (?, ?, 'completed', 150, ?)""",
        ("sync:prices:MSFT.US", "sync:prices", now - 1800),
    )
    await db.conn.commit()

    history = await db.get_job_history_for_type("sync:prices")
    assert len(history) == 2

    # Also test specific symbol
    history_aapl = await db.get_job_history_for_type("sync:prices:AAPL.US")
    assert len(history_aapl) == 1
    assert history_aapl[0]["job_id"] == "sync:prices:AAPL.US"
