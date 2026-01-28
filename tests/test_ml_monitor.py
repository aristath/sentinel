"""Test ML monitor module - per-symbol tracking."""

import pytest
import numpy as np
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

from sentinel.ml_monitor import MLMonitor


@pytest.fixture
def monitor():
    """Create monitor instance."""
    return MLMonitor()


@pytest.mark.asyncio
async def test_track_performance_no_predictions(monitor):
    """Test tracking when no predictions exist."""
    monitor.db = AsyncMock()
    monitor.db.connect = AsyncMock()
    monitor.db.conn = AsyncMock()
    monitor.settings = AsyncMock()
    monitor.settings.get = AsyncMock(return_value=14)

    # No predictions
    cursor_mock = AsyncMock()
    cursor_mock.fetchall = AsyncMock(return_value=[])
    monitor.db.conn.execute = AsyncMock(return_value=cursor_mock)

    result = await monitor.track_performance()

    assert result['status'] == 'success'
    assert result['total_predictions_evaluated'] == 0
    assert result['symbols_evaluated'] == 0
    assert result['drift_detected'] == []


@pytest.mark.asyncio
async def test_get_actual_return(monitor):
    """Test actual return calculation."""
    monitor.db = AsyncMock()
    monitor.db.conn = AsyncMock()

    # Mock price lookups
    pred_price_row = {'close': 100.0}
    future_price_row = {'close': 110.0}

    cursor_mock = AsyncMock()
    cursor_mock.fetchone = AsyncMock(side_effect=[pred_price_row, future_price_row])
    monitor.db.conn.execute = AsyncMock(return_value=cursor_mock)

    result = await monitor._get_actual_return('TEST', '2024-01-01', 14)

    # 10% return
    assert result is not None
    assert abs(result - 0.10) < 0.001


@pytest.mark.asyncio
async def test_get_actual_return_invalid_date(monitor):
    """Test actual return with invalid date."""
    monitor.db = AsyncMock()

    result = await monitor._get_actual_return('TEST', 'invalid-date', 14)
    assert result is None


@pytest.mark.asyncio
async def test_get_actual_return_no_price(monitor):
    """Test actual return when price not found."""
    monitor.db = AsyncMock()
    monitor.db.conn = AsyncMock()

    cursor_mock = AsyncMock()
    cursor_mock.fetchone = AsyncMock(return_value=None)
    monitor.db.conn.execute = AsyncMock(return_value=cursor_mock)

    result = await monitor._get_actual_return('TEST', '2024-01-01', 14)
    assert result is None


@pytest.mark.asyncio
async def test_check_symbol_drift_insufficient_history(monitor):
    """Test drift detection with insufficient history for a symbol."""
    monitor.db = AsyncMock()
    monitor.db.conn = AsyncMock()

    # Less than 5 historical records
    cursor_mock = AsyncMock()
    cursor_mock.fetchall = AsyncMock(return_value=[
        {'mean_absolute_error': 0.02, 'root_mean_squared_error': 0.03}
        for _ in range(3)
    ])
    monitor.db.conn.execute = AsyncMock(return_value=cursor_mock)

    result = await monitor._check_symbol_drift('TEST', 0.05, 0.06)

    # Should not detect drift with insufficient history
    assert result is False


@pytest.mark.asyncio
async def test_check_symbol_drift_normal(monitor):
    """Test drift detection with normal error for a symbol."""
    monitor.db = AsyncMock()
    monitor.db.conn = AsyncMock()

    # Historical data with consistent error
    historical = [
        {'mean_absolute_error': 0.02, 'root_mean_squared_error': 0.03}
        for _ in range(15)
    ]
    cursor_mock = AsyncMock()
    cursor_mock.fetchall = AsyncMock(return_value=historical)
    monitor.db.conn.execute = AsyncMock(return_value=cursor_mock)

    # Current error within normal range
    result = await monitor._check_symbol_drift('TEST', 0.021, 0.031)
    assert result == False  # Use == instead of is for numpy bool compatibility


@pytest.mark.asyncio
async def test_check_symbol_drift_detected(monitor):
    """Test drift detection with abnormal error for a symbol."""
    monitor.db = AsyncMock()
    monitor.db.conn = AsyncMock()

    # Historical data with some variance (required to establish drift baseline)
    # Mean MAE ≈ 0.02, std ≈ 0.005
    historical = [
        {'mean_absolute_error': 0.015 + (i % 5) * 0.002, 'root_mean_squared_error': 0.025 + (i % 5) * 0.002}
        for i in range(15)
    ]
    cursor_mock = AsyncMock()
    cursor_mock.fetchall = AsyncMock(return_value=historical)
    monitor.db.conn.execute = AsyncMock(return_value=cursor_mock)

    # Current error much higher than historical (> baseline + 2σ)
    # With mean ≈ 0.02 and std ≈ 0.003, threshold is about 0.026
    # Current MAE of 0.10 should definitely trigger drift
    result = await monitor._check_symbol_drift('TEST', 0.10, 0.15)
    assert result == True  # Use == instead of is for numpy bool compatibility


@pytest.mark.asyncio
async def test_evaluate_symbol(monitor):
    """Test evaluating predictions for a single symbol."""
    monitor.db = AsyncMock()
    monitor.db.conn = AsyncMock()

    # Mock price lookups for actual return calculation
    async def mock_execute(query, params=None):
        cursor = AsyncMock()
        if 'close FROM prices' in query:
            # Return different prices based on query
            if 'date >=' in query and params:
                date_str = params[1]
                if '2024-01-01' in date_str:
                    cursor.fetchone = AsyncMock(return_value={'close': 100.0})
                else:
                    cursor.fetchone = AsyncMock(return_value={'close': 105.0})
        return cursor

    monitor.db.conn.execute = mock_execute

    predictions = [
        {'symbol': 'TEST', 'predicted_at': '2024-01-01T12:00:00', 'predicted_return': 0.05},
        {'symbol': 'TEST', 'predicted_at': '2024-01-02T12:00:00', 'predicted_return': 0.03},
    ]

    result = await monitor._evaluate_symbol('TEST', predictions, 14)

    assert result is not None
    assert 'mean_absolute_error' in result
    assert 'root_mean_squared_error' in result
    assert 'prediction_bias' in result
    assert result['predictions_evaluated'] == 2


@pytest.mark.asyncio
async def test_generate_report_no_data(monitor):
    """Test report generation with no data."""
    monitor.db = AsyncMock()
    monitor.db.connect = AsyncMock()
    monitor.db.conn = AsyncMock()

    cursor_mock = AsyncMock()
    cursor_mock.fetchone = AsyncMock(return_value={'symbols': None})
    cursor_mock.fetchall = AsyncMock(return_value=[])
    monitor.db.conn.execute = AsyncMock(return_value=cursor_mock)

    result = await monitor.generate_report()

    assert "No performance data available" in result


@pytest.mark.asyncio
async def test_generate_report_with_data(monitor):
    """Test report generation with data."""
    monitor.db = AsyncMock()
    monitor.db.connect = AsyncMock()
    monitor.db.conn = AsyncMock()

    # Mock aggregate query result
    agg_result = {
        'symbols': 5,
        'avg_mae': 0.025,
        'avg_rmse': 0.035,
        'avg_bias': 0.002,
        'drift_count': 1,
        'total_predictions': 100,
    }

    # Mock per-symbol query result
    symbol_stats = [
        {'symbol': 'AAPL', 'avg_mae': 0.03, 'avg_rmse': 0.04, 'drift_count': 1},
        {'symbol': 'MSFT', 'avg_mae': 0.02, 'avg_rmse': 0.03, 'drift_count': 0},
    ]

    # Mock drifting symbols
    drifting = [{'symbol': 'AAPL'}]

    call_count = [0]
    async def mock_execute(query, params=None):
        cursor = AsyncMock()
        call_count[0] += 1
        if call_count[0] == 1:
            cursor.fetchone = AsyncMock(return_value=agg_result)
        elif call_count[0] == 2:
            cursor.fetchall = AsyncMock(return_value=symbol_stats)
        else:
            cursor.fetchall = AsyncMock(return_value=drifting)
        return cursor

    monitor.db.conn.execute = mock_execute

    result = await monitor.generate_report()

    assert "ML Performance Report" in result
    assert "Symbols tracked: 5" in result
    assert "Mean MAE" in result
    assert "AAPL" in result
    assert "DRIFT" in result


@pytest.mark.asyncio
async def test_get_symbol_history(monitor):
    """Test getting performance history for a symbol."""
    monitor.db = AsyncMock()
    monitor.db.connect = AsyncMock()
    monitor.db.conn = AsyncMock()

    history = [
        {
            'tracked_at': '2024-01-15T12:00:00',
            'mean_absolute_error': 0.02,
            'root_mean_squared_error': 0.03,
            'prediction_bias': 0.001,
            'drift_detected': 0,
            'predictions_evaluated': 10,
        }
        for _ in range(5)
    ]

    cursor_mock = AsyncMock()
    cursor_mock.fetchall = AsyncMock(return_value=history)
    monitor.db.conn.execute = AsyncMock(return_value=cursor_mock)

    result = await monitor.get_symbol_history('TEST', days=30)

    assert len(result) == 5
    assert result[0]['mean_absolute_error'] == 0.02
