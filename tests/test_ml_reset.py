"""Tests for ML reset manager."""

import os
import tempfile
from typing import cast
from unittest.mock import patch

import pytest
import pytest_asyncio

from sentinel.database import Database
from sentinel_ml.clients.monolith_client import MonolithDataClient
from sentinel_ml.database.ml import MODEL_TYPES, MLDatabase
from sentinel_ml.ml_reset import (
    TOTAL_STEPS,
    MLResetManager,
    get_active_reset,
    get_reset_status,
    is_reset_in_progress,
    set_active_reset,
)


class FakeMonolithClient:
    """Test double for monolith internal ML endpoints."""

    def __init__(self, db: Database):
        self._db = db

    async def delete_aggregates(self) -> int:
        cursor = await self._db.conn.execute("DELETE FROM prices WHERE symbol LIKE '_AGG_%'")
        await self._db.conn.commit()
        return cursor.rowcount

    async def recompute_aggregates(self) -> dict:
        return {"country": 0, "industry": 0}


@pytest_asyncio.fixture
async def db():
    """Create test database with required tables."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    database = Database(path)
    await database.connect()

    yield database

    await database.close()
    database.remove_from_cache()
    if os.path.exists(path):
        os.remove(path)


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
        os.remove(path)
    for ext in ["-wal", "-shm"]:
        wal_path = path + ext
        if os.path.exists(wal_path):
            os.unlink(wal_path)


@pytest.fixture
def manager(db, ml_db):
    """Create MLResetManager with test databases."""
    return MLResetManager(db=db, ml_db=ml_db, monolith_client=cast(MonolithDataClient, FakeMonolithClient(db)))


@pytest.mark.asyncio
async def test_delete_aggregates_removes_all_agg_symbols(db, manager):
    """Aggregate deletion uses monolith internal endpoint contract."""
    # Setup: insert aggregate prices
    await db.conn.execute(
        "INSERT INTO prices (symbol, date, open, high, low, close, volume) VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("_AGG_COUNTRY_US", "2024-01-01", 100, 100, 100, 100, 0),
    )
    await db.conn.execute(
        "INSERT INTO prices (symbol, date, open, high, low, close, volume) VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("_AGG_INDUSTRY_TECH", "2024-01-01", 100, 100, 100, 100, 0),
    )
    await db.conn.commit()

    # Verify setup
    cursor = await db.conn.execute("SELECT COUNT(*) as cnt FROM prices WHERE symbol LIKE '_AGG_%'")
    row = await cursor.fetchone()
    assert row["cnt"] == 2

    # Act
    deleted = await manager.delete_aggregates()

    # Assert
    assert deleted == 2
    cursor = await db.conn.execute("SELECT COUNT(*) as cnt FROM prices WHERE symbol LIKE '_AGG_%'")
    row = await cursor.fetchone()
    assert row["cnt"] == 0


@pytest.mark.asyncio
async def test_delete_aggregates_preserves_regular_prices(db, manager):
    """Verify regular security prices are not deleted."""
    # Setup: insert both aggregate and regular prices
    await db.conn.execute(
        "INSERT INTO prices (symbol, date, open, high, low, close, volume) VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("_AGG_COUNTRY_US", "2024-01-01", 100, 100, 100, 100, 0),
    )
    await db.conn.execute(
        "INSERT INTO prices (symbol, date, open, high, low, close, volume) VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("AAPL", "2024-01-01", 150, 155, 149, 154, 1000000),
    )
    await db.conn.execute(
        "INSERT INTO prices (symbol, date, open, high, low, close, volume) VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("MSFT", "2024-01-01", 350, 355, 349, 354, 500000),
    )
    await db.conn.commit()

    # Act
    await manager.delete_aggregates()

    # Assert: regular prices still exist
    cursor = await db.conn.execute("SELECT COUNT(*) as cnt FROM prices WHERE symbol = 'AAPL'")
    row = await cursor.fetchone()
    assert row["cnt"] == 1

    cursor = await db.conn.execute("SELECT COUNT(*) as cnt FROM prices WHERE symbol = 'MSFT'")
    row = await cursor.fetchone()
    assert row["cnt"] == 1


@pytest.mark.asyncio
async def test_delete_training_data_clears_all_tables(ml_db, manager):
    """Verify all ML tables in ml.db are emptied."""
    # Setup: insert data into ML tables via ml_db
    await ml_db.conn.execute(
        """INSERT INTO ml_training_samples
           (sample_id, symbol, sample_date, future_return, prediction_horizon_days, created_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        ("sample1", "AAPL", 1704067200, 0.05, 14, 1704067200),
    )
    for mt in MODEL_TYPES:
        await ml_db.conn.execute(
            f"INSERT INTO ml_predictions_{mt} "  # noqa: S608
            "(prediction_id, symbol, predicted_at, predicted_return, ml_score, inference_time_ms) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (f"pred_{mt}", "AAPL", 1704067200, 0.03, 0.65, 5.0),
        )
        await ml_db.conn.execute(
            f"INSERT INTO ml_models_{mt} "  # noqa: S608
            "(symbol, training_samples, validation_rmse, validation_mae, validation_r2, last_trained_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            ("AAPL", 100, 0.03, 0.02, 0.65, 1704067200),
        )
        await ml_db.conn.execute(
            f"INSERT INTO ml_performance_{mt} "  # noqa: S608
            "(symbol, tracked_at, mean_absolute_error, root_mean_squared_error, predictions_evaluated) "
            "VALUES (?, ?, ?, ?, ?)",
            ("AAPL", 1704067200, 0.02, 0.03, 10),
        )
    await ml_db.conn.execute(
        "INSERT INTO regime_states (symbol, date, regime, regime_name, confidence) VALUES (?, ?, ?, ?, ?)",
        ("AAPL", "2025-01-01", 0, "Bull", 0.9),
    )
    await ml_db.conn.execute(
        "INSERT INTO regime_models (model_id, symbols, n_states, trained_at, model_params) VALUES (?, ?, ?, ?, ?)",
        ("hmm_test", '["AAPL"]', 3, "2025-01-01T00:00:00+00:00", "abc"),
    )
    await ml_db.conn.commit()

    # Act
    await manager.delete_training_data()

    # Assert: all tables are empty
    cursor = await ml_db.conn.execute("SELECT COUNT(*) as cnt FROM ml_training_samples")
    row = await cursor.fetchone()
    assert row["cnt"] == 0, "ml_training_samples should be empty"

    for mt in MODEL_TYPES:
        for table in [f"ml_predictions_{mt}", f"ml_models_{mt}", f"ml_performance_{mt}"]:
            cursor = await ml_db.conn.execute(f"SELECT COUNT(*) as cnt FROM {table}")  # noqa: S608
            row = await cursor.fetchone()
            assert row["cnt"] == 0, f"{table} should be empty"

    for table in ["regime_states", "regime_models"]:
        cursor = await ml_db.conn.execute(f"SELECT COUNT(*) as cnt FROM {table}")  # noqa: S608
        row = await cursor.fetchone()
        assert row["cnt"] == 0, f"{table} should be empty"


@pytest.mark.asyncio
async def test_delete_model_files_removes_directory_contents(manager, tmp_path):
    """Verify model files are deleted but directory recreated."""
    # Setup: create model directory with files
    model_dir = tmp_path / "ml_models"
    model_dir.mkdir()
    (model_dir / "AAPL").mkdir()
    (model_dir / "AAPL" / "model.pt").write_text("fake model")
    (model_dir / "MSFT").mkdir()
    (model_dir / "MSFT" / "model.pt").write_text("fake model")

    # Patch DATA_DIR
    with patch("sentinel_ml.ml_reset.DATA_DIR", tmp_path):
        await manager.delete_model_files()

    # Assert: directory exists but is empty
    assert model_dir.exists()
    assert list(model_dir.iterdir()) == []


@pytest.mark.asyncio
async def test_delete_model_files_handles_nonexistent_directory(manager, tmp_path):
    """Verify delete_model_files works when directory doesn't exist."""
    model_dir = tmp_path / "ml_models"
    assert not model_dir.exists()

    with patch("sentinel_ml.ml_reset.DATA_DIR", tmp_path):
        await manager.delete_model_files()

    # Directory should be created
    assert model_dir.exists()


@pytest.mark.asyncio
async def test_reset_all_orchestrates_full_pipeline(db, ml_db, manager):
    """Verify reset_all calls all steps in correct order."""
    # Mock internal methods to track call order
    call_order = []

    async def mock_delete_agg():
        call_order.append("delete_aggregates")
        return 5

    async def mock_delete_training():
        call_order.append("delete_training_data")

    async def mock_delete_files():
        call_order.append("delete_model_files")

    async def mock_recompute():
        call_order.append("recompute_aggregates")
        return {"country": 2, "industry": 3}

    async def mock_regenerate():
        call_order.append("regenerate_training_data")
        return 100

    async def mock_retrain():
        call_order.append("retrain_all_models")
        return {"symbols_trained": 5, "symbols_skipped": 1}

    manager.delete_aggregates = mock_delete_agg
    manager.delete_training_data = mock_delete_training
    manager.delete_model_files = mock_delete_files
    manager._recompute_aggregates = mock_recompute
    manager._regenerate_training_data = mock_regenerate
    manager._retrain_all_models = mock_retrain

    # Act
    result = await manager.reset_all()

    # Assert: correct order
    expected_order = [
        "delete_aggregates",
        "delete_training_data",
        "delete_model_files",
        "recompute_aggregates",
        "regenerate_training_data",
        "retrain_all_models",
    ]
    assert call_order == expected_order

    # Assert: result structure
    assert result["status"] == "completed"
    assert result["aggregates_deleted"] == 5
    assert result["aggregates_computed"] == {"country": 2, "industry": 3}
    assert result["training_samples_generated"] == 100
    assert result["models_trained"] == 5
    assert result["models_skipped"] == 1


@pytest.mark.asyncio
async def test_delete_aggregates_returns_zero_when_no_aggregates(db, manager):
    """Verify delete_aggregates returns 0 when no aggregates exist."""
    # Insert only regular prices
    await db.conn.execute(
        "INSERT INTO prices (symbol, date, open, high, low, close, volume) VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("AAPL", "2024-01-01", 150, 155, 149, 154, 1000000),
    )
    await db.conn.commit()

    deleted = await manager.delete_aggregates()

    assert deleted == 0


# Tests for global state functions


def test_is_reset_in_progress_false_by_default():
    """Verify is_reset_in_progress returns False when no reset is active."""
    set_active_reset(None)
    assert is_reset_in_progress() is False


def test_is_reset_in_progress_true_when_set():
    """Verify is_reset_in_progress returns True when a reset is active."""
    manager = MLResetManager()
    set_active_reset(manager)
    try:
        assert is_reset_in_progress() is True
    finally:
        set_active_reset(None)


def test_get_active_reset_returns_manager():
    """Verify get_active_reset returns the active manager."""
    manager = MLResetManager()
    set_active_reset(manager)
    try:
        assert get_active_reset() is manager
    finally:
        set_active_reset(None)


def test_set_active_reset_clears_state():
    """Verify set_active_reset(None) clears the state."""
    manager = MLResetManager()
    set_active_reset(manager)
    set_active_reset(None)
    assert get_active_reset() is None
    assert is_reset_in_progress() is False


def test_get_reset_status_when_not_running():
    """Verify get_reset_status returns running=False when no reset is active."""
    set_active_reset(None)
    status = get_reset_status()
    assert status["running"] is False
    assert "current_step" not in status


def test_get_reset_status_when_running():
    """Verify get_reset_status returns progress info when reset is active."""
    manager = MLResetManager()
    manager._set_step(3, "Processing...")
    set_active_reset(manager)
    try:
        status = get_reset_status()
        assert status["running"] is True
        assert status["current_step"] == 3
        assert status["total_steps"] == TOTAL_STEPS
        assert status["step_name"] == "Deleting model files"
        assert status["details"] == "Processing..."
    finally:
        set_active_reset(None)


def test_get_reset_status_includes_model_progress():
    """Verify get_reset_status includes model training progress in step 6."""
    manager = MLResetManager()
    manager._set_step(6)
    manager._on_model_progress(5, 20, "AAPL")
    set_active_reset(manager)
    try:
        status = get_reset_status()
        assert status["running"] is True
        assert status["current_step"] == 6
        assert status["models_current"] == 5
        assert status["models_total"] == 20
        assert status["current_symbol"] == "AAPL"
    finally:
        set_active_reset(None)


def test_set_step_updates_progress():
    """Verify _set_step updates all progress fields."""
    manager = MLResetManager()
    assert manager.current_step == 0

    manager._set_step(5, "Generating for AAPL")

    assert manager.current_step == 5
    assert manager.step_name == "Generating training data"
    assert manager.step_details == "Generating for AAPL"


def test_on_model_progress_updates_training_state():
    """Verify _on_model_progress updates model training state."""
    manager = MLResetManager()
    manager._set_step(6)

    manager._on_model_progress(10, 50, "MSFT")

    assert manager.models_current == 10
    assert manager.models_total == 50
    assert manager.current_symbol == "MSFT"
    assert "MSFT" in manager.step_details
    assert "10/50" in manager.step_details
