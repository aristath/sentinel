"""Test ML retrainer module - per-symbol models."""

import pytest
import numpy as np
import pandas as pd
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from sentinel.ml_retrainer import MLRetrainer
from sentinel.ml_features import NUM_FEATURES


@pytest.fixture
def retrainer():
    """Create retrainer instance."""
    return MLRetrainer()


@pytest.fixture
def sample_training_data():
    """Generate sample training data for a symbol."""
    n = 200
    np.random.seed(42)

    data = []
    for i in range(n):
        row = {
            'sample_id': f'sample_{i}',
            'symbol': 'TEST',
            'sample_date': f'2024-{(i % 12) + 1:02d}-{(i % 28) + 1:02d}',
            'return_1d': np.random.randn() * 0.02,
            'return_5d': np.random.randn() * 0.05,
            'return_20d': np.random.randn() * 0.10,
            'return_60d': np.random.randn() * 0.15,
            'price_normalized': np.random.randn() * 0.1,
            'volatility_10d': 0.02 + np.random.rand() * 0.02,
            'volatility_30d': 0.02 + np.random.rand() * 0.02,
            'atr_14d': 0.02 + np.random.rand() * 0.02,
            'volume_normalized': 0.5 + np.random.rand(),
            'volume_trend': np.random.randn() * 0.1,
            'rsi_14': 0.3 + np.random.rand() * 0.4,
            'macd': np.random.randn() * 0.05,
            'bollinger_position': np.random.rand(),
            'wavelet_d1': 0.3 + np.random.rand() * 0.4,
            'wavelet_d4': 0.3 + np.random.rand() * 0.4,
            'sentiment_score': 0.5,
            'spy_return_20d': np.random.randn() * 0.05,
            'vix_level': 0.3 + np.random.rand() * 0.4,
            'market_regime': np.random.choice([0, 1, 2]),
            'sector_relative_strength': np.random.randn() * 0.05,
            'future_return': np.random.randn() * 0.05,
        }
        data.append(row)

    return data


@pytest.mark.asyncio
async def test_load_training_data_for_symbol(retrainer, sample_training_data):
    """Test loading training data for a specific symbol."""
    retrainer.db = AsyncMock()
    retrainer.db.connect = AsyncMock()
    retrainer.db.conn = AsyncMock()

    cursor_mock = AsyncMock()
    cursor_mock.fetchall = AsyncMock(return_value=sample_training_data)
    retrainer.db.conn.execute = AsyncMock(return_value=cursor_mock)

    X, y = await retrainer._load_training_data('TEST')

    assert X.shape[0] == len(sample_training_data)
    assert X.shape[1] == NUM_FEATURES
    assert len(y) == len(sample_training_data)


@pytest.mark.asyncio
async def test_load_training_data_empty(retrainer):
    """Test loading training data when empty."""
    retrainer.db = AsyncMock()
    retrainer.db.conn = AsyncMock()

    cursor_mock = AsyncMock()
    cursor_mock.fetchall = AsyncMock(return_value=[])
    retrainer.db.conn.execute = AsyncMock(return_value=cursor_mock)

    X, y = await retrainer._load_training_data('TEST')

    assert len(X) == 0
    assert len(y) == 0


@pytest.mark.asyncio
async def test_get_symbols_with_sufficient_data(retrainer):
    """Test finding symbols with sufficient training samples."""
    retrainer.db = AsyncMock()
    retrainer.db.conn = AsyncMock()

    cursor_mock = AsyncMock()
    cursor_mock.fetchall = AsyncMock(return_value=[
        {'symbol': 'AAPL', 'sample_count': 500},
        {'symbol': 'MSFT', 'sample_count': 300},
        {'symbol': 'GOOG', 'sample_count': 150},
    ])
    retrainer.db.conn.execute = AsyncMock(return_value=cursor_mock)

    result = await retrainer._get_symbols_with_sufficient_data(100)

    assert 'AAPL' in result
    assert 'MSFT' in result
    assert 'GOOG' in result
    assert result['AAPL'] == 500


@pytest.mark.asyncio
async def test_get_sample_count(retrainer):
    """Test getting sample count for a symbol."""
    retrainer.db = AsyncMock()
    retrainer.db.conn = AsyncMock()

    cursor_mock = AsyncMock()
    cursor_mock.fetchone = AsyncMock(return_value={'count': 250})
    retrainer.db.conn.execute = AsyncMock(return_value=cursor_mock)

    count = await retrainer._get_sample_count('TEST')

    assert count == 250


@pytest.mark.asyncio
async def test_retrain_no_symbols(retrainer):
    """Test retraining when no symbols have sufficient data."""
    retrainer.db = AsyncMock()
    retrainer.db.connect = AsyncMock()
    retrainer.db.conn = AsyncMock()
    retrainer.settings = AsyncMock()
    retrainer.settings.get = AsyncMock(return_value=100)  # min_samples

    # Mock trainer
    retrainer.trainer = AsyncMock()
    retrainer.trainer.generate_incremental_samples = AsyncMock(return_value=pd.DataFrame())

    # No symbols with sufficient data
    cursor_mock = AsyncMock()
    cursor_mock.fetchall = AsyncMock(return_value=[])
    retrainer.db.conn.execute = AsyncMock(return_value=cursor_mock)

    result = await retrainer.retrain()

    assert result['status'] == 'skipped'
    assert 'No symbols with sufficient training data' in result['reason']


@pytest.mark.asyncio
async def test_retrain_symbol_insufficient_data(retrainer):
    """Test retraining a single symbol with insufficient data."""
    retrainer.db = AsyncMock()
    retrainer.db.connect = AsyncMock()
    retrainer.db.conn = AsyncMock()
    retrainer.settings = AsyncMock()
    retrainer.settings.get = AsyncMock(return_value=100)  # min_samples

    # Only 50 samples
    cursor_mock = AsyncMock()
    cursor_mock.fetchone = AsyncMock(return_value={'count': 50})
    retrainer.db.conn.execute = AsyncMock(return_value=cursor_mock)

    result = await retrainer.retrain_symbol('TEST')

    assert result is None


@pytest.mark.asyncio
async def test_update_model_record(retrainer):
    """Test updating model record in database."""
    retrainer.db = AsyncMock()
    retrainer.db.conn = AsyncMock()
    retrainer.db.conn.execute = AsyncMock()
    retrainer.db.conn.commit = AsyncMock()

    metrics = {
        'ensemble_val_rmse': 0.03,
        'ensemble_val_mae': 0.02,
        'ensemble_val_r2': 0.65,
    }

    await retrainer._update_model_record('TEST', 200, metrics)

    # Verify execute was called with INSERT OR REPLACE
    retrainer.db.conn.execute.assert_called_once()
    call_args = retrainer.db.conn.execute.call_args
    assert 'INSERT OR REPLACE INTO ml_models' in call_args[0][0]
    assert call_args[0][1][0] == 'TEST'  # symbol
    assert call_args[0][1][1] == 200  # training_samples


@pytest.mark.asyncio
async def test_get_model_status(retrainer):
    """Test getting status of all trained models."""
    retrainer.db = AsyncMock()
    retrainer.db.connect = AsyncMock()
    retrainer.db.conn = AsyncMock()

    cursor_mock = AsyncMock()
    cursor_mock.fetchall = AsyncMock(return_value=[
        {'symbol': 'AAPL', 'training_samples': 500, 'validation_rmse': 0.03},
        {'symbol': 'MSFT', 'training_samples': 300, 'validation_rmse': 0.04},
    ])
    retrainer.db.conn.execute = AsyncMock(return_value=cursor_mock)

    result = await retrainer.get_model_status()

    assert result['total_models'] == 2
    assert len(result['models']) == 2
