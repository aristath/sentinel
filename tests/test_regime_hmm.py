"""Tests for RegimeDetector as-of-date API (backfill support)."""

from unittest.mock import AsyncMock, MagicMock

import numpy as np
import pytest
import pytest_asyncio

from sentinel.database import Database
from sentinel.regime_hmm import RegimeDetector


@pytest_asyncio.fixture
async def temp_db():
    """Temporary database for regime_states tests."""
    import os
    import tempfile

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    db = Database(db_path)
    await db.connect()
    yield db
    await db.close()
    db.remove_from_cache()
    if os.path.exists(db_path):
        os.unlink(db_path)
    for ext in ["-wal", "-shm"]:
        wal_path = db_path + ext
        if os.path.exists(wal_path):
            os.unlink(wal_path)


@pytest.mark.asyncio
async def test_extract_features_as_of_returns_none_when_insufficient_data():
    """_extract_features_as_of returns None when fewer than 100 price rows."""
    detector = RegimeDetector(lookback_days=504)
    detector._db = AsyncMock()
    detector._db.connect = AsyncMock()
    detector._db.get_prices = AsyncMock(return_value=[{"close": 100.0 + i} for i in range(50)])

    result = await detector._extract_features_as_of("SYM", "2025-01-15")
    assert result is None
    detector._db.get_prices.assert_called_once_with("SYM", days=504, end_date="2025-01-15")


@pytest.mark.asyncio
async def test_extract_features_as_of_returns_same_shape_as_extract_features():
    """_extract_features_as_of returns feature matrix with same shape as _extract_features (truncated to date)."""
    detector = RegimeDetector(lookback_days=504)
    detector._db = AsyncMock()
    detector._db.connect = AsyncMock()
    # 150 rows so we have enough for features (100+), newest first
    prices = [{"close": 100.0 + 0.01 * (150 - i) + np.random.randn() * 0.5} for i in range(150)]
    detector._db.get_prices = AsyncMock(return_value=prices)

    result = await detector._extract_features_as_of("SYM", "2025-01-15")
    assert result is not None
    assert result.ndim == 2
    # returns, vol, rsi -> 3 columns; rows = len(returns) = len(prices)-1
    assert result.shape[1] == 3
    assert result.shape[0] == len(prices) - 1


@pytest.mark.asyncio
async def test_detect_regime_as_of_returns_dict():
    """detect_regime_as_of returns {regime, regime_name, confidence}."""
    detector = RegimeDetector(lookback_days=504)
    detector._db = AsyncMock()
    detector._db.connect = AsyncMock()
    detector._db.get_prices = AsyncMock(return_value=[{"close": 100.0 + 0.02 * i} for i in range(120)])
    detector._load_model = AsyncMock()

    # Mock model: predict/proba must return arrays with same rows as features (119)
    n_rows = 119  # len(prices) - 1
    detector._model = MagicMock()
    detector._model.predict = MagicMock(return_value=np.full(n_rows, 1))
    detector._model.predict_proba = MagicMock(return_value=np.tile([0.2, 0.7, 0.1], (n_rows, 1)))

    result = await detector.detect_regime_as_of("SYM", "2025-01-20")
    assert "regime" in result
    assert "regime_name" in result
    assert "confidence" in result
    assert result["regime"] == 1
    assert result["confidence"] == 0.7


@pytest.mark.asyncio
async def test_store_regime_state_for_date_writes_to_db(temp_db):
    """store_regime_state_for_date writes (symbol, date_str, ...) to regime_states."""
    detector = RegimeDetector()
    detector._db = temp_db
    await detector.store_regime_state_for_date("X", "2025-01-28", 0, "Bull", 0.85)

    cursor = await temp_db.conn.execute(
        "SELECT symbol, date, regime, regime_name, confidence FROM regime_states WHERE symbol = ?",
        ("X",),
    )
    row = await cursor.fetchone()
    assert row is not None
    assert dict(row)["symbol"] == "X"
    assert dict(row)["date"] == "2025-01-28"
    assert dict(row)["regime"] == 0
    assert dict(row)["regime_name"] == "Bull"
    assert dict(row)["confidence"] == 0.85


@pytest.mark.asyncio
async def test_store_regime_state_for_date_idempotent(temp_db):
    """store_regime_state_for_date is idempotent (INSERT OR REPLACE)."""
    detector = RegimeDetector()
    detector._db = temp_db
    await detector.store_regime_state_for_date("Y", "2025-01-29", 1, "Sideways", 0.6)
    await detector.store_regime_state_for_date("Y", "2025-01-29", 2, "Bear", 0.9)

    cursor = await temp_db.conn.execute(
        "SELECT regime, regime_name, confidence FROM regime_states WHERE symbol = ? AND date = ?",
        ("Y", "2025-01-29"),
    )
    row = await cursor.fetchone()
    assert row is not None
    assert dict(row)["regime"] == 2
    assert dict(row)["regime_name"] == "Bear"
    assert dict(row)["confidence"] == 0.9
