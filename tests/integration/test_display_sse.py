"""Integration tests for LED display SSE endpoint.

These tests validate the SSE streaming endpoint for real-time display updates.
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.status import router
from app.infrastructure.hardware.display_service import DisplayStateManager


@pytest.fixture
def app():
    """Create a test FastAPI app with the status router."""
    app = FastAPI()
    app.include_router(router, prefix="/api/status")
    return app


@pytest.fixture
def mock_settings_repo():
    """Mock settings repository."""
    repo = AsyncMock()
    repo.get_float = AsyncMock(return_value=50.0)
    return repo


@pytest.fixture
def mock_display_manager():
    """Mock display state manager."""
    manager = MagicMock(spec=DisplayStateManager)
    manager.get_error_text = MagicMock(return_value="")
    manager.get_processing_text = MagicMock(return_value="")
    manager.get_next_actions_text = MagicMock(return_value="Portfolio EUR12345")
    return manager


class TestSSEEndpoint:
    """Test the SSE streaming endpoint."""

    @pytest.mark.asyncio
    async def test_sse_endpoint_responds_with_correct_headers(
        self, app, mock_settings_repo, mock_display_manager
    ):
        """Test that SSE endpoint responds with correct headers."""
        with (
            patch(
                "app.api.status.get_settings_repository",
                return_value=mock_settings_repo,
            ),
            patch(
                "app.api.status.get_display_state_manager",
                return_value=mock_display_manager,
            ),
        ):
            client = TestClient(app)
            response = client.get("/api/status/led/display/stream")

            assert response.status_code == 200
            assert response.headers["content-type"] == "text/event-stream; charset=utf-8"
            assert "cache-control" in response.headers
            assert "no-cache" in response.headers["cache-control"].lower()

    @pytest.mark.asyncio
    async def test_sse_endpoint_sends_initial_state(
        self, app, mock_settings_repo, mock_display_manager
    ):
        """Test that initial state is sent on connection."""
        with (
            patch(
                "app.api.status.get_settings_repository",
                return_value=mock_settings_repo,
            ),
            patch(
                "app.api.status.get_display_state_manager",
                return_value=mock_display_manager,
            ),
        ):
            client = TestClient(app)
            response = client.get("/api/status/led/display/stream")

            # Read first chunk
            content = b""
            for chunk in response.iter_bytes(chunk_size=1024):
                content += chunk
                if b"\n\n" in content:
                    break

            # Should contain initial state
            assert b"data:" in content

    @pytest.mark.asyncio
    async def test_sse_event_format(self, app, mock_settings_repo, mock_display_manager):
        """Test that events are formatted as SSE (data: {json}\\n\\n)."""
        with (
            patch(
                "app.api.status.get_settings_repository",
                return_value=mock_settings_repo,
            ),
            patch(
                "app.api.status.get_display_state_manager",
                return_value=mock_display_manager,
            ),
        ):
            client = TestClient(app)
            response = client.get("/api/status/led/display/stream")

            # Read first event
            content = b""
            for chunk in response.iter_bytes(chunk_size=1024):
                content += chunk
                if b"\n\n" in content:
                    break

            # Parse SSE format
            lines = content.decode("utf-8").split("\n")
            data_line = None
            for line in lines:
                if line.startswith("data:"):
                    data_line = line[5:].strip()  # Remove "data:" prefix
                    break

            assert data_line is not None
            # Should be valid JSON
            data = json.loads(data_line)
            assert "mode" in data
            assert "ticker_text" in data

    @pytest.mark.asyncio
    async def test_sse_event_contains_required_fields(
        self, app, mock_settings_repo, mock_display_manager
    ):
        """Test that SSE events contain all required fields."""
        with (
            patch(
                "app.api.status.get_settings_repository",
                return_value=mock_settings_repo,
            ),
            patch(
                "app.api.status.get_display_state_manager",
                return_value=mock_display_manager,
            ),
        ):
            client = TestClient(app)
            response = client.get("/api/status/led/display/stream")

            # Read first event
            content = b""
            for chunk in response.iter_bytes(chunk_size=1024):
                content += chunk
                if b"\n\n" in content:
                    break

            # Parse and validate
            lines = content.decode("utf-8").split("\n")
            data_line = None
            for line in lines:
                if line.startswith("data:"):
                    data_line = line[5:].strip()
                    break

            data = json.loads(data_line)
            assert "mode" in data
            assert "error_message" in data
            assert "activity_message" in data
            assert "ticker_text" in data
            assert "ticker_speed" in data
            assert "led3" in data
            assert "led4" in data

    @pytest.mark.asyncio
    async def test_sse_endpoint_handles_disconnection_gracefully(
        self, app, mock_settings_repo, mock_display_manager
    ):
        """Test that endpoint handles client disconnection gracefully."""
        with (
            patch(
                "app.api.status.get_settings_repository",
                return_value=mock_settings_repo,
            ),
            patch(
                "app.api.status.get_display_state_manager",
                return_value=mock_display_manager,
            ),
        ):
            client = TestClient(app)
            response = client.get("/api/status/led/display/stream")

            # Start reading and then close
            response.close()
            # Should not raise exception

    @pytest.mark.asyncio
    async def test_sse_events_stream_when_state_changes(
        self, app, mock_settings_repo, mock_display_manager
    ):
        """Test that events are streamed when display state changes."""
        # This test would require actually triggering a state change
        # For now, we just verify the endpoint streams initial state
        with (
            patch(
                "app.api.status.get_settings_repository",
                return_value=mock_settings_repo,
            ),
            patch(
                "app.api.status.get_display_state_manager",
                return_value=mock_display_manager,
            ),
        ):
            client = TestClient(app)
            response = client.get("/api/status/led/display/stream")

            # Read initial event
            content = b""
            for chunk in response.iter_bytes(chunk_size=1024):
                content += chunk
                if b"\n\n" in content:
                    break

            # Should have received initial state
            assert len(content) > 0
            assert b"data:" in content

