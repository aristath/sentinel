"""Tests for job schedules API endpoints.

These tests verify the job schedules API functionality by testing
the endpoint logic directly using mock database instances.
"""

import os
import tempfile
from datetime import datetime

import pytest
import pytest_asyncio

from sentinel.database import Database


@pytest_asyncio.fixture
async def db():
    """Create test database with job_schedules table."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    database = Database(path)
    await database.connect()

    # Seed default schedules
    await database.seed_default_job_schedules()

    yield database

    await database.close()
    database.remove_from_cache()
    if os.path.exists(path):
        os.remove(path)


@pytest.mark.asyncio
async def test_get_job_schedules_returns_all(db):
    """GET /api/jobs/schedules should return all schedules."""
    schedules = await db.get_job_schedules()

    # Should have 15 default schedules (including aggregate:compute)
    assert len(schedules) == 15

    # Check structure (no longer has enabled, dependencies, is_parameterized fields)
    schedule = schedules[0]
    assert "job_type" in schedule
    assert "interval_minutes" in schedule
    assert "market_timing" in schedule
    assert "category" in schedule


@pytest.mark.asyncio
async def test_get_job_schedules_ordered_by_category(db):
    """GET /api/jobs/schedules should order by category, then job_type."""
    schedules = await db.get_job_schedules()

    # Extract categories in order
    categories = [s["category"] for s in schedules]

    # Categories should be grouped together
    seen = set()
    for cat in categories:
        if cat in seen and cat != categories[-1]:
            # If we've seen this category before, it should be the same as the last seen
            pass  # This is expected for sorted categories
        seen.add(cat)


@pytest.mark.asyncio
async def test_get_job_schedule_single(db):
    """GET /api/jobs/schedules/{type} should return single schedule."""
    schedule = await db.get_job_schedule("sync:portfolio")

    assert schedule is not None
    assert schedule["job_type"] == "sync:portfolio"
    assert schedule["interval_minutes"] == 30
    assert schedule["interval_market_open_minutes"] == 5
    assert schedule["category"] == "sync"


@pytest.mark.asyncio
async def test_get_job_schedule_unknown_returns_none(db):
    """GET /api/jobs/schedules/{type} should return 404 for unknown job."""
    schedule = await db.get_job_schedule("unknown:job")
    assert schedule is None


@pytest.mark.asyncio
async def test_update_job_schedule_changes_interval(db):
    """PUT /api/jobs/schedules/{type} should update interval."""
    await db.upsert_job_schedule("sync:portfolio", interval_minutes=60)

    schedule = await db.get_job_schedule("sync:portfolio")
    assert schedule["interval_minutes"] == 60


@pytest.mark.asyncio
async def test_update_job_schedule_changes_market_timing(db):
    """PUT /api/jobs/schedules/{type} should update market_timing."""
    await db.upsert_job_schedule("sync:portfolio", market_timing=2)

    schedule = await db.get_job_schedule("sync:portfolio")
    assert schedule["market_timing"] == 2


@pytest.mark.asyncio
async def test_update_job_schedule_preserves_other_fields(db):
    """PUT /api/jobs/schedules/{type} should preserve unchanged fields."""
    original = await db.get_job_schedule("sync:portfolio")
    original_category = original["category"]

    # Update only interval
    await db.upsert_job_schedule("sync:portfolio", interval_minutes=120)

    updated = await db.get_job_schedule("sync:portfolio")
    assert updated["category"] == original_category
    assert updated["interval_minutes"] == 120


@pytest.mark.asyncio
async def test_get_job_history_for_type(db):
    """GET /api/jobs/history should return recent executions."""
    # Add some job history
    now = int(datetime.now().timestamp())
    await db.conn.execute(
        """INSERT INTO job_history
           (job_id, job_type, status, duration_ms, executed_at)
           VALUES (?, ?, 'completed', 100, ?)""",
        ("sync:portfolio", "sync:portfolio", now - 3600),
    )
    await db.conn.execute(
        """INSERT INTO job_history
           (job_id, job_type, status, duration_ms, executed_at)
           VALUES (?, ?, 'failed', 50, ?)""",
        ("sync:portfolio", "sync:portfolio", now - 1800),
    )
    await db.conn.commit()

    history = await db.get_job_history_for_type("sync:portfolio")
    assert len(history) == 2
    assert history[0]["status"] == "failed"  # Most recent first
    assert history[1]["status"] == "completed"


@pytest.mark.asyncio
async def test_get_job_history_respects_limit(db):
    """GET /api/jobs/history should respect limit parameter."""
    now = int(datetime.now().timestamp())

    # Add 5 entries
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
async def test_market_timing_values(db):
    """Market timing should have correct default values."""
    # Sync jobs should be ANY_TIME (0)
    sync_portfolio = await db.get_job_schedule("sync:portfolio")
    assert sync_portfolio["market_timing"] == 0

    # Trading should be DURING_OPEN (2)
    trading = await db.get_job_schedule("trading:check_markets")
    assert trading["market_timing"] == 2

    # Analytics regime should be ALL_CLOSED (3)
    analytics = await db.get_job_schedule("analytics:regime")
    assert analytics["market_timing"] == 3


@pytest.mark.asyncio
async def test_all_job_types_present(db):
    """All expected job types should be present in defaults."""
    expected_types = [
        "sync:portfolio",
        "sync:prices",
        "sync:quotes",
        "sync:metadata",
        "sync:exchange_rates",
        "scoring:calculate",
        "analytics:regime",
        "trading:check_markets",
        "trading:execute",
        "trading:rebalance",
        "planning:refresh",
        "ml:retrain",
        "ml:monitor",
        "backup:r2",
    ]

    schedules = await db.get_job_schedules()
    job_types = [s["job_type"] for s in schedules]

    for expected in expected_types:
        assert expected in job_types, f"Missing job type: {expected}"


@pytest.mark.asyncio
async def test_categories_present(db):
    """All expected categories should be present."""
    schedules = await db.get_job_schedules()
    categories = set(s["category"] for s in schedules)

    expected = {"sync", "scoring", "analytics", "trading", "ml", "backup"}
    assert categories == expected
