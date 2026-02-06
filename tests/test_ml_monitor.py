"""Test ML monitor module - per-model, per-symbol tracking."""

import os
import tempfile
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio

from sentinel.database import Database
from sentinel_ml.database.ml import MLDatabase
from sentinel_ml.ml_monitor import MLMonitor


@pytest_asyncio.fixture
async def db():
    """Create test database."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    database = Database(path)
    await database.connect()
    yield database
    await database.close()
    database.remove_from_cache()
    if os.path.exists(path):
        os.unlink(path)


@pytest_asyncio.fixture
async def ml_db():
    """Create test ML database."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    database = MLDatabase(path)
    await database.connect()
    yield database
    await database.close()
    database.remove_from_cache()
    if os.path.exists(path):
        os.unlink(path)
    for ext in ["-wal", "-shm"]:
        wal_path = path + ext
        if os.path.exists(wal_path):
            os.unlink(wal_path)


@pytest.fixture
def monitor():
    """Create monitor instance with mocked dbs."""
    m = MLMonitor()
    m.db = AsyncMock()
    m.db.connect = AsyncMock()
    m.ml_db = AsyncMock()
    m.ml_db.connect = AsyncMock()
    return m


@pytest.mark.asyncio
async def test_track_performance_no_predictions(monitor):
    """Test tracking when no predictions exist."""
    monitor.settings = AsyncMock()
    monitor.settings.get = AsyncMock(return_value=14)

    # No predictions in any model type
    cursor_mock = AsyncMock()
    cursor_mock.fetchall = AsyncMock(return_value=[])
    monitor.ml_db.conn = AsyncMock()
    monitor.ml_db.conn.execute = AsyncMock(return_value=cursor_mock)

    result = await monitor.track_performance()

    assert result["status"] == "success"
    assert result["total_predictions_evaluated"] == 0
    assert result["symbols_evaluated"] == 0
    assert result["drift_detected"] == []


@pytest.mark.asyncio
async def test_get_actual_return_with_timestamp(monitor):
    """Test actual return calculation using unix timestamp."""
    monitor.db = AsyncMock()
    monitor.db.get_prices = AsyncMock(
        return_value=[
            {"date": "2024-01-15", "close": 110.0},
            {"date": "2024-01-01", "close": 100.0},
        ]
    )

    # 1704067200 = 2024-01-01T00:00:00 UTC
    result = await monitor._get_actual_return("TEST", 1704067200, 14)

    assert result is not None
    assert abs(result - 0.10) < 0.001


@pytest.mark.asyncio
async def test_get_actual_return_no_prices(monitor):
    """Test actual return when no prices found."""
    monitor.db = AsyncMock()
    monitor.db.get_prices = AsyncMock(return_value=[])

    result = await monitor._get_actual_return("TEST", 1704067200, 14)
    assert result is None


@pytest.mark.asyncio
async def test_check_symbol_drift_insufficient_history(db, ml_db):
    """Test drift detection with insufficient history."""
    monitor = MLMonitor(db=db, ml_db=ml_db)

    # Only 3 records (< 5 required)
    for i in range(3):
        await ml_db.conn.execute(
            "INSERT INTO ml_performance_xgboost "
            "(symbol, tracked_at, mean_absolute_error, root_mean_squared_error, predictions_evaluated) "
            "VALUES (?, ?, ?, ?, ?)",
            ("TEST", 1704067200 + i * 86400, 0.02, 0.03, 10),
        )
    await ml_db.conn.commit()

    result = await monitor._check_symbol_drift("xgboost", "TEST", 0.05)
    assert result is False


@pytest.mark.asyncio
async def test_check_symbol_drift_normal(db, ml_db):
    """Test drift detection with normal error."""
    monitor = MLMonitor(db=db, ml_db=ml_db)

    for i in range(15):
        await ml_db.conn.execute(
            "INSERT INTO ml_performance_xgboost "
            "(symbol, tracked_at, mean_absolute_error, root_mean_squared_error, predictions_evaluated) "
            "VALUES (?, ?, ?, ?, ?)",
            ("TEST", 1704067200 + i * 86400, 0.02, 0.03, 10),
        )
    await ml_db.conn.commit()

    # Current error within normal range
    result = await monitor._check_symbol_drift("xgboost", "TEST", 0.021)
    assert result is False


@pytest.mark.asyncio
async def test_check_symbol_drift_detected(db, ml_db):
    """Test drift detection with abnormal error."""
    monitor = MLMonitor(db=db, ml_db=ml_db)

    for i in range(15):
        await ml_db.conn.execute(
            "INSERT INTO ml_performance_xgboost "
            "(symbol, tracked_at, mean_absolute_error, root_mean_squared_error, predictions_evaluated) "
            "VALUES (?, ?, ?, ?, ?)",
            ("TEST", 1704067200 + i * 86400, 0.015 + (i % 5) * 0.002, 0.025, 10),
        )
    await ml_db.conn.commit()

    # Current MAE much higher than historical
    result = await monitor._check_symbol_drift("xgboost", "TEST", 0.10)
    assert result is True


@pytest.mark.asyncio
async def test_evaluate_model_symbol(db, ml_db):
    """Test evaluating predictions for a single model type and symbol."""
    monitor = MLMonitor(db=db, ml_db=ml_db)
    monitor.db = AsyncMock()
    monitor.db.get_prices = AsyncMock(
        side_effect=[
            [
                {"date": "2024-01-15", "close": 105.0},
                {"date": "2024-01-01", "close": 100.0},
            ],
            [
                {"date": "2024-01-16", "close": 105.0},
                {"date": "2024-01-02", "close": 100.0},
            ],
        ]
    )

    # Insert test predictions
    ts1 = 1704067200  # 2024-01-01
    ts2 = 1704153600  # 2024-01-02
    await ml_db.conn.execute(
        "INSERT INTO ml_predictions_xgboost "
        "(prediction_id, symbol, predicted_at, predicted_return, ml_score, inference_time_ms) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        ("pred1", "TEST", ts1, 0.05, 0.75, 5.0),
    )
    await ml_db.conn.execute(
        "INSERT INTO ml_predictions_xgboost "
        "(prediction_id, symbol, predicted_at, predicted_return, ml_score, inference_time_ms) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        ("pred2", "TEST", ts2, 0.03, 0.65, 5.0),
    )
    await ml_db.conn.commit()

    result = await monitor._evaluate_model_symbol("xgboost", "TEST", ts1 - 1, ts2 + 1, 14)

    assert result is not None
    assert "mean_absolute_error" in result
    assert "root_mean_squared_error" in result
    assert "prediction_bias" in result
    assert result["predictions_evaluated"] == 2


@pytest.mark.asyncio
async def test_generate_report_no_data(db, ml_db):
    """Test report generation with no data."""
    monitor = MLMonitor(db=db, ml_db=ml_db)

    result = await monitor.generate_report()

    assert "ML Performance Report" in result
    assert "No data" in result


@pytest.mark.asyncio
async def test_generate_report_with_data(db, ml_db):
    """Test report generation with performance data."""
    monitor = MLMonitor(db=db, ml_db=ml_db)

    # Insert performance data for xgboost
    await ml_db.conn.execute(
        "INSERT INTO ml_performance_xgboost "
        "(symbol, tracked_at, mean_absolute_error, root_mean_squared_error, "
        "prediction_bias, predictions_evaluated) VALUES (?, ?, ?, ?, ?, ?)",
        ("AAPL", 1704067200, 0.025, 0.035, 0.002, 50),
    )
    await ml_db.conn.commit()

    result = await monitor.generate_report()

    assert "ML Performance Report" in result
    assert "xgboost" in result
    assert "1 symbols" in result


@pytest.mark.asyncio
async def test_track_symbol_performance(db, ml_db):
    """Test tracking performance for a single symbol across all models."""
    monitor = MLMonitor(db=db, ml_db=ml_db)
    monitor.db = AsyncMock()
    monitor.db.connect = AsyncMock()
    monitor.db.get_prices = AsyncMock(return_value=[])
    monitor.settings = AsyncMock()
    monitor.settings.get = AsyncMock(return_value=14)

    # No predictions exist, should return None
    result = await monitor.track_symbol_performance("TEST")
    assert result is None
