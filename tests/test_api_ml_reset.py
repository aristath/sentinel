"""Tests for ML reset API endpoint."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException


@pytest.mark.asyncio
async def test_endpoint_returns_started_status():
    """POST /api/ml/reset-and-retrain returns immediately with status."""
    from sentinel.api.routers.ml import reset_and_retrain

    with patch("sentinel.ml_reset.is_reset_in_progress", return_value=False):
        with patch("sentinel.api.routers.ml.asyncio.create_task", side_effect=lambda coro: coro.close()):
            result = await reset_and_retrain()

    assert result["status"] == "started"
    assert "background" in result["message"].lower()


@pytest.mark.asyncio
async def test_endpoint_triggers_background_task():
    """Verify background task is created for long-running operation."""
    from sentinel.api.routers.ml import reset_and_retrain

    captured_coro = None

    def capture_task(coro):
        nonlocal captured_coro
        captured_coro = coro
        mock_task = MagicMock()
        mock_task.done.return_value = False
        return mock_task

    with patch("sentinel.ml_reset.is_reset_in_progress", return_value=False):
        with patch("sentinel.api.routers.ml.asyncio.create_task", side_effect=capture_task):
            await reset_and_retrain()

    assert captured_coro is not None
    captured_coro.close()  # Prevent "coroutine was never awaited" warning


@pytest.mark.asyncio
async def test_endpoint_rejects_concurrent_requests():
    """Verify endpoint returns 409 when reset is already in progress."""
    from sentinel.api.routers.ml import reset_and_retrain

    with patch("sentinel.ml_reset.is_reset_in_progress", return_value=True):
        with pytest.raises(HTTPException) as exc_info:
            await reset_and_retrain()

    assert exc_info.value.status_code == 409
    assert "already in progress" in exc_info.value.detail


@pytest.mark.asyncio
async def test_run_reset_and_retrain_calls_manager():
    """Verify _run_reset_and_retrain calls MLResetManager.reset_all()."""
    from sentinel.api.routers.ml import _run_reset_and_retrain

    mock_manager = MagicMock()
    mock_manager.reset_all = AsyncMock(
        return_value={
            "status": "completed",
            "aggregates_deleted": 10,
            "models_trained": 5,
        }
    )

    with patch("sentinel.ml_reset.MLResetManager", return_value=mock_manager):
        with patch("sentinel.ml_reset.set_active_reset"):
            await _run_reset_and_retrain()

    mock_manager.reset_all.assert_called_once()


@pytest.mark.asyncio
async def test_run_reset_and_retrain_clears_state_on_success():
    """Verify active reset state is cleared after successful completion."""
    from sentinel.api.routers.ml import _run_reset_and_retrain

    mock_manager = MagicMock()
    mock_manager.reset_all = AsyncMock(return_value={"status": "completed"})

    set_calls = []

    def track_set(value):
        set_calls.append(value)

    with patch("sentinel.ml_reset.MLResetManager", return_value=mock_manager):
        with patch("sentinel.ml_reset.set_active_reset", side_effect=track_set):
            await _run_reset_and_retrain()

    # Should be called twice: once to set, once to clear
    assert len(set_calls) == 2
    assert set_calls[0] is mock_manager  # Set with manager
    assert set_calls[1] is None  # Cleared


@pytest.mark.asyncio
async def test_run_reset_and_retrain_clears_state_on_error():
    """Verify active reset state is cleared even if an error occurs."""
    from sentinel.api.routers.ml import _run_reset_and_retrain

    mock_manager = MagicMock()
    mock_manager.reset_all = AsyncMock(side_effect=Exception("Test error"))

    set_calls = []

    def track_set(value):
        set_calls.append(value)

    with patch("sentinel.ml_reset.MLResetManager", return_value=mock_manager):
        with patch("sentinel.ml_reset.set_active_reset", side_effect=track_set):
            await _run_reset_and_retrain()  # Should not raise

    # Should still clear state even on error
    assert len(set_calls) == 2
    assert set_calls[1] is None


@pytest.mark.asyncio
async def test_reset_status_endpoint_returns_status():
    """GET /api/ml/reset-status returns current status."""
    from sentinel.api.routers.ml import get_ml_reset_status

    mock_status = {
        "running": True,
        "current_step": 3,
        "total_steps": 6,
        "step_name": "Deleting model files",
        "details": "",
    }

    with patch("sentinel.ml_reset.get_reset_status", return_value=mock_status):
        result = await get_ml_reset_status()

    assert result["running"] is True
    assert result["current_step"] == 3
    assert result["total_steps"] == 6


@pytest.mark.asyncio
async def test_reset_status_endpoint_not_running():
    """GET /api/ml/reset-status returns running=False when idle."""
    from sentinel.api.routers.ml import get_ml_reset_status

    with patch("sentinel.ml_reset.get_reset_status", return_value={"running": False}):
        result = await get_ml_reset_status()

    assert result["running"] is False
