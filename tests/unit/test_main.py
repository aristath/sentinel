"""Tests for main application entry point.

These tests validate the FastAPI application setup and health checks.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestCheckDatabaseHealth:
    """Test database health check."""

    @pytest.mark.asyncio
    async def test_returns_connected_when_healthy(self):
        """Test returning connected status when database is healthy."""
        from app.main import _check_database_health

        mock_db_manager = MagicMock()
        mock_db_manager.state = AsyncMock()
        mock_db_manager.state.execute = AsyncMock()

        with patch("app.main.get_db_manager", return_value=mock_db_manager):
            status, degraded = await _check_database_health()

        assert status == "connected"
        assert degraded is False

    @pytest.mark.asyncio
    async def test_returns_error_on_exception(self):
        """Test returning error status on database exception."""
        from app.main import _check_database_health

        mock_db_manager = MagicMock()
        mock_db_manager.state = AsyncMock()
        mock_db_manager.state.execute = AsyncMock(
            side_effect=Exception("Connection failed")
        )

        with patch("app.main.get_db_manager", return_value=mock_db_manager):
            status, degraded = await _check_database_health()

        assert "error" in status
        assert "Connection failed" in status
        assert degraded is True


class TestCheckTradernetHealth:
    """Test Tradernet health check."""

    def test_returns_connected_when_already_connected(self):
        """Test returning connected when client is already connected."""
        from app.main import _check_tradernet_health

        mock_client = MagicMock()
        mock_client.is_connected = True

        with patch(
            "app.infrastructure.external.tradernet.get_tradernet_client",
            return_value=mock_client,
        ):
            status, degraded = _check_tradernet_health()

        assert status == "connected"
        assert degraded is False

    def test_returns_connected_when_connect_succeeds(self):
        """Test returning connected when connect() succeeds."""
        from app.main import _check_tradernet_health

        mock_client = MagicMock()
        mock_client.is_connected = False
        mock_client.connect.return_value = True

        with patch(
            "app.infrastructure.external.tradernet.get_tradernet_client",
            return_value=mock_client,
        ):
            status, degraded = _check_tradernet_health()

        assert status == "connected"
        assert degraded is False

    def test_returns_disconnected_when_connect_fails(self):
        """Test returning disconnected when connect() fails."""
        from app.main import _check_tradernet_health

        mock_client = MagicMock()
        mock_client.is_connected = False
        mock_client.connect.return_value = False

        with patch(
            "app.infrastructure.external.tradernet.get_tradernet_client",
            return_value=mock_client,
        ):
            status, degraded = _check_tradernet_health()

        assert status == "disconnected"
        assert degraded is True

    def test_returns_error_on_exception(self):
        """Test returning error on exception."""
        from app.main import _check_tradernet_health

        with patch(
            "app.infrastructure.external.tradernet.get_tradernet_client",
            side_effect=Exception("Import error"),
        ):
            status, degraded = _check_tradernet_health()

        assert "error" in status
        assert degraded is True


class TestCheckYahooFinanceHealth:
    """Test Yahoo Finance health check."""

    def test_returns_available_when_healthy(self):
        """Test returning available when Yahoo Finance works."""
        from app.main import _check_yahoo_finance_health

        mock_ticker = MagicMock()
        mock_ticker.info = {"symbol": "AAPL"}

        with patch("yfinance.Ticker", return_value=mock_ticker):
            status, degraded = _check_yahoo_finance_health()

        assert status == "available"
        assert degraded is False

    def test_returns_unavailable_when_no_info(self):
        """Test returning unavailable when no info returned."""
        from app.main import _check_yahoo_finance_health

        mock_ticker = MagicMock()
        mock_ticker.info = None

        with patch("yfinance.Ticker", return_value=mock_ticker):
            status, degraded = _check_yahoo_finance_health()

        assert status == "unavailable"
        assert degraded is True

    def test_returns_error_on_exception(self):
        """Test returning error on exception."""
        from app.main import _check_yahoo_finance_health

        with patch("yfinance.Ticker", side_effect=Exception("API error")):
            status, degraded = _check_yahoo_finance_health()

        assert "error" in status
        assert degraded is True


class TestHealthEndpoint:
    """Test health endpoint."""

    @pytest.mark.asyncio
    async def test_returns_healthy_when_all_services_ok(self):
        """Test returning healthy when all services are OK."""
        from app.main import health

        with (
            patch(
                "app.main._check_database_health",
                new_callable=AsyncMock,
                return_value=("connected", False),
            ),
            patch(
                "app.main._check_tradernet_health",
                return_value=("connected", False),
            ),
            patch(
                "app.main._check_yahoo_finance_health",
                return_value=("available", False),
            ),
        ):
            result = await health()

        assert result["status"] == "healthy"
        assert result["database"] == "connected"
        assert result["tradernet"] == "connected"
        assert result["yahoo_finance"] == "available"

    @pytest.mark.asyncio
    async def test_returns_degraded_on_database_error(self):
        """Test returning degraded status on database error."""
        from fastapi.responses import JSONResponse

        from app.main import health

        with (
            patch(
                "app.main._check_database_health",
                new_callable=AsyncMock,
                return_value=("error: connection failed", True),
            ),
            patch(
                "app.main._check_tradernet_health",
                return_value=("connected", False),
            ),
            patch(
                "app.main._check_yahoo_finance_health",
                return_value=("available", False),
            ),
        ):
            result = await health()

        assert isinstance(result, JSONResponse)
        assert result.status_code == 503

    @pytest.mark.asyncio
    async def test_returns_degraded_on_tradernet_error(self):
        """Test returning degraded status on Tradernet error."""
        from fastapi.responses import JSONResponse

        from app.main import health

        with (
            patch(
                "app.main._check_database_health",
                new_callable=AsyncMock,
                return_value=("connected", False),
            ),
            patch(
                "app.main._check_tradernet_health",
                return_value=("disconnected", True),
            ),
            patch(
                "app.main._check_yahoo_finance_health",
                return_value=("available", False),
            ),
        ):
            result = await health()

        assert isinstance(result, JSONResponse)
        assert result.status_code == 503

    @pytest.mark.asyncio
    async def test_returns_degraded_on_yahoo_error(self):
        """Test returning degraded status on Yahoo Finance error."""
        from fastapi.responses import JSONResponse

        from app.main import health

        with (
            patch(
                "app.main._check_database_health",
                new_callable=AsyncMock,
                return_value=("connected", False),
            ),
            patch(
                "app.main._check_tradernet_health",
                return_value=("connected", False),
            ),
            patch(
                "app.main._check_yahoo_finance_health",
                return_value=("unavailable", True),
            ),
        ):
            result = await health()

        assert isinstance(result, JSONResponse)
        assert result.status_code == 503


class TestRootEndpoint:
    """Test root endpoint."""

    @pytest.mark.asyncio
    async def test_returns_file_response(self):
        """Test returning FileResponse for dashboard."""
        from fastapi.responses import FileResponse

        from app.main import root

        with patch("app.main.FileResponse", return_value=MagicMock(spec=FileResponse)):
            result = await root()

        # The function returns FileResponse directly
        assert result is not None


class TestAppConfiguration:
    """Test application configuration."""

    def test_app_has_correct_title(self):
        """Test that app has correct title from settings."""
        from app.main import app

        assert app.title is not None

    def test_app_has_routers(self):
        """Test that app has routers configured."""
        from app.main import app

        # Check that routes exist
        route_paths = [route.path for route in app.routes]

        assert any("/api/portfolio" in path for path in route_paths)
        assert any("/api/securities" in path for path in route_paths)
        assert any("/api/trades" in path for path in route_paths)
        assert any("/api/status" in path for path in route_paths)

    def test_app_has_middleware(self):
        """Test that app has middleware configured."""
        from app.main import app

        # Check that user middleware exists (rate limit middleware)
        assert len(app.user_middleware) > 0


class TestLoggingConfiguration:
    """Test logging configuration."""

    def test_log_format_includes_correlation_id(self):
        """Test that log format includes correlation ID."""
        from app.main import log_format

        assert "correlation_id" in log_format._fmt

    def test_console_handler_has_filter(self):
        """Test that console handler has correlation ID filter."""
        from app.main import console_handler

        assert len(console_handler.filters) > 0

    def test_file_handler_has_filter(self):
        """Test that file handler has correlation ID filter."""
        from app.main import file_handler

        assert len(file_handler.filters) > 0


class TestLifespan:
    """Test application lifespan."""

    @pytest.mark.asyncio
    async def test_lifespan_raises_on_missing_credentials(self):
        """Test that lifespan raises when credentials missing."""
        from app.main import lifespan

        mock_settings = MagicMock()
        mock_settings.data_dir = MagicMock()
        mock_settings.data_dir.exists.return_value = False
        mock_settings.tradernet_api_key = None
        mock_settings.tradernet_api_secret = None

        mock_app = MagicMock()

        with (
            patch("app.main.settings", mock_settings),
            pytest.raises(ValueError) as exc_info,
        ):
            async with lifespan(mock_app):
                pass

        assert "credentials" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_lifespan_initializes_components(self):
        """Test that lifespan initializes all required components."""
        from pathlib import Path
        from tempfile import mkdtemp

        from app.main import lifespan

        temp_dir = Path(mkdtemp())

        mock_settings = MagicMock()
        mock_settings.data_dir = temp_dir
        mock_settings.tradernet_api_key = "test_key"
        mock_settings.tradernet_api_secret = "test_secret"

        mock_client = MagicMock()
        mock_client.connect.return_value = True

        mock_app = MagicMock()

        with (
            patch("app.main.settings", mock_settings),
            patch("app.main.init_databases", new_callable=AsyncMock) as mock_init_db,
            patch("app.main.init_scheduler", new_callable=AsyncMock) as mock_init_sched,
            patch("app.main.start_scheduler") as mock_start_sched,
            patch("app.main.get_tradernet_client", return_value=mock_client),
            patch("app.main.stop_scheduler") as mock_stop_sched,
            patch(
                "app.main.shutdown_databases", new_callable=AsyncMock
            ) as mock_shutdown_db,
        ):
            async with lifespan(mock_app):
                # During lifespan
                mock_init_db.assert_called_once()
                mock_init_sched.assert_called_once()
                mock_start_sched.assert_called_once()

            # After lifespan
            mock_stop_sched.assert_called_once()
            mock_shutdown_db.assert_called_once()

    @pytest.mark.asyncio
    async def test_lifespan_cleans_up_lock_files(self):
        """Test that lifespan cleans up stale lock files."""
        from pathlib import Path
        from tempfile import mkdtemp

        from app.main import lifespan

        temp_dir = Path(mkdtemp())
        lock_dir = temp_dir / "locks"
        lock_dir.mkdir()
        lock_file = lock_dir / "test.lock"
        lock_file.touch()

        mock_settings = MagicMock()
        mock_settings.data_dir = temp_dir
        mock_settings.tradernet_api_key = "test_key"
        mock_settings.tradernet_api_secret = "test_secret"

        mock_client = MagicMock()
        mock_client.connect.return_value = True

        mock_app = MagicMock()

        with (
            patch("app.main.settings", mock_settings),
            patch("app.main.init_databases", new_callable=AsyncMock),
            patch("app.main.init_scheduler", new_callable=AsyncMock),
            patch("app.main.start_scheduler"),
            patch("app.main.get_tradernet_client", return_value=mock_client),
            patch("app.main.stop_scheduler"),
            patch("app.main.shutdown_databases", new_callable=AsyncMock),
        ):
            async with lifespan(mock_app):
                pass

        # Lock file should be cleaned up
        assert not lock_file.exists()

    @pytest.mark.asyncio
    async def test_lifespan_handles_tradernet_connection_failure(self):
        """Test that lifespan handles Tradernet connection failure gracefully."""
        from pathlib import Path
        from tempfile import mkdtemp

        from app.main import lifespan

        temp_dir = Path(mkdtemp())

        mock_settings = MagicMock()
        mock_settings.data_dir = temp_dir
        mock_settings.tradernet_api_key = "test_key"
        mock_settings.tradernet_api_secret = "test_secret"

        mock_client = MagicMock()
        mock_client.connect.return_value = False  # Connection fails

        mock_app = MagicMock()

        with (
            patch("app.main.settings", mock_settings),
            patch("app.main.init_databases", new_callable=AsyncMock),
            patch("app.main.init_scheduler", new_callable=AsyncMock),
            patch("app.main.start_scheduler"),
            patch("app.main.get_tradernet_client", return_value=mock_client),
            patch("app.main.stop_scheduler"),
            patch("app.main.shutdown_databases", new_callable=AsyncMock),
        ):
            # Should not raise, just log warning
            async with lifespan(mock_app):
                pass


class TestRequestContextMiddleware:
    """Test request context middleware."""

    @pytest.mark.asyncio
    async def test_middleware_sets_correlation_id(self):
        """Test that middleware sets correlation ID."""
        from starlette.testclient import TestClient

        from app.main import app

        with (
            patch("app.main.get_db_manager") as mock_get_db,
            patch(
                "app.main._check_database_health",
                new_callable=AsyncMock,
                return_value=("connected", False),
            ),
            patch(
                "app.main._check_tradernet_health",
                return_value=("connected", False),
            ),
            patch(
                "app.main._check_yahoo_finance_health",
                return_value=("available", False),
            ),
        ):
            mock_db = MagicMock()
            mock_db.state = AsyncMock()
            mock_db.state.execute = AsyncMock()
            mock_get_db.return_value = mock_db

            client = TestClient(app, raise_server_exceptions=False)
            response = client.get("/health")

            # Response should have correlation ID header
            assert "X-Correlation-ID" in response.headers

    @pytest.mark.asyncio
    async def test_middleware_emits_web_request_event(self):
        """Test that middleware emits web request event."""
        from starlette.testclient import TestClient

        from app.main import app

        with (
            patch("app.main.emit") as mock_emit,
            patch("app.main.get_db_manager") as mock_get_db,
            patch(
                "app.main._check_database_health",
                new_callable=AsyncMock,
                return_value=("connected", False),
            ),
            patch(
                "app.main._check_tradernet_health",
                return_value=("connected", False),
            ),
            patch(
                "app.main._check_yahoo_finance_health",
                return_value=("available", False),
            ),
        ):
            mock_db = MagicMock()
            mock_db.state = AsyncMock()
            mock_db.state.execute = AsyncMock()
            mock_get_db.return_value = mock_db

            client = TestClient(app, raise_server_exceptions=False)
            client.get("/health")

            # Should emit web request event
            mock_emit.assert_called()

    @pytest.mark.asyncio
    async def test_middleware_skips_led_endpoint(self):
        """Test that middleware skips LED polling endpoint."""
        from starlette.testclient import TestClient

        from app.core.events import SystemEvent
        from app.main import app

        with patch("app.main.emit") as mock_emit:
            client = TestClient(app, raise_server_exceptions=False)
            client.get("/api/status/led-state")

            # Should NOT emit web request event for LED endpoint
            for call in mock_emit.call_args_list:
                if len(call.args) > 0:
                    assert call.args[0] != SystemEvent.WEB_REQUEST
